"""HTTP-route smoke tests via a real `QuorumHTTPServer` on a free port.

These verify the canvas routes do what they claim end-to-end without
spawning real model CLIs (the dispatcher uses a stub invoker via
`canvas_routes._invoker()` lazy memoisation; for state-only tests the
invoker is never reached).
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quorum_conductor.canvas.workspace import scaffold
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.server.http_app import create_server


@pytest.fixture
def server(tmp_path: Path):
    ws = tmp_path / "ws"
    scaffold(ws, title="initial title", now=datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC))
    paths = WorkspacePaths(root=ws)

    # Pick a free port.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    srv = create_server(paths, host="127.0.0.1", port=port)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # Tiny wait for the bind to settle.
    time.sleep(0.05)
    try:
        yield (srv, ws, port)
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=1.0)


def _request(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_state_get_returns_initial(server) -> None:
    _srv, _ws, port = server
    status, body = _request(port, "GET", "/api/canvas/state")
    assert status == 200
    assert body["title"] == "initial title"


def test_state_patch_renames_workspace(server) -> None:
    _srv, ws, port = server
    status, body = _request(
        port, "PATCH", "/api/canvas/state", {"title": "new title"}
    )
    assert status == 200
    assert body["title"] == "new title"

    # Persisted: re-GET reads from disk.
    status, body = _request(port, "GET", "/api/canvas/state")
    assert status == 200
    assert body["title"] == "new title"

    # On disk too.
    text = (ws / "state.yaml").read_text(encoding="utf-8")
    assert "title: new title" in text


def test_state_patch_rejects_empty_title(server) -> None:
    _srv, _ws, port = server
    status, body = _request(port, "PATCH", "/api/canvas/state", {"title": "   "})
    assert status == 400
    assert "empty" in body["error"]


def test_state_patch_rejects_too_long_title(server) -> None:
    _srv, _ws, port = server
    status, body = _request(
        port, "PATCH", "/api/canvas/state", {"title": "x" * 201}
    )
    assert status == 400
    assert "long" in body["error"]


def test_state_patch_ignores_unknown_keys(server) -> None:
    """PATCH should only accept the keys it knows; extras are silently
    ignored so the UI can ship more fields ahead of the server."""
    _srv, _ws, port = server
    status, body = _request(
        port,
        "PATCH",
        "/api/canvas/state",
        {"title": "kept", "schema_version": 99, "message_counter": 999},
    )
    assert status == 200
    assert body["title"] == "kept"
    # message_counter wasn't bumped via PATCH.
    assert body["message_counter"] == 0
