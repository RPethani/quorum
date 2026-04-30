# System flow — stages, transitions, loops

**Status:** brainstorm. No UI here. Goal: get the actual lifecycle
of the system written down — stages, what triggers each transition,
where the flow can loop, where it can branch. Once this is agreed,
the UI in `visual-flow-diagram.md` renders directly from it.

**Owner:** Claude (drafting), @rakesh (deciding what's right)

**Accuracy bar.** This doc is supposed to be a 100% faithful
mirror of the *current* code. Every state, phase, transition, and
file path here was verified against the source. The audit anchor
files are:

- `conductor/src/quorum_conductor/workspace/state.py` —
  `WorkspaceState` enum + `ManifestProgress`
- `conductor/src/quorum_conductor/workspace/init.py` — initial
  workspace scaffold
- `conductor/src/quorum_conductor/workspace/bootstrapper.py` —
  seed deliberation creation (`needs_bootstrap`,
  `bootstrap_seed_deliberation`)
- `conductor/src/quorum_conductor/workspace/ratify.py` —
  manifest LOCKED transition
- `conductor/src/quorum_conductor/workspace/auto_advance.py` —
  per-artifact deliberation opening
- `conductor/src/quorum_conductor/workspace/archive.py` —
  ARCHIVED transition
- `conductor/src/quorum_conductor/server/autoloop.py` — tick
  policy, `agents_unreachable` pause
- `conductor/src/quorum_conductor/server/http_app.py` —
  `_handle_wizard_apply` / `_activate_if_ready`
- `conductor/src/quorum_conductor/core/loop.py` —
  `_TERMINAL_STATUSES`, planner
- `conductor/src/quorum_conductor/core/next_actions.py` —
  every `WorkspacePhase` value

If you change any of these, this doc must change too in the same
commit. (We'll formalise that with a `.claude/rules/` rule when
the visual diagram lands.)

## Decisions locked so far

- **S2 → S3 bar:** problem statement non-empty AND ≥1 CLI
  participant registered. (Without a CLI participant the loop
  has nothing to dispatch.)
- **Starting collaboration is explicit, not implicit.** The wizard
  Apply button must NOT auto-activate the workspace. Instead, a
  visible "Start collaboration" action is the trigger to flip
  state to `ACTIVE` and begin the loop. (This reverses what's in
  the code today — `_handle_wizard_apply._activate_if_ready` flips
  state silently. We'll need to remove that and add the explicit
  trigger.)
- **DROP on the seed manifest deliberation is rejected.** *(Open Q1
  resolved + implemented.)* The seed deliberation (the one that
  ratifies `outcome-manifest.md`) cannot be DROPped — without a
  ratified manifest the workspace has no plan to work against.
  Per-artifact ratification deliberations (e.g. the deliberations
  ratifying `option-analysis.md`, `recommendation.md`, etc.)
  are NOT protected: the user is free to drop work on any specific
  artifact without abandoning the whole project. The check lives
  in `core/validator.py:validate_move` (matches
  `deliberation_ratifies == "outcome-manifest.md"` only). Both
  call sites (`transport/invoker.py` for agents,
  `server/http_app.py:_handle_append_move` for human-authored
  moves) read the source deliberation's `ratifies:` field and
  pass it through. Error message: *"DROP is not permitted on the
  seed deliberation (which ratifies the outcome manifest).
  Without a ratified manifest there is no plan to work against.
  Use DECISION to ratify or OVERRIDE to terminate, then archive
  the workspace if you want to abandon the project."* Tests in
  `tests/test_validator.py`.

---

## Two coupled state machines power the master flow

Before listing stages I need to be precise about what's actually
state in this codebase. The master flow is driven by **two
coupled state machines**:

### 1. Workspace state (`state.yaml: state`)

`WorkspaceState` enum has seven values. Three of them are
aspirational — defined but never set by any code path today:

| Value | Used in code? | Set by |
|---|---|---|
| `INITIALIZED` | yes | `workspace/init.py` (on `quorum init`); `archive.unarchive_workspace` |
| `READY` | **no** — defined but unreached | (none) |
| `ACTIVE` | yes | `_handle_wizard_apply._activate_if_ready`; CLI `_cmd_run` |
| `PAUSED` | yes | autoloop on `agents_unreachable`; CLI `_cmd_pause`; `_cmd_run` exit |
| `COMPLETED` | **no** — defined but unreached | (none) |
| `COMPLETED_AUTONOMOUS` | **no** — defined but unreached | (none) |
| `ARCHIVED` | yes | `workspace/archive.archive_workspace` |

So in practice the workspace cycles
`INITIALIZED → ACTIVE → PAUSED → ACTIVE → … → ARCHIVED`. The
`READY` and `COMPLETED*` slots exist as design intent for stages
that aren't built yet (closing ceremony / completion handshake).

### 2. Manifest status (`outcome-manifest.md` frontmatter `status`)

A separate three-state machine:

| Value | Used in code? | Set by |
|---|---|---|
| `DRAFTING` | yes | initial template; default when manifest doesn't exist |
| `READY` | partial | string-matched as a "don't re-bootstrap" signal in `bootstrapper.needs_bootstrap`; `next_actions` treats it as equivalent to LOCKED for routing decisions; **never written by automated code** |
| `LOCKED` | yes | `workspace/ratify.maybe_ratify_manifest` (after seed DECISION/OVERRIDE) |

In practice the manifest goes `DRAFTING → LOCKED` directly. The
`READY` slot is a tolerated intermediate state if the user
hand-edits, but no protocol move transitions to it.

### How they couple

The master flow advances when both machines move forward together:

- **S1 Initialise:** workspace `INITIALIZED`, manifest doesn't
  exist yet (or `DRAFTING` placeholder)
- **S2 Set up:** workspace still `INITIALIZED`, manifest still
  `DRAFTING`
- **Start collaboration:** workspace `INITIALIZED → ACTIVE`
  (manifest unchanged at `DRAFTING`)
- **S3 Bootstrap the plan:** workspace `ACTIVE`, manifest
  `DRAFTING`. Autoloop's first tick scaffolds the seed
  deliberation.
- **Seed DECISION:** manifest `DRAFTING → LOCKED` (workspace
  unchanged at `ACTIVE`). Auto-advance opens the first artifact.
- **S4 Work the artifacts:** workspace `ACTIVE`, manifest `LOCKED`.
- **S5 Closing ceremony (not built):** would presumably move
  workspace to `COMPLETED` or `COMPLETED_AUTONOMOUS`. The fields
  `closing_ceremony_eligible` and `final_deliberation_id` exist
  in `state.yaml` for this; nothing sets them.
- **S6 Archive:** workspace `ANY → ARCHIVED` via
  `archive_workspace`.

---

## The seven sub-flows are projections of one master flow

I listed seven sub-flows earlier (workspace, manifest, deliberation,
move sequence, autoloop tick, agent pipeline, Ask). They look like
seven things; they're really one.

They project onto a single timeline like this:

- The **workspace lifecycle** is the outer container. Stages live
  inside it.
- The **manifest lifecycle** is one stage of the workspace lifecycle
  (the "draft the plan" stage).
- The **deliberation lifecycle** is the inner machinery that powers
  every stage from "draft the plan" onward — one instance per
  artifact.
- The **move sequence** is the inner machinery of one deliberation.
- The **autoloop tick** and **agent pipeline** are the *engine* that
  moves the workspace through its stages — they aren't stages
  themselves; they're how stages advance.
- The **Ask lifecycle** is the protocol for "the user is currently
  the actor in this stage." It's a transient state, not a stage.

So: there's one master flow with N stages. Each stage has internal
machinery. Some stages contain a sub-loop. The engine and the Ask
protocol are *orthogonal* — they apply at every stage, not at one.

---

## The master flow — proposed stages

I'm picking names that describe what the *user* experiences, not
what the conductor is doing internally. Where I'm uncertain I flag
it.

### S1 — Initialise

The workspace has been created on disk but nothing else has
happened.

- **Files in this state:** `state.yaml` exists with
  `state: INITIALIZED`, `manifest.status: DRAFTING`. Mostly-empty
  `problem-statement.md`. Empty `participants.md` (just the table
  header). No deliberations. No `outcome-manifest.md` body yet
  (template only).
- **Trigger to enter:** `quorum init <path>` runs from the CLI.
  The UI does NOT scaffold workspaces on its own — the user
  must `quorum init` first or open an existing workspace.
- **What the user does:** nothing yet — they've just landed in a
  fresh workspace.
- **Trigger to leave:** the user starts adding setup data (any
  edit to `problem-statement.md`, `participants.md`, or the
  context registers). No state-machine transition fires; we just
  stop calling this S1 in our heads.

### S2 — Set up

The user is filling in what the project is and who's helping.

- **Files in this state:** `problem-statement.md` may be partial
  or full; `participants.md` may have 0+ entries; context files
  may exist; manifest template may be picked. Workspace state
  still `INITIALIZED`. Manifest still `DRAFTING`.
- **Trigger to enter:** any setup-related edit from S1.
- **What the user does:** writes the problem statement, registers
  participants (CLI agents + the human), attaches context (repos /
  docs / notes / URLs), optionally picks a manifest template.
- **S2 sub-block — context digestion.** When the user attaches a
  repo or a long doc, the conductor's planner can decide it needs
  to be digested before agents can read it. While digestions are
  pending, `next_actions._resolve_phase` returns
  `NEEDS_DIGESTION`. This is a real S2 sub-state that's not
  resolved by the user typing — they (or an agent) must run a
  digestion job. The phase blocks forward motion to S3 until
  pending digests reach zero.
- **Trigger to leave (forward) — locked decision:** the user
  explicitly clicks "Start collaboration." This action MUST require:
  - non-empty `problem-statement.md`
  - ≥ 1 CLI-transport participant in `participants.md`
  - 0 pending digests (or the user explicitly skips them)
  - 0 unhealthy participants flagged by the doctor (or the user
    explicitly chooses to start anyway)

  When triggered, this flips `state.state` to `ACTIVE`. Today
  the codebase auto-flips inside `_handle_wizard_apply._activate_if_ready`
  whenever the wizard runs — that's the implicit behaviour we're
  reversing.

### S3 — Bootstrap the plan (a.k.a. seed deliberation #0001)

State has flipped to `ACTIVE`. The autoloop is ticking. On the
first tick the autoloop scaffolds a seed deliberation `#0001`
whose frontmatter says `ratifies: outcome-manifest.md`. Agents
start drafting the plan.

- **Files in this state:** `deliberations/0001-*.md` exists, has
  `status: OPEN`. `outcome-manifest.md` is a placeholder with
  `status: DRAFTING`. Workspace `state.state` is `ACTIVE`.
- **Trigger to enter:** `state.state` is `ACTIVE` AND
  `bootstrapper.needs_bootstrap` returns true (no deliberation
  files exist yet, manifest is not LOCKED/READY). The autoloop's
  `_tick_once` calls `bootstrap_seed_deliberation` and the seed
  is created on disk. **Important:** the seed is NOT created at
  `quorum init` time. It's only created after the user clicks
  "Start collaboration" and the autoloop runs once. This is why
  pre-S3 there are no deliberation files.
- **Inner machinery:** the **per-deliberation move sequence**
  runs on `#0001` (see "Inner loop" below). Manifest sits at
  `DRAFTING` the whole time.
- **Trigger to leave (happy path):** terminal move on #0001:
  - `DECISION` → `maybe_ratify_manifest` writes the agreed body
    into `outcome-manifest.md` and flips manifest status to
    `LOCKED`. Then `auto_advance` opens the first artifact's
    deliberation. Forward to S4.
  - `OVERRIDE` → same code path as DECISION (terminal).
  - `DROP` → seed abandoned. **Open question:** what's the
    recovery path? Today nothing handles this — DROP on #0001
    leaves the workspace stuck with `seed_decided=True` and
    `manifest_status=DRAFTING` (see recovery-path below).
- **S3 stuck state — `NEEDS_MANIFEST_RATIFICATION`.** A real
  recovery path exists in `next_actions.py`. If the seed
  deliberation reaches a terminal status but
  `outcome-manifest.md` is still `DRAFTING` (because
  `maybe_ratify_manifest` failed for some reason — wrong move
  body, manifest file was deleted, etc.), the planner returns
  `NEEDS_MANIFEST_RATIFICATION`. The user has to manually edit
  `outcome-manifest.md` (Raw editor) to flip its status. This
  is not "transition to S4 done" — it's a stuck-S3 state the
  user has to dig out of.

### S4 — Work through the artifacts

The plan is locked. The conductor walks the manifest's listed
artifacts in order. For each artifact it opens a ratification
deliberation. Per-deliberation move sequence runs. On terminal,
the next artifact's deliberation opens.

- **Files in this state:** `outcome-manifest.md` is `LOCKED`.
  At any moment, exactly *one* artifact deliberation is open and
  non-terminal (auto-advance enforces this); zero or more are
  already terminal.
- **Trigger to enter:** manifest just transitioned to `LOCKED`
  from S3.
- **Inner machinery:** for each artifact:
  - `auto_advance.maybe_open_next_artifact_deliberation` opens
    the deliberation if not already open.
  - The per-deliberation move sequence runs (see Inner loop).
  - On terminal, auto-advance opens the next artifact's
    deliberation. Loops within S4 until every artifact has been
    handled.
- **Trigger to leave:** every artifact named in the manifest has
  reached a terminal status. **Open question:** are there
  artifacts the user can mark as "skip"? Today the only way an
  artifact gets skipped is a DROP move on its deliberation, which
  flips status to `ABANDONED`. Auto-advance treats DECIDED and
  ABANDONED as equivalent for "this artifact is done." Confirm
  this is the policy you want — there's no "skip" / "defer"
  intermediate state.

### S5 — Closing ceremony (deferred — not built yet)

`state.yaml` already carries `closing_ceremony_eligible` and
`final_deliberation_id` fields, suggesting an intended closing
flow. It's not implemented today.

- **Trigger to enter (proposed):** S4 complete (every artifact
  terminal).
- **What this stage IS, conceptually:** a final deliberation that
  reviews the work, captures retrospective notes, and produces a
  short closing summary. The output is a "decisions log" or a
  one-page recap, depending on what the user wants.
- **Open questions:**
  - Is closing automatic (auto-advance opens the closing
    deliberation), or does the user trigger it?
  - Is closing optional? I.e. can S4 → S6 directly skipping S5?
  - What does the closing artifact contain — just a summary, or
    is it where path-foreclosure / lessons-learned land?

### S6 — Archived

The workspace is done. The autoloop stops dispatching. The user
can still read everything; they just can't move forward.

- **Files in this state:** `state.yaml: state: ARCHIVED`.
- **Trigger to enter:** the user explicitly archives, or S5
  closing deliberation reaches DECISION.
- **What the user does:** reads the audit trail, exports / shares
  the result.
- **Trigger to leave:** there isn't one. Archived is terminal. To
  resume, the user creates a new workspace.

---

## What is a deliberation, in plain English?

A **deliberation** is the unit Quorum uses to make one decision
collaboratively. Think of it like one agenda item in a meeting, or
one GitHub issue: there's a question, people weigh in, the
conversation has structure, and at the end someone decides.

What it actually is, on disk: one Markdown file under
`deliberations/` with a unique numeric id (`#0001`, `#0002`, …).
The file has a title (the question being decided), a frontmatter
header that tracks status and roles, and a `## Contributions`
section where the back-and-forth lives.

### What a deliberation IS for

- A scoped, decidable question. "What criteria do we compare v2
  directions on?" or "What goes in `option-analysis.md`?"
- A place where multiple participants (Claude, Gemini, Codex, you)
  can structure a conversation: someone proposes, someone
  challenges, someone synthesises, someone decides.
- An audit trail of who said what and why — the file is the
  permanent record.

### What a deliberation is NOT

- Not free-form chat. Each contribution has a role (proposer,
  critic, synthesizer, decider) and a structured shape.
- Not the project itself. A project is a *sequence of
  deliberations* — one per artifact in the manifest, plus the
  seed and (optionally) a closing one.
- Not a discussion thread you can keep open forever. A deliberation
  has a terminal state: `DECIDED`, `ABANDONED`, or `ARCHIVED`.

### Why deliberations exist as a concept

Without them, multi-agent collaboration is just a chat log — hard
to follow, hard to trust, hard to know when a decision is "done."
A deliberation forces structure: every conversation has a defined
question, a defined set of participants playing defined roles, and
a defined exit condition. That makes the project *auditable* and
makes the loop *automatable* (the conductor can tell which agent
should speak next).

### A deliberation's life

A deliberation is born when:

- the conductor scaffolds the **seed deliberation `#0001`** that
  ratifies the manifest (one-shot, happens in stage S3),
- or the conductor's auto-advance opens an **artifact
  deliberation** for the next item in the manifest (happens
  through stage S4, one per artifact),
- or the user manually creates a deliberation via the UI (rare;
  usually for ad-hoc questions).

It then runs through the per-deliberation move sequence below
(propose → critique → synthesise → decide). It dies when one of
the **terminal moves** lands:

- `DECISION` — the decider (usually you) ratifies a position.
  Status flips to `DECIDED`. Artifact (if any) is locked.
- `OVERRIDE` — the decider unilaterally decides without going
  through synthesis. Status `DECIDED`.
- `DROP` — the deliberation is abandoned (decided to not decide).
  Status `ABANDONED`.

After death the file is read-only by convention; the move history
is the audit trail. (Technically you could edit it via Raw editor;
the protocol says don't.)

### How a deliberation appears in each stage

- **S3 (Bootstrap the plan):** exactly one deliberation exists —
  the seed `#0001`. It runs the full move sequence. When it
  decides, the manifest gets locked and we leave S3.
- **S4 (Work through artifacts):** the conductor opens one
  artifact deliberation at a time. Run the move sequence, decide,
  next artifact's deliberation opens. Loop until every artifact
  has been deliberated.
- **S5 (Closing, if implemented):** likely one final deliberation
  that summarises the project.
- **S1 / S2 / S6:** no deliberations exist (S1, S2) or none are
  active (S6).

So the user's mental model can be: **the project advances one
deliberation at a time. Each deliberation is one decision.**

### Roles inside a deliberation

The frontmatter declares who plays what role:

- **proposer** — drafts the initial position (usually an AI)
- **critics** — challenge the proposal (usually one or more AIs)
- **synthesizer** — reconciles into a candidate (usually an AI)
- **decider** — ratifies (usually you, the human)

If a role isn't pinned in frontmatter, the conductor's router
picks the best-fit participant by fitness rating + cost.

### Why "DECIDED" matters

`DECIDED` is the only thing that advances the project. The
auto-advance mechanism only opens the next artifact's deliberation
once the current one reaches a terminal state. So a deliberation
is, very literally, *one tick of forward project motion*.

---

## Inner loop — the per-deliberation move sequence

This sub-flow runs inside S3 and once per artifact in S4. It's the
only place "moves" matter.

```
[ OPEN ] ──► PROPOSAL ──► CRITIQUE(s) ──► SYNTHESIS ──► [ DECISION | OVERRIDE | DROP ]
   │          │              │              │              │
   │          │              │              │              ▼
   │          │              │              │           [ terminal ]
   │          │              │              │           DECIDED / ABANDONED
   │          │              │              │
   │          │              │              └─► [ REOPEN ] ─► back to PROPOSAL or CRITIQUE
   │          │              │                                (re-enters this sub-loop)
   │          │              │
   │          │              └─► more CRITIQUE if multiple critics declared
   │          │
   │          └─► STEER ──► (changes the deliberation's direction;
   │                          re-enters this loop with new framing)
   │
   ├─► QUESTION ──► (waits for ANSWER from human or another agent;
   │                  doesn't advance until ANSWER lands)
   │
   ├─► CLARIFY ──► (waits for EXPLANATION; doesn't advance)
   │
   └─► INTERJECTION ──► (side-channel note from any participant;
                          doesn't change the flow direction)
```

Terminal moves are `DECISION`, `OVERRIDE`, `DROP`. Everything else
is mid-loop.

**Open question — REOPEN behaviour:** REOPEN can re-enter a
previously DECIDED deliberation. Today the planner sees REOPEN as
"this deliberation is now non-terminal again" — which means
auto-advance has to handle the case where an artifact deliberation
has been reopened and the *next* artifact's deliberation is already
open. Multiple non-terminal artifact deliberations at once.
Confirm this is the desired behaviour or whether REOPEN should
suspend the next artifact's deliberation until resolved.

---

## Orthogonal: pause and block conditions

These can happen at any stage from S3 onward (some also apply in
S2). They don't change *which* stage you're in; they freeze the
inner machinery and surface a specific phase via
`next_actions._resolve_phase`.

| Condition | Planner phase | What happens | What unfreezes it |
|---|---|---|---|
| **Open Ask** (the user is the next actor) | `AWAITING_HUMAN` | Autoloop sleeps. Workspace stays `ACTIVE`. The current deliberation's status may flip to `BLOCKED_ON_HUMAN`. | User answers the Ask via the UI. The corresponding move is written, deliberation un-blocks, autoloop wakes on next tick. |
| **All viable agents failing** for an item | (autoloop pauses workspace; `next_actions` reads as `IDLE` because state ≠ ACTIVE) | Autoloop pauses the workspace (`state: ACTIVE → PAUSED`). | User fixes the participant (CLI command, auth) and re-activates. State flips back to `ACTIVE`. |
| **Cost ceiling reached** | (no dedicated phase; loop just refuses to dispatch) | Autoloop refuses to dispatch on subsequent ticks. | User raises `cost_ceiling_usd` in `config.yaml` or accepts the limit. |
| **Routing failure** for a deliberation | (`BLOCKED_ON_ROUTING` deliberation status; not a workspace-level phase) | The specific deliberation can't route a role to any handle. The deliberation's status becomes `BLOCKED_ON_ROUTING`. Other deliberations keep going. | User adds a participant or changes routing config. |
| **Manual pause** | (state is PAUSED) | User explicitly pauses via UI / CLI. State `ACTIVE → PAUSED`. | User resumes via UI / CLI. |
| **Pending agent permission requests** | `AWAITING_PERMISSION` | An agent has requested permission for a tool (Bash, Edit, etc.). The conductor blocks dispatch on that agent until the user approves/denies via the Permissions dialog. | User approves or denies. |
| **Context not yet digested** | `NEEDS_DIGESTION` | One or more attached repos / docs / URLs need digestion before agents can use them efficiently. Surfaces in S2 most often (digesting at setup time) but can re-surface mid-flight if the user adds new context. | User runs the digestion job or skips. |
| **No CLI participants registered** | `NEEDS_AGENT` | The workspace has 0 CLI-transport handles, so the loop has nothing to dispatch. Strictly an S2 condition (we now require ≥1 participant before S3), but the planner phase still exists as a defensive surface. | User adds an agent. |
| **All registered participants unreachable on PATH** | `AGENTS_UNREACHABLE` | Doctor reports every CLI handle's binary is missing. Different from "all failing on a specific item"; this is "no agent can run at all." | User installs the CLI or fixes participants.md. |
| **Workspace not yet set up** | `NEEDS_SETUP` | Empty problem statement and no deliberations. Strictly an S1/S2 condition. | User fills in setup. |

These pause conditions are exactly the cases where the visual
diagram should signal "system is waiting on you / something" rather
than showing forward motion.

---

## Loops — where can the flow go backward?

Forward-only stages: **S1 → S2 → S3 → S4 → (S5) → S6**.

Inside-stage loops:
- **S4 internal loop:** for each artifact, run the per-deliberation
  loop, then advance to the next artifact. This is a "for each"
  loop, not a backward branch.
- **Per-deliberation loop (inside S3, S4, possibly S5):** the
  PROPOSAL → CRITIQUE → SYNTHESIS sequence can iterate when:
  - More than one critic is declared and not all have CRITIQUE'd
  - REVISION supersedes a previous PROPOSAL/SYNTHESIS
  - REOPEN re-enters a previously-DECIDED deliberation
  - STEER changes direction mid-flight

True backward transitions (rare):
- **S2 → S2 within itself:** the user can keep editing setup before
  hitting Apply. Not really a backward jump; just staying in S2.
- **REOPEN from S4 back into the same artifact's deliberation
  loop:** flow re-enters the inner loop. Doesn't change which
  stage we're in.
- **No documented path from S4 back to S3.** Once the manifest is
  LOCKED, you can't un-lock it via the protocol — only edit
  manually via the Raw editor (out-of-band). Confirm this is
  intentional. (I think it is — the manifest is a contract; if you
  need to amend it, that's a follow-up project, not a regression.)

---

## Things I'm uncertain about and want to settle here

These are the points where the doc above is guessing or where I
think the system should change. Need your call.

1. ~~DROP on the seed deliberation #0001~~ — **resolved (Q1).**
   Rejected by the validator. Per-artifact ratification
   deliberations remain DROP-able.
2. ~~DROP on an artifact deliberation in S4~~ — **resolved
   alongside Q1.** DROP works on artifact deliberations; the
   artifact gets marked `ABANDONED`; auto-advance treats it as
   "done" and moves to the next artifact. No separate "skip"
   semantic needed — DROP IS the skip.
3. ~~REOPEN multiplexing~~ — **resolved (Q3).** Free
   multiplexing. The user may REOPEN any DECIDED deliberation at
   any time, regardless of what else is non-terminal. No
   auto-pause of downstream deliberations. This matches the
   non-linear way brainstorming actually works — forcing pauses
   would interrupt user flow without solving the deeper
   cross-artifact coordination problem (see follow-up doc:
   `docs-specs/cross-artifact-coordination.md`). Implementation:
   zero changes — current code already supports this.
4. ~~S5 (closing ceremony) — automatic or user-triggered?
   Optional or required?~~ — **resolved (Q4).** **User-triggered**
   and **optional**. Closing is reflective work; the user decides
   when they're done thinking, not the conductor. Some projects
   (quick decisions, throwaway investigations) don't deserve a
   recap, so skipping straight to archive must be allowed. The UI
   surfaces a "Wrap up project" action when all artifact
   deliberations have reached terminal status; the user can take
   it (opens the closing deliberation) or skip it (archive
   directly). If you want to push back on the optional part, say
   so before we lock Q5/Q6 — it's the easier of the two to
   reverse.
5. ~~What does S5's deliberation produce?~~ — **resolved (Q5).**
   A single `summary.md` artifact. The closing deliberation
   ratifies it, same mechanism as any other artifact
   deliberation. Proposed sections (firm up at build time):
   project question (verbatim from `problem-statement.md`),
   per-artifact recap (one paragraph + link to source
   deliberation each), path not taken (significant alternatives
   set aside, with reason), calibrated confidence, open
   follow-ups. The closing's DECISION also writes
   `state.yaml: state=COMPLETED` and
   `state.yaml: manifest.final_deliberation_id=<closing_id>`.
   Retrospective is **NOT** part of the workspace artifact —
   it's a system-wide observability concern (queued separately
   in `docs-specs/system-retrospective.md`).
6. ~~Resume from ARCHIVED~~ — **resolved (Q6).** **Disallowed
   for v1.** The `unarchive` CLI command and `/unarchive` TUI
   slash command have been removed. The underlying
   `unarchive_workspace` function in `workspace/archive.py`
   remains in the codebase (along with its round-trip test) so
   we can re-surface it later if a real need shows up. To revive
   a workspace pre-v2, the user copies files into a fresh
   workspace manually. Pause/resume during active collaboration
   is **unaffected** — that's `PAUSED ↔ ACTIVE`, fully
   supported, and a different mechanism entirely.

---

## What this doc lets us do next

Once these uncertainties are settled, the master flow is one
diagram with:
- 6 stages (S1..S6) as the spine
- 1 inner loop (per-deliberation move sequence) attached to S3 + S4
  (+ S5 if applicable)
- 5 orthogonal pause/block conditions overlaid as banners or
  badges on whichever stage is currently active

That's a clean enough mental model to render as one chart. The UI
brainstorm in `visual-flow-diagram.md` then becomes "how do we
*draw* this?" instead of "what are we drawing?".
