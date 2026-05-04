"""Append-only structured event log (`events.jsonl`).

After the protocol retirement, only the framework remains exposed —
`Event`, `EventLogger`, `read_events`. The protocol-era event subclasses
(MoveAppended, AgentStarted, RoutingDecisionEvent, …) still live in
`log.py` for binary-compat with existing event-log files but aren't
re-exported.
"""

from .log import EVENT_SCHEMA_VERSION, Event, EventLogger, read_events

__all__ = ["EVENT_SCHEMA_VERSION", "Event", "EventLogger", "read_events"]
