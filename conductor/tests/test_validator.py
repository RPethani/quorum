"""Full-validator (4e) tests."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.validator import (
    render_validation_feedback,
    required_sections_for,
    validate_move,
)
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace import InitOptions, init_workspace


def _ws(tmp_path: Path) -> WorkspacePaths:
    return init_workspace(InitOptions(target=tmp_path / "quorum"))


# ---------------------------------------------------------------------- #
# Section discovery from templates
# ---------------------------------------------------------------------- #


def test_required_sections_for_proposal_match_template(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    sections = required_sections_for("PROPOSAL", paths.protocol_templates)
    # The exact set is locked by protocol/templates/proposal.md.
    assert "Position" in sections
    assert "Reasoning" in sections
    assert "Assumptions" in sections
    assert "Risks I see" in sections
    assert "Alternatives I considered" in sections
    assert "Tagging" in sections


def test_required_sections_for_decision_match_template(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    sections = required_sections_for("DECISION", paths.protocol_templates)
    assert "Decision" in sections
    assert "Summary line" in sections
    assert "Rationale" in sections
    assert "Spawns ADR?" in sections
    assert "Spawns task?" in sections


# ---------------------------------------------------------------------- #
# Per-section presence
# ---------------------------------------------------------------------- #


def _proposal(*, alternatives: str = "- Permanent free tier — set aside.") -> str:
    return (
        "### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z\n\n"
        "## Position\n\nShip trial-only.\n\n"
        "## Reasoning\n\nReversibility wins.\n\n"
        "## Assumptions\n\nnone\n\n"
        "## Risks I see\n\nnone\n\n"
        f"## Alternatives I considered\n\n{alternatives}\n\n"
        "## Tagging\n\n- @gemini-pro: critique\n"
    )


def test_validate_move_happy_proposal(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _proposal(),
        expected_move_type="PROPOSAL",
        templates_dir=paths.protocol_templates,
    )
    assert v.ok, v.errors
    assert v.header is not None and v.header.move_type == "PROPOSAL"


def test_validate_move_rejects_missing_section(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    body = _proposal().replace("## Tagging\n\n- @gemini-pro: critique\n", "")
    v = validate_move(
        body, expected_move_type="PROPOSAL", templates_dir=paths.protocol_templates
    )
    assert not v.ok
    assert any("Tagging" in e for e in v.errors)


def test_validate_move_rejects_empty_alternatives(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _proposal(alternatives="  "),
        expected_move_type="PROPOSAL",
        templates_dir=paths.protocol_templates,
    )
    assert not v.ok
    assert any("Alternatives I considered" in e for e in v.errors)


# ---------------------------------------------------------------------- #
# DECISION Summary-line anti-vacuousness
# ---------------------------------------------------------------------- #


def _decision(*, summary: str = "v1 ships trial-only (14 days, then paid); free-tier decision revisited at month 6.") -> str:
    return (
        "### [DECISION] @human-rohan · 2026-04-28T15:01:12Z\n\n"
        "## Decision\n\nShip trial-only in v1.\n\n"
        f"## Summary line\n\n{summary}\n\n"
        "## Rationale\n\nReversibility argument plus compute headroom.\n\n"
        "## Path not taken\n\nPermanent free tier.\n\n"
        "## Spawns ADR?\n\nyes\n\n"
        "## Spawns task?\n\nyes\n"
    )


def test_validate_move_happy_decision(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _decision(),
        expected_move_type="DECISION",
        templates_dir=paths.protocol_templates,
    )
    assert v.ok, v.errors


def test_validate_move_rejects_short_summary(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _decision(summary="Short."),
        expected_move_type="DECISION",
        templates_dir=paths.protocol_templates,
    )
    assert not v.ok
    assert any("too short" in e for e in v.errors)


def test_validate_move_rejects_long_summary(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _decision(summary="x" * 130),
        expected_move_type="DECISION",
        templates_dir=paths.protocol_templates,
    )
    assert not v.ok
    assert any("too long" in e for e in v.errors)


def test_validate_move_rejects_vacuous_summary_patterns(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    for vacuous in ("Approved.", "decided yes", "We'll do this.", "Yes."):
        v = validate_move(
            _decision(summary=vacuous),
            expected_move_type="DECISION",
            templates_dir=paths.protocol_templates,
        )
        assert not v.ok, vacuous
        # Either the length check or the pattern check fires; both are
        # legitimate rejections.
        assert v.errors


# ---------------------------------------------------------------------- #
# EXPLANATION anti-confabulation
# ---------------------------------------------------------------------- #


def _explanation(*, sources: str = "- PROPOSAL@claude-opus#0014", gaps: str = "Nothing relevant was missing.") -> str:
    return (
        "### [EXPLANATION] @explainer · 2026-04-28T16:20:00Z → targets CLARIFY@human-rohan#0014\n\n"
        "## Explanation\n\n**General context:** RAG.\n\n**In this workspace:** see PROPOSAL@claude-opus#0014.\n\n"
        f"## Sources cited\n\n{sources}\n\n"
        f"## What I couldn't find in the workspace\n\n{gaps}\n\n"
        "## Limitations\n\nnone\n"
    )


def test_validate_move_happy_explanation(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _explanation(),
        expected_move_type="EXPLANATION",
        templates_dir=paths.protocol_templates,
    )
    assert v.ok, v.errors


def test_validate_move_rejects_explanation_without_sources(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _explanation(sources="  "),
        expected_move_type="EXPLANATION",
        templates_dir=paths.protocol_templates,
    )
    assert not v.ok
    assert any("Sources cited" in e for e in v.errors)


def test_validate_move_rejects_explanation_without_gap_acknowledgment(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    v = validate_move(
        _explanation(gaps="  "),
        expected_move_type="EXPLANATION",
        templates_dir=paths.protocol_templates,
    )
    assert not v.ok
    assert any("What I couldn't find" in e for e in v.errors)


# ---------------------------------------------------------------------- #
# Render feedback for retry
# ---------------------------------------------------------------------- #


def test_render_validation_feedback_lists_errors(tmp_path: Path) -> None:
    paths = _ws(tmp_path)
    body = _proposal().replace("## Tagging\n\n- @gemini-pro: critique\n", "")
    v = validate_move(
        body, expected_move_type="PROPOSAL", templates_dir=paths.protocol_templates
    )
    feedback = render_validation_feedback(v)
    assert "failed validation" in feedback
    assert "Tagging" in feedback
    assert "Produce the move again" in feedback


# ---------------------------------------------------------------------- #
# DROP-on-seed rule (per system-flow-stages.md open question #1)
#
# Only the seed deliberation (the one that ratifies the outcome
# manifest) is protected from DROP. Per-artifact ratification
# deliberations remain DROP-able so the user can abandon work on
# a specific artifact without abandoning the whole project.
# ---------------------------------------------------------------------- #


def _drop(targets: str = "PROPOSAL@claude-opus#0001") -> str:
    return (
        "### [DROP] @rakesh · 2026-04-30T10:00:00Z\n\n"
        f"## Targets\n\n- {targets}\n\n"
        "## Reason\n\nNo longer relevant.\n\n"
        "## Disposition of partial work\n\nKeep the proposal as-is.\n"
    )


def test_drop_on_seed_deliberation_is_rejected(tmp_path: Path) -> None:
    """DROP is forbidden on the seed manifest deliberation. Without a
    ratified manifest there's no plan to work against, so the
    workspace would be meaningless. See
    `docs-specs/system-flow-stages.md` open question #1.
    """
    paths = _ws(tmp_path)
    v = validate_move(
        _drop(),
        expected_move_type="DROP",
        templates_dir=paths.protocol_templates,
        deliberation_ratifies="outcome-manifest.md",
    )
    assert not v.ok
    assert any("seed deliberation" in e for e in v.errors), v.errors
    assert any("DECISION" in e and "OVERRIDE" in e for e in v.errors), v.errors


def test_drop_on_artifact_ratification_is_allowed(tmp_path: Path) -> None:
    """DROP IS allowed on per-artifact ratification deliberations.
    The user can decide they no longer want to produce a specific
    artifact, even mid-project. Only the seed (which ratifies the
    manifest itself) is protected."""
    paths = _ws(tmp_path)
    v = validate_move(
        _drop(),
        expected_move_type="DROP",
        templates_dir=paths.protocol_templates,
        deliberation_ratifies="recommendation.md",
    )
    assert v.ok, v.errors


def test_drop_on_regular_deliberation_is_allowed(tmp_path: Path) -> None:
    """DROP is fine on a regular deliberation (no `ratifies:`)."""
    paths = _ws(tmp_path)
    v = validate_move(
        _drop(),
        expected_move_type="DROP",
        templates_dir=paths.protocol_templates,
        deliberation_ratifies=None,
    )
    assert v.ok, v.errors


def test_drop_check_does_not_fire_for_decision_on_seed(tmp_path: Path) -> None:
    """Sanity: only DROP is rejected on the seed. DECISION is the
    happy path."""
    paths = _ws(tmp_path)
    decision = (
        "### [DECISION] @rakesh · 2026-04-30T10:00:00Z\n\n"
        "## Decision\n\nManifest ratified.\n\n"
        "## Summary line\n\n"
        "Adopt the strategic-decision template; we will work three artifacts.\n\n"
        "## Rationale\n\nMatches the problem shape: one big call, options known.\n\n"
        "## Path not taken\n\nNo template; freeform manifest. Set aside as risky.\n\n"
        "## Spawns ADR?\n\nno\n\n"
        "## Spawns task?\n\nno\n"
    )
    v = validate_move(
        decision,
        expected_move_type="DECISION",
        templates_dir=paths.protocol_templates,
        deliberation_ratifies="outcome-manifest.md",
    )
    assert v.ok, v.errors
