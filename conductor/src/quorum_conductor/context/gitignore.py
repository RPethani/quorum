"""Combined `.gitignore` + `.contextignore` matcher.

Per `docs-specs/context-seeding.md` Q2 + Q10:

- For repo entries, the digester (and any agent reading
  ``context/repos/<slug>/source/``) skips files that match either:
    * the repo's own ``.gitignore`` chain, or
    * Quorum's `.contextignore` (a default list of generally-noisy
      directories like ``node_modules/``, ``.git/``, ``dist/`` …
      with an optional per-workspace override at
      ``<workspace>/context/.contextignore``).

- This module is the single source of truth for that matching.
  Callers ask it ``should_skip(path)`` and forget the rest.

We use the well-tested `pathspec` library so we get full git-style
glob semantics (``**``, leading-slash anchors, trailing-slash
"directory only", negation with ``!``…) without rolling our own.
"""

from __future__ import annotations

from pathlib import Path

import pathspec

# Default `.contextignore` patterns — applied to every repo entry on
# top of whatever the source repo's own `.gitignore` says. Keep this
# list short and conservative; users can add more via the
# per-workspace override at `<workspace>/context/.contextignore`.
DEFAULT_PATTERNS: tuple[str, ...] = (
    # VCS metadata
    ".git/",
    ".hg/",
    ".svn/",
    # Editor / OS clutter
    ".DS_Store",
    ".idea/",
    ".vscode/",
    # JS / TS
    "node_modules/",
    "dist/",
    "build/",
    ".next/",
    ".turbo/",
    ".cache/",
    # Python
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "venv/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    # Misc
    "coverage/",
    ".tox/",
    ".nyc_output/",
    "target/",
)

CONTEXTIGNORE_FILENAME = ".contextignore"
GITIGNORE_FILENAME = ".gitignore"


class IgnoreMatcher:
    """Pre-compiled matcher for one source root.

    Construct with `IgnoreMatcher.for_repo(source_root, workspace)`
    so the right `.gitignore` / `.contextignore` files are
    discovered automatically. Then call ``should_skip(path)`` for
    every candidate path *relative to the source root*.
    """

    def __init__(self, spec: pathspec.PathSpec):
        self._spec = spec

    @classmethod
    def for_repo(cls, source_root: Path, workspace: Path | None = None) -> "IgnoreMatcher":
        patterns: list[str] = list(DEFAULT_PATTERNS)
        # Per-workspace override: more entries (or negations) the user
        # wants applied to *all* their context repos.
        if workspace is not None:
            override = workspace / "context" / CONTEXTIGNORE_FILENAME
            if override.is_file():
                patterns += _read_pattern_lines(override)
        # The source repo's own `.gitignore`.
        repo_ignore = source_root / GITIGNORE_FILENAME
        if repo_ignore.is_file():
            patterns += _read_pattern_lines(repo_ignore)
        spec = pathspec.GitIgnoreSpec.from_lines(patterns)
        return cls(spec)

    def should_skip(self, relative_path: str) -> bool:
        """Return ``True`` if ``relative_path`` (POSIX style, relative
        to the source root) matches any active ignore pattern."""
        # pathspec's match_file expects forward slashes; callers
        # passing Windows-style separators won't see a match.
        return self._spec.match_file(relative_path)


def _read_pattern_lines(path: Path) -> list[str]:
    """Read a gitignore-shaped file, stripping comments / blank lines.

    We *don't* normalise the patterns here — pathspec handles the full
    syntax (negation with ``!``, trailing slash for dir-only, etc.)
    so we can pass them through verbatim.
    """
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out
