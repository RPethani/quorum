"""Context seeding — the workspace's pointer to local repos / docs / notes.

Surface: see `docs-specs/context-seeding.md`. Phase 1 ships data +
CLI; phase 2 wires the digester; phase 3 ships UI + HTTP API; phase
4 polishes (stale detection, ignore overrides).
"""

from .digester import (
    DIGEST_SYSTEM_PROMPT,
    DigestError,
    DigestInvokeFn,
    DigestRequest,
    DigestResult,
    digest_repo,
    make_digest_invoker,
    mark_stale_repos,
)
from .gitignore import (
    CONTEXTIGNORE_FILENAME,
    DEFAULT_PATTERNS,
    IgnoreMatcher,
)
from .index import index_path, render_index
from .manifest import (
    CONTEXT_DIR,
    MANIFEST_FILENAME,
    SCHEMA_VERSION,
    VALID_KINDS,
    ContextEntry,
    ContextManifest,
    ManifestError,
    allocate_id,
    find_entry,
    load_manifest,
    manifest_path,
    save_manifest,
)
from .operations import (
    ContextOperationError,
    add_doc,
    add_note,
    add_repo,
    refresh,
    remove,
    slugify,
)

__all__ = [
    "CONTEXTIGNORE_FILENAME",
    "CONTEXT_DIR",
    "ContextEntry",
    "ContextManifest",
    "ContextOperationError",
    "DEFAULT_PATTERNS",
    "DIGEST_SYSTEM_PROMPT",
    "DigestError",
    "DigestInvokeFn",
    "DigestRequest",
    "DigestResult",
    "IgnoreMatcher",
    "MANIFEST_FILENAME",
    "ManifestError",
    "SCHEMA_VERSION",
    "VALID_KINDS",
    "add_doc",
    "add_note",
    "add_repo",
    "allocate_id",
    "digest_repo",
    "find_entry",
    "index_path",
    "load_manifest",
    "make_digest_invoker",
    "manifest_path",
    "mark_stale_repos",
    "refresh",
    "remove",
    "render_index",
    "save_manifest",
    "slugify",
]
