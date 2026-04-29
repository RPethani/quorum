"""Phase-6a tests: summarized-decisions.md auto-maintenance."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.decisions_summary import append_summary_line
from quorum_conductor.core.move_format import find_first_header

DECISION_BODY = (
    "### [DECISION] @human-rohan · 2026-04-29T15:01:12Z\n\n"
    "## Decision\n\nShip trial-only in v1.\n\n"
    "## Summary line\n\n"
    "v1 ships trial-only (14 days, then paid); free-tier decision revisited at month 6.\n\n"
    "## Rationale\n\nReversibility wins.\n\n"
    "## Spawns ADR?\n\nyes\n\n"
    "## Spawns task?\n\nno\n"
)


def test_append_summary_line_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "registers" / "summarized-decisions.md"
    header = find_first_header(DECISION_BODY)
    assert header is not None
    appended = append_summary_line(
        target, deliberation_id="0014", header=header, move_text=DECISION_BODY
    )
    assert appended is True
    body = target.read_text(encoding="utf-8")
    assert "# Summarized decisions" in body
    assert "**DECISION@human-rohan#0014**" in body
    assert "@@" not in body  # no double-@ from format
    assert "v1 ships trial-only" in body


def test_append_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "registers" / "summarized-decisions.md"
    header = find_first_header(DECISION_BODY)
    assert header is not None
    a = append_summary_line(
        target, deliberation_id="0014", header=header, move_text=DECISION_BODY
    )
    b = append_summary_line(
        target, deliberation_id="0014", header=header, move_text=DECISION_BODY
    )
    assert a is True
    assert b is False
    assert target.read_text(encoding="utf-8").count("v1 ships trial-only") == 1


def test_append_skips_non_decision_moves(tmp_path: Path) -> None:
    target = tmp_path / "registers" / "summarized-decisions.md"
    proposal = (
        "### [PROPOSAL] @x · 2026-04-29T00:00:00Z\n\n"
        "## Position\n\nBlah.\n"
    )
    header = find_first_header(proposal)
    assert header is not None
    assert (
        append_summary_line(
            target, deliberation_id="0001", header=header, move_text=proposal
        )
        is False
    )
    assert not target.is_file()


def test_append_skips_empty_summary_line(tmp_path: Path) -> None:
    target = tmp_path / "registers" / "summarized-decisions.md"
    body = (
        "### [DECISION] @x · 2026-04-29T00:00:00Z\n\n"
        "## Decision\n\nShip.\n\n"
        "## Summary line\n\n"
        "<!-- guidance: write a real summary -->\n\n"
        "## Rationale\n\nbecause.\n"
    )
    header = find_first_header(body)
    assert header is not None
    assert (
        append_summary_line(
            target, deliberation_id="0014", header=header, move_text=body
        )
        is False
    )


def test_multiple_decisions_accumulate(tmp_path: Path) -> None:
    target = tmp_path / "registers" / "summarized-decisions.md"
    h1 = find_first_header(DECISION_BODY)
    body2 = DECISION_BODY.replace("@human-rohan", "@claude-opus").replace(
        "v1 ships trial-only", "Pricing tier structure decided"
    )
    h2 = find_first_header(body2)
    assert h1 is not None and h2 is not None
    append_summary_line(target, deliberation_id="0014", header=h1, move_text=DECISION_BODY)
    append_summary_line(target, deliberation_id="0015", header=h2, move_text=body2)
    body = target.read_text(encoding="utf-8")
    assert "0014" in body
    assert "0015" in body
    assert "v1 ships trial-only" in body
    assert "Pricing tier structure" in body
