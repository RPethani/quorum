"""Compute the user's next-best actions from current workspace state.

The UI surfaces these as a persistent "What's next" panel so first-time
users aren't lost. Each action carries a short title, a longer
description, and either a UI hint (open a dialog) or a CLI command
the user can copy / paste / run from the in-app shell.

The rules are deliberately simple and ordered: the first action whose
condition matches is the *primary* one; the rest are supplementary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..paths import WorkspacePaths
from ..workspace.status import status_summary

ActionKind = Literal["dialog", "cli", "info"]
ActionSeverity = Literal["blocking", "suggested", "info"]


@dataclass(frozen=True)
class NextAction:
    """One actionable suggestion to surface in the UI.

    `severity` drives the visual treatment:
      * "blocking"  — collaboration cannot start / continue until this
        is resolved. UI renders this as a prominent amber banner.
      * "suggested" — useful but not required. UI renders these as a
        slim collapsible strip.
      * "info"      — passive nudge with no action button.
    """

    id: str
    title: str
    description: str
    kind: ActionKind
    severity: ActionSeverity = "suggested"
    # For kind="dialog": a string the UI maps to a known modal id.
    # For kind="cli": a copy-paste-friendly command (CLI or slash form).
    # For kind="info": no payload, just the description.
    payload: str | None = None
    primary: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = asdict(self)
        if self.payload is None:
            d.pop("payload", None)
        return d


def compute_next_actions(paths: WorkspacePaths) -> list[NextAction]:
    """Return ordered next-best actions for the workspace at `paths`."""
    summary = status_summary(paths)
    actions: list[NextAction] = []

    # 1. Problem statement empty? Always prompt for setup first.
    statement_empty = _file_empty(paths.problem_statement)
    if statement_empty and summary.deliberation_count == 0:
        actions.append(
            NextAction(
                id="run-setup",
                title="Tell Quorum what you're working on",
                description=(
                    "Open the setup dialog to enter a problem statement, pick a manifest "
                    "template, and choose your involvement level. The loop can't make "
                    "progress until this is done."
                ),
                kind="dialog",
                severity="blocking",
                payload="setup",
                primary=True,
            )
        )

    # 2. No CLI participants registered → loop can't make autonomous progress.
    cli_count, healthy_count, unhealthy = _cli_health_counts(paths)
    if cli_count == 0:
        actions.append(
            NextAction(
                id="register-handle",
                title="Add an AI agent to collaborate with",
                description=(
                    "Collaboration can't start without at least one agent. Pick the "
                    "CLI you have access to (Claude, Codex, …) and Quorum will register "
                    "it for you."
                ),
                kind="dialog",
                severity="blocking",
                payload="add-agent",
                primary=not actions,
            )
        )
    elif healthy_count == 0:
        # Have rows in participants.md, but none of their CLIs are on PATH.
        # The loop will fail on the first invocation; block until verified.
        bad_summary = ", ".join(unhealthy[:3]) + ("…" if len(unhealthy) > 3 else "")
        actions.append(
            NextAction(
                id="verify-agents",
                title="Your agent(s) aren't reachable",
                description=(
                    f"Quorum tried to verify {bad_summary} but the configured CLI "
                    "isn't on PATH. Open Settings → Participants to fix the cli_command "
                    "field, install the tool, or re-add the agent with the correct command."
                ),
                kind="dialog",
                severity="blocking",
                payload="settings",
                primary=not actions,
            )
        )

    # 3. Pending HUMAN moves? Prompt to act on them in the workspace.
    # `summary.inbox_pending_count` counts all inbox files with content
    # (one per participant). For the human-facing action we only care
    # about the rows tagged at the human's handle.
    pending_for_human = _count_human_pending(paths)
    if pending_for_human:
        delib_ids = sorted({line.split("#")[1].split(" ")[0] for line in pending_for_human})
        ids_summary = ", ".join(f"#{d}" for d in delib_ids[:3]) + (
            "…" if len(delib_ids) > 3 else ""
        )
        actions.append(
            NextAction(
                id="answer-inbox",
                title=(
                    f"You have {len(pending_for_human)} pending "
                    f"move(s) on {ids_summary}"
                ),
                description=(
                    "Click the deliberation in the left panel, read the latest "
                    "PROPOSAL/CRITIQUE, then click 'Compose move' to respond. The "
                    "loop pauses here until you author the next move."
                ),
                kind="info",
                severity="blocking",
                primary=not actions,
            )
        )

    # 3b. Context that hasn't been processed yet blocks the loop's first
    # real work — agents read digests/cached fetches, not raw source
    # (design-doc §1.8). Surface as blocking until cleared.
    pending_digests, pending_urls = _undigested_counts(paths)
    pending_total = pending_digests + pending_urls
    if pending_total > 0:
        bits: list[str] = []
        if pending_digests:
            bits.append(f"{pending_digests} digest{'s' if pending_digests != 1 else ''}")
        if pending_urls:
            bits.append(f"{pending_urls} URL fetch{'es' if pending_urls != 1 else ''}")
        actions.append(
            NextAction(
                id="digest-context",
                title="Context needs processing before agents can use it",
                description=(
                    f"Pending: {', '.join(bits)}. Open the Digestion panel to "
                    "pick a model and kick off summarisation; URLs auto-fetch on add but "
                    "may need a manual refresh. Runs in the background."
                ),
                kind="dialog",
                severity="blocking",
                payload="digestion",
                primary=not actions,
            )
        )

    # 4. Deliberations exist + workspace is INITIALIZED + at least one
    # healthy agent → kick the loop. (Suppressed if any context still
    # needs processing above.)
    if (
        summary.deliberation_count > 0
        and summary.state.state.value == "INITIALIZED"
        and healthy_count > 0
        and pending_total == 0
    ):
        actions.append(
            NextAction(
                id="start-loop",
                title="Start the conductor loop",
                description=(
                    "There's a seed deliberation ready. Run a single step from the in-app "
                    "shell, or daemonise the loop with `quorum start`."
                ),
                kind="cli",
                severity="suggested",
                payload="/step",
                primary=not actions,
            )
        )

    # 5. Always-available: add context to ground the agents.
    if cli_count > 0 and not _has_context(paths):
        actions.append(
            NextAction(
                id="add-context",
                title="Add a repo, doc, note, or URL for grounding",
                description=(
                    "Agents read everything you register here. Open the Context "
                    "panel to attach a local repo, paste a problem statement, or "
                    "drop reference URLs."
                ),
                kind="dialog",
                severity="suggested",
                payload="context",
            )
        )

    # No "all-clear" filler — when there's nothing to suggest, return [] so
    # the UI hides the panel completely. Less is more when collab is humming.
    return actions


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _file_empty(path: object) -> bool:
    from pathlib import Path

    p = path if isinstance(path, Path) else Path(str(path))
    if not p.is_file():
        return True
    text = p.read_text(encoding="utf-8").strip()
    # Skip the heading scaffold line if it's the only content.
    return not text or text.startswith("# Problem Statement\n\n## What I'm trying to figure out")


def _count_cli_participants(paths: WorkspacePaths) -> int:
    """Legacy helper retained for callers outside this module."""
    cli, _healthy, _bad = _cli_health_counts(paths)
    return cli


def _cli_health_counts(paths: WorkspacePaths) -> tuple[int, int, list[str]]:
    """Return (cli_count, healthy_count, unhealthy_handles).

    Calls into the doctor's PATH probe — fast (just `shutil.which`)
    so it's fine to do on every next-actions request.
    """
    from ..transport.doctor import doctor_check

    cli_count = 0
    healthy = 0
    unhealthy: list[str] = []
    for h in doctor_check(paths):
        if h.transport != "cli":
            continue
        cli_count += 1
        if h.on_path is True:
            healthy += 1
        else:
            unhealthy.append(h.handle)
    return cli_count, healthy, unhealthy


def _count_human_pending(paths: WorkspacePaths) -> list[str]:
    """Return the raw pending lines from the human's inbox.

    Identifies the human as the first manual-transport participant.
    Each line is expected to look like
        `- pending: PROPOSAL in #0001 by @claude-opus (...)`
    so callers can also extract deliberation IDs from the same list.
    """
    from .participants import parse_participants

    human: str | None = None
    if paths.participants.is_file():
        try:
            for p in parse_participants(paths.participants):
                if p.transport == "manual":
                    human = p.handle
                    break
        except Exception:
            return []
    if human is None:
        return []
    inbox_file = paths.inbox / f"{human}.md"
    if not inbox_file.is_file():
        return []
    return [
        line.strip()
        for line in inbox_file.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- pending:")
    ]


def _undigested_counts(paths: WorkspacePaths) -> tuple[int, int]:
    """Count context entries that aren't yet usable.

    Returns (digests_pending, urls_pending) where:

      * digests_pending — repos missing digest.md OR docs flagged
        `needs_digest=True` whose digested/<name>.md is missing.
      * urls_pending — URL entries whose cached/<name>.md is missing
        (failed fetch, or refresh needed).

    Side-effect: backfills `tokens_estimated` / `needs_digest` on doc
    entries that pre-date the extraction logic, so legacy adds get
    surfaced in the next-actions banner without forcing a re-add.
    """
    from .context_bundle import load_context_manifest, save_context_manifest
    from .context_extract import DOC_DIGEST_TOKEN_THRESHOLD, estimate_tokens

    try:
        manifest = load_context_manifest(paths)
    except Exception:
        return 0, 0
    digests = 0
    urls_missing = 0
    docs_dirty = False
    for r in manifest.get("repos") or []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name", "")).strip()
        if not name:
            continue
        if not (paths.context_repos / name / "digest.md").is_file():
            digests += 1
    for d in manifest.get("docs") or []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name", "")).strip()
        if not name:
            continue
        # Backfill metadata for legacy entries.
        if "tokens_estimated" not in d or "needs_digest" not in d:
            stored = paths.context_docs / "raw" / f"{name}.md"
            if not stored.is_file():
                # Try the legacy "raw/<name>.<ext>" naming too.
                candidates = list((paths.context_docs / "raw").glob(f"{name}.*"))
                stored = candidates[0] if candidates else stored
            if stored.is_file():
                try:
                    text = stored.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                if text:
                    tokens = estimate_tokens(text)
                    d["tokens_estimated"] = tokens
                    d["needs_digest"] = tokens >= DOC_DIGEST_TOKEN_THRESHOLD
                    docs_dirty = True
        if not bool(d.get("needs_digest")):
            continue
        if not (paths.context_docs / "digested" / f"{name}.md").is_file():
            digests += 1
    for u in manifest.get("urls") or []:
        if not isinstance(u, dict):
            continue
        name = str(u.get("name", "")).strip()
        if not name:
            continue
        if not (paths.context_web / "cached" / f"{name}.md").is_file():
            urls_missing += 1
    if docs_dirty:
        save_context_manifest(paths, manifest)
    return digests, urls_missing


def _has_context(paths: WorkspacePaths) -> bool:
    from .context_bundle import load_context_manifest

    try:
        manifest = load_context_manifest(paths)
    except Exception:
        return False
    return any(
        bool(manifest.get(k))
        for k in ("repos", "docs", "urls", "notes")
    )


__all__ = ["NextAction", "compute_next_actions"]
