"""Compute the user's next-best actions from current workspace state.

The UI surfaces these as a persistent "What's next" panel. We've twice
been bitten by independent if-blocks emitting actions that contradict
each other (e.g. "you have a pending move" alongside "start the
loop"). The fix is structural: collapse all the signals into a single
`WorkspacePhase` first, then let each phase emit only the actions
that are coherent with it. Suggestions and blockers can never argue.

Adding a new action means picking a phase (or set) it applies to —
not adding a new top-level if-block.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
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
    payload: str | None = None
    primary: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = asdict(self)
        if self.payload is None:
            d.pop("payload", None)
        return d


class WorkspacePhase(Enum):
    """The single dimension every banner decision branches on.

    Ordered by precedence — the resolver returns the first matching
    phase. So "needs setup" wins over "needs agent" wins over "needs
    digestion" wins over "awaiting human" etc. Lower-priority phases
    are only reached when everything more urgent is clear.
    """

    NEEDS_SETUP = "needs_setup"
    NEEDS_AGENT = "needs_agent"
    AGENTS_UNREACHABLE = "agents_unreachable"
    NEEDS_DIGESTION = "needs_digestion"
    AWAITING_PERMISSION = "awaiting_permission"
    AWAITING_HUMAN = "awaiting_human"
    READY_TO_RUN = "ready_to_run"
    RUNNING = "running"
    # The bootstrapper deliberation is DECIDED but the manifest itself
    # hasn't been written. The user needs to ratify the proposed
    # manifest into outcome-manifest.md before real work can start.
    NEEDS_MANIFEST_RATIFICATION = "needs_manifest_ratification"
    # Manifest is ratified but no follow-up deliberations exist. The
    # user needs to start a deliberation on the first artifact.
    NEEDS_FIRST_DELIBERATION = "needs_first_deliberation"
    IDLE = "idle"


@dataclass(frozen=True)
class _Signals:
    """Snapshot of the cheap-to-compute signals the resolver needs."""

    statement_empty: bool
    deliberation_count: int
    state_value: str
    cli_count: int
    healthy_count: int
    unhealthy: list[str]
    pending_digests: int
    pending_urls: int
    pending_permissions: int
    # Deliberation IDs where the planner's next-actor is a
    # manual-transport handle (i.e. the human really is blocking work).
    # NOT the same as inbox pending lines, which include FYI tags.
    human_blocker_ids: list[str]
    has_context: bool
    seed_decided: bool  # bootstrapper deliberation #0001 reached DECIDED
    manifest_status: str  # DRAFTING | READY | LOCKED
    non_seed_deliberation_count: int


def compute_next_actions(paths: WorkspacePaths) -> list[NextAction]:
    """Return ordered next-best actions for the workspace at `paths`."""
    signals = _gather_signals(paths)
    phase = _resolve_phase(signals)
    return _actions_for(phase, signals)


def compute_phase(paths: WorkspacePaths) -> WorkspacePhase:
    """Public phase resolver — useful for tests and other UI surfaces."""
    return _resolve_phase(_gather_signals(paths))


# ---------------------------------------------------------------------- #
# Phase resolution
# ---------------------------------------------------------------------- #


def _resolve_phase(s: _Signals) -> WorkspacePhase:
    if s.statement_empty and s.deliberation_count == 0:
        return WorkspacePhase.NEEDS_SETUP
    if s.cli_count == 0:
        return WorkspacePhase.NEEDS_AGENT
    if s.healthy_count == 0:
        return WorkspacePhase.AGENTS_UNREACHABLE
    if s.pending_digests + s.pending_urls > 0:
        return WorkspacePhase.NEEDS_DIGESTION
    if s.pending_permissions > 0:
        return WorkspacePhase.AWAITING_PERMISSION
    if s.human_blocker_ids:
        return WorkspacePhase.AWAITING_HUMAN
    if s.deliberation_count > 0 and s.state_value == "INITIALIZED":
        return WorkspacePhase.READY_TO_RUN
    # Workspace started, seed deliberation closed, manifest still
    # DRAFTING → the user needs to ratify the manifest content into
    # outcome-manifest.md before real work can start.
    if s.seed_decided and s.manifest_status == "DRAFTING":
        return WorkspacePhase.NEEDS_MANIFEST_RATIFICATION
    # NEEDS_FIRST_DELIBERATION is no longer reachable in normal flow:
    # `workspace/auto_advance.py` opens the first artifact's
    # deliberation as soon as the manifest is LOCKED. We keep the phase
    # for migration cases where auto-advance failed (e.g. malformed
    # manifest body that yields no artifact filenames). When that
    # happens the user will see the original "start the first
    # deliberation" banner — a real failure mode worth surfacing.
    if (
        s.seed_decided
        and s.manifest_status in {"READY", "LOCKED"}
        and s.non_seed_deliberation_count == 0
    ):
        return WorkspacePhase.NEEDS_FIRST_DELIBERATION
    if s.state_value == "ACTIVE":
        return WorkspacePhase.RUNNING
    return WorkspacePhase.IDLE


def _actions_for(phase: WorkspacePhase, s: _Signals) -> list[NextAction]:
    """Render the action list that's coherent with `phase`.

    Each branch returns a small, ordered list. Suggestions
    (severity=suggested) only appear in phases where they make
    sense — never while a higher-priority blocker is active.
    """
    if phase is WorkspacePhase.NEEDS_SETUP:
        return [
            NextAction(
                id="run-setup",
                title="Tell Quorum what you're working on",
                description=(
                    "Open the setup dialog to enter a problem statement, pick a "
                    "manifest template, and choose your involvement level. The "
                    "loop can't make progress until this is done."
                ),
                kind="dialog",
                severity="blocking",
                payload="setup",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.NEEDS_AGENT:
        return [
            NextAction(
                id="register-handle",
                title="Add an AI agent to collaborate with",
                description=(
                    "Collaboration can't start without at least one agent. Pick the "
                    "CLI you have access to (Claude, Codex, …) and Quorum will "
                    "register it for you."
                ),
                kind="dialog",
                severity="blocking",
                payload="add-agent",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.AGENTS_UNREACHABLE:
        bad_summary = ", ".join(s.unhealthy[:3]) + ("…" if len(s.unhealthy) > 3 else "")
        return [
            NextAction(
                id="verify-agents",
                title="Your agent(s) aren't reachable",
                description=(
                    f"Quorum tried to verify {bad_summary} but the configured CLI "
                    "isn't on PATH. Open Settings → Participants to fix the "
                    "cli_command field, install the tool, or re-add the agent."
                ),
                kind="dialog",
                severity="blocking",
                payload="settings",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.NEEDS_DIGESTION:
        bits: list[str] = []
        if s.pending_digests:
            bits.append(
                f"{s.pending_digests} digest{'s' if s.pending_digests != 1 else ''}"
            )
        if s.pending_urls:
            bits.append(
                f"{s.pending_urls} URL fetch{'es' if s.pending_urls != 1 else ''}"
            )
        return [
            NextAction(
                id="digest-context",
                title="Context needs processing before agents can use it",
                description=(
                    f"Pending: {', '.join(bits)}. Open the Digestion panel to pick "
                    "a model and kick off summarisation; URLs auto-fetch on add "
                    "but may need a manual refresh. Runs in the background."
                ),
                kind="dialog",
                severity="blocking",
                payload="digestion",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.AWAITING_PERMISSION:
        return [
            NextAction(
                id="permissions-pending",
                title=(
                    f"{s.pending_permissions} permission "
                    f"request{'s' if s.pending_permissions != 1 else ''} waiting on you"
                ),
                description=(
                    "An agent asked to run a tool outside its allowlist. Open the "
                    "Permissions panel to approve or deny."
                ),
                kind="dialog",
                severity="blocking",
                payload="permissions",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.AWAITING_HUMAN:
        ids_summary = ", ".join(f"#{d}" for d in s.human_blocker_ids[:3]) + (
            "…" if len(s.human_blocker_ids) > 3 else ""
        )
        return [
            NextAction(
                id="answer-inbox",
                title=(
                    f"Your move on {ids_summary} — "
                    f"{len(s.human_blocker_ids)} deliberation"
                    f"{'s' if len(s.human_blocker_ids) != 1 else ''} waiting on you"
                ),
                description=(
                    "The loop has reached a point where the next move is yours "
                    "(typically a DECISION or an ANSWER). Open the deliberation "
                    "and click the 'Your turn' callout at the top — Compose move "
                    "is pre-selected with the correct move type."
                ),
                kind="info",
                severity="blocking",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.NEEDS_MANIFEST_RATIFICATION:
        return [
            NextAction(
                id="ratify-manifest",
                title="Ratify the manifest the bootstrapper proposed",
                description=(
                    "Deliberation #0001 was decided, but outcome-manifest.md "
                    "is still DRAFTING. Open the Raw editor → "
                    "outcome-manifest.md and paste the manifest content from "
                    "the seed deliberation's PROPOSAL/SYNTHESIS, then change "
                    "`status: DRAFTING` to `status: READY`. Real work begins "
                    "after that."
                ),
                kind="dialog",
                severity="blocking",
                payload="raw-editor",
                primary=True,
            )
        ]

    if phase is WorkspacePhase.NEEDS_FIRST_DELIBERATION:
        return [
            NextAction(
                id="start-first-deliberation",
                title="Start the first deliberation on a manifest artifact",
                description=(
                    "The manifest is ratified. Pick the first artifact you want "
                    "the agents to work on and open a deliberation for it. "
                    "Click 'New deliberation' in the workspace header to "
                    "create one."
                ),
                kind="dialog",
                severity="blocking",
                payload="new-deliberation",
                primary=True,
            )
        ]

    # READY_TO_RUN / RUNNING / IDLE — no blocker, only suggestions.
    out: list[NextAction] = []
    if phase is WorkspacePhase.READY_TO_RUN:
        out.append(
            NextAction(
                id="start-loop",
                title="Start the conductor loop",
                description=(
                    "There's a seed deliberation ready. Run a single step from the "
                    "in-app shell, or daemonise the loop with `quorum start`."
                ),
                kind="cli",
                severity="suggested",
                payload="/step",
                primary=True,
            )
        )
    if not s.has_context:
        out.append(
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
    return out


# ---------------------------------------------------------------------- #
# Signals — gather once per request
# ---------------------------------------------------------------------- #


def _gather_signals(paths: WorkspacePaths) -> _Signals:
    summary = status_summary(paths)
    cli_count, healthy_count, unhealthy = _cli_health_counts(paths)
    pending_digests, pending_urls = _undigested_counts(paths)
    seed_decided, non_seed_count = _seed_and_followup_counts(paths)
    return _Signals(
        statement_empty=_file_empty(paths.problem_statement),
        deliberation_count=summary.deliberation_count,
        state_value=summary.state.state.value,
        cli_count=cli_count,
        healthy_count=healthy_count,
        unhealthy=unhealthy,
        pending_digests=pending_digests,
        pending_urls=pending_urls,
        pending_permissions=_pending_permission_count(paths),
        human_blocker_ids=_human_blocker_ids(paths),
        has_context=_has_context(paths),
        seed_decided=seed_decided,
        manifest_status=_manifest_status(paths),
        non_seed_deliberation_count=non_seed_count,
    )


def _manifest_status(paths: WorkspacePaths) -> str:
    """Read the `status:` field from outcome-manifest.md frontmatter.

    Returns `DRAFTING` (the safe default) on any read or parse error.
    """
    if not paths.outcome_manifest.is_file():
        return "DRAFTING"
    try:
        text = paths.outcome_manifest.read_text(encoding="utf-8")
    except OSError:
        return "DRAFTING"
    import re

    m = re.search(r"^status:\s*(\S+)\s*$", text, re.MULTILINE)
    if not m:
        return "DRAFTING"
    return m.group(1).upper()


def _seed_and_followup_counts(paths: WorkspacePaths) -> tuple[bool, int]:
    """Return (seed_decided, count of non-seed deliberations).

    The "seed" is deliberation #0001 if it ratifies outcome-manifest.md.
    `seed_decided` is True when its file's frontmatter is in a terminal
    state (DECIDED or ABANDONED). non_seed_count is the number of
    deliberations other than the seed.
    """
    from .deliberation import load_deliberation

    seed_decided = False
    non_seed = 0
    if not paths.deliberations.is_dir():
        return False, 0
    for path in paths.deliberations.glob("*.md"):
        try:
            meta = load_deliberation(path)
        except Exception:
            continue
        is_seed = meta.id == "0001" and (
            str(meta.extras.get("ratifies", "") or "").strip().lower()
            == "outcome-manifest.md"
        )
        if is_seed:
            if meta.status.upper() in {"DECIDED", "ABANDONED"}:
                seed_decided = True
        else:
            non_seed += 1
    return seed_decided, non_seed


def _human_blocker_ids(paths: WorkspacePaths) -> list[str]:
    """Return deliberation IDs whose next planner-action is on the human.

    This is the source of truth for "really blocked on you" — distinct
    from inbox-pending lines which also include FYI tags from agents
    notifying the decider that work happened.
    """
    from .loop import plan as _plan

    try:
        result = _plan(paths)
    except Exception:
        return []
    return [item.deliberation.id for item in result.items if item.is_manual]


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _file_empty(path: object) -> bool:
    from pathlib import Path

    p = path if isinstance(path, Path) else Path(str(path))
    if not p.is_file():
        return True
    text = p.read_text(encoding="utf-8").strip()
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
    """Return the raw pending lines from the human's inbox."""
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


def _pending_permission_count(paths: WorkspacePaths) -> int:
    from .permissions import list_requests

    try:
        return sum(1 for r in list_requests(paths) if r.status.value == "pending")
    except Exception:
        return 0


def _undigested_counts(paths: WorkspacePaths) -> tuple[int, int]:
    """Count context entries that aren't yet usable.

    Side-effect: backfills `tokens_estimated` / `needs_digest` on doc
    entries that pre-date the extraction logic.
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
        if "tokens_estimated" not in d or "needs_digest" not in d:
            stored = paths.context_docs / "raw" / f"{name}.md"
            if not stored.is_file():
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
    return any(bool(manifest.get(k)) for k in ("repos", "docs", "urls", "notes"))


__all__ = ["NextAction", "WorkspacePhase", "compute_next_actions", "compute_phase"]
