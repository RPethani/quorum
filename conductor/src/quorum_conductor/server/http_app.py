"""Local HTTP server backing the UI.

Endpoints (all under `/api/`):

  GET  /api/state                 - workspace state + status summary
  GET  /api/deliberations          - list deliberation files
  GET  /api/deliberations/<id>    - raw Markdown body of one deliberation
  GET  /api/plan                   - current planning result
  GET  /api/events                 - events.jsonl entries (?since=N for polling)
  POST /api/step                   - run one invocation, return InvocationResult

Plus `GET /healthz` returning `200 ok` for liveness checks.

CORS: the Next.js dev server runs on a different port (3000), so we
emit `Access-Control-Allow-Origin: *` on every response. Phase 9 will
tighten this once the production deployment story exists; for v1's
local-only use the wide-open allow is right.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..core import (
    NoHandleAvailableError,
    PlanResult,
    compute_cost,
    load_deliberation,
    load_routing_defaults,
    load_workspace_config,
    plan,
)
from ..events import EventLogger, RoutingDecisionEvent, read_events
from ..paths import WorkspacePaths
from ..transport.runner import run_items_sync
from ..workspace import (
    bootstrap_seed_deliberation,
    load_state,
    needs_bootstrap,
    status_summary,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8500


@dataclass
class _ServerContext:
    paths: WorkspacePaths


class QuorumHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying a `WorkspacePaths` reference."""

    paths: WorkspacePaths


def create_server(
    paths: WorkspacePaths,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> QuorumHTTPServer:
    """Bind a server but do not start it. Useful for tests."""
    server = QuorumHTTPServer((host, port), QuorumHandler)
    server.paths = paths
    return server


def serve_forever(
    paths: WorkspacePaths,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    on_listen: Any = None,
) -> None:
    """Bind and serve until interrupted. Used by `quorum serve`."""
    server = create_server(paths, host=host, port=port)
    if on_listen is not None:
        on_listen(server.server_address)
    try:
        server.serve_forever()
    finally:
        server.server_close()


# ---------------------------------------------------------------------- #
# Handler
# ---------------------------------------------------------------------- #


class QuorumHandler(BaseHTTPRequestHandler):
    server: QuorumHTTPServer  # set by ThreadingHTTPServer
    server_version = "quorum/0.1"

    # Silence default access logging; the conductor's logs are the
    # source of truth and these would otherwise spam stdout.
    def log_message(self, format: str, *args: Any) -> None:
        return

    # ------------------ routing ----------------------------------------
    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        query = parse_qs(url.query)
        try:
            if path == "/healthz":
                return self._reply_text(HTTPStatus.OK, "ok")
            if path == "/api/state":
                return self._reply_state()
            if path == "/api/plan":
                return self._reply_plan()
            if path == "/api/deliberations":
                return self._reply_deliberations()
            if path.startswith("/api/deliberations/"):
                ident = path.split("/api/deliberations/", 1)[1]
                return self._reply_deliberation(ident)
            if path == "/api/events":
                return self._reply_events(query)
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            if url.path == "/api/step":
                return self._handle_step()
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    # ------------------ endpoint impls ---------------------------------
    def _reply_state(self) -> None:
        paths = self.server.paths
        summary = status_summary(paths)
        body = {
            "workspace_id": summary.state.workspace_id,
            "mode": summary.state.mode.value,
            "state": summary.state.state.value,
            "state_changed_at": summary.state.state_changed_at,
            "counts": {
                "deliberations": summary.deliberation_count,
                "artifacts": summary.artifact_count,
                "decisions": summary.decision_count,
                "tasks": summary.task_count,
                "inbox_pending": summary.inbox_pending_count,
            },
            "processes": {
                "conductor_running": summary.conductor_running,
                "ui_running": summary.ui_running,
            },
            "cost": {
                "spent_usd": summary.cost.spent_usd,
                "ceiling_usd": summary.cost_ceiling_usd,
                "fraction": summary.cost.fraction_of(summary.cost_ceiling_usd),
                "invocations": summary.cost.invocations,
                "enforce": summary.cost_enforce,
            },
        }
        self._reply_json(HTTPStatus.OK, body)

    def _reply_deliberations(self) -> None:
        paths = self.server.paths
        rows: list[dict[str, Any]] = []
        if paths.deliberations.is_dir():
            for path in sorted(paths.deliberations.glob("*.md")):
                try:
                    meta = load_deliberation(path)
                except Exception:
                    continue
                rows.append(
                    {
                        "id": meta.id,
                        "title": meta.title,
                        "status": meta.status,
                        "tags": meta.tags,
                        "filename": path.name,
                    }
                )
        self._reply_json(HTTPStatus.OK, {"deliberations": rows})

    def _reply_deliberation(self, ident: str) -> None:
        paths = self.server.paths
        if not paths.deliberations.is_dir():
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "no deliberations"})
        for path in paths.deliberations.glob("*.md"):
            try:
                meta = load_deliberation(path)
            except Exception:
                continue
            if meta.id == ident:
                self._reply_json(
                    HTTPStatus.OK,
                    {
                        "id": meta.id,
                        "title": meta.title,
                        "status": meta.status,
                        "tags": meta.tags,
                        "filename": path.name,
                        "markdown": path.read_text(encoding="utf-8"),
                    },
                )
                return
        self._reply_json(HTTPStatus.NOT_FOUND, {"error": f"no deliberation #{ident}"})

    def _reply_plan(self) -> None:
        paths = self.server.paths
        if needs_bootstrap(paths):
            bootstrap_seed_deliberation(paths)
        try:
            result = plan(paths)
        except NoHandleAvailableError as exc:
            return self._reply_json(
                HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}
            )
        self._reply_json(HTTPStatus.OK, _plan_to_json(result))

    def _reply_events(self, query: dict[str, list[str]]) -> None:
        since = 0
        if "since" in query:
            try:
                since = int(query["since"][0])
            except ValueError:
                since = 0
        events = list(read_events(self.server.paths.events_jsonl))
        sliced = events[since:]
        self._reply_json(
            HTTPStatus.OK,
            {"since": since, "next": since + len(sliced), "events": sliced},
        )

    def _handle_step(self) -> None:
        paths = self.server.paths
        if needs_bootstrap(paths):
            bootstrap_seed_deliberation(paths)

        state = load_state(paths.state_yaml)
        config = load_workspace_config(paths.config_yaml)
        defaults = load_routing_defaults(paths.routing_defaults)

        if config.cost_enforce:
            spend = compute_cost(paths.events_jsonl, defaults)
            if spend.at_or_above_ceiling(config.cost_ceiling_usd):
                return self._reply_json(
                    HTTPStatus.PAYMENT_REQUIRED,
                    {
                        "error": (
                            f"cost ceiling reached: "
                            f"${spend.spent_usd:.2f} >= ${config.cost_ceiling_usd:.2f}"
                        ),
                    },
                )

        result = plan(paths)
        runnable = result.runnable()
        if not runnable:
            return self._reply_json(
                HTTPStatus.OK,
                {
                    "status": "idle",
                    "reason": (
                        "every deliberation is done, blocked, or waiting on a human."
                    ),
                    "plan": _plan_to_json(result),
                },
            )

        item = runnable[0]
        events = EventLogger(paths.events_jsonl)
        events.emit(
            RoutingDecisionEvent(
                handle=item.routing.handle,
                role=item.routing.role,
                deliberation_id=item.routing.deliberation_id,
                layer=item.routing.layer.value,
                fitness=item.routing.fitness,
                cost=item.routing.cost,
                alternatives=[
                    {
                        "handle": a.handle,
                        "fitness": a.fitness,
                        "cost": a.cost,
                        "rejected_because": a.rejected_because,
                    }
                    for a in item.routing.alternatives
                ],
                note=item.routing.note,
            )
        )
        results = run_items_sync(
            [item],
            paths=paths,
            events=events,
            mode=state.mode.value,
            max_concurrent=1,
        )
        ir = results[0]
        body: dict[str, Any] = {
            "status": ir.status,
            "handle": ir.handle,
            "role": ir.role,
            "move_type": ir.move_type,
            "deliberation_id": ir.deliberation_id,
            "duration_s": ir.duration_s,
            "attempts": ir.attempts,
            "appended": ir.appended,
            "inboxes_notified": ir.inboxes_notified,
            "error": ir.error,
        }
        self._reply_json(HTTPStatus.OK, body)

    # ------------------ helpers ----------------------------------------
    def _reply_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
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
        # Local dev only — see module docstring.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------- #
# Helpers (pure)
# ---------------------------------------------------------------------- #


def _plan_to_json(result: PlanResult) -> dict[str, Any]:
    return {
        "items": [
            {
                "deliberation_id": item.deliberation.id,
                "deliberation_title": item.deliberation.title,
                "role": item.role,
                "move_type": item.move_type,
                "reason": item.reason,
                "is_manual": item.is_manual,
                "handle": item.routing.handle,
                "layer": item.routing.layer.value,
                "fitness": item.routing.fitness,
                "cost": item.routing.cost,
            }
            for item in result.items
        ],
        "blocked": [
            {
                "deliberation_id": b.deliberation.id,
                "role": b.role,
                "move_type": b.move_type,
                "reason": b.reason,
            }
            for b in result.blocked
        ],
        "skipped_terminal": [m.id for m in result.skipped_terminal],
    }


# Kept for tests that want to assert dataclass shapes round-trip cleanly.
def _ctx_dict(ctx: _ServerContext) -> dict[str, Any]:
    return asdict(ctx)


__all_helpers__: Iterable[Any] = (_plan_to_json, _ctx_dict)
