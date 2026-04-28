"""Read `registers/routing-defaults.yaml` and resolve fitness with inheritance.

Per design-doc §3.6 routing defaults ship a fitness matrix per canonical
handle. Custom handles like `@claude-work-opus` inherit fitness from a
canonical handle declared via `inherits_fitness_from` in
`participants.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RoutingDefaults:
    """In-memory view of `routing-defaults.yaml`."""

    fitness: dict[str, dict[str, int]] = field(default_factory=dict)
    cost: dict[str, int] = field(default_factory=dict)
    usd_per_invocation: dict[str, float] = field(default_factory=dict)

    def fitness_for(
        self,
        handle: str,
        role: str,
        *,
        inherits_from: str | None = None,
    ) -> int | None:
        """Return the fitness score for (handle, role).

        Falls back to `inherits_from` if the handle is not directly
        rated. Returns None if neither is rated.
        """
        for candidate in (handle, inherits_from):
            if candidate is None:
                continue
            rated = self.fitness.get(candidate)
            if rated is not None and role in rated:
                return rated[role]
        return None

    def cost_for(self, handle: str, *, inherits_from: str | None = None) -> int | None:
        for candidate in (handle, inherits_from):
            if candidate is None:
                continue
            if candidate in self.cost:
                return self.cost[candidate]
        return None

    def usd_for(self, handle: str, *, inherits_from: str | None = None) -> float | None:
        """Per-invocation USD estimate for a handle.

        Used by the cost-ceiling check (design-doc §10). Inheritance
        rules mirror `cost_for` / `fitness_for`.
        """
        for candidate in (handle, inherits_from):
            if candidate is None:
                continue
            if candidate in self.usd_per_invocation:
                return self.usd_per_invocation[candidate]
        return None


def load_routing_defaults(path: Path) -> RoutingDefaults:
    """Read and validate the routing-defaults YAML.

    Returns an empty `RoutingDefaults` if the file is missing or empty.
    Raises `RoutingDefaultsError` if the file is present but malformed.
    """
    if not path.is_file():
        return RoutingDefaults()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RoutingDefaultsError(f"{path} is not a YAML mapping.")

    fitness_raw = raw.get("fitness") or {}
    cost_raw = raw.get("cost") or {}
    usd_raw = raw.get("usd_per_invocation") or {}
    if (
        not isinstance(fitness_raw, dict)
        or not isinstance(cost_raw, dict)
        or not isinstance(usd_raw, dict)
    ):
        raise RoutingDefaultsError(
            f"{path}: 'fitness', 'cost', and 'usd_per_invocation' must be mappings."
        )

    fitness: dict[str, dict[str, int]] = {}
    for handle, roles in fitness_raw.items():
        if not isinstance(roles, dict):
            continue
        fitness[str(handle)] = {str(r): _coerce_int(v) for r, v in roles.items()}

    cost: dict[str, int] = {str(h): _coerce_int(v) for h, v in cost_raw.items()}
    usd: dict[str, float] = {str(h): _coerce_float(v) for h, v in usd_raw.items()}
    return RoutingDefaults(fitness=fitness, cost=cost, usd_per_invocation=usd)


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RoutingDefaultsError(f"expected an integer, got {value!r}") from exc


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RoutingDefaultsError(f"expected a number, got {value!r}") from exc


class RoutingDefaultsError(RuntimeError):
    """Raised when routing-defaults.yaml is malformed."""
