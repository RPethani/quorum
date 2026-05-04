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


# ---------------------------------------------------------------------- #
# Context endpoints
# ---------------------------------------------------------------------- #


def test_state_patch_sets_digester_handle(server) -> None:
    _srv, _ws, port = server
    status, body = _request(
        port, "PATCH", "/api/canvas/state", {"digester_handle": "@claude-opus"}
    )
    assert status == 200
    assert body["digester_handle"] == "@claude-opus"


def test_state_patch_rejects_handle_without_at(server) -> None:
    _srv, _ws, port = server
    status, body = _request(
        port, "PATCH", "/api/canvas/state", {"digester_handle": "claude-opus"}
    )
    assert status == 400
    assert "@" in body["error"]


def test_context_list_initially_empty(server) -> None:
    _srv, _ws, port = server
    status, body = _request(port, "GET", "/api/canvas/context")
    assert status == 200
    assert body == {"entries": []}


def test_context_add_repo_and_list(server, tmp_path: Path) -> None:
    _srv, _ws, port = server
    repo = tmp_path / "v2-app"
    repo.mkdir()

    status, body = _request(
        port,
        "POST",
        "/api/canvas/context",
        {"kind": "repo", "source": str(repo)},
    )
    assert status == 200
    assert body["entry"]["kind"] == "repo"
    assert body["entry"]["digest_status"] == "pending"

    status, body = _request(port, "GET", "/api/canvas/context")
    assert status == 200
    assert len(body["entries"]) == 1


def test_context_add_doc(server, tmp_path: Path) -> None:
    _srv, _ws, port = server
    src = tmp_path / "spec.md"
    src.write_text("# Spec\n", encoding="utf-8")

    status, body = _request(
        port, "POST", "/api/canvas/context", {"kind": "doc", "source": str(src)}
    )
    assert status == 200
    assert body["entry"]["kind"] == "doc"


def test_context_add_note(server) -> None:
    _srv, _ws, port = server
    status, body = _request(
        port,
        "POST",
        "/api/canvas/context",
        {"kind": "note", "name": "tradeoff", "body": "rate-limit options"},
    )
    assert status == 200
    assert body["entry"]["kind"] == "note"
    assert body["entry"]["body"] == "rate-limit options"


def test_context_add_rejects_unknown_kind(server) -> None:
    _srv, _ws, port = server
    status, body = _request(port, "POST", "/api/canvas/context", {"kind": "url"})
    assert status == 400
    assert "kind" in body["error"]


def test_context_remove(server, tmp_path: Path) -> None:
    _srv, _ws, port = server
    repo = tmp_path / "v2-app"
    repo.mkdir()
    _, body = _request(
        port,
        "POST",
        "/api/canvas/context",
        {"kind": "repo", "source": str(repo)},
    )
    eid = body["entry"]["id"]

    status, _ = _request(port, "DELETE", f"/api/canvas/context/{eid}")
    assert status == 200

    _, body = _request(port, "GET", "/api/canvas/context")
    assert body["entries"] == []


def test_context_refresh_resets_status(server, tmp_path: Path) -> None:
    _srv, ws, port = server
    repo = tmp_path / "v2-app"
    repo.mkdir()
    _, body = _request(
        port, "POST", "/api/canvas/context", {"kind": "repo", "source": str(repo)}
    )
    eid = body["entry"]["id"]

    # Mutate manifest to simulate a successful digest.
    from dataclasses import replace as dc_replace

    from quorum_conductor.context.manifest import load_manifest, save_manifest

    m = load_manifest(ws)
    [e] = m.entries
    save_manifest(
        ws,
        dc_replace(m, entries=[dc_replace(e, digest_status="ready", stale=True)]),
    )

    status, body = _request(port, "POST", f"/api/canvas/context/{eid}/refresh")
    assert status == 200
    assert body["entry"]["digest_status"] == "pending"
    assert body["entry"]["stale"] is False


def test_context_digest_requires_handle(server, tmp_path: Path) -> None:
    """No digester_handle in state.yaml + none in body → 400."""
    _srv, _ws, port = server
    repo = tmp_path / "v2-app"
    repo.mkdir()
    _, body = _request(
        port, "POST", "/api/canvas/context", {"kind": "repo", "source": str(repo)}
    )
    eid = body["entry"]["id"]

    status, body = _request(port, "POST", f"/api/canvas/context/{eid}/digest")
    assert status == 400
    assert "digester_handle" in body["error"]
