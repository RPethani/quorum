"""End-to-end tests for `context.operations` add/remove/refresh."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from quorum_conductor.canvas.workspace import scaffold
from quorum_conductor.context.index import index_path
from quorum_conductor.context.manifest import load_manifest, manifest_path
from quorum_conductor.context.operations import (
    ContextOperationError,
    add_doc,
    add_note,
    add_repo,
    refresh,
    remove,
    slugify,
)


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    scaffold(ws, now=datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC))
    return ws


# ---------------------------------------------------------------------- #
# slugify
# ---------------------------------------------------------------------- #


def test_slugify_basic():
    assert slugify("v2-app") == "v2-app"
    assert slugify("My Doc.md") == "my-doc.md"
    assert slugify("hello   world!") == "hello-world"
    assert slugify("") == "untitled"


# ---------------------------------------------------------------------- #
# add_repo
# ---------------------------------------------------------------------- #


def test_add_repo_creates_symlink_and_manifest(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "repos" / "v2-app"
    repo.mkdir(parents=True)
    (repo / "README.md").write_text("# v2", encoding="utf-8")

    entry = add_repo(ws, repo, now=datetime(2026, 5, 4, 11, 0, 0, tzinfo=UTC))
    assert entry.id == "ctx-0001"
    assert entry.kind == "repo"
    assert entry.digest_status == "pending"
    assert entry.source == str(repo.resolve())

    link = ws / "context" / "repos" / "v2-app" / "source"
    assert link.is_symlink()
    assert link.resolve() == repo.resolve()

    # Manifest persisted
    [back] = load_manifest(ws).entries
    assert back == entry

    # Index regenerated
    body = index_path(ws).read_text(encoding="utf-8")
    assert "v2-app" in body


def test_add_repo_refuses_non_directory(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    f = tmp_path / "not-a-dir.txt"
    f.write_text("hi")
    with pytest.raises(ContextOperationError):
        add_repo(ws, f)


def test_add_repo_refuses_duplicate_source(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    add_repo(ws, repo)
    with pytest.raises(ContextOperationError):
        add_repo(ws, repo)


def test_add_repo_with_custom_name(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "long-repo-name-the-user-wants-shortened"
    repo.mkdir()
    entry = add_repo(ws, repo, name="myrepo")
    assert entry.name == "myrepo"
    assert (ws / "context" / "repos" / "myrepo" / "source").is_symlink()


# ---------------------------------------------------------------------- #
# add_doc
# ---------------------------------------------------------------------- #


def test_add_doc_copies_file(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    src = tmp_path / "spec.md"
    src.write_text("# Spec\nbody", encoding="utf-8")
    entry = add_doc(ws, src)
    assert entry.kind == "doc"
    assert entry.source == str(src.resolve())

    copied = ws / "context" / "docs" / "spec.md"
    assert copied.read_text(encoding="utf-8") == "# Spec\nbody"


def test_add_doc_refuses_directory(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(ContextOperationError):
        add_doc(ws, d)


# ---------------------------------------------------------------------- #
# add_note
# ---------------------------------------------------------------------- #


def test_add_note_writes_file_and_persists_body(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    entry = add_note(ws, "routing-edge-case", "the dispatch is sequential…")
    assert entry.kind == "note"
    assert entry.body.startswith("the dispatch")
    assert entry.source == ""

    note_file = ws / "context" / "notes" / "routing-edge-case.md"
    assert note_file.is_file()
    assert note_file.read_text(encoding="utf-8").startswith("the dispatch")


def test_add_note_refuses_empty(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    with pytest.raises(ContextOperationError):
        add_note(ws, "", "body")
    with pytest.raises(ContextOperationError):
        add_note(ws, "name", "   ")


# ---------------------------------------------------------------------- #
# remove
# ---------------------------------------------------------------------- #


def test_remove_repo_drops_symlink_not_source(tmp_path: Path) -> None:
    """Critical safety: removing a repo entry must NOT delete the
    user's actual repo on disk."""
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    (repo / "important.txt").write_text("don't delete me")
    entry = add_repo(ws, repo)

    remove(ws, entry.id)

    # Workspace symlink gone
    assert not (ws / "context" / "repos" / "v2-app").exists()
    # Source repo + contents intact
    assert repo.is_dir()
    assert (repo / "important.txt").read_text(encoding="utf-8") == "don't delete me"


def test_remove_doc_drops_copy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    src = tmp_path / "spec.md"
    src.write_text("body")
    entry = add_doc(ws, src)
    remove(ws, entry.id)
    assert not (ws / "context" / "docs" / "spec.md").exists()
    assert src.is_file()  # source untouched


def test_remove_note_drops_file(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    entry = add_note(ws, "n", "body")
    remove(ws, entry.id)
    assert not (ws / "context" / "notes" / "n.md").exists()


def test_remove_unknown_id_raises(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    with pytest.raises(ContextOperationError):
        remove(ws, "ctx-9999")


# ---------------------------------------------------------------------- #
# refresh — phase-1 stub behaviour
# ---------------------------------------------------------------------- #


def test_refresh_resets_repo_status_to_pending(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    add_repo(ws, repo)
    # Simulate a digester landing the entry as "ready" — write directly
    # via save_manifest to imitate phase 2.
    from dataclasses import replace as dc_replace

    from quorum_conductor.context.manifest import save_manifest

    m = load_manifest(ws)
    [e] = m.entries
    m = dc_replace(
        m,
        entries=[
            dc_replace(e, digest_status="ready", digest_summary="ready summary", stale=True)
        ],
    )
    save_manifest(ws, m)

    refreshed = refresh(ws, e.id)
    assert refreshed.digest_status == "pending"
    assert refreshed.stale is False


def test_refresh_refuses_non_repo(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    src = tmp_path / "spec.md"
    src.write_text("body")
    e = add_doc(ws, src)
    with pytest.raises(ContextOperationError):
        refresh(ws, e.id)
