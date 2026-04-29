"""Phase-6a tests: standing bundle + Layer-2 deliberation-declared context."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.context_bundle import (
    assemble_deliberation_bundle,
    assemble_standing_bundle,
    load_context_manifest,
    save_context_manifest,
)
from quorum_conductor.core.deliberation import DeliberationMeta, DeliberationRoles
from quorum_conductor.workspace import InitOptions, init_workspace


def _meta(extras: dict[str, object] | None = None) -> DeliberationMeta:
    return DeliberationMeta(
        id="0001",
        title="t",
        status="OPEN",
        roles=DeliberationRoles(),
        tags=[],
        extras=extras or {},
    )


def test_standing_bundle_includes_problem_and_manifest(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    paths.problem_statement.write_text("# Problem\n\nDecide X.\n", encoding="utf-8")
    paths.outcome_manifest.write_text("# Manifest\n\nartifacts: A, B.\n", encoding="utf-8")

    bundle = assemble_standing_bundle(paths)
    md = bundle.to_markdown()
    assert "## STANDING CONTEXT" in md
    assert "Problem statement" in md
    assert "Decide X" in md
    assert "Outcome manifest" in md
    assert "artifacts: A, B" in md


def test_standing_bundle_skips_missing_files(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    # Outcome manifest exists but is empty (default placeholder is non-empty
    # template — overwrite with blank to test "skip empty" path).
    paths.outcome_manifest.write_text("", encoding="utf-8")
    paths.problem_statement.write_text("Real content.\n", encoding="utf-8")

    bundle = assemble_standing_bundle(paths)
    md = bundle.to_markdown()
    # The empty manifest is skipped, but the non-empty problem-statement is in.
    assert "Outcome manifest" not in md
    assert "Problem statement" in md


def test_standing_bundle_includes_summarized_decisions(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    paths.summarized_decisions.write_text(
        "# Summarized decisions\n\n- **DECISION@x#0001** — Ship trial-only.\n",
        encoding="utf-8",
    )
    bundle = assemble_standing_bundle(paths)
    md = bundle.to_markdown()
    assert "Summarised decisions" in md
    assert "Ship trial-only" in md


def test_standing_bundle_includes_all_notes(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    paths.context_notes.mkdir(parents=True, exist_ok=True)
    (paths.context_notes / "convention.md").write_text(
        "# Conventions\n\nWe never use modal dialogs.\n", encoding="utf-8"
    )
    (paths.context_notes / "customer-context.md").write_text(
        "# Customer\n\nThey care about latency.\n", encoding="utf-8"
    )
    bundle = assemble_standing_bundle(paths)
    md = bundle.to_markdown()
    assert "Note · convention" in md
    assert "Note · customer-context" in md
    assert "modal dialogs" in md
    assert "latency" in md


def test_deliberation_bundle_includes_named_repo(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    repo_dir = paths.context_repos / "backend"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "digest.md").write_text(
        "# backend digest\n\nFastAPI + Postgres.\n", encoding="utf-8"
    )

    meta = _meta(extras={"relevant_context": {"repos": ["backend"], "docs": [], "urls": [], "notes": "all"}})
    bundle = assemble_deliberation_bundle(paths, meta)
    md = bundle.to_markdown()
    assert "## DELIBERATION CONTEXT" in md
    assert "Repo · backend" in md
    assert "FastAPI + Postgres" in md


def test_deliberation_bundle_skips_unknown_names(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    meta = _meta(extras={"relevant_context": {"repos": ["does-not-exist"], "docs": [], "urls": []}})
    bundle = assemble_deliberation_bundle(paths, meta)
    assert bundle.to_markdown() == ""


def test_deliberation_bundle_empty_when_no_relevant_context(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    bundle = assemble_deliberation_bundle(paths, _meta())
    assert bundle.to_markdown() == ""


def test_context_manifest_round_trip(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    manifest = load_context_manifest(paths)
    assert manifest["repos"] == []
    manifest["repos"].append(
        {"name": "backend", "path": "/abs/path", "relevance": "high"}
    )
    save_context_manifest(paths, manifest)
    again = load_context_manifest(paths)
    assert again["repos"] == manifest["repos"]
