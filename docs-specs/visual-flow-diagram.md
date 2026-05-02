# Visual system-flow diagram — brainstorm

**Status:** brainstorm. No code yet. Goal of this doc: surface the
design questions, list the options, decide together. Once we settle
the shape, a follow-up doc captures the spec, and a `.claude/rules/`
rule keeps the diagram honest as the system evolves.

**Owner:** Claude (drafting), @rakesh (deciding)

**Pre-requisite read:** `docs-specs/system-flow-stages.md`. The
master flow it locks (S1–S6, the per-deliberation inner loop, the
orthogonal pause conditions) is the thing this diagram renders.
Don't proceed without it.

---

## Decisions locked so far

- **Location:** right half of Simple mode (the slot we left
  reserved). The diagram sits next to the Ask card and activity feed.
- **Purpose:** operator clarity — "where is the system right now,
  what's blocked, what does it need from me." Codebase teachability
  is explicitly NOT a goal; that lives in architecture docs.
- **What it renders:** the master flow from
  `system-flow-stages.md` — S1..S6 with the per-stage inner
  machinery and orthogonal pause/block badges.
- **Style/layout — REVISED:** a real **node-graph** (not the
  earlier vertical-rows sketch). Stages are nodes connected by
  edges. The active stage *expands inline* to show its sub-flow;
  finished stages collapse to a "done" badge but stay clickable
  to expand again. For S4 specifically: an inner "document
  gallery" node holds a horizontally-scrollable strip of
  per-artifact boxes; the active artifact box is highlighted and
  auto-scrolls into view; that box connects via an edge to the
  Propose → Critique → Synthesise → Decide sub-flow.
- **Library:** **`@xyflow/react` (React Flow v12)** with
  **`@dagrejs/dagre`** for auto-layout. ~65 KB gz total, MIT,
  actively maintained. Custom nodes are first-class React
  components — exactly what we need for the document-gallery
  node and the move-step sub-flow node. Sub-flow grouping is
  built-in (`parentId` + `extent: 'parent'`). Pan/zoom built-in.
  Animated edges built-in. Memoized rendering handles SSE-driven
  updates trivially.
- **Drift defence:** single source of truth schema
  (`docs-specs/flow.yaml`) + a `.claude/rules/visual-flow.md`
  always-applied rule. The schema feeds React Flow's
  `nodes` / `edges` arrays. Tests added later if drift occurs.
- **Refresh cadence:** SSE-driven only (no extra polling — the
  secondary header already polls).

---

## What the diagram has to render — the master flow at a glance

Master flow lives in `system-flow-stages.md`. Recap, focused on
what the diagram shows:

| Stage | What's happening | What the diagram renders |
|---|---|---|
| **S1 Initialise** | Workspace files exist, nothing else. | Probably elided — too transient to deserve real estate. The user only sees this for ~2 seconds after `quorum init`. |
| **S2 Set up** | User adds problem statement, participants, context. Optionally picks manifest template. | Setup checklist: problem statement ✓/✗, participants count, context items, "Start collaboration" button when ready. NEEDS_DIGESTION sub-state surfaced. |
| **S3 Bootstrap the plan** | Seed deliberation #0001. Agents draft the manifest; user decides; manifest LOCKED. | Single "Drafting plan" row showing the move-step sequence (Propose → Critique → Synthesise → Decide) inside the seed. NEEDS_MANIFEST_RATIFICATION recovery surfaced if it fires. |
| **S4 Work the artifacts** | Per-artifact deliberations, one at a time per auto-advance. | Vertical rows, one per artifact in the manifest. Past = collapsed "done" badge. Active = expanded with move-step sequence. Future = collapsed "pending" badge. |
| **S5 Closing ceremony** | Optional, user-triggered. Produces `summary.md`. | Visible only when triggered. One row showing the closing deliberation's move sequence. |
| **S6 Archived** | Workspace shelved. | Diagram replaced by a simple "Archived" panel; no live data to track. |

Plus orthogonal pause/block badges that overlay the active row's
status note when fired:
- `AWAITING_HUMAN` (open Ask) — "Your turn — answer the question above."
- `AGENTS_UNREACHABLE` (autoloop paused) — "Paused — every agent is failing."
- `AWAITING_PERMISSION` — "An agent needs permission. Approve or deny in the Permissions dialog."
- `BLOCKED_ON_ROUTING` (per-deliberation) — "Couldn't route — fix the participant or change routing config."
- Cost ceiling reached — "Spend ceiling reached; raise the limit or end the project."

---

## How the node-graph composes

Top-level graph is the master-flow spine: stage nodes connected
left-to-right (or top-to-bottom — we'll let dagre decide based on
viewport aspect):

```
[ S1 Init ] ─► [ S2 Setup ] ─► [ S3 Bootstrap ] ─► [ S4 Work ] ─► [ S5 Closing ] ─► [ S6 Archived ]
```

Each stage node is a custom React component with two visual states:

- **Collapsed** (past, future, or unfocused): a small badge — the
  stage name and a status mark (✓ done, ◯ pending, ● active).
- **Expanded** (active stage, or any stage the user has clicked
  to view): the node grows to contain its sub-flow. Edges from
  the node fan out to its children.

The active stage auto-expands. As the system advances S3 → S4,
S3 collapses (with ✓), S4 expands. Clicking a collapsed past
stage re-expands it (in "done" visuals); clicking again
collapses. Active stage stays expanded.

### Per-stage expanded shapes

**S2 (Set up)** expands into a checklist sub-graph:
```
[ Setup ▼ ]
   ├─► [ ✓ Problem statement ]
   ├─► [ ✓ Participants 3/3 reachable ]
   ├─► [ ◯ Context optional ]
   └─► [ Start collaboration → ]   (button-node, only enabled when checks pass)
```

**S3 (Bootstrap the plan)** expands into the move-step sub-flow:
```
[ Bootstrap ▼ ]
   └─► [ Propose ] ─► [ Critique ] ─► [ Synthesise ] ─► [ Decide ]
                                                       ^
                                                       active step (pulses)
```

**S4 (Work the artifacts)** is the rich one — two layers:
```
[ Work ▼ ]
   └─► [ Document gallery ]
          ┌──────────────────────────────────────────────────────────┐
          │  [opt-anal ✓] [recom ✓] [course ●] [rollback ◯] [v2-spec ◯]│  ← horizontal strip
          └────────────────────────│─────────────────────────────────┘
                                   │
                                   ▼  (edge from active doc box)
                          [ Propose ] ─► [ Critique ] ─► [ Synthesise ] ─► [ Decide ]
```

The doc gallery is one node containing N artifact boxes. The
active box is highlighted and auto-scrolls into view (the
gallery is horizontally scrollable; we set `scrollLeft` on
state change). An edge connects the active box specifically to
the move-step sub-flow node below.

Clicking a finished doc box re-expands it in "done" visuals (its
own greyed-out move-step sub-flow showing the path it took). The
active doc keeps its live sub-flow visible in parallel.

**S5 (Closing)** mirrors S3 — single move-step sub-flow.

**S6 (Archived)** collapses the entire graph; the right-half
slot becomes a static "Archived" panel.

---

## Open question 1: per-stage rendering shapes (sketches above)

Each stage's diagram content is different. Sketches below for
each stage; commit on these or push back.

### S2 (setup)

```
┌────────────────────────────────────────────────┐
│ Set up                                         │
├────────────────────────────────────────────────┤
│ ✓ Problem statement                            │
│ ✓ Participants (3 registered, all reachable)   │
│ ◯ Context — 0 attached, optional               │
│ ◯ Manifest template — using default            │
│                                                │
│   [ Start collaboration ]                      │
└────────────────────────────────────────────────┘
```

Active blockers (e.g. "1 doc still digesting") appear inline with
a warning badge. The Start button greys out until the locked
S2→S3 bar is met (problem statement + ≥1 CLI participant).

### S3 (drafting the plan)

```
┌────────────────────────────────────────────────┐
│ Drafting the plan                              │
├────────────────────────────────────────────────┤
│ Propose ─► Critique ─► Synthesise ─► Decide    │
│    ✓          ✓            ●           …       │
│                          ─────                 │
│ Claude is synthesising. ETA ~30s.              │
└────────────────────────────────────────────────┘
```

Active step (●) pulses. Past steps grey. Future steps dashed.
Status note carries the operator-relevant sentence.

If `NEEDS_MANIFEST_RATIFICATION` fires:
```
│  ⚠ Recovery needed                             │
│  Seed decided but manifest didn't lock.        │
│  Open the Raw editor → outcome-manifest.md.    │
│  [ Open Raw editor ]                           │
```

### S4 (working the artifacts)

```
┌────────────────────────────────────────────────┐
│ Working the artifacts                          │
├────────────────────────────────────────────────┤
│ option-analysis.md          ✓ done             │
├────────────────────────────────────────────────┤
│ recommendation.md     ◀── active               │
│   Propose ─► Critique ─► Synthesise ─► Decide  │
│      ✓          ✓            ●           …     │
│                            ─────               │
│   Claude is synthesising. ETA ~30s.            │
├────────────────────────────────────────────────┤
│ course-correction-plan.md   pending            │
├────────────────────────────────────────────────┤
│ rollback-plan.md            pending            │
├────────────────────────────────────────────────┤
│   [ Wrap up project ]   ← appears only when    │
│                            every artifact is   │
│                            terminal            │
└────────────────────────────────────────────────┘
```

Done rows can be clicked to expand and view their move sequence
read-only. Pending rows can be clicked to preview their question
(from the manifest) but can't act yet.

When the user REOPENs a done artifact (Q3 → free multiplexing),
its row goes back to "active" while the previously-active row
stays active too. So multiple rows could be expanded
simultaneously — that's fine, the layout supports it.

### S5 (closing ceremony) — optional

```
┌────────────────────────────────────────────────┐
│ Wrapping up                                    │
├────────────────────────────────────────────────┤
│ Closing deliberation                           │
│   Propose ─► Critique ─► Synthesise ─► Decide  │
│      ●          …            …           …     │
└────────────────────────────────────────────────┘
```

Mirrors S3. Output is `summary.md`. After DECISION, workspace
flips to `COMPLETED` (workspace state).

### S6 (archived)

```
┌────────────────────────────────────────────────┐
│ Archived                                       │
│ This workspace was archived on 2026-04-30.     │
│ See `summary.md` for the project recap.        │
└────────────────────────────────────────────────┘
```

Read-only. No diagram chrome — just a panel.

**Push back on any of these sketches?** They're approximate; we
firm up exact wording / spacing when we build.

---

## Open question 2: highlight strategy (proposed; needs ack)

Same proposal as before — pulse the *primary* active step,
muted/grey for passed steps, dashed for future steps, brief edge
animation on transition. Status note under each active row
carries the "what's blocking" sentence in plain English.

The active row's *border* tints based on orthogonal blocks:
- Default border (no orthogonal block active): `border-default`
- `AWAITING_HUMAN`: `border-accent-warning`
- `AGENTS_UNREACHABLE` / `BLOCKED_ON_ROUTING`: `border-accent-danger`
- `AWAITING_PERMISSION`: `border-accent-warning`

Edge animation: when a step transitions from active to done,
the connector edge between that step and the next briefly pulses
along its length (~600ms). SSE event-driven.

**Anything to change in this strategy?**

---

## Open question 3: substitution visibility

When the autoloop substitutes a failing handle (Gemini → Claude
fallback for the same step), should the diagram show it?

- **A. Surface it.** The active step's participant avatar swaps
  in real time. A small "swapped" badge appears next to the new
  avatar with a tooltip explaining ("Gemini failed 3× in a row;
  Claude is taking over").
- **B. Hide it.** The active step just shows whichever handle is
  currently dispatched. The fact that an earlier substitution
  happened is in the audit trail (Activity feed) but not in the
  diagram.

I lean A. Substitution is a non-trivial change in who's doing
the work; hiding it leaves the user wondering why the avatar
changed.

**Your call — A or B?**

---

## Open question 4: pending artifacts — show all or paginate?

A manifest could in theory list 20+ artifacts. With each
collapsed row at ~32px, 20 rows fits on a tall screen but is
ugly. With 50+ rows we have a real layout problem.

- **A. Show them all, scrollable.** The right-half slot scrolls
  if needed. Same component as the activity feed — virtual
  scrolling if it gets large.
- **B. Show only the active artifact + N around it.** A "show
  all" toggle reveals the full list. Default is the active
  context (e.g. previous done + active + next 2 pending).

I lean A. Real workspaces probably stay under 10 artifacts and
the simpler "always show everything" model is easier to predict.
We add B only if it becomes a problem.

**Your call — A or B?**

---

## Open question 5: drift defence — schema or hand-rendered?

Two flavours:

- **A. Schema-driven (`docs-specs/flow.yaml`).** A YAML file
  enumerates stages, sub-steps, transitions, badges. The UI
  reads it and renders. Adding a new stage = edit YAML + ship.
  A `.claude/rules/visual-flow.md` rule says "if you add a
  stage / phase / pause condition in code, update flow.yaml in
  the same commit."
- **B. Hand-rendered React.** No external schema; the diagram
  component knows the master flow in TS. Adding a new stage =
  edit the component. The same `.claude/rules/visual-flow.md`
  rule covers it (just enforces "update visual-flow component
  when flow changes").

I lean A. The schema is small (~50 lines for the master flow),
machine-readable, and survives UI rewrites. The component reads
the schema; the schema reads the master-flow doc. One file to
keep accurate per stage change.

Schema sketch:
```yaml
# docs-specs/flow.yaml
stages:
  - id: S2
    name: Set up
    checks:
      - problem_statement
      - participants_min_one_cli
      - digestion_idle
    forward_action: start-collaboration
  - id: S3
    name: Drafting the plan
    sub_steps: [propose, critique, synthesise, decide]
    recovery_states:
      - needs_manifest_ratification
  - id: S4
    name: Working the artifacts
    rendering: per-artifact-rows
    sub_steps: [propose, critique, synthesise, decide]
    forward_action: wrap-up   # appears when all rows terminal
  ...
pause_conditions:
  - id: AWAITING_HUMAN
    label: Your turn — answer the question
    border: warning
  - id: AGENTS_UNREACHABLE
    label: Paused — every agent failing
    border: danger
  ...
```

**Your call — A (schema) or B (hand-rendered)?**

---

## Data sources, mapped to nodes

For when we build, here's the cheat-sheet:

| Element | Data source |
|---|---|
| Current stage | `state.yaml: state` + manifest status + presence of deliberations |
| S2 setup checks | `problem-statement.md` non-empty; `participants.md` parsed; pending digestion count |
| S3 active step | seed deliberation's contributions (`PROPOSAL`/`CRITIQUE`/`SYNTHESIS`/`DECISION` presence) |
| S4 artifact rows | `outcome-manifest.md` artifacts list + per-deliberation status |
| S4 active step | active artifact deliberation's contributions parse |
| Per-step participant | last `agent_started` event for the active deliberation |
| Status note text | derived from planner phase (`next_actions._resolve_phase`) |
| Substitution | recent `agent_failed` count per (handle, delib, move_type) — same source as autoloop |
| Pause-block borders | planner phase + per-deliberation status |

All of these are already exposed via existing endpoints. Zero
new backend work for the data plane.

---

## What's NOT in scope

- Mobile / responsive layout. Diagrams are tricky on phones; the
  current UI is laptop-optimised.
- Animation choreography beyond simple pulses (no Lottie etc.).
- Embeddable diagram exports (PNG/SVG download).
- Time-travel / "what was the system doing 5 minutes ago."
- Cross-workspace observability — that's the system retrospective
  feature (`docs-specs/system-retrospective.md`).

---

## Things I want @rakesh to settle

1. Per-stage node-graph sketches above (the new node-and-edge
   shapes, especially S4's doc-gallery + move-step sub-flow) —
   anything wrong or missing?
2. Q3 — surface substitution swaps in the active step (A) or
   hide them (B)?
3. Q4 — pending-artifact strip: show all (A, with horizontal
   scroll) or paginate around the active one (B)?
4. Q5 — drift defence: schema-driven (A, `flow.yaml`) or
   hand-rendered TS (B)? My lean is A; the schema feeds React
   Flow's nodes/edges arrays.
5. Anything to change about the highlight strategy (Q2)?

Once these land, we write the spec, then add the
`@xyflow/react` and `@dagrejs/dagre` dependencies, then build.
