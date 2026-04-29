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

    # 3. Pending human moves? Prompt to act on them in the workspace.
    if summary.inbox_pending_count > 0:
        actions.append(
            NextAction(
                id="answer-inbox",
                title=f"You have {summary.inbox_pending_count} pending move(s) waiting on you",
                description=(
                    "Open the deliberation tagged in your inbox and use 'Compose move' to "
                    "respond. The loop pauses on these until you author the next move."
                ),
                kind="info",
                severity="blocking",
                primary=not actions,
            )
        )

    # 4. Deliberations exist + workspace is INITIALIZED + at least one
    # healthy agent → kick the loop.
    if (
        summary.deliberation_count > 0
        and summary.state.state.value == "INITIALIZED"
        and healthy_count > 0
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
                title="Add a repo or document for grounding",
                description=(
                    "Agents read everything registered under `context/`. Add a repo "
                    "with `quorum context add-repo <path>` or a doc with "
                    "`quorum context add-doc <path>`."
                ),
                kind="cli",
                severity="suggested",
                payload="quorum context add-repo .",
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
