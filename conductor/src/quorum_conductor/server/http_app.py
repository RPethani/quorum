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
from pathlib import Path
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
from ..core.participants_edit import (
    NewParticipant,
    ParticipantsEditError,
    append_participant,
)
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
from ..transport.doctor import doctor_check
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
            if path == "/api/settings":
                return self._reply_settings()
            if path == "/api/fs/list":
                return self._reply_fs_list(query)
            if path == "/api/context/digestions":
                return self._reply_digestions()
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
            if url.path == "/api/participants":
                return self._handle_participants_add()
            if url.path == "/api/context/repos":
                return self._handle_context_add("repo")
            if url.path == "/api/context/docs":
                return self._handle_context_add("doc")
            if url.path == "/api/context/notes":
                return self._handle_context_add("note")
            if url.path == "/api/context/urls":
                return self._handle_context_add("url")
            if url.path == "/api/context/digest":
                return self._handle_digest_queue()
            if url.path == "/api/context/urls/refresh":
                return self._handle_url_refresh()
            if url.path == "/api/deliberations":
                return self._handle_deliberation_create()
            if url.path.startswith("/api/permissions/") and url.path.endswith("/approve"):
                rid = url.path[len("/api/permissions/") : -len("/approve")]
                return self._handle_permission_decide(rid, approve=True)
            if url.path.startswith("/api/permissions/") and url.path.endswith("/deny"):
                rid = url.path[len("/api/permissions/") : -len("/deny")]
                return self._handle_permission_decide(rid, approve=False)
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_DELETE(self) -> None:
        url = urlparse(self.path)
        try:
            path = url.path
            if path.startswith("/api/context/repos/"):
                return self._handle_context_remove("repo", path[len("/api/context/repos/") :])
            if path.startswith("/api/context/docs/"):
                return self._handle_context_remove("doc", path[len("/api/context/docs/") :])
            if path.startswith("/api/context/notes/"):
                return self._handle_context_remove("note", path[len("/api/context/notes/") :])
            if path.startswith("/api/context/urls/"):
                return self._handle_context_remove("url", path[len("/api/context/urls/") :])
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:
            self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def _handle_context_remove(self, kind: str, slug: str) -> None:
        """Drop one context entry from the manifest and any backing files.

        For repos / docs / notes / urls we also delete the on-disk
        artifacts (digests, raw copies, cached fetches). Tracker rows
        in runtime/services/digestions.json are left alone — they're
        refreshed on the next list call when the manifest is consulted.
        """
        from urllib.parse import unquote

        from ..core.context_bundle import load_context_manifest, save_context_manifest

        paths = self.server.paths
        slug = unquote(slug)
        if not slug:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "name required"})
        manifest = load_context_manifest(paths)
        plural = {"repo": "repos", "doc": "docs", "note": "notes", "url": "urls"}[kind]
        items = manifest.get(plural) or []
        if not isinstance(items, list):
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": f"no {plural} registered"})
        index = next(
            (
                i
                for i, item in enumerate(items)
                if isinstance(item, dict) and item.get("name") == slug
            ),
            None,
        )
        if index is None:
            return self._reply_json(
                HTTPStatus.NOT_FOUND, {"error": f"no {kind} named {slug!r}"}
            )
        removed = items.pop(index)
        save_context_manifest(paths, manifest)

        # Best-effort filesystem cleanup. Missing files aren't an error;
        # the user may have cleaned them up manually.
        import contextlib
        import shutil
        from pathlib import Path

        if kind == "repo":
            target = paths.context_repos / slug
            if target.is_dir():
                with contextlib.suppress(OSError):
                    shutil.rmtree(target)
        elif kind == "doc":
            stored = paths.context_docs / "raw" / f"{slug}.md"
            with contextlib.suppress(FileNotFoundError):
                stored.unlink()
            digested = paths.context_docs / "digested" / f"{slug}.md"
            with contextlib.suppress(FileNotFoundError):
                digested.unlink()
            # Old/legacy raw filenames with original extension.
            stored_raw = removed.get("stored_path") if isinstance(removed, dict) else None
            if isinstance(stored_raw, str):
                with contextlib.suppress(FileNotFoundError):
                    (paths.root / stored_raw).unlink()
        elif kind == "note":
            stored = paths.context_notes / f"{slug}.md"
            with contextlib.suppress(FileNotFoundError):
                stored.unlink()
        elif kind == "url":
            cached = removed.get("cached_path") if isinstance(removed, dict) else None
            if isinstance(cached, str):
                with contextlib.suppress(FileNotFoundError):
                    (paths.root / cached).unlink()
            else:
                # Fall back to slug-derived path.
                with contextlib.suppress(FileNotFoundError):
                    (paths.context_web / "cached" / f"{slug}.md").unlink()
        _ = Path  # keep import warm for type-checkers
        self._reply_json(HTTPStatus.OK, {"removed": kind, "name": slug})

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
        # Map deliberation_id → 1 when the planner says the next
        # action is on a manual handle for that deliberation. Source
        # of truth is the same as the next-actions panel — keeps the
        # left-rail badge from crying wolf about FYI inbox tags.
        pending_for_human = _planner_human_pending(paths)
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
                        "human_pending": pending_for_human.get(meta.id, 0),
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
                        "human_next_action": _human_next_action_for(paths, ident),
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
        # Run doctor inline so the UI sees live health, not whatever
        # value happens to be in the participants.md `Health` column.
        # `shutil.which` is fast — fine to do on every poll.
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
        # Decorate each entry with a derived `digested` / `cached`
        # boolean so the UI can render proper "ready / pending" badges
        # without computing paths client-side.
        for repo in manifest.get("repos") or []:
            if not isinstance(repo, dict):
                continue
            name = str(repo.get("name", ""))
            repo["digested"] = bool(
                name and (paths.context_repos / name / "digest.md").is_file()
            )
            meta_path = paths.context_repos / name / "meta.yaml"
            repo["last_digested_at"] = _read_yaml_field(meta_path, "last_digested_at")
        for doc in manifest.get("docs") or []:
            if not isinstance(doc, dict):
                continue
            name = str(doc.get("name", ""))
            doc["digested"] = bool(
                name and (paths.context_docs / "digested" / f"{name}.md").is_file()
            )
        for url in manifest.get("urls") or []:
            if not isinstance(url, dict):
                continue
            name = str(url.get("name", ""))
            url["cached"] = bool(
                name and (paths.context_web / "cached" / f"{name}.md").is_file()
            )
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

    def _handle_participants_add(self) -> None:
        """Append a new participant row to participants.md.

        Body schema:
          {
            "handle": "@claude",            # required
            "display_name": "Claude Sonnet",
            "cli_command": "claude",
            "model": "sonnet",
            "transport": "cli",             # default "cli"
            "permission_capability": "ask",
            "account_label": "personal",
            "quota_daily": 50,
            "quota_per_deliberation": 5
          }
        """
        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        handle = str(payload.get("handle", "")).strip()
        if not handle:
            return self._reply_json(
                HTTPStatus.BAD_REQUEST, {"error": "handle is required"}
            )
        new = NewParticipant(
            handle=handle,
            display_name=str(payload.get("display_name", "")).strip(),
            cli_command=str(payload.get("cli_command", "")).strip(),
            model=str(payload.get("model", "")).strip(),
            transport=str(payload.get("transport", "cli")).strip().lower() or "cli",
            quota_daily=_as_optional_int(payload.get("quota_daily")),
            quota_per_deliberation=_as_optional_int(payload.get("quota_per_deliberation")),
            permission_capability=str(payload.get("permission_capability", "ask")).strip(),
            account_label=str(payload.get("account_label", "")).strip(),
            health=str(payload.get("health", "unknown")).strip() or "unknown",
        )
        try:
            append_participant(paths.participants, new)
        except ParticipantsEditError as exc:
            return self._reply_json(
                HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
            )
        self._reply_json(HTTPStatus.OK, {"handle": new.normalised_handle()})

    def _handle_context_add(self, kind: str) -> None:
        """Append a context entry to context-manifest.yaml.

        Body schemas:
          repo:  {"path": "/abs/dir", "name"?: "...", "role"?: "...",
                  "relevance"?: "high|medium|low"}
          doc:   {"path": "/abs/file", "name"?: "..."}
          note:  {"name": "slug", "text": "<markdown>"}
          url:   {"url": "https://…", "name"?: "...", "role"?: "..."}

        Repo / doc / note actually copy or stage content; URL just
        records metadata. Digestion (the big LLM-driven summarisation)
        is deferred — the UI registers the source; the agents can
        re-read raw files via the bundle.
        """
        from datetime import UTC, datetime
        from pathlib import Path
        from shutil import copytree

        from ..core.context_bundle import load_context_manifest, save_context_manifest

        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = load_context_manifest(paths)

        if kind == "repo":
            repo_path_str = str(payload.get("path", "")).strip()
            if not repo_path_str:
                return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "path required"})
            repo_path = Path(repo_path_str).expanduser().resolve()
            if not repo_path.is_dir():
                return self._reply_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": f"{repo_path} is not a directory"},
                )
            name = str(payload.get("name") or repo_path.name).strip()
            paths.context_repos.mkdir(parents=True, exist_ok=True)
            (paths.context_repos / name).mkdir(parents=True, exist_ok=True)
            entry: dict[str, Any] = {
                "name": name,
                "path": str(repo_path),
                "role": str(payload.get("role", "")).strip(),
                "relevance": str(payload.get("relevance", "medium")).strip() or "medium",
                "digester": str(payload.get("digester", "")).strip() or None,
                "added_at": now,
            }
            repos = manifest.setdefault("repos", [])
            existing = next((r for r in repos if r.get("name") == name), None)
            if existing is not None:
                existing.update(entry)
            else:
                repos.append(entry)
            save_context_manifest(paths, manifest)
            return self._reply_json(HTTPStatus.OK, {"added": "repo", "name": name})

        if kind == "doc":
            from ..core.context_extract import (
                DOC_DIGEST_TOKEN_THRESHOLD,
                DocumentExtractError,
                extract_doc,
            )

            doc_path_str = str(payload.get("path", "")).strip()
            if not doc_path_str:
                return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "path required"})
            doc_path = Path(doc_path_str).expanduser().resolve()
            if not doc_path.is_file():
                return self._reply_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": f"{doc_path} is not a file"},
                )
            name = str(payload.get("name") or doc_path.stem).strip()
            try:
                extracted = extract_doc(doc_path)
            except DocumentExtractError as exc:
                return self._reply_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
                )

            raw_dir = paths.context_docs / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            # Always store extracted text as `<name>.md` so the bundle
            # collector finds it regardless of source extension.
            target = raw_dir / f"{name}.md"
            target.write_text(extracted.markdown, encoding="utf-8")
            needs_digest = extracted.tokens_estimated >= DOC_DIGEST_TOKEN_THRESHOLD
            entry = {
                "name": name,
                "source_path": str(doc_path),
                "source_format": doc_path.suffix.lower().lstrip("."),
                "stored_path": str(target.relative_to(paths.root)),
                "tokens_estimated": extracted.tokens_estimated,
                "needs_digest": needs_digest,
                "digester": str(payload.get("digester", "")).strip() or None,
                "added_at": now,
            }
            docs = manifest.setdefault("docs", [])
            existing = next((d for d in docs if d.get("name") == name), None)
            if existing is not None:
                existing.update(entry)
            else:
                docs.append(entry)
            save_context_manifest(paths, manifest)
            _ = copytree  # silence unused import for ruff (used elsewhere later)
            return self._reply_json(
                HTTPStatus.OK,
                {
                    "added": "doc",
                    "name": name,
                    "tokens_estimated": extracted.tokens_estimated,
                    "needs_digest": needs_digest,
                },
            )

        if kind == "note":
            name = str(payload.get("name", "")).strip()
            text = str(payload.get("text", ""))
            if not name:
                return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "name required"})
            if not text.strip():
                return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "text required"})
            paths.context_notes.mkdir(parents=True, exist_ok=True)
            target = paths.context_notes / f"{name}.md"
            if not text.endswith("\n"):
                text += "\n"
            target.write_text(text, encoding="utf-8")
            notes = manifest.setdefault("notes", [])
            if not any(n.get("name") == name for n in notes):
                notes.append({"name": name, "added_at": now})
                save_context_manifest(paths, manifest)
            return self._reply_json(HTTPStatus.OK, {"added": "note", "name": name})

        if kind == "url":
            from ..core.context_extract import UrlFetchError, fetch_url

            href = str(payload.get("url", "")).strip()
            if not href:
                return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "url required"})
            requested_name = str(payload.get("name") or "").strip()
            refresh_policy = str(payload.get("refresh_policy") or "manual").strip()
            try:
                fetched = fetch_url(href)
            except UrlFetchError as exc:
                return self._reply_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
                )
            # Use page title if no name was supplied; sluggify so it's
            # safe as a filename.
            slug = _slugify(requested_name or fetched.title or href)
            cached_dir = paths.context_web / "cached"
            cached_dir.mkdir(parents=True, exist_ok=True)
            cached_path = cached_dir / f"{slug}.md"
            cached_path.write_text(fetched.markdown, encoding="utf-8")

            entry = {
                "name": slug,
                "url": href,
                "title": fetched.title,
                "role": str(payload.get("role", "")).strip(),
                "refresh_policy": refresh_policy,
                "cached_path": str(cached_path.relative_to(paths.root)),
                "fetched_at": now,
                "added_at": now,
            }
            urls = manifest.setdefault("urls", [])
            existing = next((u for u in urls if u.get("url") == href), None)
            if existing is not None:
                existing.update(entry)
            else:
                urls.append(entry)
            save_context_manifest(paths, manifest)
            return self._reply_json(HTTPStatus.OK, {"added": "url", "name": slug})

        return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": f"unknown kind: {kind}"})

    def _reply_digestions(self) -> None:
        from ..core.digestion_queue import list_states

        paths = self.server.paths
        states = list_states(paths)
        self._reply_json(
            HTTPStatus.OK,
            {"repos": [s.to_dict() for s in states]},
        )

    def _handle_deliberation_create(self) -> None:
        """Create a new deliberation file and return its id + path.

        Body: { "title": "...", "question": "...", "tags"?: ["foo"] }
        Picks the next free id by counting existing deliberations.
        """
        from datetime import UTC, datetime

        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        title = str(payload.get("title", "")).strip()
        question = str(payload.get("question", "")).strip()
        tags_raw = payload.get("tags") or []
        if not title:
            return self._reply_json(
                HTTPStatus.BAD_REQUEST, {"error": "title is required"}
            )
        if not question:
            return self._reply_json(
                HTTPStatus.BAD_REQUEST, {"error": "question is required"}
            )
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]

        paths.deliberations.mkdir(parents=True, exist_ok=True)
        # Next-free 4-digit id, scanning existing files.
        existing_ids: set[int] = set()
        for p in paths.deliberations.glob("*.md"):
            try:
                existing_ids.add(int(p.name.split("-", 1)[0]))
            except ValueError:
                continue
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        slug_id = f"{next_id:04d}"
        slug_title = _slugify(title) or "deliberation"
        target = paths.deliberations / f"{slug_id}-{slug_title}.md"

        decider = _detect_human_handle(paths) or "@human"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        body = (
            "---\n"
            f'id: "{slug_id}"\n'
            f"title: {title}\n"
            "status: OPEN\n"
            "protocol_version: 0.1\n"
            f"created: {today}\n"
            "parent: null\n"
            "children: []\n"
            "roles:\n"
            "  proposer: null\n"
            "  critics: []\n"
            "  synthesizer: null\n"
            f'  decider: "{decider}"\n'
            f"tags: [{', '.join(_yaml_quote(t) for t in tags)}]\n"
            "relevant_context:\n"
            "  repos: []\n"
            "  docs: []\n"
            "  urls: []\n"
            "  notes: all\n"
            "final: false\n"
            "---\n\n"
            "## Question\n\n"
            f"{question}\n\n"
            "## Context\n\n"
            "## Open Questions\n\n"
            "## Decision\n\n"
            "## Contributions\n"
        )
        target.write_text(body, encoding="utf-8")
        self._reply_json(
            HTTPStatus.OK,
            {"id": slug_id, "filename": target.name},
        )

    def _handle_url_refresh(self) -> None:
        """Re-fetch a registered URL.

        Body: { "name"?: "<slug>" } or { "url": "<href>" }.
        """
        from datetime import UTC, datetime

        from ..core.context_bundle import load_context_manifest, save_context_manifest
        from ..core.context_extract import UrlFetchError, fetch_url

        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        slug = str(payload.get("name", "")).strip()
        href = str(payload.get("url", "")).strip()
        manifest = load_context_manifest(paths)
        urls = manifest.get("urls") or []
        if not isinstance(urls, list):
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "no urls registered"})
        target_entry: dict[str, Any] | None = None
        for u in urls:
            if not isinstance(u, dict):
                continue
            if slug and u.get("name") == slug:
                target_entry = u
                break
            if href and u.get("url") == href:
                target_entry = u
                break
        if target_entry is None:
            return self._reply_json(HTTPStatus.NOT_FOUND, {"error": "url not found"})
        try:
            fetched = fetch_url(str(target_entry.get("url", "")))
        except UrlFetchError as exc:
            return self._reply_json(
                HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)}
            )
        cached_dir = paths.context_web / "cached"
        cached_dir.mkdir(parents=True, exist_ok=True)
        slug_name = str(target_entry.get("name", _slugify(fetched.title or fetched.url)))
        cached_path = cached_dir / f"{slug_name}.md"
        cached_path.write_text(fetched.markdown, encoding="utf-8")
        target_entry["title"] = fetched.title
        target_entry["fetched_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        target_entry["cached_path"] = str(cached_path.relative_to(paths.root))
        save_context_manifest(paths, manifest)
        self._reply_json(HTTPStatus.OK, {"refreshed": slug_name})

    def _handle_digest_queue(self) -> None:
        """Queue a background digestion run for one repo or doc.

        Body: { "name": "<name>", "kind": "repo"|"doc" (default "repo"),
                "digester"?: "@handle" }
        """
        from ..core.digestion_queue import queue_digest

        paths = self.server.paths
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        name = str(payload.get("name", "")).strip()
        if not name:
            return self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "name required"})
        kind_raw = str(payload.get("kind", "repo")).strip().lower() or "repo"
        if kind_raw not in {"repo", "doc"}:
            return self._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"kind must be 'repo' or 'doc', got {kind_raw!r}"},
            )
        digester = payload.get("digester")
        try:
            state = queue_digest(
                paths,
                name,
                digester_handle=str(digester).strip() if digester else None,
                kind=kind_raw,  # type: ignore[arg-type]
            )
        except ValueError as exc:
            return self._reply_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
        self._reply_json(HTTPStatus.OK, state.to_dict())

    def _reply_fs_list(self, query: dict[str, list[str]]) -> None:
        """List children of a directory on the host filesystem.

        Powers the Browse… picker so users don't have to type absolute
        paths. The server is bound to 127.0.0.1, so local-only by
        construction — same threat model as the rest of the conductor.

        Query params:
          path:  absolute path (default: $HOME).
          mode:  "dirs" (default) → only folders, "files" → folders+files.
          show_hidden: "1" to include dotfiles.
        """
        from pathlib import Path

        raw = query.get("path", [""])[0] or str(Path.home())
        mode = query.get("mode", ["dirs"])[0]
        show_hidden = query.get("show_hidden", ["0"])[0] == "1"
        try:
            target = Path(raw).expanduser().resolve()
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
                entries.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "is_dir": is_dir,
                    }
                )
        except PermissionError:
            return self._reply_json(
                HTTPStatus.FORBIDDEN,
                {"error": f"permission denied reading {target}"},
            )
        parent = str(target.parent) if target != target.parent else None
        self._reply_json(
            HTTPStatus.OK,
            {
                "path": str(target),
                "parent": parent,
                "home": str(Path.home()),
                "entries": entries,
            },
        )

    def _reply_settings(self) -> None:
        """Return the live-editable subset of config.yaml as JSON."""
        import yaml

        paths = self.server.paths
        text = (
            paths.config_yaml.read_text(encoding="utf-8")
            if paths.config_yaml.is_file()
            else ""
        )
        try:
            raw = yaml.safe_load(text) or {}
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        cost = raw.get("cost") if isinstance(raw.get("cost"), dict) else {}
        ctx = raw.get("context") if isinstance(raw.get("context"), dict) else {}
        perms = raw.get("permissions") if isinstance(raw.get("permissions"), dict) else {}
        routing = raw.get("routing") if isinstance(raw.get("routing"), dict) else {}
        body: dict[str, Any] = {
            "cost_ceiling_usd": cost.get("ceiling_usd") if isinstance(cost, dict) else None,
            "cost_enforce": cost.get("enforce") if isinstance(cost, dict) else None,
            "unavailability_policy": raw.get("unavailability_policy"),
            "digester_defaults": (
                ctx.get("digester_defaults") if isinstance(ctx, dict) else {}
            )
            or {},
            "auto_approve_stakes_below": (
                perms.get("auto_approve_stakes_below") if isinstance(perms, dict) else None
            ),
            "routing_overrides": (
                routing.get("overrides") if isinstance(routing, dict) else {}
            )
            or {},
        }
        self._reply_json(HTTPStatus.OK, body)

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
        author = (
            str(payload.get("author", "")).strip()
            or _detect_human_handle(paths)
            or "@human"
        )
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
                from ..workspace.ratify import maybe_ratify_manifest

                maybe_ratify_manifest(paths, delib_path)
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

        config_keys = (
            "cost_ceiling_usd",
            "cost_enforce",
            "unavailability_policy",
            "digester_defaults",
            "auto_approve_stakes_below",
            "routing_overrides",
        )
        if any(k in payload for k in config_keys):
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
        if "digester_defaults" in payload:
            ctx = raw.get("context") if isinstance(raw.get("context"), dict) else {}
            ctx = dict(ctx) if isinstance(ctx, dict) else {}
            defaults = payload["digester_defaults"]
            if isinstance(defaults, dict):
                ctx["digester_defaults"] = {
                    k: str(v).strip()
                    for k, v in defaults.items()
                    if k in {"high", "medium", "low"} and str(v).strip()
                }
                raw["context"] = ctx
        if "auto_approve_stakes_below" in payload:
            perms = raw.get("permissions") if isinstance(raw.get("permissions"), dict) else {}
            perms = dict(perms) if isinstance(perms, dict) else {}
            v = payload["auto_approve_stakes_below"]
            if v in (None, "", "none"):
                perms.pop("auto_approve_stakes_below", None)
            elif str(v) in {"trivial", "tactical", "strategic", "irreversible"}:
                perms["auto_approve_stakes_below"] = str(v)
            raw["permissions"] = perms
        if "routing_overrides" in payload:
            r = raw.get("routing") if isinstance(raw.get("routing"), dict) else {}
            r = dict(r) if isinstance(r, dict) else {}
            ov = payload["routing_overrides"]
            if isinstance(ov, dict):
                cleaned = {
                    str(k): str(v).strip() for k, v in ov.items() if str(v).strip()
                }
                r["overrides"] = cleaned
                raw["routing"] = r
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------- #
# Helpers (pure)
# ---------------------------------------------------------------------- #


def _read_yaml_field(path: Path, key: str) -> Any:
    """Best-effort read of a single top-level field from a YAML file."""
    if not path.is_file():
        return None
    try:
        import yaml as _yaml

        data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if isinstance(data, dict):
        return data.get(key)
    return None


def _human_next_action_for(
    paths: WorkspacePaths, deliberation_id: str
) -> dict[str, Any] | None:
    """Surface the planner's per-deliberation next-action to the UI.

    Returns the move_type / role / reason / a friendly "what's
    expected" line for *this* deliberation if and only if the next
    pending move is on a manual-transport (i.e., human) handle.
    Returns None when the planner has nothing pending or the next
    actor is an agent.
    """
    try:
        result = plan(paths)
    except Exception:
        return None
    item = next(
        (i for i in result.items if i.deliberation.id == deliberation_id and i.is_manual),
        None,
    )
    if item is None:
        return None
    return {
        "move_type": item.move_type,
        "role": item.role,
        "reason": item.reason,
        "expected": _what_human_should_do(item.move_type, item.role, item.reason),
    }


def _what_human_should_do(move_type: str, role: str, reason: str) -> str:
    """Plain-English instruction for the human, derived from the
    planner's (role, move_type, reason) tuple."""
    if move_type == "PROPOSAL":
        return (
            "Author a PROPOSAL. Read what's in this deliberation so far, then "
            "open Compose move and fill in your initial proposal — the move "
            "type is pre-selected for you."
        )
    if move_type == "CRITIQUE":
        return (
            "Author a CRITIQUE of the existing PROPOSAL. Look for missing "
            "alternatives, weak reasoning, or risks the proposer hasn't "
            "addressed. Pre-selected in Compose move."
        )
    if move_type == "SYNTHESIS":
        return (
            "Author a SYNTHESIS that resolves the proposal + critiques into "
            "a single direction. Compose move has the form ready."
        )
    if move_type == "DECISION":
        return (
            "Author a DECISION. Read the SYNTHESIS, then commit to a path "
            "with a clear summary line and rationale. Compose move is "
            "pre-set to DECISION."
        )
    if move_type == "ANSWER":
        return (
            "An agent asked you a QUESTION. Open Compose move (pre-set to "
            "ANSWER) and respond — don't worry about completeness; agents "
            "will work with whatever you give them."
        )
    if move_type == "EXPLANATION":
        return (
            "An EXPLANATION was requested. Open Compose move (pre-set) and "
            "describe the prior work in plain language."
        )
    return (
        f"Author a {move_type} ({role}). Open Compose move and fill in the "
        f"sections; the move type is pre-selected for you."
    )


def _detect_human_handle(paths: WorkspacePaths) -> str | None:
    """Return the first manual-transport participant's handle, if any.

    Used as the default author for human-issued moves so the UI never
    has to hard-code `@human-rohan` (the historical default).
    """
    if not paths.participants.is_file():
        return None
    try:
        for p in parse_participants(paths.participants):
            if p.transport == "manual":
                return p.handle
    except Exception:
        return None
    return None


def _slugify(value: str) -> str:
    """Lowercase, hyphenate, strip non-alphanumeric. Bounded at 48 chars."""
    import re

    base = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    if not base:
        base = "url"
    return base[:48]


def _yaml_quote(value: str) -> str:
    """Double-quote a YAML scalar so flow-sequence tokens like `@handle`
    parse cleanly. `@` and a few other characters are reserved/invalid as
    plain-scalar starts in YAML 1.1 flow context."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _planner_human_pending(paths: WorkspacePaths) -> dict[str, int]:
    """Per-deliberation flag: 1 if the planner's next move is on a
    manual handle (i.e. the human really is the next actor)."""
    try:
        result = plan(paths)
    except Exception:
        return {}
    return {item.deliberation.id: 1 for item in result.items if item.is_manual}


def _human_pending_by_deliberation(paths: WorkspacePaths) -> dict[str, int]:
    """Return {deliberation_id: pending_count} from the human's inbox.

    Looks at the first manual-transport participant's `<inbox>.md`
    and parses lines of the form `- pending: <MOVE> in #<id> ...`.
    """
    import re

    from ..core.participants import parse_participants

    if not paths.participants.is_file():
        return {}
    human: str | None = None
    try:
        for p in parse_participants(paths.participants):
            if p.transport == "manual":
                human = p.handle
                break
    except Exception:
        return {}
    if human is None:
        return {}
    inbox_file = paths.inbox / f"{human}.md"
    if not inbox_file.is_file():
        return {}
    counts: dict[str, int] = {}
    rx = re.compile(r"^- pending:\s+\S+\s+in\s+#(\S+)")
    for line in inbox_file.read_text(encoding="utf-8").splitlines():
        m = rx.match(line.strip())
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def _live_health_dict(h: Any) -> dict[str, Any] | None:
    """Serialise a HandleHealth dataclass to a JSON-friendly shape."""
    if h is None:
        return None
    return {
        "on_path": h.on_path,
        "note": h.note,
        "transport": h.transport,
    }


def _as_optional_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


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
