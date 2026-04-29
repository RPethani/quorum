"""Permission broker — request/decision plane.

Phase 11 ships the full data plane (request file format, list/approve/
deny operations, auto-approval policy) and the UI surface
(/permissions page). The *live* stdin/stdout pipe proxying — where the
conductor intercepts an agent's "may I run this shell command?"
question and routes it to the user — is documented as a deferred
follow-up under docs/decisions/003-permission-broker-deferral.md. The
v1 default of `broker.enabled: false` means the conductor relies on
per-CLI restrictive `--allowedTools` flags as the primary defense.

Files on disk:

    runtime/permissions/<request_id>.yaml          — pending
    runtime/permissions/decided/<request_id>.yaml  — approved or denied

Each request carries the agent handle, the deliberation it was running
on, the tool / command being requested, the stakes classification (set
by the agent's own QUESTION-style ask), a one-line rationale from the
agent, and a timestamp.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from ..paths import WorkspacePaths


class PermissionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class PermissionStakes(StrEnum):
    TRIVIAL = "trivial"
    TACTICAL = "tactical"
    STRATEGIC = "strategic"
    IRREVERSIBLE = "irreversible"


@dataclass
class PermissionRequest:
    id: str
    handle: str
    deliberation_id: str
    tool: str  # e.g. "Bash" / "WebFetch" / "FileWrite"
    operation: str  # the specific request, e.g. "git push origin main"
    rationale: str  # one-line explanation from the agent
    stakes: PermissionStakes
    requested_at: str
    status: PermissionStatus = PermissionStatus.PENDING
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "handle": self.handle,
            "deliberation_id": self.deliberation_id,
            "tool": self.tool,
            "operation": self.operation,
            "rationale": self.rationale,
            "stakes": self.stakes.value,
            "requested_at": self.requested_at,
            "status": self.status.value,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
            **self.extras,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PermissionRequest:
        known = {
            "id", "handle", "deliberation_id", "tool", "operation",
            "rationale", "stakes", "requested_at", "status",
            "decided_at", "decided_by", "decision_reason",
        }
        return cls(
            id=str(raw["id"]),
            handle=str(raw["handle"]),
            deliberation_id=str(raw.get("deliberation_id", "")),
            tool=str(raw.get("tool", "")),
            operation=str(raw.get("operation", "")),
            rationale=str(raw.get("rationale", "")),
            stakes=PermissionStakes(str(raw.get("stakes", "tactical"))),
            requested_at=str(raw.get("requested_at", _now_iso())),
            status=PermissionStatus(str(raw.get("status", "pending"))),
            decided_at=raw.get("decided_at"),
            decided_by=raw.get("decided_by"),
            decision_reason=raw.get("decision_reason"),
            extras={k: v for k, v in raw.items() if k not in known},
        )


# ---------------------------------------------------------------------- #
# File-system layout
# ---------------------------------------------------------------------- #


def _pending_dir(paths: WorkspacePaths) -> Path:
    return paths.runtime / "permissions"


def _decided_dir(paths: WorkspacePaths) -> Path:
    return paths.runtime / "permissions" / "decided"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def create_request(
    paths: WorkspacePaths,
    *,
    handle: str,
    deliberation_id: str,
    tool: str,
    operation: str,
    rationale: str,
    stakes: PermissionStakes,
) -> PermissionRequest:
    """Open a new pending permission request. Phase 11+ live broker
    callers use this; the data plane is also useful for the UI to seed
    test fixtures."""
    _pending_dir(paths).mkdir(parents=True, exist_ok=True)
    request = PermissionRequest(
        id=secrets.token_hex(6),
        handle=handle,
        deliberation_id=deliberation_id,
        tool=tool,
        operation=operation,
        rationale=rationale,
        stakes=stakes,
        requested_at=_now_iso(),
        status=PermissionStatus.PENDING,
    )
    _write(paths, request)
    _emit_requested(paths, request)
    return request


def list_requests(paths: WorkspacePaths) -> list[PermissionRequest]:
    """All requests (pending + decided), newest first."""
    out: list[PermissionRequest] = []
    for d in (_pending_dir(paths), _decided_dir(paths)):
        if not d.is_dir():
            continue
        for entry in d.glob("*.yaml"):
            try:
                raw = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
                if isinstance(raw, dict):
                    out.append(PermissionRequest.from_dict(raw))
            except Exception:
                continue
    out.sort(key=lambda r: r.requested_at, reverse=True)
    return out


def get_request(paths: WorkspacePaths, request_id: str) -> PermissionRequest | None:
    for d in (_pending_dir(paths), _decided_dir(paths)):
        path = d / f"{request_id}.yaml"
        if path.is_file():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                return PermissionRequest.from_dict(raw)
    return None


def approve(
    paths: WorkspacePaths,
    request_id: str,
    *,
    decided_by: str = "@human",
    reason: str | None = None,
) -> PermissionRequest | None:
    return _decide(
        paths,
        request_id,
        new_status=PermissionStatus.APPROVED,
        decided_by=decided_by,
        reason=reason,
    )


def deny(
    paths: WorkspacePaths,
    request_id: str,
    *,
    decided_by: str = "@human",
    reason: str | None = None,
) -> PermissionRequest | None:
    return _decide(
        paths,
        request_id,
        new_status=PermissionStatus.DENIED,
        decided_by=decided_by,
        reason=reason,
    )


def auto_approve_if_allowed(
    paths: WorkspacePaths,
    request: PermissionRequest,
    *,
    auto_approve_stakes_below: PermissionStakes | None,
) -> PermissionRequest:
    """Apply the workspace's auto-approval policy.

    `auto_approve_stakes_below` is the highest stakes that auto-approve.
    `None` disables auto-approval entirely. The intended ordering is
    `trivial < tactical < strategic < irreversible`.
    """
    if auto_approve_stakes_below is None:
        return request
    order = {
        PermissionStakes.TRIVIAL: 0,
        PermissionStakes.TACTICAL: 1,
        PermissionStakes.STRATEGIC: 2,
        PermissionStakes.IRREVERSIBLE: 3,
    }
    if order[request.stakes] <= order[auto_approve_stakes_below]:
        decided = _decide(
            paths,
            request.id,
            new_status=PermissionStatus.AUTO_APPROVED,
            decided_by="@conductor",
            reason=f"auto-approved: stakes={request.stakes.value} <= {auto_approve_stakes_below.value}",
        )
        if decided is not None:
            return decided
    return request


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _write(paths: WorkspacePaths, request: PermissionRequest) -> None:
    if request.status == PermissionStatus.PENDING:
        target = _pending_dir(paths) / f"{request.id}.yaml"
    else:
        target = _decided_dir(paths) / f"{request.id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(request.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _decide(
    paths: WorkspacePaths,
    request_id: str,
    *,
    new_status: PermissionStatus,
    decided_by: str,
    reason: str | None,
) -> PermissionRequest | None:
    pending = _pending_dir(paths) / f"{request_id}.yaml"
    if not pending.is_file():
        return None
    raw = yaml.safe_load(pending.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return None
    request = PermissionRequest.from_dict(raw)
    request.status = new_status
    request.decided_at = _now_iso()
    request.decided_by = decided_by
    request.decision_reason = reason
    pending.unlink()
    _write(paths, request)
    _emit_decided(paths, request)
    return request


def _emit_requested(paths: WorkspacePaths, request: PermissionRequest) -> None:
    from ..events import EventLogger, PermissionRequested

    EventLogger(paths.events_jsonl).emit(
        PermissionRequested(
            request_id=request.id,
            handle=request.handle,
            deliberation_id=request.deliberation_id,
            tool=request.tool,
            operation=request.operation,
            stakes=request.stakes.value,
        )
    )


def _emit_decided(paths: WorkspacePaths, request: PermissionRequest) -> None:
    from ..events import EventLogger, PermissionDecided

    EventLogger(paths.events_jsonl).emit(
        PermissionDecided(
            request_id=request.id,
            handle=request.handle,
            decision=request.status.value,
            decided_by=request.decided_by or "",
            reason=request.decision_reason,
        )
    )
