# Ask-based UX Overhaul

**Status:** in progress
**Owner:** Claude (acting on @rakesh's brief, 2026-04-30)
**Scope:** user-facing surface only; protocol layer unchanged

---

## Why

Today's UI exposes the protocol directly. The user sees deliberations, moves
(PROPOSAL / CRITIQUE / SYNTHESIS / DECISION / OVERRIDE / DROP / …), a
manifest with three statuses, eleven move-types in a Compose dialog, and a
loop they have to manually advance. They are expected to know which artifact
to deliberate on first, how to phrase a question, and which move type to
pick when the loop reaches them.

The user's brief, verbatim:

> *I write a problem statement and walk away; agents go back and forth; I get
> pinged only when they truly need me to choose. But I also clearly able to
> identify what I am being asked and what options I am being given.*

> *Sometimes it could just be simple yes/no. Sometimes it could be multiple
> options where I could choose one or more. Sometimes I need to explain in
> details and so on.*

This doc captures the design we agreed to. The protocol underneath is
authoritative and unchanged; this overhaul adds a thin surface on top.

---

## The mental model

Three UI states, ever:

1. **Setup** — one screen: problem statement, AI participants, involvement
   level. Done once.
2. **Working** — live activity feed. Agents talking. Nothing for the user.
3. **Your turn** — a single **Ask** card with a question and an answer shape.

After setup the user sees only "Working" or "Your turn." No deliberation
list, no move-type picker, no manifest status, no loop controls in the
default surface. The Raw tab is preserved for power users / debugging.

---

## The Ask abstraction

An **Ask** is the only thing the user interacts with after setup.

Fields (persisted as `asks/<id>.json` in the workspace):

| Field | Type | Notes |
|---|---|---|
| `id` | string | `ask-<n>` zero-padded |
| `created_at` | ISO-8601 | |
| `answered_at` | ISO-8601 \| null | |
| `status` | `open` \| `answered` \| `closed` | `closed` = invalidated by a later move |
| `question` | string | plain English, one sentence |
| `why` | string | one-line context ("Two agents disagree on weighting.") |
| `shape` | `confirm` \| `pick_one` \| `pick_any` \| `write` | answer-shape enum |
| `options` | array \| null | `[{value, label, summary, expand}]` for `pick_one` / `pick_any` |
| `min_select` / `max_select` | int \| null | for `pick_any` only |
| `default_value` | any \| null | optional pre-fill for `write` |
| `source_deliberation` | string | `0002` |
| `source_move_id` | string | identifier for the originating move (timestamp + author) |
| `target_move_type` | string | the protocol move that will be written when answered (e.g. `DECISION`, `ANSWER`) |
| `answer` | object \| null | shape-specific payload, set on answer |

### Answer shapes

- **confirm** — Yes / No / "I need more info" → re-asks with `write`.
- **pick_one** — radio list. Each option has a one-line summary; clicking
  expands to the full body extracted from the source move.
- **pick_any** — checkbox list, with `min_select` / `max_select` constraints.
- **write** — free-text textarea. A "Let an agent draft this for me" button
  is a v2 nicety; not in v1.

### How an Ask is generated

The conductor watches the protocol move stream. Whenever a move's planner
result names the human as next-actor, the conductor builds an Ask:

| Trigger | Resulting Ask | `target_move_type` |
|---|---|---|
| Pending DECISION on a deliberation tagging the human as decider | `pick_one` over the live PROPOSAL / SYNTHESIS bodies as options, plus a "None of the above — write your own" escape | `DECISION` |
| `[QUESTION]` move tagging the human | `write` | `ANSWER` |
| `[INTERJECTION]` requesting a yes/no from the human | `confirm` | `ANSWER` (or whatever the move requests) |
| Manifest ratification needed (legacy bootstrapper case) | `confirm` ("Lock in this plan?") | DECISION on #0001 |

Option extraction for `pick_one`: the conductor takes the latest live
PROPOSAL/SYNTHESIS bodies in the deliberation, runs them through a small
LLM to summarise each into `{label, summary}`. The full body is preserved
in `expand`. If no LLM is available the option label falls back to the
move's `## Position` heading (or first non-empty line) and `summary` is
empty.

### How an Ask is answered

`POST /api/asks/{id}/answer` with `{value: …}`. The conductor:

1. Validates the answer against the shape.
2. Renders a protocol move from the answer using a fixed template per
   `target_move_type`.
3. Appends the move via `append_move` (so frontmatter status, audit log,
   ratification, inbox propagation all happen unchanged).
4. Marks the Ask `answered`. The loop resumes on next tick.

Idempotency: if the same Ask is answered twice, the second call returns
the existing `answered_at` without writing a new move.

---

## Auto-advance after manifest ratification

Today, after the seed deliberation locks `outcome-manifest.md`, the user
hits a banner asking them to start the first deliberation. In the new
world the conductor itself opens the next deliberation.

The manifest declares an ordered list of canonical artifacts (e.g.
`option-analysis.md`, `recommendation.md`, `course-correction-plan.md`).
For each artifact the conductor:

1. Checks whether a deliberation `ratifies: <artifact>` already exists.
2. If not, opens one with a templated question derived from the
   manifest's per-artifact section.
3. Tags the configured AI participants and the human (as decider).

Between artifacts: only one open ratification deliberation at a time. The
next one opens when the previous one decides.

### v1 simplification

For v1 we recognise an explicit `artifacts:` list in the manifest's
frontmatter and walk it in order. The richer "free-form artifacts named
in the body" parsing is deferred. We'll add a manifest-template helper
that emits the frontmatter list automatically when the user picks a
template at setup, so existing manifests still get auto-advance.

---

## Auto-running loop

Setup completion flips workspace state to `ACTIVE`. The conductor's
existing scheduler runs continuously:

- **Tick wakes up** → check open Asks. If any, sleep.
- **No open Asks** → run one planner step (existing `loop.plan`).
- **Planner picks a manual handle** → an Ask should already exist (or
  is generated this tick). Sleep.
- **Planner picks an AI handle** → invoke that agent (existing path).
- **All agents blocked / nothing to do** → state pill shows Quiet.

The status pill at the top of the UI reflects this:

- 🟢 **Working** — a planner step is running or about to.
- 🟡 **Your turn** — at least one open Ask.
- ⚪ **Quiet** — no open Asks and the planner has nothing to do.

The user can still pause via the existing control; we're just changing
the default from PAUSED to ACTIVE on setup completion.

---

## Vocabulary scrub

| Today | Tomorrow |
|---|---|
| Deliberation | hidden in default surface; "thread" in Raw tab |
| Move, PROPOSAL, CRITIQUE, SYNTHESIS, DECISION, OVERRIDE, DROP | hidden; appear only in Raw tab |
| Outcome manifest | "Plan" (or hidden behind Setup) |
| Compose move | replaced by Ask answer form |
| Conductor / loop / step | replaced by the Working/Quiet pill |
| `@handle`, `#0001` | "Claude", "Gemini", "this question" |

The activity feed renders moves into plain-English lines. Examples:

- `[PROPOSAL] @claude-opus on #0002` → "Claude proposed comparison criteria"
- `[CRITIQUE] @gemini-pro on #0002` → "Gemini pushed back on Claude's criteria"
- `[SYNTHESIS] @codex-gpt5 on #0002` → "Codex reconciled the disagreement"
- `[DECISION] @rakesh on #0002` → "You decided"

The Raw tab keeps everything as-is.

---

## Phasing

v1 of the overhaul (this work):

1. Design doc (this file).
2. Ask data model + storage.
3. Ask generator for `pending DECISION` and tagged `QUESTION`.
4. Ask answerer.
5. HTTP endpoints + UI client wrappers.
6. New home screen — banner, Ask card, activity feed, Raw tab.
7. Auto-advance for explicit `artifacts:` lists.
8. Auto-running loop (state defaults to ACTIVE on setup).

Stretch (v2+):

- `confirm` and `pick_any` shapes wired into a wider set of triggers.
- "Let an agent draft this for me" on `write` Asks.
- Free-form artifact extraction from manifest bodies (no `artifacts:` list).
- Activity feed with citations into the underlying moves.

---

## Open questions / things we're deferring

- **What if the user disagrees with all options in a `pick_one`?** v1: a
  hard-coded "None of the above — write your own" escape that converts
  the Ask to `write` in place. The submitted text becomes the DECISION
  body verbatim.
- **Multiple open Asks at once?** Possible (two deliberations both blocked
  on the human). v1 surfaces them as a stack; the banner says "3 questions
  waiting"; the user opens them one at a time.
- **Ask invalidation.** If the protocol state changes (e.g. an OVERRIDE
  resolves the deliberation) before the user answers, the Ask is closed
  with `status=closed` and a reason. The UI shows it as "no longer
  needed."
- **Activity feed phrasing.** v1 uses fixed templates per move-type. The
  per-deliberation context (e.g. "comparison criteria") comes from the
  deliberation's title.
