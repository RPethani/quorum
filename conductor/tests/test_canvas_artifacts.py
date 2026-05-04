"""Tests for `canvas.artifacts.extract_artifacts`."""

from __future__ import annotations

from quorum_conductor.canvas.artifacts import (
    ArtifactEmit,
    extract_artifacts,
)


def test_no_blocks_returns_reply_unchanged():
    reply = "Just a plain message with no artifacts."
    out = extract_artifacts(reply)
    assert out.cleaned == reply
    assert out.artifacts == []


def test_single_block_extracted_and_replaced():
    reply = (
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
    out = extract_artifacts(reply)
    assert out.artifacts == [
        ArtifactEmit(filename="requirements.md", body="# Requirements\n- one\n- two")
    ]
    assert "📝 updated `requirements.md`" in out.cleaned
    # Original block body is gone from the cleaned reply.
    assert "# Requirements" not in out.cleaned
    assert "```artifact:" not in out.cleaned


def test_multiple_blocks_in_one_reply():
    reply = (
        "Two updates:\n"
        "\n"
        "```artifact:requirements.md\n"
        "Reqs\n"
        "```\n"
        "\n"
        "Then:\n"
        "\n"
        "```artifact:implementation.md\n"
        "Impl\n"
        "```\n"
        "\n"
        "Done."
    )
    out = extract_artifacts(reply)
    assert [a.filename for a in out.artifacts] == [
        "requirements.md",
        "implementation.md",
    ]
    assert out.artifacts[0].body == "Reqs"
    assert out.artifacts[1].body == "Impl"
    assert out.cleaned.count("📝 updated") == 2


def test_nested_path_filenames():
    reply = (
        "```artifact:specs/api.md\n"
        "# API\n"
        "```"
    )
    out = extract_artifacts(reply)
    assert out.artifacts == [ArtifactEmit(filename="specs/api.md", body="# API")]


def test_block_body_can_contain_other_fenced_code():
    """The artifact body itself may contain fenced ```python``` blocks."""
    reply = (
        "```artifact:notes.md\n"
        "Here's a snippet:\n"
        "\n"
        "    def hello():\n"
        "        pass\n"
        "\n"
        "End.\n"
        "```"
    )
    out = extract_artifacts(reply)
    assert len(out.artifacts) == 1
    assert "def hello()" in out.artifacts[0].body


def test_inline_text_around_block_preserved():
    reply = "Before block.\n\n```artifact:x.md\nbody\n```\n\nAfter block."
    out = extract_artifacts(reply)
    assert out.cleaned.startswith("Before block.")
    assert out.cleaned.endswith("After block.")
    assert "📝 updated `x.md`" in out.cleaned


def test_empty_artifact_body():
    """Edge case: agent emits an empty artifact (truncate-to-zero)."""
    reply = "```artifact:empty.md\n```"
    out = extract_artifacts(reply)
    assert out.artifacts == [ArtifactEmit(filename="empty.md", body="")]


def test_artifact_block_with_whitespace_after_lang_tag():
    """A trailing space after `artifact:filename` shouldn't break the parser."""
    reply = "```artifact:notes.md  \nbody\n```"
    out = extract_artifacts(reply)
    assert out.artifacts == [ArtifactEmit(filename="notes.md", body="body")]
