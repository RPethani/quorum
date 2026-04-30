---
description: Diagnose why the Quorum autoloop isn't making progress. Invoke when the user reports "nothing is happening", "stuck", "agent keeps failing", or when state appears wrong.
---

# Debug the autoloop

The autoloop ticks every 5 seconds inside `quorum serve`. When it
seems frozen, walk these checks in order — they map to the four
reasons it can be stuck.

## Check 1: state is ACTIVE

```bash
curl -sS http://127.0.0.1:8500/api/state | jq -r '"state=\(.state)"'
```

- `ACTIVE` → loop is ticking. Move to Check 2.
- `PAUSED` → either the user paused, or `agents_unreachable` triggered
  it (every viable participant is exhausted). Look at recent
  `agent_failed` events to confirm. Re-activate via:
  ```bash
  curl -sS -X POST -H 'Content-Type: application/json' \
    -d '{"mode":"interactive"}' http://127.0.0.1:8500/api/wizard/apply
  ```
- `INITIALIZED` → setup wasn't applied. Open the Setup dialog or
  apply via wizard endpoint.

## Check 2: any open Asks?

```bash
curl -sS http://127.0.0.1:8500/api/asks | jq -r \
  '.asks[] | select(.status=="open") | "\(.id) on #\(.source_deliberation): \(.question)"'
```

If any rows print, the human is the next actor and the loop is
correctly idle. Tell the user. Don't restart anything.

## Check 3: what's the planner's view?

```bash
curl -sS http://127.0.0.1:8500/api/plan | jq -r \
  '.items[] | "\(.handle) → \(.move_type) on #\(.deliberation_id) manual=\(.is_manual)"'
```

- Empty → nothing to do; everything's DECIDED, BLOCKED, or terminal.
  The workspace is genuinely quiet.
- One or more non-manual items → an agent should run within 5s.
  If it doesn't, move to Check 4.

## Check 4: are agents failing?

```bash
ls -t /Users/rakeshpethani/quorum-test/quorum/runtime/streams/failed/ | head
tail -20 /Users/rakeshpethani/quorum-test/quorum/runtime/events/events.jsonl \
  | jq -c '{type,handle,move_type,deliberation_id,reason,error}'
```

Look at:
- The latest stream in `runtime/streams/failed/` for the raw stdout.
- The last 20 events for the failure pattern.

Common patterns:
- `subprocess_failed` with `return_code: 55` → CLI flag missing
  (typical: gemini needs `-p "" --skip-trust --yolo`).
- `validation_failed` with `errors: [...preamble...]` → agent emitted
  prose before the canonical header. The conductor's normalizer
  should catch this; if it isn't, the header isn't where the
  normalizer can find it.
- `timeout` → API hang. Counts as 3 strikes immediately, so the
  next tick will substitute or pause.

## Live tail

```bash
tail -f /Users/rakeshpethani/quorum-test/quorum/runtime/events/events.jsonl \
  | jq -c '{ts,type,handle,move_type,deliberation_id,reason}'
```

Run this when you want to *see* the tick happen. If you don't see
events appearing every 5s, the autoloop thread is wedged — restart
the conductor (see `/restart-conductor`).

## What NOT to do

- **Don't `pkill` mid-investigation** without first reading the live
  events. You'll lose information.
- **Don't manually answer Asks** through the API to "unstick" the
  loop unless the user has explicitly asked. The Ask exists because
  a real decision is needed.
- **Don't conclude "it's broken" from a single tick.** Wait at least
  10 seconds (two tick intervals) before deciding nothing is moving.
