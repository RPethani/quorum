"""Contributions-section parser tests."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.contributions import parse_contributions


def _seed(path: Path, contributions: str = "") -> None:
    """Seed a deliberation file with `## Contributions` as the last H2.

    This matches the canonical template (see
    `protocol/templates/deliberation.md`); move bodies use H2 sub-
    headings, so Contributions has to be last for the parser to be
    able to extract it cleanly.
    """
    path.write_text(
        "---\n"
        'id: "0001"\n'
        "title: t\n"
        "status: OPEN\n"
        "---\n\n"
        "## Question\n\nWhat?\n\n"
        "## Open Questions\n\n"
        "## Decision\n\n"
        f"## Contributions\n{contributions}",
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


def test_parse_ignores_headers_before_contributions(tmp_path: Path) -> None:
    """Move headers above the `## Contributions` heading must be ignored.

    `## Contributions` is the last H2 in the canonical template; H2
    sub-headings inside move bodies (`## Position`, `## Decision`) are
    therefore allowed without confusing the parser. But anything ABOVE
    Contributions — e.g. a stray header in the Decision section — must
    not be picked up.
    """
    p = tmp_path / "0001.md"
    _seed(
        p,
        "\n### [PROPOSAL] @claude-opus · 2026-04-28T14:00:00Z\n\nbody\n",
    )
    # Inject a fake header in the pre-Contributions Decision section.
    body = p.read_text(encoding="utf-8").replace(
        "## Decision\n",
        "## Decision\n\n### [DECISION] @x · 2026-04-28T15:00:00Z\n\nbody\n",
    )
    p.write_text(body, encoding="utf-8")
    view = parse_contributions(p)
    assert [m.move_type for m in view.moves] == ["PROPOSAL"]
