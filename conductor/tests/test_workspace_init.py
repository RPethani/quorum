"""Round-trip and structural tests for `quorum init` + `quorum status`."""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.paths import WorkspacePaths, find_workspace
from quorum_conductor.workspace import (
    InitOptions,
    WorkspaceMode,
    WorkspaceState,
    archive_workspace,
    init_workspace,
    load_state,
    status_summary,
    unarchive_workspace,
)
from quorum_conductor.workspace.scaffolding import ScaffoldingError


def test_init_creates_expected_layout(tmp_path: Path) -> None:
    target = tmp_path / "quorum"
    paths = init_workspace(InitOptions(target=target))

    assert paths.state_yaml.is_file()
    assert paths.config_yaml.is_file()
    assert paths.problem_statement.is_file()
    assert paths.outcome_manifest.is_file()
    assert paths.gitignore.is_file()
    assert paths.participants.is_file()
    assert paths.routing_defaults.is_file()
    for d in paths.all_directories():
        assert d.is_dir(), f"missing directory: {d}"


def test_init_writes_state_yaml_with_expected_fields(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    state = load_state(paths.state_yaml)

    assert state.state == WorkspaceState.INITIALIZED
    assert state.mode == WorkspaceMode.INTERACTIVE
    assert state.workspace_id  # non-empty hex token
    assert state.schema_version == "0.1"


def test_init_autonomous_mode(tmp_path: Path) -> None:
    paths = init_workspace(
        InitOptions(target=tmp_path / "quorum", mode=WorkspaceMode.AUTONOMOUS)
    )
    assert load_state(paths.state_yaml).mode == WorkspaceMode.AUTONOMOUS


def test_init_refuses_to_clobber(tmp_path: Path) -> None:
    target = tmp_path / "quorum"
    init_workspace(InitOptions(target=target))
    with pytest.raises(ScaffoldingError):
        init_workspace(InitOptions(target=target))


def test_routing_defaults_are_copied_from_repo(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    body = paths.routing_defaults.read_text(encoding="utf-8")
    # The bundled file ships with an Opus row; the stub fallback does not.
    assert "@claude-opus" in body, "expected the repo's routing-defaults to be copied"


def test_find_workspace_walks_upward(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    nested = paths.deliberations / "subdir"
    nested.mkdir(parents=True)
    found = find_workspace(nested)
    assert found is not None
    assert found.root == paths.root


def test_status_summary_counts_zero_on_fresh_workspace(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    summary = status_summary(paths)
    assert summary.deliberation_count == 0
    assert summary.artifact_count == 0
    assert summary.decision_count == 0
    assert summary.task_count == 0
    assert summary.inbox_pending_count == 0
    assert not summary.conductor_running
    assert not summary.ui_running


def test_status_counts_inbox_pending_only_for_nonempty(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    (paths.inbox / "@claude-opus.md").write_text("- pending: review #0001\n", encoding="utf-8")
    summary = status_summary(paths)
    assert summary.inbox_pending_count == 1


def test_archive_then_unarchive_round_trip(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    assert paths.runtime.is_dir()

    archive_workspace(paths, reason="testing")
    state = load_state(paths.state_yaml)
    assert state.state == WorkspaceState.ARCHIVED
    assert not paths.runtime.exists(), "archive must remove runtime/"
    assert state.extras.get("archive", {}).get("reason") == "testing"

    unarchive_workspace(paths)
    state = load_state(paths.state_yaml)
    assert state.state == WorkspaceState.INITIALIZED
    assert paths.runtime.is_dir(), "unarchive must restore runtime/"
    assert "archive" not in state.extras


def test_state_yaml_round_trip_preserves_unknown_keys(tmp_path: Path) -> None:
    """A future schema field should survive load/save without being dropped."""
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    text = paths.state_yaml.read_text(encoding="utf-8")
    # Append a hypothetical future field at the bottom.
    paths.state_yaml.write_text(text + "future_field: kept\n", encoding="utf-8")

    state = load_state(paths.state_yaml)
    assert state.extras.get("future_field") == "kept"

    # Save and re-load: still there.
    from quorum_conductor.workspace.state import save_state

    save_state(paths.state_yaml, state)
    state2 = load_state(paths.state_yaml)
    assert state2.extras.get("future_field") == "kept"


def test_workspace_paths_dataclass_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    paths = WorkspacePaths(root=Path("/tmp/example"))
    with pytest.raises(FrozenInstanceError):
        paths.root = Path("/tmp/other")  # type: ignore[misc]
