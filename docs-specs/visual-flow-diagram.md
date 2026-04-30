# Visual system-flow diagram — brainstorm

**Status:** brainstorm. No code yet. Goal of this doc: surface the
design questions, list the options, decide together. Once we settle
the shape, a follow-up doc captures the spec, and a `.claude/rules/`
rule keeps the diagram honest as the system evolves.

**Owner:** Claude (drafting), @rakesh (deciding)

## Decisions locked so far

- **Location:** right half of Simple mode (the slot we left
  reserved). The diagram sits next to the Ask card and activity feed.
- **Purpose:** operator clarity — "where is the system right now,
  what's blocked, what does it need from me." This is the *only*
  goal we optimise for. Codebase teachability is a non-goal here;
  if a design choice trades operator clarity for teachability we
  reject it. Teachability lives in the architecture docs (later).

---

## Why we want this

Quorum has a lot of moving parts: a workspace lifecycle, a manifest
lifecycle, per-deliberation move sequences, an autoloop tick, an
agent-invocation pipeline, an Ask flow, an auto-advance flow. Right
now the only way to understand where the system is at any moment is
to read state.yaml + plan + asks + events all at once and synthesise
in your head.

A live diagram fixes two problems:

1. **Operator clarity.** "Where are we right now?" answered visually,
   not by hunting across four endpoints.
2. **Codebase teachability.** A new contributor (human or AI) can
   look at the diagram and understand what the system does in 30
   seconds without reading source.

A bonus we'll need to design for explicitly: **drift prevention.**
The diagram is only useful if it's accurate. Once we add it to the
project, every code change that alters a flow has to update the
diagram in the same commit. That's where the future `.claude/rules/`
rule comes in.

---

## What's in scope — there isn't one flow, there are seven

The system has multiple interlocking lifecycles. Before we draw
anything, we have to agree on which to show, at what zoom level, and
how they relate. The seven I can see:

1. **Workspace lifecycle** — `INITIALIZED` → `ACTIVE` → (`PAUSED`) →
   `ARCHIVED`. The lifecycle of "is the loop turning at all?"
2. **Manifest lifecycle** — `DRAFTING` → `READY` → `LOCKED`. The
   plan's status. Locks once the seed deliberation decides.
3. **Deliberation lifecycle** — `OPEN` → `IN_REVIEW` →
   `BLOCKED_ON_HUMAN`/`BLOCKED_ON_ROUTING` → `DECIDED`/`ABANDONED` →
   `ARCHIVED`. One per deliberation; many in parallel.
4. **Move sequence within a deliberation** —
   `PROPOSAL` → `CRITIQUE(s)` → `SYNTHESIS` → `DECISION` (or
   `OVERRIDE`/`DROP`). The actual collaborative loop.
5. **Autoloop tick** — `Asleep` → `tick` → `state == ACTIVE?` →
   `open Asks?` → `cost ceiling?` → `plan` → `substitute around
   failures` → `dispatch one item` → `Asleep`. The conductor's
   heartbeat.
6. **Agent invocation pipeline** — `route` → `context_loaded` →
   `agent_started` → `subprocess` → `normalize` → `validate` →
   `append_move` → (`maybe_ratify_manifest`) →
   `update_inboxes`. The transport's path.
7. **Ask lifecycle** — `generated` (planner manual-block detected) →
   `open` → `answered` (or `closed`) → corresponding move written →
   loop resumes.

These nest: workspace contains manifest, manifest spawns
deliberations, deliberations contain moves, the autoloop dispatches
moves via the agent pipeline, the manual-block in the autoloop
generates Asks. Drawing all seven at once would be a wall of boxes.

---

## Open question 1: what does "operator clarity" actually require us
## to draw?

Given the locked decision (operator-only, Simple right-half), the
question is no longer "which views?" — it's "what's the minimum set
of nodes/regions an operator needs in one chart so they always
know what's happening?"

I'd argue operator clarity needs answers to three questions:

1. **Where in the project are we?** — i.e. which artifact's
   deliberation are we in, and what's done before it.
2. **What's the current step in that deliberation?** — proposal /
   critique / synthesis / decision.
3. **What's blocking forward motion right now?** — agent in flight,
   Ask waiting, all-agents-failing pause, cost ceiling, etc.

Anything outside those three answers is decoration. Specifically:

- **Workspace state pill** (`ACTIVE` / `PAUSED`) — already in the
  secondary header; don't duplicate. Diagram doesn't need it.
- **Manifest status** — already implicit in "where in the project
  are we" (we're past Setup → past Manifest LOCKED if we have any
  artifact deliberations).
- **Autoloop tick** — operator doesn't care about the heartbeat;
  they care about *outcomes* (waiting / working / blocked). The
  secondary header's stats already convey "AI activity: N" and
  "Awaiting your input: N." Hide.
- **Agent invocation pipeline internals** (`route → context →
  spawn → validate → append`) — operator doesn't care which step
  the agent is on, just that an agent is "thinking" (or failed).

So the diagram answers the three questions and stops. One picture,
not two.

**Proposed shape:** a horizontal lane of artifact deliberations
(left to right, in plan order). Each artifact is a column showing
its move sequence vertically. The currently-active column is
highlighted. Within it, the active move-step is highlighted. A small
status note on the active step explains the blocker if any
("Waiting on Claude" / "Waiting on you" / "Paused — every agent
failing").

That's it. Three regions, one screen, no toggling.

---

## Open question 2: how do we highlight "where the system is right now"?

The system is in multiple places at once. A workspace is `ACTIVE`,
the manifest is `LOCKED`, deliberation #0007 is `IN_REVIEW`,
deliberation #0008 is `BLOCKED_ON_HUMAN`, the autoloop is `Asleep`,
agent `@claude-opus` is mid-`subprocess` on #0007. Showing one
"current location" oversimplifies; showing all six at once is busy.

**Highlighting strategies, not mutually exclusive:**

1. **Pulsing accent ring** on the *primary* current node. Define
   "primary" as "the most user-relevant one right now" via priority:
   - if any Ask is open → highlight the Ask's source-deliberation's
     DECISION node
   - else if any agent is mid-flight → highlight that agent's node
     in the pipeline
   - else if the loop is sleeping → highlight the autoloop's
     "asleep" node
2. **Soft tints** on every node that's currently active (no
   pulsing) — multiple at once, but visually quiet so the primary
   pulse still wins attention.
3. **Greyed-out** for nodes the system has *passed through* (turned
   into history). E.g. once `PROPOSAL` lands, that node is grey;
   `CRITIQUE` goes active.
4. **Edge animation** — when a transition happens (e.g.
   `PROPOSAL` → `CRITIQUE`), the edge between them briefly
   animates / pulses to signal motion. SSE event-driven.

**My lean:** all four. They compose. Primary pulse for the eye-
attractor; tints for "what else is happening"; greyed for history;
brief edge animation on transitions makes the diagram feel alive.

---

## Open question 3: how often does the diagram refresh?

The data sources for "where am I" are:
- `state.yaml` — workspace state (changes rarely)
- `outcome-manifest.md` frontmatter — manifest status (rarely)
- `deliberations/*.md` frontmatter — deliberation statuses (per
  move append)
- `asks/*.json` — open Asks (per Ask create/answer)
- `events.jsonl` — every agent event (frequent)
- `/api/plan` — what's about to happen (re-derived, polled)

Two reasonable cadences:

- **Event-driven only.** Subscribe to SSE; redraw the highlighted
  nodes on each event. Cheap. Loses no information because every
  state change emits an event.
- **Event-driven + 5s poll.** SSE for liveness, 5s poll as a
  safety net. Matches what the secondary header already does.

**My lean:** event-driven only for the diagram. The secondary
header's poll is enough belt-and-suspenders for the whole UI.

---

## Open question 4: what does a node represent, exactly?

Each node will eventually need:
- a **name** (the user-facing label)
- a **state** (`pending` / `active` / `passed` / `skipped` /
  `failed`)
- maybe a **count** (e.g. "3 critiques received" on the CRITIQUE
  node)
- a **link** somewhere — clicking should usually navigate to
  whatever surface lets the user act on it (deliberation file,
  Ask card, raw editor, …)

We need to pick a small, explicit vocabulary for node states so the
diagram doesn't accumulate ad-hoc colours over time.

**Proposed node state set:**
- `pending` — neutral grey, dashed outline
- `active` — accent-primary fill
- `passed` — neutral grey, solid outline (history)
- `skipped` — light strikethrough (e.g. a deliberation that
  reached `OVERRIDE` skips the rest of the move sequence)
- `failed` — accent-danger fill (the agent kept failing; substitute
  in progress; or paused on `agents_unreachable`)
- `awaiting-human` — accent-warning fill (Ask is open here)

These map cleanly to the design-system tokens we already use; no
new colours.

---

## Open question 5: how do we make sure it doesn't drift from code?

This is the load-bearing point. Two layers of defence.

**Layer 1 — the rule.**
A new `.claude/rules/visual-flow.md` (always-applied) that says:
- This file lists every node and edge in the diagram with a one-
  line description and the source-of-truth file/line for the
  state/transition.
- When you change any of those source-of-truth files in a way that
  alters a node's behaviour or adds/removes a transition, you
  update this file in the same commit and update the diagram
  source.
- If you can't reconcile, you stop and ask the user.

**Layer 2 — single source of truth for the diagram.**
The diagram is rendered from a JSON/YAML schema (e.g.
`docs-specs/flow.yaml`). The UI reads it and renders. The schema is
the *only* place node/edge definitions live. The rule above tells
the next session "if you touch X, also update flow.yaml."

We could go one step further: **derive the schema from typed code
constants** (e.g. the protocol move types are already an enum;
deliberation statuses are an enum; workspace state is an enum). Any
state added to the enum without an entry in flow.yaml could be
caught by a test. This is most rigorous; needs more thought before
committing.

**My lean:** start with the schema + rule (Layer 1+2). Defer the
test-based enforcement until we hit our first drift incident.

---

## Open question 6: what's the visual style?

Now that we're committed to "one chart, three regions" (artifact
columns, move steps inside each, a status note on the active step),
the style choice narrows:

- **Horizontal artifact columns + vertical move steps.**
  Read left-to-right for "where in the project," top-to-bottom
  inside the active column for "where in the deliberation."
- **Vertical artifact rows + horizontal move steps.**
  Same content, transposed. Reads top-to-bottom.

The right-half slot is taller than wide. Vertical artifact rows fit
the slot better; horizontal artifact columns fit better if we ever
move it elsewhere.

**My lean:** vertical artifact rows. Each artifact gets a row;
inside the row, four little step nodes (Propose → Critique →
Synthesise → Decide); the row's pulsing step is where the system
is. Past artifacts collapse to a single "done" badge. Future
artifacts collapse to a single "pending" badge. Compact, fits the
slot, scales to many artifacts.

---

## Data sources, mapped to nodes

For when we lock the design, here's the mapping cheat-sheet I'll
lift into the spec:

| Node / region | Data source |
|---|---|
| Workspace state pill | `state.yaml: state` |
| Manifest status | `outcome-manifest.md` frontmatter `status` |
| Active deliberations list | `deliberations/*.md` frontmatter `status` filtered to non-terminal |
| Per-deliberation move sequence | `## Contributions` section parsed |
| Autoloop "asleep / ticking / dispatching" | derived from `events.jsonl` recency + plan |
| Agent pipeline current step | last `events.jsonl` entry for the active deliberation |
| Pending Asks | `asks/*.json` filtered to `status: open` |
| Per-handle health ring | `/api/participants` `live_health.on_path` |

All exposed via existing endpoints — no new backend work for the
data plane.

---

## Sketch — the right-half slot

Vertical artifact rows. Currently-active row expanded to show its
four step nodes. Past rows collapsed; future rows collapsed.

```
┌─────────────────────────────────────────────┐
│ option-analysis.md                done ✓    │
├─────────────────────────────────────────────┤
│ recommendation.md                 done ✓    │
├─────────────────────────────────────────────┤
│ course-correction-plan.md   ◀── active      │
│   Propose ─► Critique ─► Synthesise ─► Decide
│      ✓          ✓            ●           …  │
│                            ─────                 ▲ pulsing
│   Claude is synthesising. ETA ~30s.         │
├─────────────────────────────────────────────┤
│ rollback-plan.md             pending        │
├─────────────────────────────────────────────┤
│ v2-spec.md                   pending        │
└─────────────────────────────────────────────┘
```

When the active row is "Awaiting your input," the same row looks
like:

```
│ course-correction-plan.md   ◀── awaiting you │
│   Propose ─► Critique ─► Synthesise ─► Decide│
│      ✓          ✓            ✓            ●  │
│                                          ─── │
│   Your turn — open the Ask above to decide.  │
```

The status note under the step nodes is the operator's "what do I
do next" channel. It changes based on planner state.

---

## Things I still want @rakesh to decide

1. **Highlight strategy.** Proposed: pulse the active step node;
   grey out passed steps; dashed/muted future steps; brief edge
   animation on transitions. Status note under the row carries the
   "what's blocking" sentence.
2. **Drift defence.** Proposed: a single `docs-specs/flow.yaml`
   schema as source of truth (artifacts, steps, transitions). The
   diagram renders from it; a `.claude/rules/visual-flow.md` always-
   applied rule says "if you change a flow, update flow.yaml in the
   same commit." Add tests that pin enums (move types, deliberation
   statuses) to the schema only after the first drift incident.
3. **Style & layout.** Proposed: vertical artifact rows; active row
   expanded; past/future rows collapsed.
4. **Refresh cadence.** Proposed: SSE-driven only (no extra poll —
   the secondary header's poll is enough).
5. **Two edge cases I want a call on:**
   - When agents are *substituting* (Gemini failed → Claude
     stepping in for the same step), do we surface that visually
     (swap the participant avatar in the active step) or hide it?
     I lean surface, with a small "swapped" badge.
   - When the active deliberation hits `agents_unreachable` and the
     workspace pauses, how loud should that be? I lean: row turns
     amber-bordered, status note says "Paused — every agent failing.
     [Restart conductor]" with a link to the right surface.

Once these land we'll write the spec. The spec then gets a follow-up
`.claude/rules/visual-flow.md` so future sessions can't change a
flow without updating the diagram.

---

## What's NOT in scope yet

- The mobile / responsive story. Diagrams are tricky on phones; the
  current UI is laptop-optimised anyway.
- Animation choreography beyond simple pulses (no Lottie etc.).
- Embeddable diagram exports (PNG/SVG download).
- A diff view between "what the system is doing now" and "what it
  did 5 minutes ago."

These are real but later. Get the static + live-highlight working
first.
