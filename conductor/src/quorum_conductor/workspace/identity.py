"""Detect a sensible default human handle for a fresh workspace.

The previous v1 hardcoded `@human-rohan` (a leftover from the design
doc's worked examples). Real users want their own name on their moves.
We detect at `quorum init` time using a small fall-through:

  1. `QUORUM_HUMAN_HANDLE` env var if set (raw — caller's responsibility)
  2. `$USER` env var slugified (POSIX shells, macOS / Linux)
  3. `git config user.name` slugified (works on Windows too)
  4. fallback `@human`

Slug rules: lowercase, ASCII letters / digits / hyphens, runs of
non-alphanumerics collapse to a single hyphen, leading / trailing
hyphens stripped. The handle gets a `@human-` prefix so it's visually
distinct from agent handles like `@claude-opus`.
"""

from __future__ import annotations

import os
import re
import subprocess


def default_human_handle() -> str:
    """Return the best-guess `@human-…` handle for this user."""
    explicit = os.environ.get("QUORUM_HUMAN_HANDLE", "").strip()
    if explicit:
        # Caller-controlled override — accepted as-is, but ensure it
        # starts with @ so it round-trips through the participants table.
        return explicit if explicit.startswith("@") else f"@{explicit}"

    user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    slug = _slugify(user)
    if slug:
        return f"@human-{slug}"

    git_name = _try_git_user_name()
    slug = _slugify(git_name)
    if slug:
        return f"@human-{slug}"

    return "@human"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    if not name:
        return ""
    cleaned = _SLUG_RE.sub("-", name.lower()).strip("-")
    # Cap at 24 chars so the handle stays scannable in tables.
    return cleaned[:24]


def _try_git_user_name() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
