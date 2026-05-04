"""Server-Sent Events stream for the UI.

Per CLAUDE.md the project standard is SSE (not WebSockets) for live
updates. This module implements one endpoint:

    GET /api/stream

The conductor's server runs a single background poller thread that
watches three things:

  * `runtime/events/events.jsonl` — line count grows when an event
    fires; we tail any new lines and re-emit them.
  * `runtime/active/` — directory contents change when an invocation
    starts (file appears) or completes (file disappears).
  * `state.yaml` — mtime changes on every state transition.

When any of those change, the watcher pushes an SSE message to every
connected client. Each connection gets its own queue so a slow client
can't block others.

This is a polling watcher (250ms tick) not a kqueue/inotify watcher —
adding `watchdog` would be a new dep for ~5 Python lines of payoff.
The 250ms tick is well under the human-perceptible threshold.

The wire format:

    event: <type>
    data: <one-line JSON>

    event: <type>
    data: <one-line JSON>

Types emitted:

  * `events_appended`  payload: list of new event records
  * `active_changed`   payload: {"active": ["@x--0001--PROPOSAL", …]}
  * `state_changed`    payload: the same shape /api/state returns
  * `keepalive`        payload: {} — sent every 15s so proxies don't
                                 idle-disconnect long-lived clients
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canvas.state import StateError, load_state
from ..events import read_events
from ..paths import WorkspacePaths

POLL_INTERVAL_S: float = 0.25
KEEPALIVE_INTERVAL_S: float = 15.0
QUEUE_MAX = 256  # backpressure; slow client gets dropped after this many


@dataclass
class StreamMessage:
    type: str
    payload: Any


class StreamHub:
    """Singleton-per-server fan-out: one watcher thread, many subscribers.

    Lifecycle is bound to the HTTP server: constructed once on first
    `subscribe()`, runs forever. Idle hubs are cheap (~250ms wakeups)
    so we don't bother shutting it down between requests.
    """

    def __init__(self, paths: WorkspacePaths):
        self._paths = paths
        self._subs: list[queue.Queue[StreamMessage]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------- subscriber API ----------------
    def subscribe(self) -> queue.Queue[StreamMessage]:
        q: queue.Queue[StreamMessage] = queue.Queue(maxsize=QUEUE_MAX)
        with self._lock:
            self._subs.append(q)
        # Send an initial snapshot so first-paint isn't blank.
        try:
            q.put_nowait(StreamMessage("state_changed", _state_payload(self._paths)))
            q.put_nowait(StreamMessage("active_changed", _active_payload(self._paths)))
            initial_events = list(read_events(self._paths.events_jsonl))
            if initial_events:
                q.put_nowait(StreamMessage("events_appended", initial_events))
        except queue.Full:
            pass
        return q

    def unsubscribe(self, q: queue.Queue[StreamMessage]) -> None:
        import contextlib

        with self._lock, contextlib.suppress(ValueError):
            self._subs.remove(q)

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    # ------------- watcher loop ------------------
    def _run(self) -> None:
        last_event_count = _file_line_count(self._paths.events_jsonl)
        last_active = _active_set(self._paths)
        last_state_mtime = _mtime(self._paths.state_yaml)
        last_keepalive = time.monotonic()

        while not self._stop_event.is_set():
            time.sleep(POLL_INTERVAL_S)

            # events.jsonl growth
            current_count = _file_line_count(self._paths.events_jsonl)
            if current_count > last_event_count:
                new_events = list(read_events(self._paths.events_jsonl))[
                    last_event_count:current_count
                ]
                if new_events:
                    self._broadcast(StreamMessage("events_appended", new_events))
                last_event_count = current_count

            # runtime/active/ delta
            current_active = _active_set(self._paths)
            if current_active != last_active:
                self._broadcast(
                    StreamMessage("active_changed", {"active": sorted(current_active)})
                )
                last_active = current_active

            # state.yaml mtime
            current_mtime = _mtime(self._paths.state_yaml)
            if current_mtime != last_state_mtime:
                self._broadcast(StreamMessage("state_changed", _state_payload(self._paths)))
                last_state_mtime = current_mtime

            now = time.monotonic()
            if now - last_keepalive >= KEEPALIVE_INTERVAL_S:
                self._broadcast(StreamMessage("keepalive", {}))
                last_keepalive = now

    def _broadcast(self, message: StreamMessage) -> None:
        import contextlib

        with self._lock:
            dead: list[queue.Queue[StreamMessage]] = []
            for q in self._subs:
                try:
                    q.put_nowait(message)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                with contextlib.suppress(ValueError):
                    self._subs.remove(q)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _file_line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _active_set(paths: WorkspacePaths) -> set[str]:
    if not paths.runtime_active.is_dir():
        return set()
    try:
        return {p.name for p in paths.runtime_active.iterdir() if p.is_file()}
    except OSError:
        return set()


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _state_payload(paths: WorkspacePaths) -> dict[str, Any]:
    """Tiny canvas-state snapshot for SSE clients.

    Replaces the protocol-era summary. Just title + cost + message
    counter, mirroring the shape `/api/state` returns.
    """
    if not paths.state_yaml.is_file():
        return {}
    try:
        state = load_state(paths.root)
    except StateError:
        return {}
    return {
        "title": state.title,
        "message_counter": state.message_counter,
        "cost": {
            "spent": state.cost.spent,
            "cap": state.cost.cap,
            "enforce": state.cost.enforce,
        },
    }


def _active_payload(paths: WorkspacePaths) -> dict[str, Any]:
    return {"active": sorted(_active_set(paths))}


# ---------------------------------------------------------------------- #
# SSE wire format
# ---------------------------------------------------------------------- #


def format_sse(message: StreamMessage) -> bytes:
    payload = json.dumps(message.payload, separators=(",", ":"))
    return f"event: {message.type}\ndata: {payload}\n\n".encode()
