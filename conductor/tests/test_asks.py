"""Tests for `workspace/asks.py` — the Ask data model and storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace.asks import (
    AskError,
    AskOption,
    close_ask,
    create_ask,
    find_open_ask_for_move,
    get_ask,
    list_asks,
    list_open_asks,
    mark_answered,
    next_ask_id,
    validate_answer,
)


def _paths(tmp_path: Path) -> WorkspacePaths:
    (tmp_path / "state.yaml").write_text("schema_version: '0.1'\n", encoding="utf-8")
    return WorkspacePaths(root=tmp_path)


def test_create_ask_persists_and_assigns_id(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ask = create_ask(
        paths,
        question="Pick criteria?",
        why="Two agents disagree.",
        shape="pick_one",
        source_deliberation="0002",
        source_move_id="claude-opus@2026-04-30T00:00:00Z",
        target_move_type="DECISION",
        options=[
            AskOption(value="a", label="Option A", summary="first"),
            AskOption(value="b", label="Option B"),
        ],
    )
    assert ask.id == "ask-0001"
    on_disk = get_ask(paths, ask.id)
    assert on_disk is not None
    assert on_disk.question == "Pick criteria?"
    assert [o.value for o in on_disk.options] == ["a", "b"]


def test_next_ask_id_increments(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    assert next_ask_id(paths) == "ask-0002"


def test_pick_one_requires_options(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.raises(AskError):
        create_ask(
            paths,
            question="?",
            why="",
            shape="pick_one",
            source_deliberation="0002",
            source_move_id="m1",
            target_move_type="DECISION",
        )


def test_list_open_skips_answered(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m2",
        target_move_type="ANSWER",
    )
    mark_answered(paths, a.id, answer={"text": "done"})
    open_ids = [x.id for x in list_open_asks(paths)]
    assert a.id not in open_ids
    assert len(list_asks(paths)) == 2


def test_mark_answered_is_idempotent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    first = mark_answered(paths, a.id, answer={"text": "first"})
    second = mark_answered(paths, a.id, answer={"text": "second"})
    assert first.answered_at == second.answered_at
    assert second.answer == {"text": "first"}


def test_close_ask_invalidates(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    close_ask(paths, a.id, reason="superseded by OVERRIDE")
    again = get_ask(paths, a.id)
    assert again is not None
    assert again.status == "closed"
    assert again.closed_reason == "superseded by OVERRIDE"


def test_find_open_ask_for_move(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m-target",
        target_move_type="ANSWER",
    )
    found = find_open_ask_for_move(paths, source_move_id="m-target")
    assert found is not None and found.id == a.id
    assert find_open_ask_for_move(paths, source_move_id="other") is None


def test_validate_confirm(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="ok?",
        why="",
        shape="confirm",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    validate_answer(a, {"value": "yes"})
    validate_answer(a, {"value": "no"})
    with pytest.raises(AskError):
        validate_answer(a, {"value": "maybe"})


def test_validate_pick_one_with_custom_escape(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="pick",
        why="",
        shape="pick_one",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="DECISION",
        options=[AskOption(value="a", label="A"), AskOption(value="b", label="B")],
    )
    validate_answer(a, {"value": "a"})
    validate_answer(a, {"value": "__custom__", "text": "neither"})
    with pytest.raises(AskError):
        validate_answer(a, {"value": "c"})
    with pytest.raises(AskError):
        validate_answer(a, {"value": "__custom__", "text": ""})


def test_validate_pick_any_min_max(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="any",
        why="",
        shape="pick_any",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="DECISION",
        options=[AskOption(value="x", label="X"), AskOption(value="y", label="Y"), AskOption(value="z", label="Z")],
        min_select=1,
        max_select=2,
    )
    validate_answer(a, {"values": ["x"]})
    validate_answer(a, {"values": ["x", "y"]})
    with pytest.raises(AskError):
        validate_answer(a, {"values": []})
    with pytest.raises(AskError):
        validate_answer(a, {"values": ["x", "y", "z"]})
    with pytest.raises(AskError):
        validate_answer(a, {"values": ["x", "x"]})


def test_validate_write_requires_text(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    validate_answer(a, {"text": "hi"})
    with pytest.raises(AskError):
        validate_answer(a, {"text": " "})


def test_round_trip_via_disk(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    a = create_ask(
        paths,
        question="?",
        why="reason",
        shape="pick_one",
        source_deliberation="0002",
        source_move_id="m1",
        target_move_type="DECISION",
        options=[
            AskOption(value="a", label="A", summary="s", expand="e"),
            AskOption(value="b", label="B"),
        ],
    )
    fresh = get_ask(paths, a.id)
    assert fresh is not None
    assert fresh.options[0].summary == "s"
    assert fresh.options[0].expand == "e"
    assert fresh.options[1].summary == ""
