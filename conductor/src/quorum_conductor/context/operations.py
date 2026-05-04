"""Add / remove / refresh context entries.

Each operation is a small function that:

  1. Validates inputs.
  2. Updates the manifest.
  3. Performs the side-effect on disk (symlink, copy, file write,
     rmtree, …).
  4. Persists the manifest.
  5. Re-renders ``context/index.md``.

Phase 1 ships add (repo / doc / note) and remove. Refresh + digest
land in phase 2; the stub is here for CLI parity.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .index import render_index
from .manifest import (
    CONTEXT_DIR,
    VALID_KINDS,
    ContextEntry,
    ContextManifest,
    allocate_id,
    find_entry,
    load_manifest,
    save_manifest,
)


class ContextOperationError(RuntimeError):
    """Raised when an add/remove/refresh fails before any partial
    on-disk state has landed. The conductor treats it as a 4xx-style
    user error and surfaces the message verbatim."""


# ---------------------------------------------------------------------- #
# Add
# ---------------------------------------------------------------------- #


def add_repo(
    workspace: Path,
    source: Path,
    *,
    name: str | None = None,
    now: datetime | None = None,
) -> ContextEntry:
    """Add a repository (folder) as a context entry.

    Per Q2: we **symlink** the source into
    ``<workspace>/context/repos/<slug>/source/`` rather than copying.
    The digester (phase 2) reads through the symlink and writes a
    one-page summary to ``digest.md`` in the same folder.
    """
    source = source.expanduser().resolve()
    if not source.is_dir():
        raise ContextOperationError(f"not a directory: {source}")
    display_name = name or source.name
    manifest = load_manifest(workspace)
    _refuse_if_duplicate(manifest, source)

    entry_id, manifest = allocate_id(manifest)
    slug = slugify(display_name)
    repo_root = workspace / CONTEXT_DIR / "repos" / slug
    repo_root.mkdir(parents=True, exist_ok=True)

    link = repo_root / "source"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(source, target_is_directory=True)

    entry = ContextEntry(
        id=entry_id,
        kind="repo",
        name=display_name,
        added_at=now or datetime.now(UTC),
        source=str(source),
        digest_status="pending",
    )
    manifest = _append(manifest, entry)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return entry


def add_doc(
    workspace: Path,
    source: Path,
    *,
    name: str | None = None,
    now: datetime | None = None,
) -> ContextEntry:
    """Add a single document file. We **copy** the file's contents
    into ``<workspace>/context/docs/<slug>.md`` (Q6 — raw, no
    digestion in v1)."""
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ContextOperationError(f"not a file: {source}")
    display_name = name or source.name
    manifest = load_manifest(workspace)
    _refuse_if_duplicate(manifest, source)

    entry_id, manifest = allocate_id(manifest)
    docs_dir = workspace / CONTEXT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = docs_dir / doc_filename(display_name)
    shutil.copyfile(source, target)

    entry = ContextEntry(
        id=entry_id,
        kind="doc",
        name=display_name,
        added_at=now or datetime.now(UTC),
        source=str(source),
    )
    manifest = _append(manifest, entry)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return entry


def add_note(
    workspace: Path,
    name: str,
    body: str,
    *,
    now: datetime | None = None,
) -> ContextEntry:
    """Add a free-form note. Body is stored both inline in the
    manifest *and* as ``context/notes/<slug>.md`` so agents can read
    it as a normal file."""
    name = name.strip()
    body = body.strip()
    if not name:
        raise ContextOperationError("note name is required")
    if not body:
        raise ContextOperationError("note body is required")

    manifest = load_manifest(workspace)
    entry_id, manifest = allocate_id(manifest)
    slug = slugify(name)
    notes_dir = workspace / CONTEXT_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"{slug}.md").write_text(body + "\n", encoding="utf-8")

    entry = ContextEntry(
        id=entry_id,
        kind="note",
        name=name,
        added_at=now or datetime.now(UTC),
        body=body,
    )
    manifest = _append(manifest, entry)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return entry


# ---------------------------------------------------------------------- #
# Remove
# ---------------------------------------------------------------------- #


def remove(workspace: Path, entry_id: str) -> ContextEntry:
    """Remove a context entry by id. Cleans up its on-disk files /
    symlinks and re-renders the index."""
    manifest = load_manifest(workspace)
    entry = find_entry(manifest, entry_id)
    if entry is None:
        raise ContextOperationError(f"no entry with id {entry_id!r}")

    slug = slugify(entry.name)
    if entry.kind == "repo":
        target = workspace / CONTEXT_DIR / "repos" / slug
        _safe_rmtree(target)
    elif entry.kind == "doc":
        target = workspace / CONTEXT_DIR / "docs" / doc_filename(entry.name)
        target.unlink(missing_ok=True)
    elif entry.kind == "note":
        target = workspace / CONTEXT_DIR / "notes" / f"{slug}.md"
        target.unlink(missing_ok=True)

    new_entries = [e for e in manifest.entries if e.id != entry_id]
    manifest = replace(manifest, entries=new_entries)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return entry


# ---------------------------------------------------------------------- #
# Refresh — phase-1 stub
# ---------------------------------------------------------------------- #


def refresh(workspace: Path, entry_id: str) -> ContextEntry:
    """Re-trigger digestion for a repo entry.

    Phase 1: just resets ``digest_status`` to ``pending``. The phase-2
    digester picks up pending entries and runs them.
    """
    manifest = load_manifest(workspace)
    entry = find_entry(manifest, entry_id)
    if entry is None:
        raise ContextOperationError(f"no entry with id {entry_id!r}")
    if entry.kind != "repo":
        raise ContextOperationError(
            f"refresh only applies to repo entries; {entry_id} is a {entry.kind}"
        )

    bumped = replace(entry, digest_status="pending", digest_error="", stale=False)
    new_entries = [bumped if e.id == entry_id else e for e in manifest.entries]
    manifest = replace(manifest, entries=new_entries)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return bumped


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify(name: str) -> str:
    """Filesystem-safe slug derived from a name.

    Conservative — preserves dots and dashes so ``my-doc.md`` round-
    trips, lowercases the rest, collapses runs of separator chars to
    single ``-``, and strips leading/trailing separators.
    """
    s = _SLUG_RE.sub("-", name.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def doc_filename(name: str) -> str:
    """On-disk filename for a doc entry.

    Splits ``name`` into stem + suffix so we don't double-append
    ``.md`` when the source already has an extension. Falls back to
    ``.md`` for extension-less names.

    Examples::

        doc_filename("spec.md")        → "spec.md"
        doc_filename("MyDoc")          → "mydoc.md"
        doc_filename("notes.txt")      → "notes.txt"
        doc_filename("My Architecture.md") → "my-architecture.md"
    """
    p = Path(name)
    stem = slugify(p.stem)
    suffix = p.suffix or ".md"
    return f"{stem}{suffix}"


def _append(manifest: ContextManifest, entry: ContextEntry) -> ContextManifest:
    return replace(manifest, entries=[*manifest.entries, entry])


def _refuse_if_duplicate(manifest: ContextManifest, source: Path) -> None:
    """Don't allow two entries to point at the same source path —
    keeps `context/repos/<slug>/source` symlinks unambiguous."""
    src_str = str(source)
    if any(e.source == src_str for e in manifest.entries):
        raise ContextOperationError(
            f"a context entry for {source} already exists; "
            "remove it first or pick a different source"
        )


def _safe_rmtree(path: Path) -> None:
    """`rmtree` that tolerates missing paths and never follows the
    repo symlink — we want to remove the symlink itself, not delete
    the user's actual repository."""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        # The `source` symlink inside the repo directory — kill it
        # explicitly first so rmtree doesn't try to recurse into the
        # user's real repo.
        for child in path.iterdir():
            if child.is_symlink():
                child.unlink()
        shutil.rmtree(path, ignore_errors=False)
