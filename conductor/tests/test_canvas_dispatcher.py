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


def test_no_mention_routes_to_last_mentioned_agent(tmp_path: Path) -> None:
    """Quick follow-ups (no @mention) route to whoever the same author
    last @-mentioned, so 'thanks' / 'say more' don't dead-end."""
    ws = _ws(tmp_path)
    invocations: list[str] = []

    def invoke(req: InvocationRequest) -> InvocationResult:
        invocations.append(req.handle)
        return InvocationResult(reply="ok")

    # Establish a prior mention of @gemini.
    dispatch(ws, "@gemini what do you think?", invoke=invoke, now=_fixed_now)
    # User now follows up without mentioning anyone.
    result = dispatch(ws, "thanks", invoke=invoke, now=_fixed_now)

    assert invocations == ["@gemini", "@gemini"]
    assert len(result.turns) == 1
    assert result.turns[0].handle == "@gemini"


def test_no_mention_picks_last_mention_in_document_order(tmp_path: Path) -> None:
    """When the prior message had multiple mentions, the *last* one in
    document order wins — that's the agent the user spoke to most
    recently."""
    ws = _ws(tmp_path)
    invocations: list[str] = []

    def invoke(req: InvocationRequest) -> InvocationResult:
        invocations.append(req.handle)
        return InvocationResult(reply="ok")

    dispatch(ws, "@claude-opus and @gemini compare notes", invoke=invoke, now=_fixed_now)
    result = dispatch(ws, "say more", invoke=invoke, now=_fixed_now)

    # First dispatch ran both; follow-up routes only to @gemini.
    assert invocations == ["@claude-opus", "@gemini", "@gemini"]
    assert [t.handle for t in result.turns] == ["@gemini"]


def test_no_mention_with_no_history_is_a_no_op(tmp_path: Path) -> None:
    """If the user hasn't mentioned anyone yet, an unaddressed message
    just appends to the canvas — no implicit target to fall back to."""
    ws = _ws(tmp_path)

    def never_called(_req: InvocationRequest) -> InvocationResult:
        raise AssertionError("invoke should not run with no prior mentions")

    result = dispatch(ws, "hello world", invoke=never_called, now=_fixed_now)
    assert result.turns == []


def test_no_mention_ignores_other_authors_history(tmp_path: Path) -> None:
    """The fallback looks at the *same* author's history. An agent's
    message that happens to contain `@x` shouldn't redirect a different
    author's follow-up."""
    ws = _ws(tmp_path)

    def replies_with_mention(_req: InvocationRequest) -> InvocationResult:
        # Agent reply mentions another agent; this should NOT count as
        # a "user mentioned" for the routing fallback.
        return InvocationResult(reply="cc @gemini you might want to weigh in")

    dispatch(ws, "@claude-opus draft something", invoke=replies_with_mention, now=_fixed_now)

    invocations: list[str] = []

    def capture(req: InvocationRequest) -> InvocationResult:
        invocations.append(req.handle)
        return InvocationResult(reply="ok")

    dispatch(ws, "thanks", invoke=capture, now=_fixed_now)

    # Routes to @claude-opus (the user's last mention), NOT @gemini
    # (which appeared inside the agent's reply body).
    assert invocations == ["@claude-opus"]


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
