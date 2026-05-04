"""Tests for `canvas.workspace.scaffold`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from quorum_conductor.canvas.workspace import (
    DEFAULT_COST_CAP_USD,
    STATE_SCHEMA_VERSION,
    ScaffoldError,
    scaffold,
)


def test_scaffold_creates_layout(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target, now=datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC))

    assert (target / "canvas.md").is_file()
    assert (target / "events.jsonl").is_file()
    assert (target / "artifacts").is_dir()
    assert (target / "registers").is_dir()
    assert (target / "registers" / "participants.md").is_file()
    assert (target / ".trash").is_dir()
    assert (target / "state.yaml").is_file()
    # Context defaults — phase-4 polish from `context-seeding.md`.
    assert (target / "context").is_dir()
    contextignore = target / "context" / ".contextignore"
    assert contextignore.is_file()
    body = contextignore.read_text(encoding="utf-8")
    assert "package-lock.json" in body
    assert ".env" in body


def test_scaffold_state_yaml_shape(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    when = datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
    scaffold(target, title="v2 architecture ideas", now=when)

    state = yaml.safe_load((target / "state.yaml").read_text(encoding="utf-8"))
    assert state["schema_version"] == STATE_SCHEMA_VERSION
    assert state["title"] == "v2 architecture ideas"
    assert state["created_at"] == "2026-05-03T10:00:00Z"
    assert state["message_counter"] == 0
    assert state["cost"] == {
        "spent": 0.0,
        "cap": DEFAULT_COST_CAP_USD,
        "enforce": True,
    }


def test_scaffold_default_title(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target, now=datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC))
    state = yaml.safe_load((target / "state.yaml").read_text(encoding="utf-8"))
    assert state["title"] == "Untitled brainstorm"


def test_scaffold_canvas_md_starts_empty(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    assert (target / "canvas.md").read_text(encoding="utf-8") == ""


def test_scaffold_participants_md_has_header_only(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    body = (target / "registers" / "participants.md").read_text(encoding="utf-8")
    assert body.startswith("# Participants")
    # Header columns are case-preserved in the file (parser lowercases when reading).
    assert "| Handle |" in body
    assert "| CLI Command |" in body
    # No data rows on a fresh scaffold — the user adds participants
    # via D10's panel.
    data_rows = [
        line for line in body.splitlines()
        if line.startswith("|") and "@" in line
    ]
    assert data_rows == []


def test_scaffold_refuses_existing_workspace(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    with pytest.raises(ScaffoldError):
        scaffold(target)


def test_scaffold_creates_parent_dirs(tmp_path: Path) -> None:
    """Target's parent doesn't have to exist beforehand."""
    target = tmp_path / "deep" / "nested" / "ws"
    scaffold(target)
    assert (target / "state.yaml").is_file()


def test_scaffold_now_defaults_to_current_utc(tmp_path: Path) -> None:
    """When `now=None`, `created_at` is roughly the current time."""
    target = tmp_path / "ws"
    before = datetime.now(UTC)
    scaffold(target)
    after = datetime.now(UTC)

    state = yaml.safe_load((target / "state.yaml").read_text(encoding="utf-8"))
    iso = state["created_at"]
    assert iso.endswith("Z")
    parsed = datetime.fromisoformat(iso[:-1] + "+00:00")
    assert before <= parsed <= after
