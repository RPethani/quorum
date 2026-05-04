"""Tests for `canvas.state` — load, save, next_message_id."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quorum_conductor.canvas.state import (
    CostState,
    StateError,
    load_state,
    next_message_id,
    save_state,
)
from quorum_conductor.canvas.workspace import scaffold


def _setup(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    scaffold(ws, title="test", now=datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC))
    return ws


def test_load_after_scaffold(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    state = load_state(ws)
    assert state.title == "test"
    assert state.created_at == datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
    assert state.message_counter == 0
    assert state.cost == CostState(spent=0.0, cap=50.0, enforce=True)


def test_load_missing_state_raises(tmp_path: Path) -> None:
    with pytest.raises(StateError):
        load_state(tmp_path / "no-such-ws")


def test_save_round_trip(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    original = load_state(ws)
    bumped = replace(
        original,
        message_counter=42,
        cost=CostState(spent=12.34, cap=100.0, enforce=False),
    )
    save_state(ws, bumped)
    assert load_state(ws) == bumped


def test_next_message_id_starts_at_one(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    assert next_message_id(ws) == "msg-0001"


def test_next_message_id_monotonic(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    ids = [next_message_id(ws) for _ in range(5)]
    assert ids == ["msg-0001", "msg-0002", "msg-0003", "msg-0004", "msg-0005"]


def test_next_message_id_persists_across_loads(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    next_message_id(ws)
    next_message_id(ws)
    # New "process" — fresh load.
    assert next_message_id(ws) == "msg-0003"
    assert load_state(ws).message_counter == 3


def test_save_is_atomic_no_temp_file_left(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    save_state(ws, replace(load_state(ws), message_counter=7))
    leftovers = [p.name for p in ws.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_load_handles_malformed_cost_block_gracefully(tmp_path: Path) -> None:
    """If `cost:` is missing or partial, defaults fill in cleanly."""
    ws = _setup(tmp_path)
    # Hand-edit state.yaml to remove the cost block.
    sp = ws / "state.yaml"
    sp.write_text(
        "schema_version: 1\n"
        "title: t\n"
        "created_at: '2026-05-03T10:00:00Z'\n"
        "message_counter: 0\n",
        encoding="utf-8",
    )
    state = load_state(ws)
    assert state.cost == CostState()  # all defaults
