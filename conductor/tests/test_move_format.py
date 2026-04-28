"""Header-line and minimal-validator tests."""

from __future__ import annotations

from quorum_conductor.core.move_format import (
    KNOWN_MOVE_TYPES,
    find_first_header,
    is_known_move_type,
    parse_header,
    validate_minimal,
)


def test_parse_header_basic() -> None:
    h = parse_header("### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z")
    assert h is not None
    assert h.move_type == "PROPOSAL"
    assert h.author == "@claude-opus"
    assert h.timestamp == "2026-04-28T14:32:18Z"
    assert h.targets is None


def test_parse_header_with_targets() -> None:
    h = parse_header(
        "### [CRITIQUE] @gemini-pro · 2026-04-28T14:34:02Z → targets PROPOSAL@claude-opus#0014"
    )
    assert h is not None
    assert h.move_type == "CRITIQUE"
    assert h.targets == "PROPOSAL@claude-opus#0014"


def test_parse_header_rejects_garbage() -> None:
    assert parse_header("### proposal by claude") is None
    assert parse_header("PROPOSAL @claude · 2026-04-28") is None


def test_known_move_type_set_matches_protocol() -> None:
    # Sanity: every move template we ship corresponds to a known type.
    expected = {
        "PROPOSAL", "CRITIQUE", "QUESTION", "ANSWER", "SYNTHESIS",
        "DECISION", "DEPUTY_DECISION", "REVISION", "ARTIFACT_REVISION",
        "ABSTAIN", "EXPLANATION", "INTERJECTION", "OVERRIDE", "REOPEN",
        "DROP", "STEER", "CLARIFY",
    }
    assert expected == KNOWN_MOVE_TYPES


def test_find_first_header_skips_prelude() -> None:
    text = "Some preamble.\n\nMore preamble.\n\n### [DECISION] @human-rohan · 2026-04-28T15:01:12Z\n"
    h = find_first_header(text)
    assert h is not None
    assert h.move_type == "DECISION"


def test_validate_minimal_happy_path() -> None:
    text = "### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z\n\n## Position\n\nShip trial-only.\n"
    v = validate_minimal(text, expected_move_type="PROPOSAL")
    assert v.ok
    assert v.errors == []
    assert v.header is not None and v.header.move_type == "PROPOSAL"


def test_validate_minimal_rejects_missing_header() -> None:
    v = validate_minimal("just some prose, no header")
    assert not v.ok
    assert v.header is None
    assert any("no canonical move header" in e for e in v.errors)


def test_validate_minimal_rejects_unknown_type() -> None:
    v = validate_minimal("### [INVENTED] @x · 2026-04-28T00:00:00Z\n\nbody")
    assert not v.ok
    assert any("unknown move type" in e for e in v.errors)


def test_validate_minimal_rejects_wrong_expected_type() -> None:
    v = validate_minimal(
        "### [PROPOSAL] @x · 2026-04-28T00:00:00Z\n\nbody",
        expected_move_type="CRITIQUE",
    )
    assert not v.ok
    assert any("expected move type" in e for e in v.errors)


def test_validate_minimal_rejects_empty() -> None:
    v = validate_minimal("")
    assert not v.ok
    assert v.errors == ["empty output"]


def test_is_known_move_type() -> None:
    assert is_known_move_type("PROPOSAL")
    assert not is_known_move_type("UNRELATED")
