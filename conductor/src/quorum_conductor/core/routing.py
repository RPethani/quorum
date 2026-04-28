"""The layered routing engine (design-doc §3.6).

For each (role, deliberation) the conductor walks four layers in order:

  Layer 1  per-deliberation override (handle pinned in frontmatter)
  Layer 2  workspace override (config.yaml `routing.overrides`)
  Layer 3  fitness-based defaults from routing-defaults.yaml + availability
  Layer 4  fallback — highest-cost available handle, with a warning

The function takes only data — no I/O. Loaders in `core/{config,
deliberation, participants, routing_defaults}` produce the inputs; the
conductor's loop (Phase 4f) calls `route()` and acts on the result.
Returning a `RoutingDecision` rather than logging directly keeps this
module deterministic and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .config import WorkspaceConfig
from .deliberation import DeliberationMeta
from .participants import Participant
from .routing_defaults import RoutingDefaults


class RoutingLayer(StrEnum):
    PER_DELIBERATION = "per_deliberation"  # Layer 1
    WORKSPACE = "workspace"  # Layer 2
    DEFAULTS = "defaults"  # Layer 3
    FALLBACK = "fallback"  # Layer 4


@dataclass(frozen=True)
class Alternative:
    handle: str
    fitness: int | None
    cost: int | None
    rejected_because: str  # short tag for telemetry


@dataclass(frozen=True)
class RoutingDecision:
    handle: str
    role: str
    deliberation_id: str
    layer: RoutingLayer
    fitness: int | None
    cost: int | None
    alternatives: list[Alternative] = field(default_factory=list)
    note: str = ""


class NoHandleAvailableError(RuntimeError):
    """Raised when every layer is exhausted.

    The conductor (Phase 4f) catches this and transitions the
    deliberation to BLOCKED_ON_ROUTING with the embedded explanation.
    """

    def __init__(self, role: str, deliberation_id: str, alternatives: list[Alternative]):
        super().__init__(
            f"No handle available for role {role!r} on deliberation {deliberation_id!r}."
        )
        self.role = role
        self.deliberation_id = deliberation_id
        self.alternatives = alternatives


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def route(
    *,
    role: str,
    deliberation: DeliberationMeta,
    participants: list[Participant],
    config: WorkspaceConfig,
    defaults: RoutingDefaults,
) -> RoutingDecision:
    """Decide which handle should fulfil `role` on this deliberation.

    Walks Layer 1 → Layer 4 and returns the first match. Raises
    `NoHandleAvailableError` if every layer is exhausted (rare; usually means
    every fitness-rated handle is unhealthy or absent from the
    participants registry).
    """
    by_handle = {p.handle: p for p in participants}
    deliberation_id = deliberation.id

    # ---------------- Layer 1: per-deliberation override --------------- #
    pinned = deliberation.roles.for_role(role)
    if pinned and pinned in by_handle and _is_available(by_handle[pinned]):
        p = by_handle[pinned]
        return RoutingDecision(
            handle=pinned,
            role=role,
            deliberation_id=deliberation_id,
            layer=RoutingLayer.PER_DELIBERATION,
            fitness=defaults.fitness_for(
                pinned, role, inherits_from=p.inherits_fitness_from
            ),
            cost=defaults.cost_for(pinned, inherits_from=p.inherits_fitness_from),
        )

    # ---------------- Layer 2: workspace override ---------------------- #
    override = config.routing_overrides.get(role)
    if override and override in by_handle and _is_available(by_handle[override]):
        p = by_handle[override]
        return RoutingDecision(
            handle=override,
            role=role,
            deliberation_id=deliberation_id,
            layer=RoutingLayer.WORKSPACE,
            fitness=defaults.fitness_for(
                override, role, inherits_from=p.inherits_fitness_from
            ),
            cost=defaults.cost_for(override, inherits_from=p.inherits_fitness_from),
        )

    # ---------------- Layer 3: fitness-based defaults ------------------ #
    rated: list[tuple[Participant, int, int]] = []
    unrated_available: list[Participant] = []
    rejections: list[Alternative] = []

    for p in participants:
        if not _is_available(p):
            rejections.append(
                Alternative(
                    handle=p.handle,
                    fitness=defaults.fitness_for(
                        p.handle, role, inherits_from=p.inherits_fitness_from
                    ),
                    cost=defaults.cost_for(p.handle, inherits_from=p.inherits_fitness_from),
                    rejected_because=_unavailability_reason(p),
                )
            )
            continue
        fitness = defaults.fitness_for(p.handle, role, inherits_from=p.inherits_fitness_from)
        if fitness is None or fitness == 0:
            unrated_available.append(p)
            continue
        cost = defaults.cost_for(p.handle, inherits_from=p.inherits_fitness_from) or 0
        rated.append((p, fitness, cost))

    if rated:
        # Highest fitness wins; lowest cost breaks ties.
        rated.sort(key=lambda t: (-t[1], t[2]))
        winner, fitness, cost = rated[0]
        alternatives: list[Alternative] = []
        for p, fit, c in rated[1:]:
            alternatives.append(
                Alternative(
                    handle=p.handle,
                    fitness=fit,
                    cost=c,
                    rejected_because="lower_fitness" if fit < fitness else "higher_cost",
                )
            )
        alternatives.extend(rejections)
        return RoutingDecision(
            handle=winner.handle,
            role=role,
            deliberation_id=deliberation_id,
            layer=RoutingLayer.DEFAULTS,
            fitness=fitness,
            cost=cost,
            alternatives=alternatives,
        )

    # ---------------- Layer 4: fallback -------------------------------- #
    if unrated_available:
        # Pick the *highest-cost* available handle; if a workspace has
        # only an Opus and a Haiku registered for an unrated role, the
        # Opus is the safer bet. Cost has the design-doc tie-break
        # interpretation (relative quality proxy).
        unrated_available.sort(
            key=lambda p: defaults.cost_for(
                p.handle, inherits_from=p.inherits_fitness_from
            )
            or 0,
            reverse=True,
        )
        winner = unrated_available[0]
        winner_cost: int | None = defaults.cost_for(
            winner.handle, inherits_from=winner.inherits_fitness_from
        )
        alternatives = [
            Alternative(
                handle=p.handle,
                fitness=None,
                cost=defaults.cost_for(p.handle, inherits_from=p.inherits_fitness_from),
                rejected_because="lower_cost_than_fallback",
            )
            for p in unrated_available[1:]
        ]
        alternatives.extend(rejections)
        return RoutingDecision(
            handle=winner.handle,
            role=role,
            deliberation_id=deliberation_id,
            layer=RoutingLayer.FALLBACK,
            fitness=None,
            cost=winner_cost,
            alternatives=alternatives,
            note=(
                f"No fitness rating for role {role!r}; falling back to highest-cost "
                "available handle. Add a fitness rating to routing-defaults.yaml or "
                "pin a handle in config.yaml's routing.overrides to silence this."
            ),
        )

    raise NoHandleAvailableError(
        role=role, deliberation_id=deliberation_id, alternatives=rejections
    )


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _is_available(p: Participant) -> bool:
    """Pre-Phase-4g availability check.

    Phase 4g (events.jsonl) introduces real per-day quota tracking; for
    now we honour `health` only. `red` is unhealthy; everything else
    (green, yellow, unknown, n/a for manual handles) routes.
    """
    return p.health.lower() != "red"


def _unavailability_reason(p: Participant) -> str:
    if p.health.lower() == "red":
        return "unhealthy"
    return "unavailable"
