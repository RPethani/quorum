"""`state.yaml` schema and atomic I/O.

Per design-doc §7.5, `state.yaml` is the *current* truth (events.jsonl is
the *history*). It's written atomically — temp-file + fsync + rename —
because a crash mid-write must never corrupt the file.

Only the conductor writes this. The UI is read-only on it.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "0.1"


class WorkspaceMode(StrEnum):
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"


class WorkspaceState(StrEnum):
    """Top-level workspace state. Distinct from per-deliberation status."""

    INITIALIZED = "INITIALIZED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    COMPLETED_AUTONOMOUS = "COMPLETED_AUTONOMOUS"
    ARCHIVED = "ARCHIVED"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ManifestProgress:
    status: str = "DRAFTING"  # DRAFTING | READY | LOCKED
    total_artifacts: int = 0
    artifacts_complete: int = 0
    artifacts_in_production: int = 0
    artifacts_pending: int = 0
    quality_gates_clear: bool = False
    closing_ceremony_eligible: bool = False
    final_deliberation_id: str | None = None


@dataclass
class WorkspaceStateModel:
    """In-memory representation of `state.yaml`.

    Fields below correspond 1:1 with the v0.1 schema in design-doc §7.5.
    Unknown keys read from disk are preserved on round-trip via `extras`
    so a future schema-bumping change does not silently drop fields.
    """

    schema_version: str = SCHEMA_VERSION
    workspace_id: str = ""
    mode: WorkspaceMode = WorkspaceMode.INTERACTIVE
    state: WorkspaceState = WorkspaceState.INITIALIZED
    state_changed_at: str = field(default_factory=_now)
    last_activity_at: str = field(default_factory=_now)
    last_human_activity_at: str | None = None
    pending_deputy_count: int = 0
    manifest: ManifestProgress = field(default_factory=ManifestProgress)
    extras: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # YAML round-trip
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "mode": self.mode.value,
            "state": self.state.value,
            "state_changed_at": self.state_changed_at,
            "last_activity_at": self.last_activity_at,
            "last_human_activity_at": self.last_human_activity_at,
            "pending_deputy_count": self.pending_deputy_count,
            "manifest": {
                "status": self.manifest.status,
                "total_artifacts": self.manifest.total_artifacts,
                "artifacts_complete": self.manifest.artifacts_complete,
                "artifacts_in_production": self.manifest.artifacts_in_production,
                "artifacts_pending": self.manifest.artifacts_pending,
                "quality_gates_clear": self.manifest.quality_gates_clear,
                "closing_ceremony_eligible": self.manifest.closing_ceremony_eligible,
                "final_deliberation_id": self.manifest.final_deliberation_id,
            },
        }
        # Preserve unknown keys verbatim so we don't silently drop
        # forward-compatible fields written by a newer conductor.
        for key, value in self.extras.items():
            if key not in out:
                out[key] = value
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkspaceStateModel:
        known: set[str] = {
            "schema_version",
            "workspace_id",
            "mode",
            "state",
            "state_changed_at",
            "last_activity_at",
            "last_human_activity_at",
            "pending_deputy_count",
            "manifest",
        }
        manifest_raw = raw.get("manifest", {}) or {}
        manifest = ManifestProgress(
            status=manifest_raw.get("status", "DRAFTING"),
            total_artifacts=int(manifest_raw.get("total_artifacts", 0)),
            artifacts_complete=int(manifest_raw.get("artifacts_complete", 0)),
            artifacts_in_production=int(manifest_raw.get("artifacts_in_production", 0)),
            artifacts_pending=int(manifest_raw.get("artifacts_pending", 0)),
            quality_gates_clear=bool(manifest_raw.get("quality_gates_clear", False)),
            closing_ceremony_eligible=bool(manifest_raw.get("closing_ceremony_eligible", False)),
            final_deliberation_id=manifest_raw.get("final_deliberation_id"),
        )
        return cls(
            schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
            workspace_id=str(raw.get("workspace_id", "")),
            mode=WorkspaceMode(raw.get("mode", WorkspaceMode.INTERACTIVE.value)),
            state=WorkspaceState(raw.get("state", WorkspaceState.INITIALIZED.value)),
            state_changed_at=str(raw.get("state_changed_at", _now())),
            last_activity_at=str(raw.get("last_activity_at", _now())),
            last_human_activity_at=raw.get("last_human_activity_at"),
            pending_deputy_count=int(raw.get("pending_deputy_count", 0)),
            manifest=manifest,
            extras={k: v for k, v in raw.items() if k not in known},
        )


def load_state(path: Path) -> WorkspaceStateModel:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise StateFileError(f"{path} is not a YAML mapping.")
    return WorkspaceStateModel.from_dict(raw)


def save_state(path: Path, model: WorkspaceStateModel) -> None:
    """Write `model` to `path` atomically.

    Rationale: a crash mid-write would otherwise leave a corrupted
    `state.yaml` and the workspace would be unrecoverable without
    reconstructing from `events.jsonl`. Atomic rename is cheap insurance.
    """
    payload = yaml.safe_dump(model.to_dict(), sort_keys=False, default_flow_style=False)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".state.yaml.", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; the original file is untouched.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


class StateFileError(RuntimeError):
    """Raised when `state.yaml` is malformed or unreadable."""
