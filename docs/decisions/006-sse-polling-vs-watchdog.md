# 006: Phase 8 stream — polling vs. inotify/watchdog

**Date:** 2026-04-29
**Phase:** 8
**Status:** active

## Context

The Phase 8 plan called out a **file-watcher** that pushes events to clients
("File-watcher (server-side, pushes via WebSocket)"). The shipped
implementation in `conductor/src/quorum_conductor/server/stream.py` is a
250 ms polling loop over `events.jsonl`'s tail position, broadcasting any new
lines through Server-Sent Events to every subscribed client.

This ADR records the deliberate substitution so the deviation isn't a silent
skip in a future audit.

## Decision

The stream layer ships as:

- **Transport: SSE** instead of WebSocket. The browser only consumes the
  feed; we don't need a duplex channel. SSE is simpler, has built-in retry,
  and works through every proxy without the WebSocket upgrade dance.
- **Watch mechanism: ~250 ms polling** of file size + cursor on
  `events.jsonl`. New lines are read, parsed, and broadcast to all
  subscribers. We also poll `runtime/active/` for the agent-composing
  marker fan-out and `state.yaml` for state transitions.
- **No `watchdog` / `inotify` / FSEvents**. We chose not to take a third-party
  filesystem-events dependency in v1.

## Reasoning

`watchdog`'s real-world behaviour is fiddly:

- **Cross-platform inconsistency.** On macOS FSEvents coalesces events with
  ~100ms granularity anyway; on Linux inotify's recursive watch on a deep
  tree is expensive; on Windows ReadDirectoryChangesW has its own race
  conditions on rapid edits. The vendor library smooths these but each
  platform still has corner cases that show up in production.
- **Append-only file workload.** events.jsonl is append-only and small
  (line count grows linearly with invocations). 250 ms polling reads the
  file's size, seeks if changed, and parses new lines — the cost is a single
  `stat()` per tick when nothing's happening. On a workspace with no agent
  running this is well under 1% CPU.
- **Latency budget.** The SSE consumer is a human-attended UI. 250 ms tail
  latency is imperceptible; sub-millisecond push from a real watcher would
  be a feature looking for a problem here.
- **Dep weight.** `watchdog` pulls in platform-specific extension modules
  (`xattr`, `pyobjc-framework-FSEvents` on macOS, etc.). For a v1 conductor
  whose other deps stayed minimal (`PyYAML`, `prompt_toolkit`, `trafilatura`,
  `pdfplumber`, `python-docx`) this is meaningful weight.

Polling is the right complexity floor for a single-user, single-host,
append-only event log. If we ever add a remote-conductor-with-many-clients
scenario where push semantics matter for cost or scale, we'll reach for a
real watcher then.

## Alternatives considered

- **`watchdog` library** with one observer per workspace path. Tested
  briefly during Phase 8 design; the cross-platform error surface (especially
  on macOS rapid-fire creates) outweighed the latency win.
- **Linux-only `inotify` direct binding** (no vendor library). Cleaner but
  ties Quorum to Linux for production use, which we explicitly want to
  avoid.
- **WebSocket with a broker (Redis pub/sub)** to fan out across processes.
  Way too much for v1's local-only model.

## Consequences

- Worst-case event latency from append to UI: ~250 ms + SSE-frame round-trip,
  call it ~300 ms. Imperceptible for human consumers; bounded for any
  follow-up scripts.
- On a workspace with thousands of events.jsonl entries, every poll seeks
  past the cursor and reads only new bytes — O(new events), not O(total).
  Memory footprint per stream is the broadcast queue, currently bounded by
  `QUEUE_MAX = 64`.
- If the user externally truncates `events.jsonl` (rotation), the cursor
  resets correctly on the next poll because we re-stat. We don't currently
  rotate from inside the conductor; that's a Phase-after-v1 concern.
- A future rewrite to a real watcher is an isolated change in
  `server/stream.py` and doesn't propagate to consumers.
