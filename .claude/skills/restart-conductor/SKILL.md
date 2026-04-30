---
description: Kill the running Quorum conductor and start a fresh one from source. User-only — invoke via `/restart-conductor`. Claude must not auto-restart the server.
disable-model-invocation: true
---

# Restart the conductor

The Quorum conductor lives at `127.0.0.1:8500` and runs the autoloop
in-process. After Python changes you must restart it; UI changes
hot-reload and need no restart.

## Procedure

```bash
# 1. Kill any running conductor (covers both `quorum_conductor` and
#    the stale `~/.local/bin/quorum` if it's been launched).
pkill -f quorum_conductor 2>&1; sleep 2

# 2. Confirm the port is free. If something else holds 8500,
#    identify it by PID and kill explicitly — pkill -f sometimes
#    misses processes whose argv shows just `quorum`.
lsof -iTCP:8500 -sTCP:LISTEN -n -P 2>/dev/null

# 3. Start from source. NEVER use `~/.local/bin/quorum` — that's a
#    stale uv-installed snapshot that won't pick up working-tree changes.
cd /Users/rakeshpethani/Personal/quorum/conductor
uv run python -m quorum_conductor serve \
  --path /Users/rakeshpethani/quorum-test/quorum \
  --host 127.0.0.1 --port 8500 \
  > /tmp/quorum-serve.log 2>&1 &
disown

# 4. Wait 4s, then sanity-check.
sleep 4
curl -sS http://127.0.0.1:8500/healthz   # → "ok"
curl -sS http://127.0.0.1:8500/api/state | jq -r '"state=\(.state)"'
```

## Common gotchas

- **Bind error on restart.** Old conductor still holds the socket.
  Find the PID via `lsof -iTCP:8500 -sTCP:LISTEN`, kill by PID.
- **`/api/asks` returns `{"error":"not found"}`.** You're hitting an
  old build that didn't have the Asks endpoint. Confirm by curling
  again after restart.
- **Path differs by user.** This skill assumes the workspace lives at
  `/Users/rakeshpethani/quorum-test/quorum`. Adjust if the user has
  pointed at another workspace.

## Don't

- Don't use the `quorum` binary on PATH for anything except discovery
  (`which quorum`). It's stale and will silently run old code.
- Don't kill the process during an in-flight agent invocation if the
  user has explicitly asked you to wait — let it finish first.
