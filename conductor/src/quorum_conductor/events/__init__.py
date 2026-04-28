"""Append-only structured event log (`runtime/events/events.jsonl`).

Per design-doc §10.5 events are the workspace's history. The complement
to `state.yaml`, which is the *current* truth: events answer "what
happened, when, in what order?"; state.yaml answers "where are we?".

This module owns:

  * the event schema (one type per dataclass below)
  * the `EventLogger` that appends serialised events to events.jsonl
  * the `read_events()` helper for tests, status, and the future UI feed

Append discipline: each event is one line of UTF-8 JSON ending with
`\\n`. Line writes ≤PIPE_BUF are atomic on POSIX, so concurrent
appenders (the future parallel loop in 4f) can safely write without
extra locking. Daily rotation lives in 4f's loop, not here.
"""

from .log import (
    EVENT_SCHEMA_VERSION,
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    Event,
    EventLogger,
    MoveAppended,
    RoutingDecisionEvent,
    ValidationFailed,
    read_events,
)

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "AgentCompleted",
    "AgentFailed",
    "AgentStarted",
    "Event",
    "EventLogger",
    "MoveAppended",
    "RoutingDecisionEvent",
    "ValidationFailed",
    "read_events",
]
