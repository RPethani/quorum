"""Read / write the context manifest.

The manifest is a single YAML file at
``<workspace>/context/context-manifest.yaml`` that lists every
context entry (repos, docs, notes). It's the only writer-path for
context state — `context/index.md`, the on-disk symlinks and copies
all derive from it.

See `docs-specs/context-seeding.md` for the design contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

import yaml

CONTEXT_DIR = "context"
MANIFEST_FILENAME = "context-manifest.yaml"
SCHEMA_VERSION = 1

# Allowed values for `kind` — keep as a set so callers don't drift.
VALID_KINDS = frozenset({"repo", "doc", "note"})


class ManifestError(RuntimeError):
    """Raised on missing / unreadable / malformed manifest files."""


@dataclass(frozen=True)
class ContextEntry:
    """One context entry — a repo, a doc, or a free-form note.

    Fields that don't apply to a given ``kind`` simply stay empty —
    e.g. a note has no ``source``; a doc has no ``digest_*``.
    """

    id: str
    """``ctx-NNNN`` allocated by the manifest's counter."""
    kind: str
    """``"repo"`` | ``"doc"`` | ``"note"``."""
    name: str
    """Human-readable label; defaults to the source's basename."""
    added_at: datetime
    """When the entry was first added."""

    source: str = ""
    """Absolute on-disk source path. Empty for notes."""

    # ── repo-only ──────────────────────────────────────────────────
    digest_status: str = ""
    """``"pending"`` | ``"running"`` | ``"ready"`` | ``"failed"``.
    Empty string for non-repo entries."""
    digest_summary: str = ""
    """One-line summary written by the digester after success."""
    digest_error: str = ""
    """Error string after a failed digest run."""
    digest_at: datetime | None = None
    """When the most recent digest completed."""
    source_git_ref: str = ""
    """``git rev-parse HEAD`` of the source repo at last digest;
    used by the stale-detection probe."""
    stale: bool = False
    """``True`` when the source repo's HEAD has moved since the last
    successful digest. Surfaced in the UI via a "stale" badge."""

    # ── note-only ──────────────────────────────────────────────────
    body: str = ""
    """The note's body text. Empty for non-note entries."""


@dataclass(frozen=True)
class ContextManifest:
    """The full manifest. Treat as immutable; use ``replace_with`` for edits."""

    schema_version: int = SCHEMA_VERSION
    next_id_counter: int = 0
    """Monotonically-increasing counter for new entry IDs."""
    entries: list[ContextEntry] = field(default_factory=list)


# ---------------------------------------------------------------------- #
# I/O
# ---------------------------------------------------------------------- #


def manifest_path(workspace: Path) -> Path:
    return workspace / CONTEXT_DIR / MANIFEST_FILENAME


def load_manifest(workspace: Path) -> ContextManifest:
    """Read the manifest from disk. Returns an empty manifest if the
    file doesn't exist (the conductor lazily creates it on first add)."""
    p = manifest_path(workspace)
    if not p.is_file():
        return ContextManifest()
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ManifestError(f"{p} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ManifestError(f"{p} root is not a mapping")
    return _from_dict(raw)


def save_manifest(workspace: Path, manifest: ContextManifest) -> None:
    """Write the manifest atomically.

    Also ensures ``<workspace>/context/`` exists. The caller is
    responsible for re-rendering ``context/index.md`` after a
    successful save (see `index.render`).
    """
    p = manifest_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(_to_dict(manifest), sort_keys=False, default_flow_style=False)
    tmp = p.with_suffix(".yaml.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, p)


def allocate_id(manifest: ContextManifest) -> tuple[str, ContextManifest]:
    """Reserve the next ``ctx-NNNN`` and return ``(id, new_manifest)``.

    The new manifest has the bumped counter — the caller is expected
    to either save it (with the new entry appended) or discard it.
    """
    new_n = manifest.next_id_counter + 1
    return f"ctx-{new_n:04d}", replace(manifest, next_id_counter=new_n)


def find_entry(manifest: ContextManifest, entry_id: str) -> ContextEntry | None:
    return next((e for e in manifest.entries if e.id == entry_id), None)


# ---------------------------------------------------------------------- #
# Internals: dict <-> dataclass
# ---------------------------------------------------------------------- #


def _to_dict(manifest: ContextManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "next_id_counter": manifest.next_id_counter,
        "entries": [_entry_to_dict(e) for e in manifest.entries],
    }


def _entry_to_dict(e: ContextEntry) -> dict[str, object]:
    out: dict[str, object] = {
        "id": e.id,
        "kind": e.kind,
        "name": e.name,
        "added_at": _iso_z(e.added_at),
    }
    if e.source:
        out["source"] = e.source
    if e.kind == "repo":
        out["digest_status"] = e.digest_status or "pending"
        if e.digest_summary:
            out["digest_summary"] = e.digest_summary
        if e.digest_error:
            out["digest_error"] = e.digest_error
        if e.digest_at is not None:
            out["digest_at"] = _iso_z(e.digest_at)
        if e.source_git_ref:
            out["source_git_ref"] = e.source_git_ref
        if e.stale:
            out["stale"] = True
    if e.kind == "note" and e.body:
        out["body"] = e.body
    return out


def _from_dict(raw: dict[str, object]) -> ContextManifest:
    entries_raw = raw.get("entries", []) or []
    if not isinstance(entries_raw, list):
        raise ManifestError("`entries` must be a list")
    entries = [_entry_from_dict(d) for d in entries_raw if isinstance(d, dict)]
    return ContextManifest(
        schema_version=int(raw.get("schema_version", SCHEMA_VERSION)),
        next_id_counter=int(raw.get("next_id_counter", 0)),
        entries=entries,
    )


def _entry_from_dict(raw: dict[str, object]) -> ContextEntry:
    kind = str(raw.get("kind", "")).strip()
    if kind not in VALID_KINDS:
        raise ManifestError(f"unknown kind in manifest: {kind!r}")
    digest_at_raw = raw.get("digest_at")
    digest_at = _parse_iso(str(digest_at_raw)) if digest_at_raw else None
    return ContextEntry(
        id=str(raw["id"]),
        kind=kind,
        name=str(raw.get("name", "")),
        added_at=_parse_iso(str(raw.get("added_at", _now_iso()))),
        source=str(raw.get("source", "")),
        digest_status=str(raw.get("digest_status", "")),
        digest_summary=str(raw.get("digest_summary", "")),
        digest_error=str(raw.get("digest_error", "")),
        digest_at=digest_at,
        source_git_ref=str(raw.get("source_git_ref", "")),
        stale=bool(raw.get("stale", False)),
        body=str(raw.get("body", "")),
    )


def _now_iso() -> str:
    return _iso_z(datetime.now(UTC))


def _iso_z(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    iso = ts.astimezone(UTC).isoformat()
    return iso[:-6] + "Z" if iso.endswith("+00:00") else iso


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)
