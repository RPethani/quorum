# Quorum

A local-first multi-agent collaboration hub. Multiple AI participants
(Claude, Gemini, Codex, …) work alongside a human on file-shaped
deliberations. The protocol is markdown-and-YAML; the conductor
orchestrates; the UI is a thin window.

The core insight: **the user writes a problem statement, walks away,
and is only pinged when an actual decision is needed**. Agents loop;
humans interject.

## Layout

```
conductor/    Python — protocol, planner, transport, HTTP server
ui/           Next.js + Tailwind — workspace UI
protocol/     Spec + per-move templates
docs/         Authoritative docs (humans only)
docs-specs/   AI-authored design specs and progress notes
prompts/      Standing prompt + augmentations sent to agents
```

## Constants

- **Repo root**: `/Users/rakeshpethani/Personal/quorum`
- **Live test workspace**: `/Users/rakeshpethani/quorum-test/quorum`
  (the path the running conductor is serving — read state via the
  API or by `cat`-ing files under this path)
- **Conductor URL**: `http://127.0.0.1:8500`
- **UI URL**: `http://localhost:3000`

## Where the rules live

This file stays light by design. The detail is in three places, all
loaded automatically:

### Rules — auto-loaded based on what you're editing

| File | Loaded when |
|---|---|
| `.claude/rules/non-negotiables.md` | Always |
| `.claude/rules/terminology.md` | Always |
| `.claude/rules/ui-design-system.md` | Editing `ui/**` |
| `.claude/rules/conductor-architecture.md` | Editing `conductor/**/*.py` |

### Skills — user-invocable

| Slash command | Type | What it does |
|---|---|---|
| `/restart-conductor` | User-only | Kill + start the conductor from source |
| `/run-tests` | User-only | Full Python + UI test/lint sequence |
| `/debug-loop` | Auto + user | Walk through "why isn't anything happening" diagnostics. Claude may auto-invoke this when the user reports the loop is stuck. |

`/restart-conductor` and `/run-tests` are user-only (the model can't
trigger them) because both have side effects that should be gated by
intent: a server restart kills in-flight invocations; a test run is
sequenced work the user controls. `/debug-loop` is auto-invocable
because diagnostics are read-only and useful when Claude reasons
about a stuck loop.

## One thing not to forget

Always run the conductor from source — `cd conductor && uv run
python -m quorum_conductor serve …`. The `~/.local/bin/quorum`
binary is a uv-installed snapshot from an earlier source state and
will silently run old code. Hours have been lost to this.
