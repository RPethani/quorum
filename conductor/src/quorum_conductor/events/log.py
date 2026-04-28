"""events.jsonl — schema, logger, reader.

Schema notes:
  * Every event has `type`, `ts` (ISO-8601 UTC), and `schema_version`.
  * Event-specific fields live alongside; consumers should ignore unknown
    fields rather than reject them (forward-compatible).
  * `__repr__`/dataclass equality matter only for tests; the on-disk
    form is what consumers (UI, future replay tooling) see.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT_SCHEMA_VERSION = "0.1"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------- #
# Event types
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class Event:
    """Base event. Subclasses must override `type` via class init."""

    type: str
    ts: str = field(default_factory=_now_iso)
    schema_version: str = EVENT_SCHEMA_VERSION

    def to_json_line(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


@dataclass(frozen=True)
class RoutingDecisionEvent(Event):
    """Emitted right after the routing engine returns a decision."""

    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    layer: str = ""
    fitness: int | None = None
    cost: int | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        layer: str,
        fitness: int | None,
        cost: int | None,
        alternatives: list[dict[str, Any]],
        note: str = "",
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "routing_decision")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "fitness", fitness)
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "alternatives", alternatives)
        object.__setattr__(self, "note", note)


@dataclass(frozen=True)
class AgentStarted(Event):
    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    move_type: str = ""
    attempt: int = 1

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        move_type: str,
        attempt: int = 1,
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "agent_started")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "move_type", move_type)
        object.__setattr__(self, "attempt", attempt)


@dataclass(frozen=True)
class AgentCompleted(Event):
    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    move_type: str = ""
    duration_s: float = 0.0
    return_code: int = 0
    attempt: int = 1
    stdout_chars: int = 0

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        move_type: str,
        duration_s: float,
        return_code: int,
        attempt: int = 1,
        stdout_chars: int = 0,
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "agent_completed")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "move_type", move_type)
        object.__setattr__(self, "duration_s", duration_s)
        object.__setattr__(self, "return_code", return_code)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(self, "stdout_chars", stdout_chars)


@dataclass(frozen=True)
class AgentFailed(Event):
    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    move_type: str = ""
    duration_s: float = 0.0
    return_code: int | None = None
    attempt: int = 1
    reason: str = ""  # `subprocess_failed` | `timeout` | `validation_failed` | …
    error: str = ""

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        move_type: str,
        duration_s: float,
        reason: str,
        error: str,
        attempt: int = 1,
        return_code: int | None = None,
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "agent_failed")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "move_type", move_type)
        object.__setattr__(self, "duration_s", duration_s)
        object.__setattr__(self, "return_code", return_code)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "error", error)


@dataclass(frozen=True)
class ValidationFailed(Event):
    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    move_type: str = ""
    attempt: int = 1
    errors: list[str] = field(default_factory=list)

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        move_type: str,
        errors: list[str],
        attempt: int = 1,
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "validation_failed")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "move_type", move_type)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(self, "errors", errors)


@dataclass(frozen=True)
class MoveAppended(Event):
    handle: str = ""
    role: str = ""
    deliberation_id: str = ""
    move_type: str = ""
    inboxes_notified: list[str] = field(default_factory=list)

    def __init__(
        self,
        *,
        handle: str,
        role: str,
        deliberation_id: str,
        move_type: str,
        inboxes_notified: list[str],
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "move_appended")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "move_type", move_type)
        object.__setattr__(self, "inboxes_notified", inboxes_notified)


# ---------------------------------------------------------------------- #
# Logger
# ---------------------------------------------------------------------- #


class EventLogger:
    """Thread-safe append-only writer for `events.jsonl`.

    Per-line writes <PIPE_BUF are atomic on POSIX, so multiple processes
    can also append safely; the lock here only guards the in-process
    file handle from interleaving partial writes between threads.
    """

    def __init__(self, events_path: Path):
        self._path = events_path
        self._lock = threading.Lock()
        events_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def emit(self, event: Event) -> None:
        line = event.to_json_line().encode("utf-8")
        with self._lock:
            # `O_APPEND` semantics: every write is implicitly seek-to-end.
            fd = os.open(
                str(self._path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o644,
            )
            try:
                os.write(fd, line)
            finally:
                os.close(fd)


def read_events(path: Path) -> Iterator[dict[str, Any]]:
    """Yield each JSON object from `events.jsonl`, skipping malformed lines."""
    if not path.is_file():
        return iter(())

    def _iter() -> Iterator[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj

    return _iter()
