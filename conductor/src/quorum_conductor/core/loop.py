"""The conductor's planning loop.

Pure-data API: given the workspace's deliberations, participants,
config, and routing defaults, return the list of items the runner
should invoke next.

The planner is intentionally simple — it walks the protocol's role flow
per deliberation:

  OPEN deliberation, no PROPOSAL          → schedule proposer for PROPOSAL
  OPEN/IN_REVIEW with PROPOSAL but        → schedule each missing critic for CRITIQUE
   not all critics have CRITIQUE'd
  IN_REVIEW with full PROPOSAL+CRITIQUEs  → schedule synthesizer for SYNTHESIS
   but no SYNTHESIS yet
  SYNTHESIS exists, no DECISION yet,      → schedule decider for DECISION
   decider transport == cli                 (manual decider → BLOCKED_ON_HUMAN)

Manual-transport handles (e.g. @human-rohan) are surfaced as items the
loop reports but never auto-runs; they appear in `quorum status` so the
human knows their turn is up.

Items are returned independent — at most one per deliberation per
planning pass — so the runner can concurrently invoke without
contending on the per-deliberation file lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..paths import WorkspacePaths
from .config import WorkspaceConfig, load_workspace_config
from .contributions import ContributionsView, parse_contributions
from .deliberation import DeliberationMeta, load_deliberation
from .participants import Participant, parse_participants
from .routing import (
    NoHandleAvailableError,
    RoutingDecision,
    route,
)
from .routing_defaults import RoutingDefaults, load_routing_defaults

ItemReason = Literal[
    "open_needs_proposal",
    "missing_critique",
    "ready_for_synthesis",
    "ready_for_decision",
]


@dataclass(frozen=True)
class PendingItem:
    """One unit of work the runner can dispatch."""

    deliberation: DeliberationMeta
    deliberation_path: Path
    role: str
    move_type: str
    reason: ItemReason
    routing: RoutingDecision
    handle: Participant
    is_manual: bool  # transport == "manual"; cannot be auto-invoked


@dataclass(frozen=True)
class BlockedItem:
    """A deliberation that wants a move but routing failed.

    Surfaces as `BLOCKED_ON_ROUTING` in the UI/status. The loop catches
    `NoHandleAvailableError` from the routing engine and records this.
    """

    deliberation: DeliberationMeta
    deliberation_path: Path
    role: str
    move_type: str
    reason: str  # short human-readable explanation


@dataclass(frozen=True)
class PlanResult:
    items: tuple[PendingItem, ...]
    blocked: tuple[BlockedItem, ...]
    skipped_terminal: tuple[DeliberationMeta, ...]  # DECIDED / ARCHIVED / ABANDONED

    def runnable(self) -> tuple[PendingItem, ...]:
        return tuple(i for i in self.items if not i.is_manual)

    def manual(self) -> tuple[PendingItem, ...]:
        return tuple(i for i in self.items if i.is_manual)


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


_TERMINAL_STATUSES = {"DECIDED", "ARCHIVED", "ABANDONED"}


def plan(paths: WorkspacePaths) -> PlanResult:
    """Scan all deliberations and return the next batch of work.

    Reads participants / config / routing-defaults once per call; cheap
    enough that we don't bother caching. Re-reading on each pass means
    the loop responds to user edits without restart.
    """
    if not paths.deliberations.is_dir():
        return PlanResult(items=(), blocked=(), skipped_terminal=())

    participants = parse_participants(paths.participants)
    config = load_workspace_config(paths.config_yaml)
    defaults = load_routing_defaults(paths.routing_defaults)
    by_handle = {p.handle: p for p in participants}

    items: list[PendingItem] = []
    blocked: list[BlockedItem] = []
    skipped: list[DeliberationMeta] = []

    for delib_path in sorted(paths.deliberations.glob("*.md")):
        try:
            meta = load_deliberation(delib_path)
        except Exception:
            continue
        if meta.status.upper() in _TERMINAL_STATUSES:
            skipped.append(meta)
            continue
        contributions = parse_contributions(delib_path)
        plan_for_delib(
            meta,
            delib_path,
            contributions,
            participants,
            config,
            defaults,
            by_handle,
            items,
            blocked,
        )

    return PlanResult(
        items=tuple(items), blocked=tuple(blocked), skipped_terminal=tuple(skipped)
    )


# ---------------------------------------------------------------------- #
# Per-deliberation planner
# ---------------------------------------------------------------------- #


def plan_for_delib(
    meta: DeliberationMeta,
    delib_path: Path,
    contributions: ContributionsView,
    participants: list[Participant],
    config: WorkspaceConfig,
    defaults: RoutingDefaults,
    by_handle: dict[str, Participant],
    items: list[PendingItem],
    blocked: list[BlockedItem],
) -> None:
    next_action = _next_action(meta, contributions)
    if next_action is None:
        return
    role, move_type, reason = next_action
    try:
        decision = route(
            role=role,
            deliberation=meta,
            participants=participants,
            config=config,
            defaults=defaults,
        )
    except NoHandleAvailableError as exc:
        blocked.append(
            BlockedItem(
                deliberation=meta,
                deliberation_path=delib_path,
                role=role,
                move_type=move_type,
                reason=str(exc),
            )
        )
        return

    handle = by_handle.get(decision.handle)
    if handle is None:
        blocked.append(
            BlockedItem(
                deliberation=meta,
                deliberation_path=delib_path,
                role=role,
                move_type=move_type,
                reason=(
                    f"routing chose {decision.handle} but it is missing from "
                    "participants.md"
                ),
            )
        )
        return

    items.append(
        PendingItem(
            deliberation=meta,
            deliberation_path=delib_path,
            role=role,
            move_type=move_type,
            reason=reason,
            routing=decision,
            handle=handle,
            is_manual=handle.transport == "manual",
        )
    )


def _next_action(
    meta: DeliberationMeta, contributions: ContributionsView
) -> tuple[str, str, ItemReason] | None:
    """Decide which (role, move_type) is next for this deliberation.

    Returns None if nothing is pending (deliberation is in a state the
    auto-loop should not progress, e.g. BLOCKED_ON_HUMAN, or already
    has a DECISION but the file has not been moved to DECIDED status).
    """
    status = meta.status.upper()
    if status.startswith("BLOCKED"):
        return None
    if contributions.has("DECISION") or contributions.has("OVERRIDE"):
        return None

    # Step 1: PROPOSAL.
    if not contributions.has("PROPOSAL"):
        return ("proposer", "PROPOSAL", "open_needs_proposal")

    # Step 2: CRITIQUE per critic.
    declared_critics = list(meta.roles.critics)
    if declared_critics:
        crits = {h.author for h in contributions.by_type("CRITIQUE")}
        for critic in declared_critics:
            if critic not in crits:
                return ("critic", "CRITIQUE", "missing_critique")
    elif not contributions.has("CRITIQUE"):
        # No critics declared in frontmatter — let routing pick one.
        return ("critic", "CRITIQUE", "missing_critique")

    # Step 3: SYNTHESIS.
    if not contributions.has("SYNTHESIS"):
        return ("synthesizer", "SYNTHESIS", "ready_for_synthesis")

    # Step 4: DECISION.
    return ("decider", "DECISION", "ready_for_decision")
