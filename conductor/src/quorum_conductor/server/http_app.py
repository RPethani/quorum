"""HTTP server for the canvas surface.

Slim, canvas-only. The protocol-era endpoints (deliberations, asks,
manifest, plan, next-actions, permissions, etc.) have been retired with
the protocol surface; what remains is:

    GET  /healthz                 readiness probe
    GET  /api/state               canvas state.yaml + cost
    GET  /api/canvas/messages     parsed canvas.md
    POST /api/canvas/messages     append + dispatch on @mention
    POST /api/canvas/messages/{id}/retry   re-invoke after failure
    GET  /api/canvas/artifacts    list of live artifacts
    GET  /api/canvas/artifacts/{name}      artifact body
    DELETE /api/canvas/artifacts/{name}    move to .trash/
    GET  /api/participants        registered participant rows + live health
    POST /api/participants        add a row (PATCH/DELETE deferred — edit
                                  registers/participants.md by hand for MVP)
    GET  /api/canvas/context              list context entries
    POST /api/canvas/context              add repo / doc / note
    DELETE /api/canvas/context/{id}       remove an entry
    POST /api/canvas/context/{id}/refresh  reset digest_status to pending
    POST /api/canvas/context/{id}/digest   run digestion synchronously
    GET  /api/events?since=N      append-only event log tail
    GET  /api/stream              Server-Sent Events for liveness

There is no autoloop — agents only run when the user `@mentions` them.
The conductor is otherwise idle.
"""

from __future__ import annotations

import contextlib
import json
import sys
import traceback
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ..core.participants import parse_participants
from ..core.participants_edit import (
    NewParticipant,
    ParticipantsEditError,
    append_participant,
)
from ..events import read_events
from ..paths import WorkspacePaths
from ..transport.doctor import HandleHealth, doctor_check
from . import canvas_routes
from .stream import StreamHub, format_sse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8500


# ---------------------------------------------------------------------- #
# Server lifecycle
# ---------------------------------------------------------------------- #


class QuorumHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with workspace + stream-hub attached."""

    paths: WorkspacePaths
    stream_hub: StreamHub
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc_type, _exc, _tb = sys.exc_info()
        # Suppress the noise from clients dropping a long-lived SSE stream.
        if exc_type is not None and issubclass(
            exc_type, ConnectionResetError | BrokenPipeError | ConnectionAbortedError
        ):
            return
        sys.stderr.write("Exception occurred during processing of request:\n")
        traceback.print_exc()


def create_server(
    paths: WorkspacePaths,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> QuorumHTTPServer:
    """Bind a server but do not start it. Useful for tests."""
    server = QuorumHTTPServer((host, port), QuorumHandler)
    server.paths = paths
    server.stream_hub = StreamHub(paths)
    return server


def serve_forever(
    paths: WorkspacePaths,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    on_listen: Any = None,
) -> None:
    """Bind and serve until interrupted."""
    server = create_server(paths, host=host, port=port)
    if on_listen is not None:
        on_listen(server.server_address)
    try:
        server.serve_forever()
    finally:
        server.server_close()


# ---------------------------------------------------------------------- #
# Request handler
# ---------------------------------------------------------------------- #


class QuorumHandler(BaseHTTPRequestHandler):
    server: QuorumHTTPServer
    server_version = "quorum/0.2"

    def log_message(self, format: str, *args: Any) -> None:
        # Silence default access logging — too noisy for a local dev server.
        return

    # ------------------------------ GET ------------------------------ #
    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        query = parse_qs(url.query)
        try:
            if path == "/healthz":
                return self._reply_text(HTTPStatus.OK, "ok")

            if path == "/api/state":
                return canvas_routes.reply_state(self)
            if path == "/api/canvas/state":
                # Back-compat alias.
                return canvas_routes.reply_state(self)

            if path == "/api/canvas/messages":
                return canvas_routes.reply_messages(self)

            if path == "/api/canvas/artifacts":
                return canvas_routes.reply_artifacts_list(self)
            if path.startswith("/api/canvas/artifacts/"):
                name = unquote(path[len("/api/canvas/artifacts/") :])
                return canvas_routes.reply_artifact(self, name)

            if path == "/api/canvas/context":
                return canvas_routes.reply_context_list(self)

            if path == "/api/fs/list":
                return self._reply_fs_list(query)

            if path == "/api/participants":
                return self._reply_participants()

            if path == "/api/events":
                return self._reply_events(query)

            if path == "/api/stream":
                return self._handle_stream()

            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    # ------------------------------ POST ----------------------------- #
    def do_POST(self) -> None:
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/api/canvas/messages":
                return canvas_routes.handle_send_message(self)
            if path.startswith("/api/canvas/messages/") and path.endswith("/retry"):
                mid = path[len("/api/canvas/messages/") : -len("/retry")]
                return canvas_routes.handle_retry(self, unquote(mid))
            if path == "/api/canvas/remediations/apply":
                return canvas_routes.handle_remediation_apply(self)

            if path == "/api/canvas/context":
                return canvas_routes.handle_context_add(self)
            if path.startswith("/api/canvas/context/") and path.endswith("/refresh"):
                eid = path[len("/api/canvas/context/") : -len("/refresh")]
                return canvas_routes.handle_context_refresh(self, unquote(eid))
            if path.startswith("/api/canvas/context/") and path.endswith("/digest"):
                eid = path[len("/api/canvas/context/") : -len("/digest")]
                return canvas_routes.handle_context_digest(self, unquote(eid))

            if path == "/api/participants":
                return self._handle_participants_add()

            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    # ----------------------------- PATCH ----------------------------- #
    def do_PATCH(self) -> None:
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/api/canvas/state":
                return canvas_routes.handle_state_patch(self)
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    # ----------------------------- DELETE ---------------------------- #
    def do_DELETE(self) -> None:
        url = urlparse(self.path)
        path = url.path
        try:
            if path.startswith("/api/canvas/artifacts/"):
                name = unquote(path[len("/api/canvas/artifacts/") :])
                return canvas_routes.handle_artifact_delete(self, name)
            if path.startswith("/api/canvas/context/"):
                eid = path[len("/api/canvas/context/") :]
                return canvas_routes.handle_context_remove(self, unquote(eid))
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    # ----------------------------- OPTIONS --------------------------- #
    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    # ----------------------------------------------------------------- #
    # Generic surfaces
    # ----------------------------------------------------------------- #

    def _reply_participants(self) -> None:
        paths = self.server.paths
        rows = parse_participants(paths.participants)
        health_by_handle = {h.handle: h for h in doctor_check(paths)}
        self._reply_json(
            HTTPStatus.OK,
            {
                "participants": [
                    {
                        "handle": p.handle,
                        "display_name": p.display_name,
                        "model": p.model,
                        "transport": p.transport,
                        "cli_command": p.cli_command,
                        "quota_daily": p.quota_daily,
                        "quota_per_deliberation": p.quota_per_deliberation,
                        "permission_capability": p.permission_capability,
                        "account_label": p.account_label,
                        "health": p.health,
                        "inherits_fitness_from": p.inherits_fitness_from,
                        "live_health": _live_health_dict(health_by_handle.get(p.handle)),
                    }
                    for p in rows
                ],
            },
        )

    def _handle_participants_add(self) -> None:
        payload = self._read_json_body()
        try:
            new = NewParticipant(
                handle=str(payload.get("handle", "")).strip(),
                display_name=str(payload.get("display_name", "")).strip(),
                cli_command=str(payload.get("cli_command", "")).strip(),
                model=str(payload.get("model", "")).strip(),
                transport=str(payload.get("transport", "cli")).strip(),
                quota_daily=payload.get("quota_daily"),
                quota_per_deliberation=payload.get("quota_per_deliberation"),
                permission_capability=str(payload.get("permission_capability", "ask")).strip(),
                account_label=str(payload.get("account_label", "")).strip(),
                health=str(payload.get("health", "unknown")).strip(),
            )
            append_participant(self.server.paths.participants, new)
        except ParticipantsEditError as e:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        self._reply_json(HTTPStatus.OK, {"handle": new.handle})

    def _reply_fs_list(self, query: dict[str, list[str]]) -> None:
        """List children of a directory on the host filesystem.

        Powers the Browse… picker so users don't have to type absolute
        paths. The server is bound to 127.0.0.1, so local-only by
        construction — same threat model as the rest of the conductor.
        """
        from pathlib import Path as _Path

        raw = query.get("path", [""])[0] or str(_Path.home())
        mode = query.get("mode", ["dirs"])[0]
        show_hidden = query.get("show_hidden", ["0"])[0] == "1"
        try:
            target = _Path(raw).expanduser().resolve()
        except OSError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        if not target.is_dir():
            return self._reply_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": f"{target} is not a directory"},
            )
        entries: list[dict[str, Any]] = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if not show_hidden and child.name.startswith("."):
                    continue
                is_dir = child.is_dir()
                if mode == "dirs" and not is_dir:
                    continue
                entries.append({"name": child.name, "path": str(child), "is_dir": is_dir})
        except PermissionError:
            return self._reply_json(
                HTTPStatus.FORBIDDEN, {"error": f"permission denied reading {target}"}
            )
        parent = str(target.parent) if target != target.parent else None
        self._reply_json(
            HTTPStatus.OK,
            {
                "path": str(target),
                "parent": parent,
                "home": str(_Path.home()),
                "entries": entries,
            },
        )

    def _reply_events(self, query: dict[str, list[str]]) -> None:
        since = 0
        with contextlib.suppress(ValueError, IndexError):
            since = int(query.get("since", ["0"])[0])
        events = list(read_events(self.server.paths.events_jsonl))[since:]
        self._reply_json(HTTPStatus.OK, {"events": events, "next_since": since + len(events)})

    def _handle_stream(self) -> None:
        """Open a long-lived SSE response that fans out from `StreamHub`."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self._cors_headers()
        self.end_headers()

        q = self.server.stream_hub.subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=15.0)
                except Exception:
                    self.wfile.write(format_sse_keepalive())
                    self.wfile.flush()
                    continue
                self.wfile.write(format_sse(msg))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.server.stream_hub.unsubscribe(q)

    # ----------------------------------------------------------------- #
    # Tiny helpers (canvas_routes uses these via duck-typed `handler`)
    # ----------------------------------------------------------------- #

    def _read_json_body(self) -> dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        try:
            length = int(length_header) if length_header is not None else 0
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            obj = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return obj if isinstance(obj, dict) else {}

    def _reply_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _reply_text(self, status: HTTPStatus, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def format_sse_keepalive() -> bytes:
    return b": keepalive\n\n"


def _live_health_dict(h: HandleHealth | None) -> dict[str, Any] | None:
    if h is None:
        return None
    d = asdict(h)
    # Drop the `handle` key — already known by the parent record.
    d.pop("handle", None)
    return d
