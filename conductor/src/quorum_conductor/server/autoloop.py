"""Background ticker that runs `plan → step` while the workspace is ACTIVE.

Per the Ask UX overhaul (`docs-specs/asks-ux-overhaul.md`), once setup
completes the conductor should keep ticking on its own — the user
shouldn't have to click "step" or run `quorum step`. This module runs a
single daemon thread per HTTP server that:

  - Wakes every TICK_INTERVAL_S seconds.
  - Loads `state.yaml`. If state != ACTIVE, sleeps.
  - If any Ask is open (`workspace.asks.list_open_asks`), sleeps.
  - Else regenerates Asks (which also runs auto-advance), runs the
    planner, picks the first runnable item, and invokes it via the
    existing `transport.runner.run_items_sync` path.

The loop is intentionally serial — at most one agent invocation at a
time — so cost is bounded and ordering is predictable. The HTTP `/api/
step` endpoint stays available for users who want to step manually; the
two paths share `transport.runner`, so events / status are identical.

A planner step that fails for transport reasons (e.g. CLI not on PATH)
emits an event and the loop just continues. Cost-ceiling enforcement
mirrors the manual `/api/step`.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ..core.config import load_workspace_config
from ..core.cost import compute_cost
from ..core.loop import PendingItem, plan
from ..core.participants import parse_participants
from ..core.routing import NoHandleAvailableError, route
from ..core.routing_defaults import load_routing_defaults
from ..events import EventLogger, RoutingDecisionEvent
from ..events.log import read_events
from ..paths import WorkspacePaths
from ..transport.runner import run_items_sync
from ..workspace.asks import list_open_asks
from ..workspace.bootstrapper import bootstrap_seed_deliberation, needs_bootstrap
from ..workspace.state import WorkspaceState, load_state, save_state

TICK_INTERVAL_S: float = 5.0
"""How often the ticker wakes up to look for work. Five seconds is a
compromise — fast enough that the user feels it as 'live', slow enough
that idle workspaces don't burn CPU."""

REPEAT_FAILURE_THRESHOLD: int = 3
"""How many consecutive subprocess failures on the same (handle,
deliberation, move_type) before the autoloop excludes that handle for
this work item. Below this, transient blips don't kick the agent out;
at or above, we treat the agent as unavailable for this attempt and
let routing pick someone else."""


class AutoLoop:
    """Daemon-threaded auto-runner. One per HTTP server."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self._paths = paths
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="quorum-autoloop", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------ #
    # Tick loop
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick_once()
            except Exception:
                # The loop must never die — a single bad tick gets
                # swallowed and we try again next interval.
                pass
            self._stop.wait(TICK_INTERVAL_S)

    def _tick_once(self) -> None:
        paths = self._paths
        if not paths.state_yaml.is_file():
            return
        state = load_state(paths.state_yaml)
        if state.state is not WorkspaceState.ACTIVE:
            return

        # Best-effort bootstrap: brand-new workspaces get a seed
        # deliberation on first ACTIVE tick. Same trigger the manual
        # /api/step endpoint uses.
        if needs_bootstrap(paths):
            try:
                bootstrap_seed_deliberation(paths)
            except Exception:
                return

        # Asks pause the loop — the human is the next actor.
        try:
            from ..workspace.ask_generator import regenerate_asks

            regenerate_asks(paths)
        except Exception:
            pass
        if list_open_asks(paths):
            return

        config = load_workspace_config(paths.config_yaml)
        defaults = load_routing_defaults(paths.routing_defaults)

        if config.cost_enforce:
            spend = compute_cost(paths.events_jsonl, defaults)
            if spend.at_or_above_ceiling(config.cost_ceiling_usd):
                return

        result = plan(paths)
        runnable = list(result.runnable())
        if not runnable:
            return

        # Per-handle failure exclusion. If the handle the planner chose
        # for an item has just failed `REPEAT_FAILURE_THRESHOLD` times
        # consecutively on the same (deliberation, move_type), we
        # re-route the item with that handle excluded — picking the
        # next-best alternative. Only when *every* viable handle for
        # the item is exhausted do we drop the item from this tick;
        # only when *every* runnable item is dropped do we pause the
        # workspace. This matches the original requirement: "loop
        # halts on agent unavailability" means *no agent is available*,
        # not "the preferred agent had a bad day."
        recent = _recent_failure_counts(paths)
        runnable = self._reroute_around_failures(paths, runnable, recent)
        if not runnable:
            self._pause_with_reason(paths, "agents_unreachable")
            return

        item = runnable[0]
        events = EventLogger(paths.events_jsonl)
        try:
            events.emit(
                RoutingDecisionEvent(
                    handle=item.routing.handle,
                    role=item.routing.role,
                    deliberation_id=item.routing.deliberation_id,
                    layer=item.routing.layer.value,
                    fitness=item.routing.fitness,
                    cost=item.routing.cost,
                    alternatives=[
                        {
                            "handle": a.handle,
                            "fitness": a.fitness,
                            "cost": a.cost,
                            "rejected_because": a.rejected_because,
                        }
                        for a in item.routing.alternatives
                    ],
                    note=item.routing.note,
                )
            )
        except Exception:
            pass

        try:
            run_items_sync([item], paths=paths, events=events, mode=state.mode.value)
        except Exception:
            return


    @staticmethod
    def _reroute_around_failures(
        paths: WorkspacePaths,
        items: list[PendingItem],
        recent: dict[tuple[str, str, str], int],
    ) -> list[PendingItem]:
        """For each item whose chosen handle has failed too many times
        recently, re-route by excluding that handle. Drop the item if
        no viable alternative exists. Returns the surviving items."""
        if not recent:
            return items
        try:
            participants = parse_participants(paths.participants)
            config = load_workspace_config(paths.config_yaml)
            defaults = load_routing_defaults(paths.routing_defaults)
        except Exception:
            return items

        survivors: list[PendingItem] = []
        for item in items:
            key = (item.handle.handle, item.deliberation.id, item.move_type)
            if recent.get(key, 0) < REPEAT_FAILURE_THRESHOLD:
                survivors.append(item)
                continue
            # The chosen handle is exhausted; try alternatives.
            excluded = {item.handle.handle}
            substitute = _find_substitute(
                item=item,
                excluded=excluded,
                recent=recent,
                participants=participants,
                config=config,
                defaults=defaults,
            )
            if substitute is not None:
                survivors.append(substitute)
            # else: silently drop; pause logic above handles the all-
            # items-dropped case.
        return survivors

    @staticmethod
    def _pause_with_reason(paths: WorkspacePaths, reason: str) -> None:
        """Flip workspace state to PAUSED. Idempotent.

        We don't currently persist `reason` anywhere structured — the
        events.jsonl already shows the failure trail and that's enough
        for the UI to surface why we paused. Future work: a dedicated
        `state.pause_reason` field surfaced in /api/state.
        """
        try:
            state = load_state(paths.state_yaml)
        except Exception:
            return
        if state.state is WorkspaceState.PAUSED:
            return
        state.state = WorkspaceState.PAUSED
        try:
            save_state(paths.state_yaml, state)
        except Exception:
            return
        _ = reason  # placeholder for the future structured field


def _find_substitute(
    *,
    item: PendingItem,
    excluded: set[str],
    recent: dict[tuple[str, str, str], int],
    participants: Any,
    config: Any,
    defaults: Any,
) -> PendingItem | None:
    """Re-route `item` excluding handles in `excluded` plus any handle
    that has crossed the failure threshold for this (delib, move_type).
    Returns a new PendingItem with the substitute handle, or None if
    every viable handle is exhausted."""
    delib_key_prefix = (item.deliberation.id, item.move_type)
    # Exclude any handle that's already exhausted for this (delib,
    # move_type), regardless of whether they were the originally-
    # chosen one. This stops us from cycling through every alternate
    # in a workspace where multiple handles share the same failure.
    auto_excluded = {
        handle
        for (handle, did, mt), n in recent.items()
        if (did, mt) == delib_key_prefix and n >= REPEAT_FAILURE_THRESHOLD
    }
    block = excluded | auto_excluded
    available = [p for p in participants if p.handle not in block]
    if not available:
        return None
    try:
        decision = route(
            role=item.role,
            deliberation=item.deliberation,
            participants=available,
            config=config,
            defaults=defaults,
        )
    except NoHandleAvailableError:
        return None
    by_handle = {p.handle: p for p in available}
    handle = by_handle.get(decision.handle)
    if handle is None or handle.transport == "manual":
        return None
    from dataclasses import replace

    return replace(
        item,
        routing=decision,
        handle=handle,
        is_manual=False,
    )


def _recent_failure_counts(paths: WorkspacePaths) -> dict[tuple[str, str, str], int]:
    """Return consecutive failure counts per (handle, deliberation,
    move_type), reset by any subsequent `move_appended` for the same
    deliberation.

    Failure-weighting policy: a `timeout` failure counts as
    `REPEAT_FAILURE_THRESHOLD` strikes immediately, so the workspace
    pauses after a single 10-minute hang rather than burning 30+
    minutes on three retries. Subprocess errors (exit code) and
    validation failures count as one strike each — they're cheap and
    often transient (rate limits, recoverable parse glitches).

    Walking the event log every tick is fine for v1: the log is small
    (sub-MB until thousands of moves), and reading it is cheap relative
    to spawning a subprocess. If this becomes hot we can keep an
    in-memory cursor in `AutoLoop`.
    """
    if not paths.events_jsonl.is_file():
        return {}
    counts: dict[tuple[str, str, str], int] = {}
    failures: list[tuple[str, str, str, int]] = []
    for raw in read_events(paths.events_jsonl):
        ev_type = str(raw.get("type", ""))
        delib_id = str(raw.get("deliberation_id", "") or "")
        if not delib_id:
            continue
        if ev_type == "move_appended":
            failures = [f for f in failures if f[1] != delib_id]
            continue
        if ev_type == "agent_failed":
            handle = str(raw.get("handle", "") or "")
            move_type = str(raw.get("move_type", "") or "")
            reason = str(raw.get("reason", "") or "")
            weight = (
                REPEAT_FAILURE_THRESHOLD if reason == "timeout" else 1
            )
            failures.append((handle, delib_id, move_type, weight))
    for handle, delib_id, move_type, weight in failures:
        key = (handle, delib_id, move_type)
        counts[key] = counts.get(key, 0) + weight
    return counts


__all__ = ["AutoLoop", "TICK_INTERVAL_S", "REPEAT_FAILURE_THRESHOLD"]


# Type-checker keep-warm. `Any` is imported above for future use in
# tests that monkeypatch the runner; remove when those tests land.
_ = Any
