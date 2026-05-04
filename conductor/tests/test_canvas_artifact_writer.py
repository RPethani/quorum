"""Tests for `canvas.artifact_writer.write_artifact`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quorum_conductor.canvas.artifact_writer import write_artifact
from quorum_conductor.canvas.artifacts import ArtifactEmit
from quorum_conductor.canvas.workspace import scaffold


def _setup(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    scaffold(ws)
    return ws


def test_write_creates_new_artifact(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    emit = ArtifactEmit(filename="requirements.md", body="# Reqs\n- one")
    result = write_artifact(ws, emit)

    assert result.archived_path is None
    assert result.artifact_path == ws / "artifacts" / "requirements.md"
    assert result.artifact_path.read_text(encoding="utf-8") == "# Reqs\n- one\n"


def test_write_appends_trailing_newline_if_missing(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    write_artifact(ws, ArtifactEmit(filename="x.md", body="no trailing newline"))
    assert (ws / "artifacts" / "x.md").read_text(encoding="utf-8") == "no trailing newline\n"


def test_write_preserves_existing_trailing_newline(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    write_artifact(ws, ArtifactEmit(filename="x.md", body="already there\n"))
    # Single trailing newline, not two.
    assert (ws / "artifacts" / "x.md").read_text(encoding="utf-8") == "already there\n"


def test_write_archives_prior_version_to_trash(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    write_artifact(
        ws,
        ArtifactEmit(filename="x.md", body="v1"),
        now=datetime(2026, 5, 3, 9, 31, 22, tzinfo=UTC),
    )
    result = write_artifact(
        ws,
        ArtifactEmit(filename="x.md", body="v2"),
        now=datetime(2026, 5, 3, 10, 15, 30, tzinfo=UTC),
    )

    assert result.artifact_path.read_text(encoding="utf-8") == "v2\n"
    assert result.archived_path is not None
    assert result.archived_path == ws / ".trash" / "x.20260503T101530Z.md"
    assert result.archived_path.read_text(encoding="utf-8") == "v1\n"


def test_multiple_revisions_accumulate_in_trash(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v1"),
                   now=datetime(2026, 5, 3, 9, 0, 0, tzinfo=UTC))
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v2"),
                   now=datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC))
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v3"),
                   now=datetime(2026, 5, 3, 11, 0, 0, tzinfo=UTC))

    trashed = sorted((ws / ".trash").iterdir())
    assert len(trashed) == 2  # v1 and v2 archived; v3 is current
    assert (ws / "artifacts" / "x.md").read_text(encoding="utf-8") == "v3\n"


def test_duplicate_timestamp_does_not_clobber(tmp_path: Path) -> None:
    """If two writes happen in the same second, the second archive
    gets a counter suffix instead of overwriting the first."""
    ws = _setup(tmp_path)
    same = datetime(2026, 5, 3, 10, 0, 0, tzinfo=UTC)
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v1"), now=same)
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v2"), now=same)
    # Now write a third with the same timestamp — must archive without losing v2.
    write_artifact(ws, ArtifactEmit(filename="x.md", body="v3"), now=same)

    trashed = sorted(p.name for p in (ws / ".trash").iterdir())
    # v1 archived plain, v2 archived with `.1` suffix.
    assert "x.20260503T100000Z.md" in trashed
    assert "x.20260503T100000Z.1.md" in trashed


def test_nested_path_creates_subdirectory(tmp_path: Path) -> None:
    ws = _setup(tmp_path)
    write_artifact(ws, ArtifactEmit(filename="specs/api.md", body="# API"))
    assert (ws / "artifacts" / "specs" / "api.md").read_text(encoding="utf-8") == "# API\n"
