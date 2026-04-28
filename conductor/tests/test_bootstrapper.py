"""Bootstrapper (4h) tests."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core import plan
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace import (
    InitOptions,
    bootstrap_seed_deliberation,
    init_workspace,
    needs_bootstrap,
)

_ = WorkspacePaths  # imported for type-checking continuity in helpers


def test_needs_bootstrap_on_fresh_workspace(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    assert needs_bootstrap(paths)


def test_needs_bootstrap_false_after_seed(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    bootstrap_seed_deliberation(paths)
    assert not needs_bootstrap(paths)


def test_seed_creates_deliberation_0001(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    p = bootstrap_seed_deliberation(paths)
    assert p.is_file()
    body = p.read_text(encoding="utf-8")
    assert 'id: "0001"' in body
    assert "ratifies: outcome-manifest.md" in body
    assert "## Contributions" in body


def test_seed_is_idempotent(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    p1 = bootstrap_seed_deliberation(paths)
    p2 = bootstrap_seed_deliberation(paths)
    assert p1 == p2
    assert sum(1 for _ in paths.deliberations.glob("0001-*.md")) == 1


def test_planner_picks_up_seed_with_bootstrapper_role(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    bootstrap_seed_deliberation(paths)
    paths.participants.write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| @fake | Fake | python3 -V | x | cli | 30/5 | fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )
    result = plan(paths)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.deliberation.id == "0001"
    assert item.move_type == "PROPOSAL"
    # Vertical-slice finding: the seed must route under the bootstrapper
    # role so the standing prompt's bootstrapper augmentation fires.
    assert item.role == "bootstrapper"
    assert item.reason == "open_needs_manifest_proposal"


def test_init_copies_manifest_templates(tmp_path: Path) -> None:
    """Vertical-slice finding: the bootstrapper agent expects to read
    the manifest templates from the workspace."""
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    target = paths.protocol_manifest_templates
    assert target.is_dir()
    files = sorted(p.name for p in target.glob("*.md"))
    # Should have at least the five canonical archetypes.
    assert "saas-product.md" in files
    assert "research-direction.md" in files
    assert "architecture-decision.md" in files
    assert "coding-plan.md" in files
    assert "strategic-decision.md" in files
