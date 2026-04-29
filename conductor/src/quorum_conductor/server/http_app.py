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
    parse_participants,
    plan,
)
from ..core.context_bundle import load_context_manifest
from ..core.next_actions import compute_next_actions
from ..core.permissions import (
    PermissionStakes,
)
from ..core.permissions import (
    approve as approve_permission,
)
from ..core.permissions import (
    create_request as create_permission_request,
)
from ..core.permissions import (
    deny as deny_permission,
)
from ..core.permissions import (
    list_requests as list_permission_requests,
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
from .raw_files import whitelist as raw_whitelist
from .stream import StreamHub, format_sse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8500


@dataclass
class _ServerContext:
    paths: WorkspacePaths


class QuorumHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying a `WorkspacePaths` reference and the SSE hub."""

    daemon_threads = True  # let SSE-handler threads die with the server.

    paths: WorkspacePaths
    stream_hub: StreamHub | None = None

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Silently drop connection-reset / broken-pipe noise.

        These are emitted whenever the browser tears down an EventSource
        (page reload, navigation, devtools refresh) — benign for the
        server, but the stdlib default prints a full traceback for every
        one. We only suppress the connection-tier errors; everything
        else still falls through to the default logger.
        """
        import sys
        import traceback

        exc_type, _exc_value, _tb = sys.exc_info()
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
            if path == "/api/stream":
                return self._handle_stream()
            if path == "/api/participants":
                return self._reply_participants()
            if path == "/api/manifest":
                return self._reply_manifest()
            if path == "/api/context":
                return self._reply_context()
            if path == "/api/inboxes":
                return self._reply_inboxes()
            if path == "/api/raw":
                return self._reply_raw_listing()
            if path.startswith("/api/raw/"):
                return self._reply_raw_file(path[len("/api/raw/") :])
            if path == "/api/permissions":
                return self._reply_permissions_list()
            if path == "/api/next-actions":
                return self._reply_next_actions()
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            if url.path == "/api/step":
                return self._handle_step()
            if url.path == "/api/wizard/apply":
                return self._handle_wizard_apply()
            if url.path == "/api/settings/apply":
                return self._handle_settings_apply()
            if url.path == "/api/moves":
                return self._handle_append_move()
            if url.path.startswith("/api/raw/"):
                return self._handle_raw_write(url.path[len("/api/raw/") :])
            if url.path == "/api/permissions":
                return self._handle_permissions_create()
            if url.path.startswith("/api/permissions/") and url.path.endswith("/approve"):
                rid = url.path[len("/api/permissions/") : -len("/approve")]
                return self._handle_permission_decide(rid, approve=True)
            if url.path.startswith("/api/permissions/") and url.path.endswith("/deny"):
                rid = url.path[len("/api/permissions/") : -len("/deny")]
                return self._handle_permission_decide(rid, approve=False)
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

    def _reply_participants(self) -> None:
        paths = self.server.paths
        rows = parse_participants(paths.participants)
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
                    }
                    for p in rows
                ],
            },
        )

    def _reply_manifest(self) -> None:
        paths = self.server.paths
        body: dict[str, Any] = {
            "exists": paths.outcome_manifest.is_file(),
            "markdown": "",
            "progress": None,
        }
        if paths.outcome_manifest.is_file():
            body["markdown"] = paths.outcome_manifest.read_text(encoding="utf-8")
        # Progress comes from state.yaml's manifest block.
        state = load_state(paths.state_yaml)
        m = state.manifest
        body["progress"] = {
            "status": m.status,
            "total_artifacts": m.total_artifacts,
            "artifacts_complete": m.artifacts_complete,
            "artifacts_in_production": m.artifacts_in_production,
            "artifacts_pending": m.artifacts_pending,
            "quality_gates_clear": m.quality_gates_clear,
            "closing_ceremony_eligible": m.closing_ceremony_eligible,
        }
        self._reply_json(HTTPStatus.OK, body)

    def _reply_context(self) -> None:
        paths = self.server.paths
        manifest = load_context_manifest(paths)
        self._reply_json(HTTPStatus.OK, manifest)

    def _reply_inboxes(self) -> None:
        paths = self.server.paths
        out: list[dict[str, Any]] = []
        if paths.inbox.is_dir():
            for entry in sorted(paths.inbox.glob("*.md")):
                body = entry.read_text(encoding="utf-8") if entry.is_file() else ""
                pending_lines = [
                    line for line in body.splitlines() if line.strip().startswith("- pending:")
                ]
                out.append(
                    {
                        "handle": entry.stem,
                        "filename": entry.name,
                        "body": body,
                        "pending_count": len(pending_lines),
                    }
                )
        self._reply_json(HTTPStatus.OK, {"inboxes": out})

    def _handle_stream(self) -> None:
        """Long-lived SSE connection. Holds the request thread for the
        lifetime of the client; the parent ThreadingHTTPServer keeps
        other requests responsive in their own threads."""
        hub = self.server.stream_hub
        if hub is None:
            return self._reply_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "stream hub not initialised"},
            )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors_headers()
        self.end_headers()

        sub = hub.subscribe()
        try:
            while True:
                try:
                    msg = sub.get(timeout=30.0)
                except Exception:  # queue.Empty or other
                    continue
                try:
                    self.wfile.write(format_sse(msg))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            hub.unsubscribe(sub)

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

    def _reply_raw_listing(self) -> None:
        paths = self.server.paths
        wl = raw_whitelist(paths)
        rows = []
        for rel, p in wl.items():
            rows.append(
                {
                    "path": rel,
                    "exists": p.is_file(),
                    "size_bytes": p.stat().st_size if p.is_file() else 0,
                }
            )
        self._reply_json(HTTPStatus.OK, {"files": rows})

    def _reply_raw_file(self, rel: str) -> None:
        paths = self.server.paths
        wl = raw_whitelist(paths)
        if rel not in wl:
            return self._reply_json(
                HTTPStatus.FORBIDDEN, {"error": f"raw file {rel!r} not in whitelist"}
            )
        target = wl[rel]
        if not target.is_file():
            return self._reply_json(
                HTTPStatus.NOT_FOUND, {"error": f"{rel} does not exist"}
            )
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as exc:
            return self._reply_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)}
            )
        self._reply_json(HTTPStatus.OK, {"path": rel, "content": text})

    def _handle_raw_write(self, rel: str) -> None:
        paths = self.server.paths
        wl = raw_whitelist(paths)
        if rel not in wl:
            return self._reply_json(
                HTTPStatus.FORBIDDEN, {"error": f"raw file {rel!r} not in whitelist"}
            )
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        content = payload.get("content")
        if not isinstance(content, str):
            return self._reply_json(
                HTTPStatus.BAD_REQUEST, {"error": "expected string `content`"}
            )
        target = wl[rel]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._reply_json(
            HTTPStatus.OK, {"path": rel, "size_bytes": len(content.encode("utf-8"))}
        )

    def _reply_next_actions(self) -> None:
        paths = self.server.paths
        actions = compute_next_actions(paths)
        self._reply_json(
            HTTPStatus.OK, {"actions": [a.to_dict() for a in actions]}
        )

    def _reply_permissions_list(self) -> None:
        paths = self.server.paths
        rows = [r.to_dict() for r in list_permission_requests(paths)]
        self._reply_json(HTTPStatus.OK, {"requests": rows})

    def _handle_permissions_create(self) -> None:
        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        try:
            stakes = PermissionStakes(str(payload.get("stakes", "tactical")))
        except ValueError:
            return self._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "stakes must be one of trivial/tactical/strategic/irreversible"},
            )
        req = create_permission_request(
            paths,
            handle=str(payload.get("handle", "")),
            deliberation_id=str(payload.get("deliberation_id", "")),
            tool=str(payload.get("tool", "")),
            operation=str(payload.get("operation", "")),
            rationale=str(payload.get("rationale", "")),
            stakes=stakes,
        )
        self._reply_json(HTTPStatus.OK, req.to_dict())

    def _handle_permission_decide(self, request_id: str, *, approve: bool) -> None:
        paths = self.server.paths
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            payload = self._read_json_body() if length > 0 else {}
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        decided_by = str(payload.get("decided_by", "@human"))
        reason = payload.get("reason") or None
        fn = approve_permission if approve else deny_permission
        result = fn(paths, request_id, decided_by=decided_by, reason=reason)
        if result is None:
            return self._reply_json(
                HTTPStatus.NOT_FOUND, {"error": f"no pending permission {request_id!r}"}
            )
        self._reply_json(HTTPStatus.OK, result.to_dict())

    def _handle_append_move(self) -> None:
        from datetime import UTC, datetime

        from ..core.decisions_summary import append_summary_line
        from ..core.deliberation import load_deliberation
        from ..core.validator import validate_move
        from ..events import EventLogger, MoveAppended
        from ..transport.locks import deliberation_lock
        from ..workspace.deliberation_file import (
            AppendError,
            append_move,
            update_inboxes_from_move,
        )

        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        deliberation_id = str(payload.get("deliberation_id", "")).strip()
        move_type = str(payload.get("move_type", "")).strip().upper()
        author = str(payload.get("author", "")).strip() or "@human-rohan"
        targets = payload.get("targets")
        sections = payload.get("sections") or {}
        if not deliberation_id or not move_type or not isinstance(sections, dict):
            return self._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "deliberation_id, move_type, and sections are required"},
            )

        delib_path = _find_deliberation_path(paths, deliberation_id)
        if delib_path is None:
            return self._reply_json(
                HTTPStatus.NOT_FOUND,
                {"error": f"no deliberation with id {deliberation_id!r}"},
            )

        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = _render_move_block(move_type, author, ts, targets, sections)
        validation = validate_move(
            body, expected_move_type=move_type, templates_dir=paths.protocol_templates
        )
        if not validation.ok or validation.header is None:
            return self._reply_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "; ".join(validation.errors) or "validation failed"},
            )

        try:
            with deliberation_lock(delib_path):
                append_move(delib_path, body)
                tagged = update_inboxes_from_move(
                    body,
                    inbox_dir=paths.inbox,
                    deliberation_id=deliberation_id,
                    move_type=validation.header.move_type,
                    author=validation.header.author,
                )
        except AppendError as exc:
            return self._reply_json(
                HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
            )

        events = EventLogger(paths.events_jsonl)
        events.emit(
            MoveAppended(
                handle=validation.header.author,
                role="human",
                deliberation_id=deliberation_id,
                move_type=validation.header.move_type,
                inboxes_notified=list(tagged),
            )
        )
        append_summary_line(
            paths.summarized_decisions,
            deliberation_id=deliberation_id,
            header=validation.header,
            move_text=body,
        )
        # Touch the deliberation so the planner re-evaluates.
        _ = load_deliberation(delib_path)

        self._reply_json(
            HTTPStatus.OK,
            {
                "appended": True,
                "move_type": validation.header.move_type,
                "deliberation_id": deliberation_id,
                "inboxes_notified": tagged,
            },
        )

    def _handle_settings_apply(self) -> None:
        """Phase-9 settings panel writes. Same shape as wizard.apply but
        scoped to live-editable settings (per design-doc §9.8 editability
        rules). The conductor accepts whatever subset of fields the UI
        sends; absent fields are not touched.

        Frozen-at-first-start fields (workspace mode, manifest template,
        workspace_id) are accepted only if state == INITIALIZED. After
        first start the request is rejected with HTTP 409 Conflict so
        the UI can show the lock indicator.
        """
        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        applied: list[str] = []
        rejected: list[dict[str, str]] = []

        # Frozen fields require state == INITIALIZED.
        if "mode" in payload:
            state = load_state(paths.state_yaml)
            if state.state.value != "INITIALIZED":
                rejected.append({"field": "mode", "reason": "frozen after first start"})
            else:
                self._update_state_mode(paths, str(payload["mode"]))
                applied.append("mode")

        if any(k in payload for k in ("cost_ceiling_usd", "cost_enforce", "unavailability_policy")):
            self._update_config_yaml_extended(paths, payload)
            applied.append("config.yaml")

        if rejected:
            return self._reply_json(
                HTTPStatus.CONFLICT,
                {"applied": applied, "rejected": rejected},
            )
        self._reply_json(HTTPStatus.OK, {"applied": applied, "rejected": []})

    @staticmethod
    def _update_config_yaml_extended(paths: WorkspacePaths, payload: dict[str, Any]) -> None:
        import yaml

        config_text = (
            paths.config_yaml.read_text(encoding="utf-8") if paths.config_yaml.is_file() else ""
        )
        raw = yaml.safe_load(config_text) or {}
        if not isinstance(raw, dict):
            raw = {}
        if "cost_ceiling_usd" in payload or "cost_enforce" in payload:
            existing_cost = raw.get("cost")
            cost: dict[str, Any] = (
                dict(existing_cost) if isinstance(existing_cost, dict) else {}
            )
            if "cost_ceiling_usd" in payload:
                cost["ceiling_usd"] = float(payload["cost_ceiling_usd"])
            if "cost_enforce" in payload:
                cost["enforce"] = bool(payload["cost_enforce"])
            cost.setdefault("enforce", True)
            raw["cost"] = cost
        if "unavailability_policy" in payload:
            raw["unavailability_policy"] = str(payload["unavailability_policy"])
        paths.config_yaml.write_text(
            yaml.safe_dump(raw, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _handle_wizard_apply(self) -> None:
        """Apply Phase-7 setup-wizard answers to the workspace.

        Body schema (all fields optional; only provided fields are
        applied):

            {
              "manifest_template": "saas-product" | ... | null,
              "mode": "interactive" | "autonomous",
              "unavailability_policy": "strict" | "substitute" |
                                       "substitute_aggressively",
              "cost_ceiling_usd": 50.0,
              "problem_statement": "<full text>",
              "human_handle": "@human-jane"
            }

        Edits config.yaml + state.yaml + problem-statement.md +
        participants.md in place.
        """
        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        applied: list[str] = []

        if "problem_statement" in payload:
            text = str(payload["problem_statement"]).strip()
            if text:
                if not text.endswith("\n"):
                    text += "\n"
                paths.problem_statement.write_text(text, encoding="utf-8")
                applied.append("problem_statement")

        if any(k in payload for k in ("cost_ceiling_usd", "unavailability_policy")):
            self._update_config_yaml(paths, payload)
            applied.append("config.yaml")

        if "mode" in payload:
            self._update_state_mode(paths, str(payload["mode"]))
            applied.append("state.mode")

        if "human_handle" in payload:
            handle = str(payload["human_handle"]).strip()
            if handle:
                if not handle.startswith("@"):
                    handle = f"@{handle}"
                self._rename_human_handle(paths, handle)
                applied.append("human_handle")

        self._reply_json(HTTPStatus.OK, {"applied": applied})

    @staticmethod
    def _rename_human_handle(paths: WorkspacePaths, new_handle: str) -> None:
        """Replace whichever manual-transport handle is currently in
        participants.md with `new_handle`. Also rename the inbox file so
        the loop can find pending notifications under the new name."""
        from ..core.participants import parse_participants

        if not paths.participants.is_file():
            return
        text = paths.participants.read_text(encoding="utf-8")
        existing = next(
            (p for p in parse_participants(paths.participants) if p.transport == "manual"),
            None,
        )
        if existing is None or existing.handle == new_handle:
            return
        # Conservative literal replace — the participants table is small
        # and the handle string is unique enough that a regex isn't
        # worth the complexity.
        updated = text.replace(existing.handle, new_handle)
        paths.participants.write_text(updated, encoding="utf-8")
        # Rename the inbox file in place if it exists.
        old_inbox = paths.inbox / f"{existing.handle}.md"
        new_inbox = paths.inbox / f"{new_handle}.md"
        if old_inbox.is_file() and not new_inbox.exists():
            old_inbox.rename(new_inbox)

    @staticmethod
    def _update_config_yaml(paths: WorkspacePaths, payload: dict[str, Any]) -> None:
        import yaml

        config_text = paths.config_yaml.read_text(encoding="utf-8") if paths.config_yaml.is_file() else ""
        # Round-trip through YAML so we can edit fields without losing
        # comments only on lines we don't touch. This is best-effort —
        # YAML comments are inherently fragile under structured edits.
        raw = yaml.safe_load(config_text) or {}
        if not isinstance(raw, dict):
            raw = {}
        if "cost_ceiling_usd" in payload:
            cost = raw.setdefault("cost", {}) if isinstance(raw.get("cost"), dict) else {}
            cost["ceiling_usd"] = float(payload["cost_ceiling_usd"])
            cost.setdefault("enforce", True)
            raw["cost"] = cost
        if "unavailability_policy" in payload:
            raw["unavailability_policy"] = str(payload["unavailability_policy"])
        paths.config_yaml.write_text(
            yaml.safe_dump(raw, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    @staticmethod
    def _update_state_mode(paths: WorkspacePaths, mode: str) -> None:
        from ..workspace import WorkspaceMode, save_state

        if mode not in {m.value for m in WorkspaceMode}:
            return
        state = load_state(paths.state_yaml)
        state.mode = WorkspaceMode(mode)
        save_state(paths.state_yaml, state)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

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


def _find_deliberation_path(paths: WorkspacePaths, deliberation_id: str) -> Any:
    if not paths.deliberations.is_dir():
        return None
    for candidate in paths.deliberations.glob("*.md"):
        try:
            meta = load_deliberation(candidate)
        except Exception:
            continue
        if meta.id == deliberation_id:
            return candidate
    return None


def _render_move_block(
    move_type: str,
    author: str,
    ts: str,
    targets: Any,
    sections: dict[str, Any],
) -> str:
    """Build the canonical Markdown for a structured human-authored move."""
    header = f"### [{move_type}] {author} · {ts}"
    if isinstance(targets, str) and targets.strip():
        header += f" → targets {targets.strip()}"
    parts: list[str] = [header, ""]
    for name, value in sections.items():
        parts.append(f"## {name}")
        parts.append("")
        text = "" if value is None else str(value)
        parts.append(text.rstrip() if text.strip() else "none")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


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
