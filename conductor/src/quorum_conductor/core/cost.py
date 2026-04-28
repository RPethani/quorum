"""Per-workspace cost tracking and ceiling enforcement.

Approach (Phase 4i):

  * Each successful `agent_completed` event represents one invocation.
  * USD cost per invocation is a flat estimate per handle, looked up
    from `routing-defaults.yaml`'s `usd_per_invocation` block.
  * Cumulative spend = sum over events. Cheap to compute on demand
    because events.jsonl is small (one short line per invocation).
  * The loop checks the ceiling before scheduling the next batch and
    refuses to dispatch if it would exceed the cap.

This is intentionally crude: real model cost varies with input/output
length and we don't observe either side via a CLI. The flat-rate
estimate gives the user a *safety bound* — far better than nothing.
Tune `usd_per_invocation` per-workspace if you need tighter accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..events import read_events
from .routing_defaults import RoutingDefaults


@dataclass(frozen=True)
class CostSummary:
    spent_usd: float
    invocations: int
    by_handle: dict[str, float]
    by_handle_invocations: dict[str, int]
    unknown_handles: list[str]  # invocations whose handle has no usd estimate

    def fraction_of(self, ceiling_usd: float) -> float:
        if ceiling_usd <= 0:
            return 0.0
        return self.spent_usd / ceiling_usd

    def at_or_above_ceiling(self, ceiling_usd: float) -> bool:
        return self.spent_usd >= ceiling_usd


def compute_cost(events_path: Path, defaults: RoutingDefaults) -> CostSummary:
    """Walk events.jsonl and sum estimated USD spend.

    Counts only `agent_completed` events; `agent_failed` and
    `validation_failed` represent attempts that never produced a
    persisted move, but the user did still pay for the model call.
    Treat them as billable too.
    """
    spent = 0.0
    by_handle: dict[str, float] = {}
    by_handle_invocations: dict[str, int] = {}
    unknown: set[str] = set()
    invocations = 0

    if not events_path.is_file():
        return CostSummary(
            spent_usd=0.0,
            invocations=0,
            by_handle={},
            by_handle_invocations={},
            unknown_handles=[],
        )

    for record in read_events(events_path):
        event_type = record.get("type")
        if event_type not in ("agent_completed", "agent_failed", "validation_failed"):
            continue
        handle = str(record.get("handle", ""))
        if not handle:
            continue
        invocations += 1
        by_handle_invocations[handle] = by_handle_invocations.get(handle, 0) + 1
        usd = defaults.usd_for(handle)
        if usd is None:
            unknown.add(handle)
            continue
        spent += usd
        by_handle[handle] = by_handle.get(handle, 0.0) + usd

    return CostSummary(
        spent_usd=round(spent, 4),
        invocations=invocations,
        by_handle={h: round(v, 4) for h, v in by_handle.items()},
        by_handle_invocations=by_handle_invocations,
        unknown_handles=sorted(unknown),
    )
