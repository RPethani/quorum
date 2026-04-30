---
description: Conductor module map, layering rules, and key control flows. Loads only when editing Python in conductor/.
paths:
  - "conductor/**/*.py"
---

# Architecture — what lives where

The codebase is two layers (conductor + UI) plus a protocol the user
edits as files. This file explains how the layers fit, so changes
land in the right place.

---

## High-level shape

```
[ Files in workspace ] ←── written by ←── [ conductor ]
       ↑                                       ↑
       └── read by ──── [ Next.js UI ] ── HTTP ┘
```

Files are the source of truth. The conductor is the single writer.
The UI is read-mostly with a few POST endpoints that go through the
conductor.

---

## Conductor (`conductor/src/quorum_conductor/`)

```
core/         pure protocol logic — no I/O
  deliberation.py     parse a deliberation file
  contributions.py    extract `## Contributions` section + headers
  move_format.py      canonical header parser, validate_minimal
  validator.py        full structural validation (section presence)
  routing.py          layered router (per-deliberation → defaults → fallback)
  participants.py     parse `registers/participants.md`
  routing_defaults.py parse `routing-defaults.yaml`
  config.py           parse `config.yaml`
  loop.py             planner — given workspace state, returns next moves
  cost.py             event-log → spend
  prompts.py          standing-prompt + augmentation rendering
  decisions_summary.py  registers/summarized-decisions.md helper

transport/    invoking external CLIs
  invoker.py          spawn → capture stdout → normalize → validate → append
  runner.py           run_items + run_items_sync (concurrent dispatch)
  doctor.py           PATH probe per participant

workspace/    file-shaped surface area
  paths.py            WorkspacePaths — every path the workspace uses
  state.py            state.yaml read/write
  status.py           aggregate status_summary
  bootstrapper.py     first-deliberation seed
  deliberation_file.py  append_move + inbox propagation
  ratify.py           auto-lock manifest on DECISION
  auto_advance.py     open next ratification deliberation
  asks.py             Ask data model + storage
  ask_generator.py    planner manual-blocks → Asks
  ask_answerer.py     answer payload → protocol move
  ...

server/       HTTP + autoloop
  http_app.py         routes, handlers, server lifecycle
  autoloop.py         daemon thread that ticks plan→dispatch→sleep
  stream.py           SSE hub

events/       JSONL append-only event log
  log.py              EventLogger, read_events
  *.py                event dataclasses

cli.py        argparse entrypoint (`quorum init|serve|status|...`)
```

**Layering rule:** `core/` depends on nothing except stdlib + yaml.
`workspace/` depends on `core/`. `transport/` depends on
`core/` + `workspace/`. `server/` depends on everything. Don't cross
back.

---

## UI (`ui/`)

```
app/
  page.tsx               landing
  layout.tsx             theme + fonts
  workspace/page.tsx     the workspace shell (Header + SecondaryHeader + Home/Advanced)

components/
  ui/                    primitives (Button, Card, Badge, Dialog, Input, ...)
  design-system/         theme toggle + design-system showcase pieces
  dialogs/               full-screen dialogs (Setup, Settings, AddAgent, Context, ...)
  workspace/             the Ask UX + Home view + Advanced 3-pane bits

lib/
  api/conductor.ts       typed HTTP client + SSE subscribe wrapper
  utils.ts               cn() etc.
```

**Layering rule:** `app/` depends on `components/` + `lib/`.
`components/workspace/` may depend on `components/ui/` and
`components/design-system/`, but `components/ui/` must not depend on
`components/workspace/`. `lib/` depends on nothing else in `ui/`.

---

## Workspace files (the user's working directory)

```
state.yaml                lifecycle state (mode, state, manifest summary, cost)
config.yaml               cost ceiling, unavailability policy, routing overrides
problem-statement.md      what we're trying to figure out
outcome-manifest.md       the plan (status DRAFTING|READY|LOCKED)

deliberations/
  0001-outcome-manifest.md    seed deliberation (ratifies the manifest)
  0002-*.md                   subsequent deliberations
  ...

asks/
  ask-0001.json               one Ask per actionable user question

inbox/
  @rakesh.md                  one inbox file per participant
  @claude-opus.md             ...

registers/
  participants.md             pipe-table registry
  routing-defaults.yaml       per-handle, per-role fitness scores
  open-questions.md, glossary.md, summarized-decisions.md

context/
  repos/<name>/digest.md      digested code
  docs/{raw,digested}/*.md
  web/cached/*.md
  notes/*.md
  context-manifest.yaml

prompts/
  agent-standing-prompt.md    sent to every CLI invocation
  overrides/                  per-(handle|role|move) overrides

protocol/
  PROTOCOL.md                 the spec
  templates/<MOVE_TYPE>.md    one file per move type
  manifest-templates/*.md

runtime/
  events/events.jsonl         append-only audit log
  active/*.start              one marker per in-flight invocation
  streams/*.stream            captured stdout
  streams/failed/*.stream     failed captures (renamed)
  conductor.pid, ui.pid
```

The conductor never writes outside this tree. The user can edit
anything by hand; the next planner pass will pick it up.

---

## Key control flows

### "User answers an Ask"
```
UI POST /api/asks/{id}/answer
  → http_app._handle_ask_answer
    → workspace.ask_answerer.answer_ask
      → ask_answerer._render_move           (templated body)
      → workspace.deliberation_file.append_move  (writes the file)
      → workspace.ratify.maybe_ratify_manifest   (if DECISION on seed)
        → workspace.auto_advance.maybe_open_next_artifact_deliberation
      → asks.mark_answered
  → autoloop tick (≤5s later) sees no open Asks → resumes
```

### "Conductor's autoloop tick"
```
server.autoloop.AutoLoop._tick_once
  state != ACTIVE                  → return
  needs_bootstrap                  → bootstrap_seed_deliberation
  workspace.ask_generator.regenerate_asks   (also runs auto_advance)
  list_open_asks() not empty       → return (human is the next actor)
  cost.compute_cost ≥ ceiling      → return
  plan(paths) → runnable items
  filter / re-route around recent failures
  no items                         → pause, return
  invoker.run_items_sync([item])   → emits move_appended on success
```

### "Setup wizard apply"
```
UI POST /api/wizard/apply
  → http_app._handle_wizard_apply
    → write problem-statement.md
    → update config.yaml
    → update state mode
    → (optionally) rename human handle
    → _activate_if_ready          (flips state to ACTIVE if statement is real)
```

---

## Things that might surprise you

- **The autoloop normalises agent output before validation.** Less-
  obedient models emit prose preamble + a hallucinated author handle
  + a future timestamp. `transport/invoker._normalize_agent_response`
  finds the first canonical header and rewrites the author /
  timestamp with conductor-known values. Body content is verbatim.
- **The contributions parser uses "everything after `## Contributions`"**,
  not "section between `## Contributions` and the next H2". Move
  bodies use H2 sub-headings; if the parser stopped at the next H2
  it would truncate the section. This is why Contributions has to
  be the last H2 in a deliberation file.
- **Routing uses "fitness inheritance" for non-canonical handles.**
  The user's `participants.md` has `@gemini` (their handle), but
  fitness defaults are keyed by canonical names like `@gemini-pro`.
  The `Inherits Fitness From` column maps one to the other. Without
  it, routing falls back to "highest-cost available" which always
  picks `@claude-opus`.
- **Asks are stored as JSON, not markdown.** Everything else in the
  workspace is markdown — Asks are the exception because they're an
  internal data record, not a protocol artefact.
- **The `quorum` binary on PATH is stale.** `~/.local/bin/quorum`
  was uv-installed from an earlier source state. Always run from
  source: `cd conductor && uv run python -m quorum_conductor serve …`.
