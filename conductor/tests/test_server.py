"""HTTP server smoke tests.

Stand up a real `QuorumHTTPServer` on an ephemeral port, hit each
endpoint with stdlib `http.client`, and assert the responses. Each
test serves the lifetime of one request batch so we can use
`tmp_path` workspaces freely without leaking sockets.
"""

from __future__ import annotations

import json
import sys
import textwrap
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path

import pytest

from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.server import create_server
from quorum_conductor.workspace import InitOptions, init_workspace


@contextmanager
def _running_server(paths: WorkspacePaths) -> Iterator[tuple[str, int]]:
    server = create_server(paths, host="127.0.0.1", port=0)
    addr = server.server_address
    host = str(addr[0])
    port = int(addr[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (host, port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _get(host: str, port: int, path: str) -> tuple[int, dict[str, object] | str]:
    conn = HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        if resp.getheader("Content-Type", "").startswith("application/json"):
            return resp.status, json.loads(body)
        return resp.status, body
    finally:
        conn.close()


def _post(host: str, port: int, path: str) -> tuple[int, dict[str, object]]:
    conn = HTTPConnection(host, port, timeout=10)
    try:
        conn.request("POST", path, body=b"")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)
    finally:
        conn.close()


def _write_fake_cli(path: Path, output: str) -> Path:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.stdout.write({output!r})
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


_GOOD = textwrap.dedent(
    """\
    ### [PROPOSAL] @fake-cli · 2026-04-29T01:00:00Z

    ## Position

    Baseline manifest.

    ## Reasoning

    Two artifacts cover scope.

    ## Assumptions

    none

    ## Risks I see

    none

    ## Alternatives I considered

    - none — obvious.

    ## Tagging

    - @human-rohan: review.
    """
)


def _participants(paths: WorkspacePaths, fake_cli: Path) -> None:
    paths.participants.write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        f"| @fake-cli | Fake | {sys.executable} {fake_cli} | fake | cli | 30/5 | "
        "fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------- #
# Read endpoints
# ---------------------------------------------------------------------- #


def test_healthz(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/healthz")
    assert status == 200
    assert body == "ok"


def test_state_endpoint(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/state")
    assert status == 200
    assert isinstance(body, dict)
    assert body["state"] == "INITIALIZED"
    assert body["mode"] == "interactive"
    assert "cost" in body
    assert "counts" in body


def test_plan_endpoint_bootstraps_seed(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    fake = _write_fake_cli(tmp_path / "fake.py", _GOOD)
    _participants(paths, fake)
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/plan")
    assert status == 200
    assert isinstance(body, dict)
    items = body["items"]
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["deliberation_id"] == "0001"
    assert items[0]["role"] == "proposer"
    # And the seed file got created on disk.
    seed = paths.deliberations / "0001-outcome-manifest.md"
    assert seed.is_file()


def test_deliberation_endpoint_returns_markdown(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    from quorum_conductor.workspace import bootstrap_seed_deliberation

    bootstrap_seed_deliberation(paths)
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/deliberations/0001")
    assert status == 200
    assert isinstance(body, dict)
    assert body["id"] == "0001"
    markdown = body["markdown"]
    assert isinstance(markdown, str)
    assert "## Contributions" in markdown


def test_deliberations_listing(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    from quorum_conductor.workspace import bootstrap_seed_deliberation

    bootstrap_seed_deliberation(paths)
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/deliberations")
    assert status == 200
    assert isinstance(body, dict)
    rows = body["deliberations"]
    assert isinstance(rows, list)
    assert any(r["id"] == "0001" for r in rows)


def test_events_endpoint_supports_since(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    from quorum_conductor.events import AgentStarted, EventLogger

    log = EventLogger(paths.events_jsonl)
    for _ in range(3):
        log.emit(
            AgentStarted(
                handle="@x",
                role="proposer",
                deliberation_id="0001",
                move_type="PROPOSAL",
            )
        )
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/events")
        assert status == 200 and isinstance(body, dict)
        events = body["events"]
        assert isinstance(events, list)
        assert len(events) == 3
        assert body["next"] == 3

        status2, body2 = _get(host, port, "/api/events?since=2")
        assert status2 == 200 and isinstance(body2, dict)
        events2 = body2["events"]
        assert isinstance(events2, list)
        assert len(events2) == 1
        assert body2["next"] == 3


# ---------------------------------------------------------------------- #
# Mutating endpoint
# ---------------------------------------------------------------------- #


def test_step_endpoint_runs_one_invocation(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    fake = _write_fake_cli(tmp_path / "fake.py", _GOOD)
    _participants(paths, fake)

    with _running_server(paths) as (host, port):
        status, body = _post(host, port, "/api/step")

    assert status == 200, body
    assert body["status"] == "ok"
    assert body["appended"] is True
    assert body["move_type"] == "PROPOSAL"
    seed = paths.deliberations / "0001-outcome-manifest.md"
    assert "[PROPOSAL] @fake-cli" in seed.read_text(encoding="utf-8")


def test_step_endpoint_idle_when_nothing_runnable(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    # Default scaffold has only @human-rohan (manual) — nothing the
    # auto-loop can run.
    with _running_server(paths) as (host, port):
        status, body = _post(host, port, "/api/step")
    assert status == 200
    assert body["status"] == "idle"


def test_unknown_route_returns_404(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    with _running_server(paths) as (host, port):
        status, body = _get(host, port, "/api/nonexistent")
    assert status == 404
    assert isinstance(body, dict)
    assert body["error"] == "not found"


# ---------------------------------------------------------------------- #
# Smoke
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    ["/api/state", "/api/plan", "/api/deliberations", "/api/events"],
)
def test_get_endpoints_emit_cors_header(tmp_path: Path, path: str) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    with _running_server(paths) as (host, port):
        conn = HTTPConnection(host, port, timeout=5)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            assert resp.getheader("Access-Control-Allow-Origin") == "*"
            resp.read()
        finally:
            conn.close()
