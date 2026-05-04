"""Digest a context repo into a one-page agent-readable summary.

A "digest" is what an agent reads when it wants to understand a
repo without opening every file. We delegate the actual reading
and summarising to a participant CLI (so we don't bake LLM access
into the conductor) — the conductor just orchestrates: pick a
repo, ask the configured digester participant to summarise it,
write the result to ``context/repos/<slug>/digest.md``, capture
the source's git HEAD so we can later detect drift.

This module is the *engine*. It does not know about the autoloop,
HTTP, or CLI — those layers (phase 3+) drive it. It takes a
pluggable invoke fn so tests can run end-to-end with a stub.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from quorum_conductor.core.participants import parse_participants

from .index import render_index
from .manifest import (
    CONTEXT_DIR,
    ContextEntry,
    ContextManifest,
    find_entry,
    load_manifest,
    save_manifest,
)
from .operations import slugify

# ---------------------------------------------------------------------- #
# Public API — the InvokeFn protocol mirrors the canvas dispatcher's so
# the same participant CLIs can be reused for digestion. Kept as its
# own pair (DigestRequest / DigestResult) to make it obvious in stack
# traces which layer ran the spawn.
# ---------------------------------------------------------------------- #


DIGEST_SYSTEM_PROMPT = """\
You are summarising a code repository for another AI participant
in a brainstorming workspace.

The repository is mounted at `{source}` (a symlink under
`context/repos/{slug}/source/`). Read enough of it to understand:

  - What the project is and what problem it solves.
  - The primary languages, frameworks, and entry points.
  - The high-level module / package layout — name the top-level
    folders and what each contains, in one or two lines each.
  - Any notable build / test / run commands (from README,
    package.json scripts, Makefile, etc.).

Respond with a single self-contained markdown document. Aim for
roughly one page (no more than ~400 words). Don't include
boilerplate like "Here's a summary"; just the summary.

Do not emit `artifact:` fenced blocks. Just write the digest as
your reply.
"""


@dataclass(frozen=True)
class DigestRequest:
    """What the digester hands to the invoke callable."""

    handle: str
    """Participant handle, e.g. ``@claude-opus``."""
    workspace: Path
    """Workspace root — agent is spawned here as cwd."""
    entry_id: str
    """Manifest id of the repo being digested."""
    slug: str
    """Slug used for ``context/repos/<slug>/`` paths."""
    source: Path
    """Resolved source root (the user's actual repo)."""
    prompt: str
    """Fully rendered prompt to feed via stdin."""


@dataclass(frozen=True)
class DigestResult:
    """Outcome of an invoke call."""

    body: str = ""
    error: str | None = None


DigestInvokeFn = Callable[[DigestRequest], DigestResult]
"""Pluggable invocation. Tests can pass a lambda; production wiring
uses :func:`make_digest_invoker`."""


# ---------------------------------------------------------------------- #
# Run
# ---------------------------------------------------------------------- #


class DigestError(RuntimeError):
    """Raised by :func:`digest_repo` for caller-fixable problems
    (no digester configured, entry doesn't exist, etc.). Invoke
    failures are reported via the manifest, not raised."""


def digest_repo(
    workspace: Path,
    entry_id: str,
    *,
    invoke: DigestInvokeFn,
    handle: str,
    now: datetime | None = None,
) -> ContextEntry:
    """Synchronously digest one repo.

    Loads the manifest, validates the entry is a repo, calls
    ``invoke`` with a digestion prompt, writes ``digest.md`` on
    success, and persists the updated entry. Returns the new entry.

    Failures from ``invoke`` are surfaced via the entry's
    ``digest_status="failed"`` and ``digest_error``; the manifest
    is still saved. The function does **not** raise on invoke
    failure — callers (CLI, HTTP) inspect the returned entry.
    """
    manifest = load_manifest(workspace)
    entry = find_entry(manifest, entry_id)
    if entry is None:
        raise DigestError(f"no entry with id {entry_id!r}")
    if entry.kind != "repo":
        raise DigestError(
            f"digestion only applies to repos; {entry_id} is a {entry.kind}"
        )
    if not handle.strip():
        raise DigestError("no digester handle configured")

    slug = slugify(entry.name)
    source = Path(entry.source)
    repo_root = workspace / CONTEXT_DIR / "repos" / slug
    repo_root.mkdir(parents=True, exist_ok=True)

    # Mark in-progress so concurrent reads see it (and the index
    # surfaces "running" rather than the stale prior status).
    in_progress = replace(entry, digest_status="running", digest_error="")
    manifest = _replace_entry(manifest, in_progress)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)

    prompt = DIGEST_SYSTEM_PROMPT.format(slug=slug, source=str(source))
    req = DigestRequest(
        handle=handle,
        workspace=workspace,
        entry_id=entry_id,
        slug=slug,
        source=source,
        prompt=prompt,
    )
    result = invoke(req)
    ts = now or datetime.now(UTC)

    if result.error is not None or not result.body.strip():
        failed = replace(
            in_progress,
            digest_status="failed",
            digest_error=result.error or "digester returned empty body",
            digest_at=ts,
        )
        manifest = _replace_entry(manifest, failed)
        save_manifest(workspace, manifest)
        render_index(workspace, manifest)
        return failed

    digest_path = repo_root / "digest.md"
    digest_path.write_text(result.body.rstrip() + "\n", encoding="utf-8")

    git_ref = _capture_git_ref(source)
    summary = _first_meaningful_line(result.body)

    succeeded = replace(
        in_progress,
        digest_status="ready",
        digest_summary=summary,
        digest_error="",
        digest_at=ts,
        source_git_ref=git_ref,
        stale=False,
    )
    manifest = _replace_entry(manifest, succeeded)
    save_manifest(workspace, manifest)
    render_index(workspace, manifest)
    return succeeded


# ---------------------------------------------------------------------- #
# Stale detection
# ---------------------------------------------------------------------- #


def mark_stale_repos(workspace: Path) -> ContextManifest:
    """Compare each repo entry's stored ``source_git_ref`` against the
    source's current HEAD. Flips ``stale`` on/off accordingly.

    Repos without a git history (or a missing source) are left as-is —
    we only flip the flag when we have a meaningful signal. Returns
    the updated manifest (and persists it if anything changed).
    """
    manifest = load_manifest(workspace)
    changed = False
    new_entries: list[ContextEntry] = []
    for e in manifest.entries:
        if e.kind != "repo" or not e.source_git_ref:
            new_entries.append(e)
            continue
        current = _capture_git_ref(Path(e.source))
        if not current:
            new_entries.append(e)
            continue
        should_be_stale = current != e.source_git_ref
        if should_be_stale != e.stale:
            new_entries.append(replace(e, stale=should_be_stale))
            changed = True
        else:
            new_entries.append(e)

    if not changed:
        return manifest
    updated = replace(manifest, entries=new_entries)
    save_manifest(workspace, updated)
    render_index(workspace, updated)
    return updated


# ---------------------------------------------------------------------- #
# Production invoke fn — spawns the participant CLI in workspace cwd.
# Mirrors `canvas.transport_adapter.make_invoker` but for digestion.
# ---------------------------------------------------------------------- #


DEFAULT_DIGEST_TIMEOUT_S = 600.0


def make_digest_invoker(
    *,
    timeout_s: float = DEFAULT_DIGEST_TIMEOUT_S,
) -> DigestInvokeFn:
    """Build the real invoke fn the digester uses in production.

    Looks up the participant in ``registers/participants.md``,
    spawns its ``cli_command`` with cwd = workspace, pipes the
    prompt into stdin, and returns the captured stdout.
    """

    def _invoke(req: DigestRequest) -> DigestResult:
        participants_path = req.workspace / "registers" / "participants.md"
        try:
            participants = parse_participants(participants_path)
        except Exception as e:
            return DigestResult(error=f"participants registry unreadable: {e}")

        match = next((p for p in participants if p.handle == req.handle), None)
        if match is None:
            return DigestResult(
                error=f"{req.handle} is not in the participants registry"
            )
        if not match.cli_command.strip():
            return DigestResult(error=f"{req.handle} has no cli_command configured")

        try:
            result = subprocess.run(
                shlex.split(match.cli_command),
                input=req.prompt,
                capture_output=True,
                text=True,
                cwd=str(req.workspace),
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return DigestResult(error=f"timed out after {timeout_s:.0f}s")
        except FileNotFoundError:
            return DigestResult(
                error=(
                    f"CLI binary not found for {req.handle} — "
                    f"check `cli_command` in registers/participants.md"
                )
            )
        except Exception as e:
            return DigestResult(error=f"spawn failed: {e}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "(no stderr output)"
            return DigestResult(error=f"exit {result.returncode}: {stderr[:200]}")

        return DigestResult(body=result.stdout)

    return _invoke


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _replace_entry(manifest: ContextManifest, entry: ContextEntry) -> ContextManifest:
    new_entries = [entry if e.id == entry.id else e for e in manifest.entries]
    return replace(manifest, entries=new_entries)


def _capture_git_ref(source: Path) -> str:
    """Return the source's current git HEAD, or ``""`` if not a git
    repo / git unavailable / source missing."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(source),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _first_meaningful_line(body: str) -> str:
    """Pluck a one-line summary from the digest body (first non-empty
    non-heading line, trimmed). Used for the manifest's
    ``digest_summary`` field — what the index renders inline."""
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line[:200]
    return ""
