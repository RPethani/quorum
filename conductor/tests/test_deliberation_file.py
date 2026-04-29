"""Tests for `workspace/deliberation_file.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.workspace.deliberation_file import (
    AppendError,
    append_move,
    update_inboxes_from_move,
)


def _seed(path: Path, contributions: str = "") -> None:
    path.write_text(
        "---\n"
        'id: "0001"\n'
        "title: test\n"
        "status: OPEN\n"
        "---\n\n"
        "## Question\n\nWhat?\n\n"
        f"## Contributions\n{contributions}\n"
        "## Open Questions\n\n"
        "## Decision\n",
        encoding="utf-8",
    )


def test_append_move_inserts_under_contributions(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib)
    move = "### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z\n\n## Position\n\nShip trial-only.\n"
    append_move(delib, move)
    body = delib.read_text(encoding="utf-8")
    # The move must appear AFTER `## Contributions` and BEFORE `## Open Questions`.
    contrib_idx = body.index("## Contributions")
    next_h2_idx = body.index("## Open Questions")
    move_idx = body.index("[PROPOSAL]")
    assert contrib_idx < move_idx < next_h2_idx


def test_append_move_preserves_existing_moves(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib, contributions="\n### [PROPOSAL] @claude-opus · 2026-04-28T14:00:00Z\n\nFirst.\n")
    second = "### [CRITIQUE] @gemini-pro · 2026-04-28T14:30:00Z\n\nObjection.\n"
    append_move(delib, second)
    body = delib.read_text(encoding="utf-8")
    assert body.index("First.") < body.index("Objection.")


def test_append_move_raises_when_no_contributions_heading(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    delib.write_text("# no contributions section here\n", encoding="utf-8")
    with pytest.raises(AppendError):
        append_move(delib, "### [PROPOSAL] @x · 2026-04-28T00:00:00Z\n\nbody")


def test_decision_flips_status_to_decided(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib)
    decision = (
        "### [DECISION] @human-rohan · 2026-04-29T10:00:00Z\n\n"
        "## Decision\n\nShip the trial-only path."
    )
    append_move(delib, decision)
    body = delib.read_text(encoding="utf-8")
    assert "status: DECIDED" in body
    assert "status: OPEN" not in body


def test_override_also_flips_to_decided(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib)
    override = (
        "### [OVERRIDE] @human-rohan · 2026-04-29T10:00:00Z\n\n"
        "## Decision\n\nUnilateral end."
    )
    append_move(delib, override)
    assert "status: DECIDED" in delib.read_text(encoding="utf-8")


def test_drop_flips_to_abandoned(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib)
    drop = (
        "### [DROP] @human-rohan · 2026-04-29T10:00:00Z\n\n## Reason\n\nNo longer relevant."
    )
    append_move(delib, drop)
    assert "status: ABANDONED" in delib.read_text(encoding="utf-8")


def test_non_terminal_move_leaves_status_alone(tmp_path: Path) -> None:
    delib = tmp_path / "0001-test.md"
    _seed(delib)
    proposal = (
        "### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z\n\n"
        "## Position\n\nShip trial-only."
    )
    append_move(delib, proposal)
    assert "status: OPEN" in delib.read_text(encoding="utf-8")


def test_update_inboxes_tags_other_handles_only(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    move = (
        "### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z\n\n"
        "## Tagging\n- @gemini-pro: critique\n- @human-rohan: decider\n"
    )
    notified = update_inboxes_from_move(
        move,
        inbox_dir=inbox,
        deliberation_id="0001",
        move_type="PROPOSAL",
        author="@claude-opus",
    )
    assert notified == ["@gemini-pro", "@human-rohan"]
    assert (inbox / "@gemini-pro.md").is_file()
    assert (inbox / "@human-rohan.md").is_file()
    body = (inbox / "@gemini-pro.md").read_text(encoding="utf-8")
    assert "PROPOSAL in #0001" in body
    assert "@claude-opus" in body


def test_update_inboxes_dedupes_repeats(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    move = (
        "### [SYNTHESIS] @codex-gpt5 · 2026-04-28T15:00:00Z\n\n"
        "## Reconciles\n- PROPOSAL@claude-opus#0001\n- CRITIQUE@gemini-pro#0001\n"
        "@gemini-pro mentioned twice but should only appear once.\n"
    )
    notified = update_inboxes_from_move(
        move,
        inbox_dir=inbox,
        deliberation_id="0001",
        move_type="SYNTHESIS",
        author="@codex-gpt5",
    )
    assert notified.count("@gemini-pro") == 1
