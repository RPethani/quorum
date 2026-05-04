"""Scaffold a fresh canvas workspace on disk.

Creates the minimal folder layout described in `docs-specs/canvas-
redesign.md` S1::

    my-brainstorm/
      state.yaml
      canvas.md            (empty)
      events.jsonl         (empty)
      artifacts/
      registers/participants.md
      .trash/

Deliberately simpler than the existing protocol scaffolder
(`workspace/scaffolding.py`) — no problem-statement, no manifest
templates, no routing defaults, no protocol copies. The canvas
needs none of those.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

# Schema version for `state.yaml` written by this scaffolder. Bump
# when the file shape changes incompatibly.
STATE_SCHEMA_VERSION = 1

# Default cost ceiling, mirrors current Quorum's default. Adjustable
# from the Settings UI (D16 / D17).
DEFAULT_COST_CAP_USD = 50.0

# Header for `registers/participants.md`. Mirrors the format the
# core `participants.parse_participants` helper expects so we can
# reuse the existing parser without a fork.
_PARTICIPANTS_HEADER = """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota (daily/per-deliberation) | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
"""


class ScaffoldError(RuntimeError):
    """Raised when the target directory is already a workspace."""


def scaffold(
    path: Path,
    *,
    title: str = "Untitled brainstorm",
    now: datetime | None = None,
) -> None:
    """Create a fresh canvas workspace at *path*.

    Refuses to run if ``state.yaml`` already exists, to avoid
    silently clobbering an existing workspace.

    Parameters
    ----------
    path:
        Target directory. Created if it doesn't exist.
    title:
        Human-readable workspace title (D9). Defaults to
        ``"Untitled brainstorm"``.
    now:
        Override the timestamp written to ``state.yaml`` — handy
        for tests. Defaults to the current UTC time.
    """
    state_path = path / "state.yaml"
    if state_path.exists():
        raise ScaffoldError(
            f"Refusing to scaffold: {state_path} already exists. "
            "This directory is already a canvas workspace."
        )

    path.mkdir(parents=True, exist_ok=True)
    (path / "artifacts").mkdir(exist_ok=True)
    (path / "registers").mkdir(exist_ok=True)
    (path / ".trash").mkdir(exist_ok=True)

    (path / "canvas.md").touch()
    (path / "events.jsonl").touch()
    (path / "registers" / "participants.md").write_text(
        _PARTICIPANTS_HEADER, encoding="utf-8"
    )
    state_path.write_text(_render_state(title, now or datetime.now(UTC)), encoding="utf-8")


def _render_state(title: str, created_at: datetime) -> str:
    """Render `state.yaml` as a stable, deterministically ordered YAML doc."""
    body: dict[str, object] = {
        "schema_version": STATE_SCHEMA_VERSION,
        "title": title,
        "created_at": _iso_z(created_at),
        "message_counter": 0,
        "cost": {
            "spent": 0.0,
            "cap": DEFAULT_COST_CAP_USD,
            "enforce": True,
        },
    }
    return yaml.safe_dump(body, sort_keys=False, default_flow_style=False)


def _iso_z(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    iso = ts.astimezone(UTC).isoformat()
    return iso[:-6] + "Z" if iso.endswith("+00:00") else iso
