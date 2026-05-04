"""HTTP routes for the canvas surface (`/api/canvas/*`).

Per `docs-specs/canvas-redesign.md` S4. The canvas API is mounted
alongside the protocol-era endpoints during migration; the UI's new
shell consumes this surface, the legacy UI keeps using the existing
deliberation/manifest endpoints. Both will coexist until the legacy
surface retires.

Each handler is implemented as a free function that takes the live
`QuorumHandler` instance plus any URL-path arguments. This keeps
`http_app.py` from ballooning further while still letting handlers
use the request/response helpers it already exposes
(`_reply_json`, `_read_json_body`, etc).
"""

from __future__ import annotations

import shutil
from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..canvas import (
    InvokeFn,
    StateError,
    dispatch,
    extract_mentions,
    load_state,
    parse_canvas,
    save_state,
)
from ..canvas import remediation as remediation_mod
from ..canvas.transport_adapter import make_invoker
from ..context import (
    ContextEntry,
    ContextOperationError,
    DigestError,
    add_doc,
    add_note,
    add_repo,
    digest_repo,
    load_manifest,
    make_digest_invoker,
    mark_stale_repos,
    refresh as context_refresh,
    remove as context_remove,
)
from ..context.digester import DigestInvokeFn

if TYPE_CHECKING:
    from .http_app import QuorumHandler


# Lazily memoised invoker — created once per handler module load so
# repeat dispatches don't re-build the closure every turn.
_INVOKER: InvokeFn | None = None
_DIGEST_INVOKER: DigestInvokeFn | None = None


def _invoker() -> InvokeFn:
    global _INVOKER
    if _INVOKER is None:
        _INVOKER = make_invoker()
    return _INVOKER


def _digest_invoker() -> DigestInvokeFn:
    global _DIGEST_INVOKER
    if _DIGEST_INVOKER is None:
        _DIGEST_INVOKER = make_digest_invoker()
    return _DIGEST_INVOKER


def _workspace(handler: QuorumHandler) -> Path:
    return handler.server.paths.root


# ---------------------------------------------------------------------- #
# GET /api/canvas/state
# ---------------------------------------------------------------------- #


def reply_state(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    try:
        state = load_state(ws)
    except StateError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})

    handler._reply_json(
        HTTPStatus.OK,
        {
            "title": state.title,
            "created_at": _iso(state.created_at),
            "message_counter": state.message_counter,
            "cost": {
                "spent": state.cost.spent,
                "cap": state.cost.cap,
                "enforce": state.cost.enforce,
            },
            "digester_handle": state.digester_handle,
            "schema_version": state.schema_version,
        },
    )


# ---------------------------------------------------------------------- #
# GET /api/canvas/messages
# ---------------------------------------------------------------------- #


def reply_messages(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    msgs = parse_canvas(ws / "canvas.md")
    handler._reply_json(
        HTTPStatus.OK,
        {
            "messages": [
                {
                    "id": m.id,
                    "author": m.author,
                    "ts": _iso(m.timestamp),
                    "body": m.body,
                }
                for m in msgs
            ]
        },
    )


# ---------------------------------------------------------------------- #
# POST /api/canvas/messages   {body, author?}
# ---------------------------------------------------------------------- #


def handle_send_message(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    payload = handler._read_json_body()
    body = str(payload.get("body", "")).strip()
    if not body:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST, {"error": "body is required"}
        )
    author = str(payload.get("author") or "@rakesh")

    try:
        result = dispatch(ws, body, invoke=_invoker(), author=author)
    except StateError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})

    handler._reply_json(
        HTTPStatus.OK,
        {
            "user_message": _msg_dict(result.user_message),
            "turns": [
                {
                    "handle": t.handle,
                    "message": _msg_dict(t.message) if t.message else None,
                    "artifacts": [
                        {
                            "filename": a.filename,
                            "archived": str(a.archived_path)
                            if a.archived_path
                            else None,
                        }
                        for a in t.artifacts
                    ],
                    "error": t.error,
                }
                for t in result.turns
            ],
        },
    )


# ---------------------------------------------------------------------- #
# POST /api/canvas/messages/<id>/retry
# ---------------------------------------------------------------------- #


def handle_retry(handler: QuorumHandler, message_id: str) -> None:
    """Re-invoke the agent for a failed turn.

    Strategy: walk back through ``canvas.md`` to find the @system
    error message with id == ``message_id``, then the user message
    that preceded it. Re-run dispatch on that user message body.
    """
    ws = _workspace(handler)
    msgs = parse_canvas(ws / "canvas.md")

    # Find the failed @system message and the originating user message.
    target_idx = next(
        (i for i, m in enumerate(msgs) if m.id == message_id),
        None,
    )
    if target_idx is None:
        return handler._reply_json(
            HTTPStatus.NOT_FOUND, {"error": f"message {message_id} not found"}
        )

    # Walk backward to the most recent user message (non-@system,
    # non-AI). For MVP we treat any non-@system author whose mentions
    # the failed handle as the trigger. Simpler: just take the most
    # recent message authored by something other than @system.
    user_msg = None
    for m in reversed(msgs[:target_idx]):
        if m.author == "@system":
            continue
        if m.author.startswith("@") and extract_mentions(m.body):
            user_msg = m
            break
    if user_msg is None:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST,
            {"error": "could not locate a user message to retry from"},
        )

    try:
        result = dispatch(ws, user_msg.body, invoke=_invoker(), author=user_msg.author)
    except StateError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})

    handler._reply_json(
        HTTPStatus.OK,
        {
            "user_message": _msg_dict(result.user_message),
            "turns": [
                {
                    "handle": t.handle,
                    "message": _msg_dict(t.message) if t.message else None,
                    "error": t.error,
                }
                for t in result.turns
            ],
        },
    )


# ---------------------------------------------------------------------- #
# GET /api/canvas/artifacts
# ---------------------------------------------------------------------- #


def reply_artifacts_list(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    art_dir = ws / "artifacts"
    items = []
    if art_dir.is_dir():
        for p in sorted(art_dir.rglob("*.md")):
            stat = p.stat()
            items.append(
                {
                    "filename": str(p.relative_to(art_dir).as_posix()),
                    "size": stat.st_size,
                    "modified_at": _iso(
                        datetime.fromtimestamp(stat.st_mtime, tz=UTC)
                    ),
                }
            )
    handler._reply_json(HTTPStatus.OK, {"artifacts": items})


# ---------------------------------------------------------------------- #
# GET /api/canvas/artifacts/<name>
# ---------------------------------------------------------------------- #


def reply_artifact(handler: QuorumHandler, filename: str) -> None:
    ws = _workspace(handler)
    target = _safe_artifact_path(ws, filename)
    if target is None:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST, {"error": "invalid artifact path"}
        )
    if not target.is_file():
        return handler._reply_json(
            HTTPStatus.NOT_FOUND, {"error": f"{filename} not found"}
        )
    body = target.read_text(encoding="utf-8")
    stat = target.stat()
    handler._reply_json(
        HTTPStatus.OK,
        {
            "filename": filename,
            "body": body,
            "size": stat.st_size,
            "modified_at": _iso(datetime.fromtimestamp(stat.st_mtime, tz=UTC)),
        },
    )


# ---------------------------------------------------------------------- #
# DELETE /api/canvas/artifacts/<name>
# ---------------------------------------------------------------------- #


def handle_artifact_delete(handler: QuorumHandler, filename: str) -> None:
    ws = _workspace(handler)
    target = _safe_artifact_path(ws, filename)
    if target is None:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST, {"error": "invalid artifact path"}
        )
    if not target.is_file():
        return handler._reply_json(
            HTTPStatus.NOT_FOUND, {"error": f"{filename} not found"}
        )

    trash_dir = ws / ".trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archived = trash_dir / f"{target.stem}.{ts}{target.suffix}"
    counter = 0
    while archived.exists():
        counter += 1
        archived = trash_dir / f"{target.stem}.{ts}.{counter}{target.suffix}"
    shutil.move(str(target), str(archived))

    # Bump state.yaml mtime so SSE clients refresh artifact list.
    try:
        state = load_state(ws)
        save_state(ws, state)
    except StateError:
        pass

    handler._reply_json(
        HTTPStatus.OK,
        {"filename": filename, "archived": str(archived.relative_to(ws))},
    )




# ---------------------------------------------------------------------- #
# PATCH /api/canvas/state   {title}
# ---------------------------------------------------------------------- #


def handle_state_patch(handler: QuorumHandler) -> None:
    """Update mutable workspace metadata.

    Currently only ``title`` is editable; other state.yaml fields
    (counter, cost, schema_version) are conductor-managed.
    """
    ws = _workspace(handler)
    payload = handler._read_json_body()

    try:
        state = load_state(ws)
    except StateError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})

    if "title" in payload:
        new_title = str(payload["title"]).strip()
        if not new_title:
            return handler._reply_json(
                HTTPStatus.BAD_REQUEST, {"error": "title cannot be empty"}
            )
        if len(new_title) > 200:
            return handler._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "title is too long (max 200 chars)"},
            )
        state = dc_replace(state, title=new_title)

    if "digester_handle" in payload:
        new_handle = str(payload.get("digester_handle") or "").strip()
        if new_handle and not new_handle.startswith("@"):
            return handler._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "digester_handle must start with '@' (or be empty)"},
            )
        state = dc_replace(state, digester_handle=new_handle)

    save_state(ws, state)

    handler._reply_json(
        HTTPStatus.OK,
        {
            "title": state.title,
            "created_at": _iso(state.created_at),
            "message_counter": state.message_counter,
            "cost": {
                "spent": state.cost.spent,
                "cap": state.cost.cap,
                "enforce": state.cost.enforce,
            },
            "digester_handle": state.digester_handle,
            "schema_version": state.schema_version,
        },
    )


# ---------------------------------------------------------------------- #
# Context endpoints
# ---------------------------------------------------------------------- #


def reply_context_list(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    manifest = mark_stale_repos(ws)
    handler._reply_json(
        HTTPStatus.OK,
        {"entries": [_entry_dict(e) for e in manifest.entries]},
    )


def handle_context_add(handler: QuorumHandler) -> None:
    ws = _workspace(handler)
    payload = handler._read_json_body()
    kind = str(payload.get("kind", "")).strip()
    name_opt = payload.get("name")
    name = str(name_opt).strip() if name_opt is not None else None

    try:
        if kind == "repo":
            source = _resolved_source(payload)
            if source is None:
                return handler._reply_json(
                    HTTPStatus.BAD_REQUEST, {"error": "source path is required"}
                )
            entry = add_repo(ws, source, name=name)
        elif kind == "doc":
            source = _resolved_source(payload)
            if source is None:
                return handler._reply_json(
                    HTTPStatus.BAD_REQUEST, {"error": "source path is required"}
                )
            entry = add_doc(ws, source, name=name)
        elif kind == "note":
            note_name = str(payload.get("name", "")).strip()
            body = str(payload.get("body", ""))
            entry = add_note(ws, note_name, body)
        else:
            return handler._reply_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "kind must be 'repo', 'doc', or 'note'"},
            )
    except ContextOperationError as e:
        return handler._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})

    handler._reply_json(HTTPStatus.OK, {"entry": _entry_dict(entry)})


def handle_context_remove(handler: QuorumHandler, entry_id: str) -> None:
    ws = _workspace(handler)
    try:
        entry = context_remove(ws, entry_id)
    except ContextOperationError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
    handler._reply_json(HTTPStatus.OK, {"removed": _entry_dict(entry)})


def handle_context_refresh(handler: QuorumHandler, entry_id: str) -> None:
    ws = _workspace(handler)
    try:
        entry = context_refresh(ws, entry_id)
    except ContextOperationError as e:
        return handler._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
    handler._reply_json(HTTPStatus.OK, {"entry": _entry_dict(entry)})


def handle_context_digest(handler: QuorumHandler, entry_id: str) -> None:
    ws = _workspace(handler)
    payload = handler._read_json_body()

    try:
        state = load_state(ws)
    except StateError as e:
        return handler._reply_json(HTTPStatus.NOT_FOUND, {"error": str(e)})

    handle = str(payload.get("handle") or state.digester_handle or "").strip()
    if not handle:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST,
            {
                "error": (
                    "no digester_handle configured — set one in Settings "
                    "or pass {handle: '@…'} in the body"
                )
            },
        )

    try:
        entry = digest_repo(ws, entry_id, invoke=_digest_invoker(), handle=handle)
    except DigestError as e:
        return handler._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})

    handler._reply_json(HTTPStatus.OK, {"entry": _entry_dict(entry)})


# ---------------------------------------------------------------------- #
# POST /api/canvas/remediations/apply   {id, handle}
# ---------------------------------------------------------------------- #


def handle_remediation_apply(handler: QuorumHandler) -> None:
    """Run a named remediation against the current workspace.

    Request body: ``{"id": "<rule-id>", "handle": "<participant>"}``.
    Returns ``{"applied": <id>, "summary": "<message>"}`` on success;
    a 4xx with ``{"error": ...}`` on failure.
    """
    payload = handler._read_json_body()
    rid = str(payload.get("id", "")).strip()
    handle = str(payload.get("handle", "")).strip()
    if not rid or not handle:
        return handler._reply_json(
            HTTPStatus.BAD_REQUEST, {"error": "id and handle are required"}
        )
    try:
        summary = remediation_mod.apply(rid, _workspace(handler), handle)
    except remediation_mod.RemediationError as e:
        return handler._reply_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
    handler._reply_json(HTTPStatus.OK, {"applied": rid, "summary": summary})


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _safe_artifact_path(workspace: Path, filename: str) -> Path | None:
    """Reject path traversal — every artifact must live under
    ``workspace/artifacts/``."""
    candidate = (workspace / "artifacts" / filename).resolve()
    base = (workspace / "artifacts").resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def _resolved_source(payload: dict[str, Any]) -> Path | None:
    raw = payload.get("source")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return Path(s).expanduser()


def _entry_dict(entry: ContextEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "name": entry.name,
        "added_at": _iso(entry.added_at),
        "source": entry.source,
        "digest_status": entry.digest_status,
        "digest_summary": entry.digest_summary,
        "digest_error": entry.digest_error,
        "digest_at": _iso(entry.digest_at) if entry.digest_at else None,
        "source_git_ref": entry.source_git_ref,
        "stale": entry.stale,
        "body": entry.body,
    }


def _msg_dict(message: Any) -> dict[str, Any]:
    return {
        "id": message.id,
        "author": message.author,
        "ts": _iso(message.timestamp),
        "body": message.body,
    }


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    iso = ts.astimezone(UTC).isoformat()
    return iso[:-6] + "Z" if iso.endswith("+00:00") else iso
