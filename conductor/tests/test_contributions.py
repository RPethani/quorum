"""Contributions-section parser tests."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.contributions import parse_contributions


def _seed(path: Path, contributions: str = "") -> None:
    path.write_text(
        "---\n"
        'id: "0001"\n'
        "title: t\n"
        "status: OPEN\n"
        "---\n\n"
        "## Question\n\nWhat?\n\n"
        f"## Contributions\n{contributions}\n"
        "## Open Questions\n\n"
        "## Decision\n",
        encoding="utf-8",
    )


def test_parse_empty_contributions(tmp_path: Path) -> None:
    p = tmp_path / "0001.md"
    _seed(p)
    view = parse_contributions(p)
    assert view.moves == ()


def test_parse_collects_moves_in_order(tmp_path: Path) -> None:
    p = tmp_path / "0001.md"
    _seed(
        p,
        "\n### [PROPOSAL] @claude-opus · 2026-04-28T14:00:00Z\n\nFirst.\n\n"
        "### [CRITIQUE] @gemini-pro · 2026-04-28T14:30:00Z\n\nObjection.\n",
    )
    view = parse_contributions(p)
    assert [m.move_type for m in view.moves] == ["PROPOSAL", "CRITIQUE"]
    assert view.has("PROPOSAL")
    assert view.has("CRITIQUE")
    assert not view.has("SYNTHESIS")
    crits = view.by_type("CRITIQUE")
    assert len(crits) == 1
    assert crits[0].author == "@gemini-pro"


def test_parse_ignores_headers_outside_contributions(tmp_path: Path) -> None:
    p = tmp_path / "0001.md"
    _seed(
        p,
        "\n### [PROPOSAL] @claude-opus · 2026-04-28T14:00:00Z\n\nbody\n",
    )
    # Append a fake header line in the Decision section (after Contributions).
    body = p.read_text(encoding="utf-8")
    body = body.replace(
        "## Decision\n",
        "## Decision\n\n### [DECISION] @x · 2026-04-28T15:00:00Z\n\nbody\n",
    )
    p.write_text(body, encoding="utf-8")
    view = parse_contributions(p)
    # Only the move under ## Contributions should be returned.
    assert [m.move_type for m in view.moves] == ["PROPOSAL"]
