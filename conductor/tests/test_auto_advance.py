"""Tests for `workspace/auto_advance.py`."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.workspace.auto_advance import (
    maybe_open_next_artifact_deliberation,
)
from tests.test_ask_generator import _bootstrap_workspace


def _write_manifest(tmp_path: Path, *, locked: bool, body: str = "") -> None:
    """Drop a minimal outcome-manifest.md into the workspace."""
    fm = "status: " + ("LOCKED" if locked else "DRAFTING")
    text = f"---\n{fm}\nprotocol_version: 0.1\n---\n\n# Manifest\n\n{body}\n"
    (tmp_path / "outcome-manifest.md").write_text(text, encoding="utf-8")


def test_no_op_when_manifest_drafting(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(tmp_path, locked=False, body="Mention `option-analysis.md`.")
    assert maybe_open_next_artifact_deliberation(paths) is None
    assert list(paths.deliberations.glob("*.md")) == []


def test_opens_first_artifact_when_locked(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(
        tmp_path,
        locked=True,
        body=(
            "Three artifacts:\n"
            "1. `option-analysis.md`\n"
            "2. `recommendation.md`\n"
            "3. `course-correction-plan.md`\n"
        ),
    )
    new_path = maybe_open_next_artifact_deliberation(paths)
    assert new_path is not None
    body = new_path.read_text(encoding="utf-8")
    assert "ratifies: option-analysis.md" in body
    assert 'decider: "@rakesh"' in body
    assert "@claude-opus" in body  # CLI handle tagged
    assert "## Contributions" in body


def test_only_one_open_at_a_time(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(
        tmp_path,
        locked=True,
        body="Need `option-analysis.md` and `recommendation.md`.",
    )
    first = maybe_open_next_artifact_deliberation(paths)
    second = maybe_open_next_artifact_deliberation(paths)
    assert first is not None
    assert second is None  # first is still open; we don't pile up
    paths_to_files = list(paths.deliberations.glob("*.md"))
    assert len(paths_to_files) == 1


def test_advances_after_previous_decided(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(
        tmp_path,
        locked=True,
        body="`option-analysis.md` then `recommendation.md`.",
    )
    first = maybe_open_next_artifact_deliberation(paths)
    assert first is not None

    # Mark the first ratification deliberation as DECIDED.
    text = first.read_text(encoding="utf-8").replace(
        "status: OPEN", "status: DECIDED"
    )
    first.write_text(text, encoding="utf-8")

    second = maybe_open_next_artifact_deliberation(paths)
    assert second is not None
    body = second.read_text(encoding="utf-8")
    assert "ratifies: recommendation.md" in body


def test_explicit_frontmatter_artifacts_list_overrides_body(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    text = (
        "---\n"
        "status: LOCKED\n"
        "protocol_version: 0.1\n"
        'artifacts: ["only-this.md"]\n'
        "---\n\n"
        "# Manifest\n\n"
        "Body mentions `something-else.md` which should be ignored.\n"
    )
    (tmp_path / "outcome-manifest.md").write_text(text, encoding="utf-8")
    new_path = maybe_open_next_artifact_deliberation(paths)
    assert new_path is not None
    body = new_path.read_text(encoding="utf-8")
    assert "ratifies: only-this.md" in body
    assert "something-else.md" not in body


def test_excludes_outcome_manifest_itself(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(
        tmp_path,
        locked=True,
        body="The outcome-manifest.md is locked. Now produce `option-analysis.md`.",
    )
    new_path = maybe_open_next_artifact_deliberation(paths)
    assert new_path is not None
    assert "ratifies: option-analysis.md" in new_path.read_text(encoding="utf-8")


def test_path_prefixed_filenames_are_ignored(tmp_path: Path) -> None:
    """`*.md` mentions inside a path (e.g.
    `protocol/manifest-templates/strategic-decision.md`) must not be
    picked up as artifacts. Real artifacts in the same manifest body
    must still be found."""
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(
        tmp_path,
        locked=True,
        body=(
            "Adopt `protocol/manifest-templates/strategic-decision.md` "
            "as the base. Three artifacts are required:\n"
            "1. `option-analysis.md`\n"
            "2. `recommendation.md`\n"
        ),
    )
    new_path = maybe_open_next_artifact_deliberation(paths)
    assert new_path is not None
    body = new_path.read_text(encoding="utf-8")
    assert "ratifies: option-analysis.md" in body
    assert "strategic-decision.md" not in body


def test_no_artifacts_does_nothing(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_manifest(tmp_path, locked=True, body="No filenames mentioned here.")
    assert maybe_open_next_artifact_deliberation(paths) is None
