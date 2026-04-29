# Quorum troubleshooting

Common failure modes and the smallest-thing-that-fixes-them.

## "command not on PATH"

```
status   : subprocess_failed
error    : command not on PATH: claude
```

The CLI binary registered in `participants.md` isn't on the conductor's PATH. The conductor inherits the PATH of the shell that ran `quorum start` / `quorum run`. Fix:

```bash
which claude   # confirm where it is
```

Either add the directory to your PATH and restart the conductor, or change the `cli_command` in `participants.md` to use the absolute path.

## "cost ceiling reached"

```
cost ceiling reached: $50.00 >= $50.00. Pausing.
```

You hit the workspace's configured ceiling. Three options, all in `config.yaml`:

- raise `cost.ceiling_usd`,
- set `cost.enforce: false` (tracks but doesn't pause),
- accept the stop and switch to a cheaper model in `participants.md`.

The workspace transitions to `PAUSED`; resume with `quorum resume` after editing.

## Validator rejects "no canonical move header"

The agent emitted prose preamble before the canonical `### [MOVE_TYPE] @author …` line. The validator one-retry path will feed this back to the agent and it usually clears on attempt 2. If it persists, look at `runtime/streams/failed/<...>.validation_failed.stream` — the raw output is preserved there for diagnosis.

Most often the cause is a CLI agent that has Write/Edit tools available and is trying to write the move to disk itself. The conductor is the writer; the agent should output text only. If you can constrain the CLI's tools (e.g. `claude --allowedTools Read`), do so.

## SSE shows "○polling" instead of "●live"

The browser couldn't establish (or lost) the EventSource connection to `/api/stream`. Check:

- Is `quorum serve` running? `curl http://127.0.0.1:8500/healthz` should return `ok`.
- Does the UI's `?api=` override match? You can pin the API base via `?api=http://127.0.0.1:8500` on the URL.
- CORS is permissive (`*`) by design; if a corporate network strips Last-Event-ID headers or buffers SSE bodies, the connection dies. Use the Refresh button as the fallback.

## Conductor refuses to start

```
error: Conductor is already running for /path/to/workspace (pid 12345). Use `quorum pause` to stop it first.
```

A stale `runtime/conductor.pid` from a previous crash. `quorum pause` clears it (no-op if nothing's running), then `quorum start` again.

If `quorum pause` reports "no running conductor" but `quorum start` still refuses, the pidfile points to a process that's dead but the OS hasn't reused the PID. Delete the pidfile manually:

```bash
rm runtime/conductor.pid
quorum start
```

## "no canonical move header" on a manually-composed move

If you used `/workspace`'s "Compose move" form, the conductor renders the canonical block for you. If the validator still rejects, the most likely cause is a missing required section. Check `protocol/templates/<move_type>.md` — every `## Heading` must be present. Empty sections are filled with "none" automatically; missing headings are not.

## The bootstrapper agent says "no manifest template found"

The bootstrapper expects to read templates from `protocol/manifest-templates/<archetype>.md` inside the workspace. `quorum init` copies them at scaffold time. If they're missing, your repo install is incomplete:

```bash
ls protocol/manifest-templates/
# expect: saas-product.md  research-direction.md  …
```

If empty, copy them from the upstream Quorum repo:

```bash
cp -R ~/.quorum/protocol/manifest-templates/. protocol/manifest-templates/
```

## Stale lifecycle markers

`quorum status` may show:

```
warning: 2 stale lifecycle markers in runtime/active/
```

A previous invocation crashed before cleaning up its `runtime/active/<...>.start` marker. The threshold is 15 minutes since marker creation. If you're sure no agent is actually running, clear them:

```bash
rm runtime/active/*
```

## The activity feed says "validation_failed" but no failed moves are visible

A validation failure preserves the raw stream under `runtime/streams/failed/<handle>--<delib>--<movetype>.validation_failed.stream` and never appends to the deliberation file. To inspect:

```bash
ls runtime/streams/failed/
cat runtime/streams/failed/<filename>
```

If you see content with a canonical header inside but the validator rejected it, look at the events log entry's `errors` array for the specific issue:

```bash
jq 'select(.type == "validation_failed")' runtime/events/events.jsonl | tail -1
```

## `quorum doctor` says "non-cli handle; no PATH check applies"

Working as designed for `transport: manual` (humans) and `transport: mcp` / `transport: ide` (v2 transports). Only `cli`-transport handles get a PATH check.

## I want to run two workspaces in parallel

Each workspace gets its own conductor and HTTP server. The conductor binds to a fixed `runtime/conductor.pid` per-workspace, and `quorum serve` defaults to port 8500. To run two:

```bash
# workspace A
cd ~/project-a/quorum
quorum start
quorum serve --port 8500

# workspace B (separate terminal, different port)
cd ~/project-b/quorum
quorum start
quorum serve --port 8501
```

In the UI, append `?api=http://127.0.0.1:8501` to point at the second workspace.

## Where do logs go?

- Conductor daemonised via `quorum start`: `runtime/conductor.log`.
- Conductor foreground via `quorum run`: stdout / stderr of the terminal you ran it in.
- HTTP server: by design, access logs are silenced. If you need them, run the conductor under `--debug` (Phase-14 future addition; for now, edit `server/http_app.py:log_message`).
- Events.jsonl: `runtime/events/events.jsonl`. Append-only, one JSON object per line.

## I want to start over

```bash
cd /path/to/workspace
quorum archive --reason rebuild
rm -rf runtime/                                    # ephemeral state
# edit problem-statement.md, participants.md if needed
rm -rf deliberations/* artifacts/* decisions/* tasks/*
quorum unarchive
quorum start
```

Or just delete the workspace folder and `quorum init` a new one.
