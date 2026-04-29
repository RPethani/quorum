"""Repo / document digestion via an agent invocation.

Per design-doc §1.8 each context source is digested once at setup and
the digest gets reused by every later invocation. Digestion is itself
an agent invocation — relevance-tiered:

    relevance: high   → top-tier reasoning model (default `@claude-opus`)
    relevance: medium → mid-tier (default `@claude-sonnet`)
    relevance: low    → cheap model (default `@claude-haiku`)

Bulk overrides live in `config.yaml` under `context.digester_defaults`.
This module:

  * resolves which handle to digest with (config → routing-defaults
    → fallback to first available `cli` handle),
  * renders the digester prompt (the agent receives a focused brief
    rather than the workspace's full standing prompt),
  * spawns the subprocess via the existing transport.invoker._spawn
    and writes the digest to disk,
  * never raises on ordinary failure modes — returns a structured
    `DigestionResult`.

The standing prompt is *not* sent to a digester invocation. Digestion
is its own job with its own contract; conflating it with the
move-producing prompt produces confusing output.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml

from .config import WorkspaceConfig
from .participants import Participant

_RELEVANCE_DEFAULTS: dict[str, str] = {
    "high": "@claude-opus",
    "medium": "@claude-sonnet",
    "low": "@claude-haiku",
}

_REPO_DIGEST_PROMPT = """\
You are a context-digester for the Quorum collaboration system. Produce a
short, structured Markdown digest of the local code repository at the
path below. Subsequent agents will read this digest as their primary
view of the repo, so it must be accurate and useful, not exhaustive.

Repository path: {path}
Role descriptor (one-liner provided by the user): {role}
Relevance level: {relevance}

Your digest must use exactly these top-level sections (Markdown H2):

## Architecture overview

One or two paragraphs naming the major components and how they
relate. No code; prose.

## File tree (annotated)

A concise list of the most important files and directories with a
one-line note on what each is for. Skip vendored / generated / test
fixture content unless central. Use indented bullets for nesting.

## Key entry points

Where reading should start. Specific files and (optionally) line
ranges. One bullet per entry point.

## Important interfaces

Public types / endpoints / contracts that downstream code or other
repos depend on. One bullet each.

## Conventions and idioms

How this repo is written: naming, error-handling style, async vs sync,
dependency-injection pattern, test-layout, etc. Bullet list.

## Places to be careful

Subtle bugs, foot-guns, hand-built invariants, "this looks generic but
isn't" code paths. Bullet list. Be specific.

## What this digest does NOT cover

Areas you skipped, or where your sample of files was too thin. Required
section — write "nothing material" only if you genuinely covered the
whole repo.

Constraints:
- Output ONLY the Markdown digest. No preamble, no fenced code blocks
  wrapping the response, no follow-up instructions.
- Length budget: ≤2000 words for `medium`/`low` relevance; ≤3500 words
  for `high`.
- Read source files inside the repo path on-demand. Do not read
  outside the repo.
"""


@dataclass(frozen=True)
class RepoSpec:
    name: str  # workspace-local short name; used as folder under context/repos/
    path: Path  # absolute path to the repo on disk
    role: str  # user-supplied one-liner ("user-facing web app; React, TS")
    relevance: Literal["high", "medium", "low"]


@dataclass(frozen=True)
class DigestionResult:
    status: Literal["ok", "subprocess_failed", "timeout", "no_handle"]
    digester_handle: str | None
    digest_path: Path | None
    duration_s: float
    return_code: int | None
    error: str | None


def resolve_digester(
    relevance: str,
    config: WorkspaceConfig,
    participants: list[Participant],
) -> Participant | None:
    """Pick a digester handle for `relevance`.

    Priority:
      1. config.yaml override (`context.digester_defaults.<relevance>`)
      2. canonical default per `_RELEVANCE_DEFAULTS`
      3. first available `cli`-transport handle in participants

    Returns None if no usable handle is registered.
    """
    overrides = (config.extras.get("context") or {}).get("digester_defaults") or {}
    by_handle = {p.handle: p for p in participants}

    candidate = overrides.get(relevance) if isinstance(overrides, dict) else None
    if candidate and candidate in by_handle:
        p = by_handle[candidate]
        if p.transport == "cli" and p.health.lower() != "red":
            return p

    canonical = _RELEVANCE_DEFAULTS.get(relevance)
    if canonical and canonical in by_handle:
        p = by_handle[canonical]
        if p.transport == "cli" and p.health.lower() != "red":
            return p

    for p in participants:
        if p.transport == "cli" and p.health.lower() != "red":
            return p
    return None


def digest_repo(
    spec: RepoSpec,
    digester: Participant,
    target_dir: Path,
    *,
    timeout_s: float = 600.0,
) -> DigestionResult:
    """Invoke `digester` to produce a digest for `spec`. Synchronous.

    Writes `target_dir/digest.md` and `target_dir/meta.yaml` on success.
    Never raises for ordinary failures.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    prompt = _REPO_DIGEST_PROMPT.format(
        path=spec.path, role=spec.role, relevance=spec.relevance
    )
    cmd = shlex.split(digester.cli_command)
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            cwd=str(spec.path),
        )
    except subprocess.TimeoutExpired:
        return DigestionResult(
            status="timeout",
            digester_handle=digester.handle,
            digest_path=None,
            duration_s=(datetime.now(UTC) - started).total_seconds(),
            return_code=None,
            error=f"digestion timed out after {timeout_s}s",
        )
    except FileNotFoundError as exc:
        return DigestionResult(
            status="subprocess_failed",
            digester_handle=digester.handle,
            digest_path=None,
            duration_s=(datetime.now(UTC) - started).total_seconds(),
            return_code=None,
            error=f"command not on PATH: {exc.filename}",
        )

    duration = (datetime.now(UTC) - started).total_seconds()
    if proc.returncode != 0:
        return DigestionResult(
            status="subprocess_failed",
            digester_handle=digester.handle,
            digest_path=None,
            duration_s=duration,
            return_code=proc.returncode,
            error=(proc.stderr or "").strip() or f"digester exited with code {proc.returncode}",
        )

    digest_path = target_dir / "digest.md"
    meta_path = target_dir / "meta.yaml"
    digest_path.write_text(proc.stdout, encoding="utf-8")
    meta_path.write_text(
        yaml.safe_dump(
            {
                "name": spec.name,
                "source_path": str(spec.path),
                "role": spec.role,
                "relevance": spec.relevance,
                "digester": digester.handle,
                "last_digested_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "digest_chars": len(proc.stdout),
            },
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return DigestionResult(
        status="ok",
        digester_handle=digester.handle,
        digest_path=digest_path,
        duration_s=duration,
        return_code=proc.returncode,
        error=None,
    )
