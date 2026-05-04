"""Tests for `@mention` extraction.

Behaviour covered:
- preserves document order, deduplicates
- skips mentions inside fenced and inline code
- ignores email addresses (preceded by an alphanumeric)
- handles names with hyphens and dots
"""

from __future__ import annotations

from quorum_conductor.canvas.mentions import extract_mentions


def test_no_mentions_returns_empty():
    assert extract_mentions("Plain message with no handles.") == []


def test_single_mention_extracted():
    assert extract_mentions("@claude-opus what do you think?") == ["@claude-opus"]


def test_multiple_mentions_in_order():
    body = "@gemini and @claude-opus, can you both weigh in?"
    assert extract_mentions(body) == ["@gemini", "@claude-opus"]


def test_duplicates_collapsed_first_occurrence_wins():
    body = "@claude what about X? Earlier @claude said Y."
    assert extract_mentions(body) == ["@claude"]


def test_handle_with_dots_and_hyphens():
    body = "ping @claude-opus.4 and @gemini-pro."
    assert extract_mentions(body) == ["@claude-opus.4", "@gemini-pro"]


def test_email_addresses_are_not_mentions():
    """`foo@bar.com` looks superficially like a mention — must not match."""
    body = "Email me at rakesh@example.com or ping @claude."
    assert extract_mentions(body) == ["@claude"]


def test_fenced_code_block_skipped():
    body = (
        "Quoting earlier:\n"
        "\n"
        "```\n"
        "@claude-opus said something\n"
        "```\n"
        "\n"
        "Now @gemini, your turn."
    )
    assert extract_mentions(body) == ["@gemini"]


def test_artifact_emit_block_skipped():
    body = (
        "Capturing this:\n"
        "\n"
        "```artifact:notes.md\n"
        "@claude-opus is the lead\n"
        "```\n"
        "\n"
        "@codex please verify."
    )
    assert extract_mentions(body) == ["@codex"]


def test_inline_code_skipped():
    body = "Earlier I said `@claude-opus is the lead`. Now @gemini please respond."
    assert extract_mentions(body) == ["@gemini"]


def test_mention_at_line_start():
    assert extract_mentions("@claude\nfollow-up question.") == ["@claude"]


def test_mention_with_punctuation():
    body = "(@claude), [@gemini], <@codex>: thoughts?"
    assert extract_mentions(body) == ["@claude", "@gemini", "@codex"]
