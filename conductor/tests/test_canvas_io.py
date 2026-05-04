"""Round-trip and edge-case tests for `canvas.md` I/O.

The parser must survive any markdown we'd realistically see in an
agent's reply: headings, fenced code blocks, embedded HTML
comments other than the message fences, and so on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quorum_conductor.canvas import Message, append_message, parse_canvas


def _msg(
    msg_id: str,
    author: str,
    body: str,
    ts: datetime | None = None,
) -> Message:
    return Message(
        id=msg_id,
        author=author,
        timestamp=ts or datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC),
        body=body,
    )


def test_parse_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert parse_canvas(tmp_path / "canvas.md") == []


def test_parse_empty_file_returns_empty_list(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    p.write_text("", encoding="utf-8")
    assert parse_canvas(p) == []
    p.write_text("   \n\n", encoding="utf-8")
    assert parse_canvas(p) == []


def test_round_trip_single_message(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    msg = _msg("msg-0001", "@rakesh", "Let's brainstorm v2 architecture.")
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed == msg


def test_round_trip_multiple_messages_in_order(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    a = _msg("msg-0001", "@rakesh", "First.")
    b = _msg("msg-0002", "@claude-opus", "Reply.")
    c = _msg("msg-0003", "@gemini", "Another.")
    append_message(p, a)
    append_message(p, b)
    append_message(p, c)
    assert parse_canvas(p) == [a, b, c]


def test_body_can_contain_markdown_headings(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    body = (
        "Sure — here's my take:\n"
        "\n"
        "## My take\n"
        "\n"
        "- Heading inside a body must not break the parser.\n"
        "\n"
        "## Another section\n"
        "\n"
        "More body."
    )
    msg = _msg("msg-0001", "@claude-opus", body)
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.body == body


def test_body_can_contain_artifact_emit_block(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    body = (
        "Capturing this:\n"
        "\n"
        "```artifact:requirements.md\n"
        "# Requirements\n"
        "- one\n"
        "- two\n"
        "```\n"
        "\n"
        "Anything else?"
    )
    msg = _msg("msg-0001", "@claude-opus", body)
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.body == body


def test_body_can_contain_html_comments_other_than_fences(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    body = "Some text <!-- aside --> more text <!-- another note -->."
    msg = _msg("msg-0001", "@rakesh", body)
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.body == body


def test_handles_with_hyphens_and_dots_parse(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    msg = _msg("msg-0001", "@claude-opus.4", "ok")
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.author == "@claude-opus.4"


def test_timestamp_emitted_with_z_suffix(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    append_message(p, _msg("msg-0001", "@rakesh", "x"))
    text = p.read_text(encoding="utf-8")
    assert "2026-05-03T10:00:00Z" in text
    # And no `+00:00` form leaks into the file.
    assert "+00:00" not in text


def test_timestamp_round_trip_normalises_naive_to_utc(tmp_path: Path) -> None:
    p = tmp_path / "canvas.md"
    naive = datetime(2026, 5, 3, 10, 0, 0)  # no tzinfo
    msg = _msg("msg-0001", "@rakesh", "x", ts=naive)
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.timestamp == datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)


def test_blank_line_separates_blocks_in_file(tmp_path: Path) -> None:
    """Cosmetic check: appended blocks get a blank line between them."""
    p = tmp_path / "canvas.md"
    append_message(p, _msg("msg-0001", "@rakesh", "first"))
    append_message(p, _msg("msg-0002", "@claude", "second"))
    text = p.read_text(encoding="utf-8")
    # Two msg blocks + blank line between them.
    assert text.count("<!-- msg:") == 2
    assert "\n\n<!-- msg:msg-0002 -->" in text


def test_messages_with_no_body_round_trip(tmp_path: Path) -> None:
    """Edge case: an agent might emit just a heading and nothing else."""
    p = tmp_path / "canvas.md"
    msg = _msg("msg-0001", "@claude", "")
    append_message(p, msg)
    [parsed] = parse_canvas(p)
    assert parsed.body == ""
