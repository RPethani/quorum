"""Read and write the workspace's `state.yaml`.

`state.yaml` is the small metadata file at the workspace root —
title, message counter, cost accounting. Schema is anchored by
`canvas.workspace.STATE_SCHEMA_VERSION`.

This module owns:

- a typed view of the file (`WorkspaceState`),
- atomic `load_state` / `save_state`, and
- `next_message_id`, the helper the dispatcher uses to allocate
  monotonic IDs (`msg-0001`, `msg-0002`, …) when appending messages.

`save_state` writes through a temporary file + `os.replace` so a
crash mid-write never leaves a partial `state.yaml` on disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .workspace import DEFAULT_COST_CAP_USD, STATE_SCHEMA_VERSION


@dataclass(frozen=True)
class CostState:
    """Cost accounting block of `state.yaml`."""

    spent: float = 0.0
    cap: float = DEFAULT_COST_CAP_USD
    enforce: bool = True


@dataclass(frozen=True)
class WorkspaceState:
    """Typed view of `state.yaml`."""

    title: str
    created_at: datetime
    message_counter: int = 0
    cost: CostState = field(default_factory=CostState)
    digester_handle: str = ""
    """Participant handle (e.g. ``@claude-opus``) used to summarise
    repos added via the context-seeding flow. Empty means no
    digester is configured — pending repos sit at status ``pending``
    until the user picks one (Settings → Default agents → Digester
    in phase 3)."""
    schema_version: int = STATE_SCHEMA_VERSION


class StateError(RuntimeError):
    """Raised on missing or malformed `state.yaml`."""


def load_state(workspace: Path) -> WorkspaceState:
    """Parse `workspace/state.yaml` into a `WorkspaceState`.

    Raises `StateError` if the file is missing — the workspace
    isn't a canvas workspace until `canvas.workspace.scaffold()`
    has run.
    """
    path = workspace / "state.yaml"
    if not path.exists():
        raise StateError(
            f"{path} not found — run `canvas.workspace.scaffold()` first."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cost_raw = raw.get("cost") or {}
    return WorkspaceState(
        title=str(raw.get("title", "Untitled brainstorm")),
        created_at=_parse_iso(str(raw.get("created_at"))),
        message_counter=int(raw.get("message_counter", 0)),
        cost=CostState(
            spent=float(cost_raw.get("spent", 0.0)),
            cap=float(cost_raw.get("cap", DEFAULT_COST_CAP_USD)),
            enforce=bool(cost_raw.get("enforce", True)),
        ),
        digester_handle=str(raw.get("digester_handle", "") or ""),
        schema_version=int(raw.get("schema_version", STATE_SCHEMA_VERSION)),
    )


def save_state(workspace: Path, state: WorkspaceState) -> None:
    """Write *state* to `workspace/state.yaml` atomically."""
    path = workspace / "state.yaml"
    body = _render(state)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def next_message_id(workspace: Path) -> str:
    """Allocate the next message ID and persist the bumped counter.

    Returns the new ID formatted as ``msg-{n:04d}``. Writes back to
    `state.yaml` immediately so a crash between calls doesn't reuse
    an ID.
    """
    state = load_state(workspace)
    new_n = state.message_counter + 1
    save_state(workspace, replace(state, message_counter=new_n))
    return f"msg-{new_n:04d}"


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _render(state: WorkspaceState) -> str:
    payload: dict[str, object] = {
        "schema_version": state.schema_version,
        "title": state.title,
        "created_at": _iso_z(state.created_at),
        "message_counter": state.message_counter,
        "cost": {
            "spent": state.cost.spent,
            "cap": state.cost.cap,
            "enforce": state.cost.enforce,
        },
        "digester_handle": state.digester_handle,
    }
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _iso_z(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    iso = ts.astimezone(UTC).isoformat()
    return iso[:-6] + "Z" if iso.endswith("+00:00") else iso
