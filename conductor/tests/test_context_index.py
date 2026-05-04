"""Tests for `context.index.render_index`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quorum_conductor.context.index import index_path, render_index
from quorum_conductor.context.manifest import ContextEntry, ContextManifest


def _entry(**overrides: object) -> ContextEntry:
    base = {
        "id": "ctx-0001",
        "kind": "doc",
        "name": "thing",
        "added_at": datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC),
        "source": "/tmp/thing",
    }
    base.update(overrides)
    return ContextEntry(**base)  # type: ignore[arg-type]


def test_empty_manifest_renders_helpful_placeholder(tmp_path: Path) -> None:
    render_index(tmp_path, ContextManifest())
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert body.startswith("# Context")
    assert "No context configured" in body


def test_repo_section_includes_path_and_links(tmp_path: Path) -> None:
    repo = _entry(
        id="ctx-0001",
        kind="repo",
        name="v2-app",
        source="/Users/rakesh/Projects/v2-app",
        digest_status="ready",
        digest_summary="42 files; TypeScript + Python",
    )
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[repo]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "## Repos" in body
    assert "v2-app" in body
    assert "/Users/rakesh/Projects/v2-app" in body
    assert "context/repos/v2-app/digest.md" in body
    assert "context/repos/v2-app/source/" in body
    assert "42 files" in body


def test_repo_status_pending_is_surfaced(tmp_path: Path) -> None:
    repo = _entry(id="ctx-0001", kind="repo", name="v2-app", digest_status="pending")
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[repo]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "status: `pending`" in body


def test_stale_repo_marked(tmp_path: Path) -> None:
    repo = _entry(id="ctx-0001", kind="repo", name="v2-app", digest_status="ready", stale=True)
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[repo]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "stale" in body.lower()


def test_doc_section_links_to_copy(tmp_path: Path) -> None:
    doc = _entry(id="ctx-0001", kind="doc", name="spec.md", source="/docs/spec.md")
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[doc]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "## Docs" in body
    assert "context/docs/spec.md" in body


def test_note_section_renders(tmp_path: Path) -> None:
    note = _entry(id="ctx-0001", kind="note", name="thought", source="", body="some text")
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[note]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "## Notes" in body
    assert "context/notes/thought.md" in body


def test_sections_only_appear_when_relevant(tmp_path: Path) -> None:
    """If there are no repos, the `## Repos` heading shouldn't render."""
    note = _entry(id="ctx-0001", kind="note", name="n", source="", body="x")
    render_index(tmp_path, ContextManifest(next_id_counter=1, entries=[note]))
    body = index_path(tmp_path).read_text(encoding="utf-8")
    assert "## Repos" not in body
    assert "## Docs" not in body
    assert "## Notes" in body
