"""Tests for the canvas dispatcher.

The dispatcher is driven through a stub `invoke` callable so we
exercise routing, artifact handling, and error propagation without
spawning subprocesses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quorum_conductor.canvas.dispatcher import (
    SYSTEM_HANDLE,
    InvocationRequest,
    InvocationResult,
    dispatch,
)
from quorum_conductor.canvas.io import parse_canvas
from quorum_conductor.canvas.workspace import scaffold


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    scaffold(ws, now=datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC))
    return ws


def _fixed_now() -> datetime:
    return datetime(2026, 5, 3, 10, 30, 0, tzinfo=UTC)


def test_no_mentions_appends_user_message_only(tmp_path: Path) -> None:
    ws = _ws(tmp_path)

    def never_called(_req: InvocationRequest) -> InvocationResult:
        raise AssertionError("invoke should not be called when no @mentions")

    result = dispatch(ws, "Just a thought.", invoke=never_called, now=_fixed_now)

    assert result.user_message.body == "Just a thought."
    assert result.turns == []
    [stored] = parse_canvas(ws / "canvas.md")
    assert stored == result.user_message


def test_single_mention_invokes_agent_and_appends_reply(tmp_path: Path) -> None:
    ws = _ws(tmp_path)

    def invoke(req: InvocationRequest) -> InvocationResult:
        assert req.handle == "@claude-opus"
        assert req.workspace == ws
        return InvocationResult(reply="Sure — what's the question?")

    result = dispatch(
        ws, "@claude-opus what about routing?", invoke=invoke, now=_fixed_now
    )

    assert len(result.turns) == 1
    assert result.turns[0].handle == "@claude-opus"
    assert result.turns[0].message is not None
    assert result.turns[0].message.body == "Sure — what's the question?"
    assert result.turns[0].error is None

    msgs = parse_canvas(ws / "canvas.md")
    assert [m.author for m in msgs] == ["@rakesh", "@claude-opus"]


def test_multiple_mentions_invoked_in_order(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    seen: list[str] = []

    def invoke(req: InvocationRequest) -> InvocationResult:
        seen.append(req.handle)
        return InvocationResult(reply=f"reply from {req.handle}")

    dispatch(
        ws,
        "@gemini and @claude-opus, weigh in.",
        invoke=invoke,
        now=_fixed_now,
    )

    assert seen == ["@gemini", "@claude-opus"]
    msgs = parse_canvas(ws / "canvas.md")
    assert [m.author for m in msgs] == [
        "@rakesh",
        "@gemini",
        "@claude-opus",
    ]


def test_artifact_emit_is_extracted_and_written(tmp_path: Path) -> None:
    ws = _ws(tmp_path)

    def invoke(_req: InvocationRequest) -> InvocationResult:
        return InvocationResult(
            reply=(
                "Capturing this:\n"
                "\n"
                "```artifact:requirements.md\n"
                "# Reqs\n"
                "- one\n"
                "```\n"
                "\n"
                "Done."
            )
        )

    result = dispatch(
        ws,
        "@claude-opus please track this",
        invoke=invoke,
        now=_fixed_now,
    )

    [turn] = result.turns
    assert len(turn.artifacts) == 1
    assert turn.artifacts[0].filename == "requirements.md"

    # File on disk has the artifact body.
    written = (ws / "artifacts" / "requirements.md").read_text(encoding="utf-8")
    assert written == "# Reqs\n- one\n"

    # Stored agent message has the indicator, not the raw fenced block.
    msgs = parse_canvas(ws / "canvas.md")
    assert "📝 updated `requirements.md`" in msgs[1].body
    assert "```artifact:" not in msgs[1].body


def test_invocation_failure_appends_system_error_and_continues(tmp_path: Path) -> None:
    ws = _ws(tmp_path)

    def invoke(req: InvocationRequest) -> InvocationResult:
        if req.handle == "@gemini":
            return InvocationResult(error="rate-limited")
        return InvocationResult(reply=f"hi from {req.handle}")

    result = dispatch(
        ws,
        "@gemini and @claude-opus please respond.",
        invoke=invoke,
        now=_fixed_now,
    )

    assert len(result.turns) == 2
    assert result.turns[0].error == "rate-limited"
    assert result.turns[0].handle == "@gemini"
    assert result.turns[1].error is None
    assert result.turns[1].handle == "@claude-opus"

    msgs = parse_canvas(ws / "canvas.md")
    assert [m.author for m in msgs] == [
        "@rakesh",
        SYSTEM_HANDLE,
        "@claude-opus",
    ]
    assert "couldn't respond" in msgs[1].body
    assert "rate-limited" in msgs[1].body


def test_mentions_inside_code_blocks_do_not_dispatch(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    called_with: list[str] = []

    def invoke(req: InvocationRequest) -> InvocationResult:
        called_with.append(req.handle)
        return InvocationResult(reply="ok")

    dispatch(
        ws,
        "Earlier I said `@claude-opus is the lead`. Now @gemini, your turn.",
        invoke=invoke,
        now=_fixed_now,
    )

    assert called_with == ["@gemini"]


def test_user_message_id_passed_through_for_retry(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    captured: list[str] = []

    def invoke(req: InvocationRequest) -> InvocationResult:
        captured.append(req.user_message_id)
        return InvocationResult(reply="ok")

    result = dispatch(
        ws, "@claude-opus please respond.", invoke=invoke, now=_fixed_now
    )

    assert captured == [result.user_message.id]
