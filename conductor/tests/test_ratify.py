"""Auto-ratification of outcome-manifest.md on terminal seed-deliberation moves."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.workspace import InitOptions, init_workspace
from quorum_conductor.workspace.bootstrapper import bootstrap_seed_deliberation
from quorum_conductor.workspace.deliberation_file import append_move
from quorum_conductor.workspace.ratify import maybe_ratify_manifest


def _seed_with_proposal_and_decision(tmp_path: Path) -> Path:
    """Initialise a workspace, seed deliberation #0001, and append a
    PROPOSAL + SYNTHESIS + DECISION. Returns the deliberation path."""
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    seed = bootstrap_seed_deliberation(paths)
    append_move(
        seed,
        "### [PROPOSAL] @claude-opus · 2026-04-29T10:00:00Z\n\n"
        "## Position\n\nManifest content goes here: artifacts X, Y, Z.\n\n"
        "## Reasoning\n\nBecause...",
    )
    append_move(
        seed,
        "### [SYNTHESIS] @claude-opus · 2026-04-29T10:30:00Z\n\n"
        "## Summary\n\nFinal manifest content: artifacts A, B, C "
        "with completion checks K1 K2 K3.\n",
    )
    append_move(
        seed,
        "### [DECISION] @human-rakesh · 2026-04-29T10:45:00Z\n\n"
        "## Decision\n\nApprove the synthesised manifest.",
    )
    return seed


def test_ratification_writes_manifest_with_synthesis_body(tmp_path: Path) -> None:
    seed = _seed_with_proposal_and_decision(tmp_path)
    paths_dir = seed.parent.parent
    from quorum_conductor.paths import WorkspacePaths

    paths = WorkspacePaths(root=paths_dir)
    # The append_move calls inside the helper don't yet auto-ratify
    # (they only auto-ratify when called via invoker / http_app); here
    # we drive the function directly to test it in isolation.
    assert maybe_ratify_manifest(paths, seed) is True
    body = paths.outcome_manifest.read_text(encoding="utf-8")
    assert "status: LOCKED" in body
    assert "Final manifest content: artifacts A, B, C" in body


def test_ratification_idempotent(tmp_path: Path) -> None:
    seed = _seed_with_proposal_and_decision(tmp_path)
    from quorum_conductor.paths import WorkspacePaths

    paths = WorkspacePaths(root=seed.parent.parent)
    assert maybe_ratify_manifest(paths, seed) is True
    # Second call is a no-op because manifest is already LOCKED.
    assert maybe_ratify_manifest(paths, seed) is False


def test_ratification_falls_back_to_proposal_when_no_synthesis(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    seed = bootstrap_seed_deliberation(paths)
    append_move(
        seed,
        "### [PROPOSAL] @claude-opus · 2026-04-29T10:00:00Z\n\n"
        "## Position\n\nDirect manifest from proposal.",
    )
    append_move(
        seed,
        "### [DECISION] @human-rakesh · 2026-04-29T10:30:00Z\n\n## Decision\n\nApprove.",
    )
    assert maybe_ratify_manifest(paths, seed) is True
    body = paths.outcome_manifest.read_text(encoding="utf-8")
    assert "status: LOCKED" in body
    assert "Direct manifest from proposal" in body


def test_ratification_skips_non_ratifying_deliberation(tmp_path: Path) -> None:
    """Deliberations without `ratifies: outcome-manifest.md` aren't touched."""
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    delib = paths.deliberations / "0042-other.md"
    paths.deliberations.mkdir(parents=True, exist_ok=True)
    delib.write_text(
        "---\n"
        'id: "0042"\n'
        "title: unrelated\n"
        "status: OPEN\n"
        "---\n\n"
        "## Question\n\n## Contributions\n\n"
        "### [DECISION] @human · 2026-04-29T10:00:00Z\n\nApprove.\n",
        encoding="utf-8",
    )
    assert maybe_ratify_manifest(paths, delib) is False
    # outcome-manifest.md must remain in DRAFTING.
    body = paths.outcome_manifest.read_text(encoding="utf-8")
    assert "status: DRAFTING" in body


def test_ratification_skips_non_terminal_move(tmp_path: Path) -> None:
    """If the latest move is a CRITIQUE, manifest stays untouched."""
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    seed = bootstrap_seed_deliberation(paths)
    append_move(
        seed,
        "### [PROPOSAL] @claude · 2026-04-29T10:00:00Z\n\n## Position\n\nProposed.",
    )
    append_move(
        seed,
        "### [CRITIQUE] @gemini · 2026-04-29T10:15:00Z\n\n## Targets\n\nIssue raised.",
    )
    assert maybe_ratify_manifest(paths, seed) is False
