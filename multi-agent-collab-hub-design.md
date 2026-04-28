# Quorum — Living Design Document

> **Status:** v0.18 — Critical-review pass: derisking v1 implementation. All six identified gaps committed; build order restructured for higher v1 confidence.
> **Last updated:** 2026-04-27
> **Owner:** Rohan (human-in-the-loop)
> **Purpose:** A neutral collaboration workspace where multiple premium AI agents (Claude, ChatGPT, Gemini, Codex CLI, Claude Code, Cursor, Windsurf, etc.) collaborate on complex problems through shared structured artifacts rather than direct model-to-model API calls.

---

## 0. How to read and evolve this document

This is a **living artifact**. It will go through many revisions as we reason more deeply about each section. Conventions:

- Each top-level section has a **Status** marker: `🟢 Settled`, `🟡 In progress`, `🔴 Open question`, `⚪ Not yet addressed`.
- When a section changes meaningfully, bump its mini-version (e.g., `§3 v0.2`) and note what changed in the changelog at the bottom.
- Open questions get pulled into §15 so we don't lose them.
- The doc itself is the first artifact this system would produce — meta but appropriate.

---

## 0.5. Project Identity · 🟢 Settled

**Name:** **Quorum**

**Why:** A quorum is the minimum number of members of a deliberative body needed to make valid decisions. The name encodes both core properties of the system:

1. **Multiple voices required** — a single agent cannot constitute a quorum; the system is meaningless without a body of participants.
2. **Decisions get made** — the purpose of a quorum is to enable binding decisions, not endless discussion.

The READY-state enforcement (need ≥1 critic, need a bootstrapper, etc.) is *literally* a quorum check. The name and the mechanism align.

**CLI command:** `quorum`

Used as: `quorum init`, `quorum start`, `quorum status`, `quorum doctor`, `quorum archive`, etc.

**Workspace directory:** `/quorum/`

The directory inside a user's project is `/quorum/` — branding-consistent with the CLI command. When a user runs `quorum init` inside their existing project, the resulting `my-app/quorum/` folder is unambiguously identifiable as Quorum's workspace. (Originally we considered keeping the folder generic as `/collab/`, but consistency with the product name won — see v0.5.1 changelog entry.)

**Tagline (working):** *Where premium AI subscriptions deliberate together.*

**Repo:** `github.com/<owner>/quorum`

---

## 1. The Problem & Goal · 🟢 Settled (v0.2)

**Goal:** Make best use of multiple paid AI subscriptions by allowing their outputs to compound together in a structured, auditable, reusable workflow — turning vague ideas, rough requirements, and open questions into well-reasoned, documented decisions and specs.

**The problem with existing approaches:**
- API-based orchestration doubles cost when premium subscriptions are already paid for.
- Browser automation (Playwright et al.) is fragile and not a serious long-term path.
- Ad-hoc copy-pasting between web UIs doesn't compound — outputs don't accumulate into anything reusable. Three brainstorming sessions across ChatGPT, Claude, and Gemini produce three disconnected transcripts and no synthesis.

**The core idea:** Agents collaborate through **shared structured artifacts**, not direct messaging. The repo is the medium, Markdown is the lingua franca, and a human is editor-in-chief (initially) or designated decider (always). The canonical journey is **vague thought → deliberation → critical human questions → synthesis → decided spec/ADR/brief.**

**Primary target use cases (the niche we own):**
- Turning vague product ideas into refined, decided product briefs and specs
- Complex architecture brainstorming and design reviews
- Product strategy and roadmap reasoning
- Spec refinement (taking a rough draft to a complete, well-reasoned spec)
- Framework / system design
- Research synthesis (multiple sources → coherent direction)
- Long-running project reasoning where decisions need provenance

**Secondary applications (same protocol, no redesign required):**
- Strategic planning (board-deck prep, GTM)
- Editorial workflows (long-form pieces, books, technical writing)
- Policy / governance / compliance documents
- Security review and threat modeling

**Hard constraints:**
- No model APIs initially (use existing paid subscriptions).
- No browser automation.
- GitHub/repo/Markdown-first.
- MCP and UI come later, on top of the same protocol — except a minimal UI ships in v1 (see §1.5 and §9).
- Generic and reusable across projects.

---

## 1.5. Niche & Scope · 🟢 Settled

We are deliberately scoping this product to **collaborative reasoning**, not code-execution coordination. This is a strategic choice that shapes everything downstream.

### What we own

**Collaborative reasoning** — the work of turning vague thoughts into decided artifacts (specs, ADRs, briefs, design docs). The protocol's move vocabulary (PROPOSAL / CRITIQUE / SYNTHESIS / DECISION) is fundamentally a *peer-review* vocabulary, well-suited to brainstorming, design, and strategy.

### What we deliberately don't own

**Code-execution coordination** — multiple coding agents simultaneously editing a codebase, coordinating who-touches-what-when, avoiding overwrite collisions. This is a **concurrency problem**, not a reasoning problem. Tools like Cursor, Windsurf, Aider, and various MCP-based coordination layers already address this space and the architectural shape (concurrent file locking, real-time messaging) is fundamentally different from ours (turn-based, append-only, document-centric).

### Why this distinction matters

| Dimension | Coding-team coordination | Brainstorming/strategy hub (us) |
|---|---|---|
| Primary artifact | Code | Reasoning (deliberations, ADRs, specs) |
| Failure mode | Collision, overwrite, drift | Premature consensus, blind spots, lost reasoning |
| Coordination | Concurrent with locking | Turn-based with role separation |
| Speed priority | High (parallel execution) | Low (depth matters more than throughput) |
| Human's role | Reviewer of output | Decider, ambiguity-resolver, editor-in-chief |
| "Done" looks like | Working code | A decided question with documented rationale |

### The growth path

The protocol works for any structured collaborative reasoning, so once the brainstorming/spec-derivation flow is excellent, the same protocol naturally extends to architecture review, research synthesis, strategic planning, editorial workflows, and policy docs — without redesign.

### The handoff to execution

The hub's *output* (a decided spec) can become the *input* to a coding-agent team using a tool like the one in the Medium article we reviewed. We are the front-end of execution tools, not a competitor to them. "Coding plan review" remains in scope as a use case — we produce coding plans for execution agents to implement.

---

## 1.6. User Workflow & Workspace Lifecycle · 🟢 Settled

This section defines the canonical user journey from "I want to think through a problem" to "the collab is running." It's the experience contract that everything else has to support.

### Distribution

**v0.1: git clone + shell script.** The honest, iteration-friendly approach.

```bash
git clone https://github.com/<repo>/quorum.git ~/.quorum
~/.quorum/install.sh
# install.sh: adds 'quorum' to PATH, installs Python deps, installs Node deps for UI
```

After install, `quorum` works as a command anywhere on the user's machine.

**Graduation criteria for v0.2 packaging** (npm/pip global, or single-binary via Go/Rust/pkg-bundle):
- The CLI surface stops changing week-to-week
- `PROTOCOL.md` reaches v0.3 or later (i.e., has been through real revisions)
- Breaking changes become rare enough that distribution overhead is worth paying

Until then, git clone is correct. Distribution is a tax we don't pay until the surface stabilizes.

### Workspace state machine

A workspace has its own high-level state, distinct from any individual deliberation's status:

```
INITIALIZED → READY → ACTIVE → PAUSED → ACTIVE (resumed)
                          ↓
                      COMPLETED  (manifest satisfied + closing ceremony complete)
                          ↓
                       ARCHIVED
                          ↑
                COMPLETED_AUTONOMOUS  (autonomous mode only — see Workspace modes below)
```

| State | What it means | Conductor running? |
|---|---|---|
| `INITIALIZED` | `quorum init` has run; UI is up; participants can be registered; problem statement can be edited | ❌ No |
| `READY` | Problem statement marked ready; ≥1 healthy CLI handle registered; user can press Start | ❌ No |
| `ACTIVE` | Conductor running; deliberations being processed; agents being invoked | ✅ Yes |
| `PAUSED` | Conductor stopped (manual, stop condition, or BLOCKED_ON_HUMAN); state preserved | ❌ No |
| `COMPLETED` | Interactive workspace: outcome manifest satisfied, all quality gates clear, closing ceremony complete; artifacts ready for review/download | ❌ No |
| `COMPLETED_AUTONOMOUS` | Autonomous run finished (manifest satisfied or hard cap hit); workspace open for review; can convert to interactive or archive | ❌ No |
| `ARCHIVED` | Workspace closed for new work; read-only; can be reopened | ❌ No |

The transition `READY → ACTIVE` is the moment of commitment. Nothing happens behind the user's back in `INITIALIZED` or `READY` — they're free to write, edit, register, configure.

The transition `ACTIVE → COMPLETED` is **the closing ceremony** (§1.7), not a silent state change.

### Workspace modes

A workspace operates in one of two modes, declared at init and locked once the workspace has activity:

| Mode | Who's in the loop | Default |
|---|---|---|
| `interactive` | Human is the source of authority; agents collaborate; human is decider, ambiguity-resolver, final ratifier | ✅ Default |
| `autonomous` | No human in the loop; agents drive the entire deliberation; a designated panel of agents serves as decider | Opt-in via `--autonomous` |

**Why two modes (not just one with extreme settings).** "Autonomous" isn't a special case of human-timeout policy with `wait_minutes: 0`. Those would produce piles of DEPUTY_DECISIONs awaiting review by a human who isn't coming. The semantics are genuinely different — autonomous deliberations have *real* DECISIONs (final, not provisional), no human inbox, no "your turn" UI affordance, and explicit make-and-document-assumptions behavior when problem statements are ambiguous.

**When to use autonomous:**
- *Sanity-check brainstorms* — half-formed thoughts you want to see explored overnight.
- *Calibration runs* — learning what Quorum produces without you, so you know whether to trust it interactively.
- *Comparative experiments* — same problem statement, different decider configs, compare outputs.
- *Throwaway / fun* — small problems where you just want to see what comes back.

#### Autonomous mode specifics

When `mode: autonomous`:

1. **No human inbox.** No `@human-rohan.md` is created. The human is not a registered participant in the workspace.
2. **Panel of deciders.** Instead of a single decider, autonomous mode declares an *ordered list* of decider handles. The conductor walks the list top-to-bottom: first available + healthy + within-quota wins. This generalizes the same pattern used for `deputy_deciders` in interactive mode.
   
   **Decider role scope:** the panel members are *only* deciders, not synthesizers. Synthesizer role for each deliberation is routed normally per §3.6 fitness. The decider issues the final DECISION move on a deliberation; another (potentially different) handle authored the SYNTHESIS that the decider is acting on. This separation matters: it preserves the "synthesis presents the case, decider rules" structure even in autonomous mode. A panel member *can* be routed as synthesizer for a different deliberation if their fitness ratings warrant it; the panel role is per-DECISION, not per-handle.
3. **Real DECISIONs, not DEPUTY_DECISIONs.** The decider issues normal DECISION moves. They're final. There is no provisional state — there's no human coming back to ratify.
4. **No DEPUTY_DECISION mechanism.** The `human_timeout` config is incompatible with autonomous mode. Validation refuses both being set.
5. **Make-and-document assumptions.** When agents find ambiguity in the problem statement, they document the assumption explicitly in the move's `Assumptions` section and proceed. They never issue QUESTIONs tagged at humans (there are none). If a question genuinely needs resolution, it's tagged at the decider panel for an ANSWER move from one of them.
6. **Standing prompt augmentation.** Every agent invocation in autonomous mode receives an additional clause: *"This workspace has no human participant. Do not ask a human to clarify or decide. If the problem statement is ambiguous, document your assumption explicitly in `Assumptions` and proceed. If a decision is required, the designated decider panel will resolve it."*
7. **Hard stop conditions become load-bearing.** With no human gate, the system relies entirely on caps to not run forever:
   - `max_total_invocations` (default: 100)
   - `max_deliberations` (default: 10 sub-deliberations spawned from the bootstrap)
   - All existing per-deliberation invocation caps and no-progress detector
8. **No human-blocking states ever entered.** `BLOCKED_ON_HUMAN` and its sub-states are not reachable in autonomous mode. If the conductor would otherwise enter one, it's a protocol violation — logged and the deliberation is force-resolved by the decider panel.

#### Configuration schema

`config.yaml` (autonomous mode):

```yaml
mode: autonomous
autonomous:
  decider_panel:                     # ordered list; first available wins
    - "@claude-opus"
    - "@claude-sonnet"
    - "@gemini-pro"
  bootstrapper_handle: "@claude-opus"  # who reads problem statement and creates #0001
  max_total_invocations: 100
  max_deliberations: 10
  on_completion: notify              # notify | archive_immediately
  on_max_invocations: best_effort    # best_effort (force-resolve with current state) | block (mark incomplete)
```

**Validation rules:**
- If `mode: autonomous` and `human_timeout.default_enabled: true` → **config refused.** The two are semantically incompatible.
- If `mode: autonomous` and `decider_panel` is empty → **config refused.** No deciders means no DECISION can be issued.
- If a handle in `decider_panel` is not present in `participants.md` → refused.
- If `mode: interactive` (or omitted, the default) → autonomous fields are ignored if present.

#### Completion behavior (autonomous)

When an autonomous run completes — all deliberations DECIDED, or hard cap hit — the workspace transitions to a new state: `COMPLETED_AUTONOMOUS`. This is distinct from `DECIDED` (per-deliberation) and from `ARCHIVED` (closed for new work).

Default: `on_completion: notify`. The workspace stays open; user reviews the artifacts (deliberations, ADRs, tasks) when they want; can convert to interactive mode (see below) or archive.

The completion view in the UI is reframed for review: instead of "what's next," it shows "what was decided" — a summary of all DECISIONs, ADRs spawned, tasks generated, and any deliberations that hit caps without resolving.

#### Mode conversion

**Autonomous → Interactive (allowed):**
The user can engage with an autonomous workspace at any point — during the run (which pauses it) or after completion. They're then participating in interactive mode going forward. The audit trail honestly preserves: "autonomous run from <date>, then @human-rohan engaged on <date>."

Specifically: any human-issued move converts the workspace to interactive mode for all subsequent work. The agents' standing prompt updates on the next invocation (no longer told "no human"). The workspace state file records the conversion.

**Interactive → Autonomous (not allowed in v1):**
Mid-stream conversion would require retroactively converting pending human decisions into agent decisions, which muddles the audit trail. If the user wants this, the path is: archive the current workspace, then `quorum fork --autonomous` from its problem statement (see below).

#### `quorum fork`

A first-class command for spawning a new workspace seeded from another's problem statement. Useful for comparative experiments and for the "let me try this autonomously" path:

```bash
# Inside an existing workspace, fork to a new directory:
quorum fork ../my-product-autonomous --autonomous --decider-panel @claude-opus,@gemini-pro

# Or fork to interactive (if you started autonomous and want a parallel interactive run):
quorum fork ../my-product-interactive
```

Forking copies:
- `problem-statement.md` (verbatim)
- `participants.md` (filtered: removes `@human-rohan` if forking to autonomous)
- `routing-defaults.yaml`

Forking does NOT copy:
- Deliberations, decisions, tasks, events log — the fork is a fresh thinking surface from the same seed

The new workspace is created in `INITIALIZED` state, ready for `quorum start`. Provenance is recorded in the new workspace's `state.yaml`:
```yaml
forked_from: /path/to/original/quorum
forked_at: 2026-04-29T10:14:22Z
forked_with_mode_change: interactive_to_autonomous
```

This is what makes comparative experiments cheap. Same seed, different configurations, run them in parallel, compare outputs.

### `quorum init`

```bash
quorum init [--autonomous]
```

**Order of operations:**
1. Check current directory (empty / existing codebase / already initialized — different bootstrap paths).
2. Scaffold `/quorum/` with full folder structure from §7, including `/context/` with empty source-type subdirectories.
3. Create `/quorum/.gitignore` so `/runtime/` doesn't pollute commits.
4. Fetch latest `routing-defaults.yaml` from upstream (offline fallback to bundled defaults; warn user if fetch fails).
5. Generate default `participants.md`. In `interactive` mode (default): includes `@human-rohan` (or git user) plus stub agent entries. In `autonomous` mode (`--autonomous`): omits the human row; agent stubs are uncommented as primary participants.
6. Create the seed `problem-statement.md` (see below).
7. Set workspace `mode` in `config.yaml` (`interactive` or `autonomous`).
8. Start UI server on a local port (e.g., `localhost:3737`).
9. Print the localhost URL and next-step hints.

**Critical:** `quorum init` does NOT start the conductor. The conductor is what invokes agents and writes moves. Until the user is ready to start collaborating, the conductor stays off. Only the UI is alive — for writing the problem statement, registering participants, and adding context sources (§1.8) via UI panels.

**Note on context:** Earlier drafts proposed `--with-codebase` as an init flag for adding a single repo. v0.13 supersedes this with the full Context Surface (§1.8), where repos, documents, URLs, and notes are all added through UI panels in Settings → Context. CLI flags for paths are error-prone (typos succeed silently); UI-based addition is the right surface.

### Agent registration ≠ agent invocation

A subtle but crucial distinction: **registering an agent and invoking an agent are different things.**

- **Registration is permanent.** "Claude Code is a participant in this workspace, here's how to invoke it." Lives in `participants.md`. A fact about the workspace, not a running process.
- **Invocation is per-turn.** The conductor spawns a CLI process for the duration of one move; the process exits when the move is done. Agents are short-lived, stateless invocations.

The user does NOT start agent CLIs in separate terminals. They register agents through the UI:

1. UI shows an "Add agent" button in the participants panel.
2. Modal asks for: which CLI (Claude Code / Gemini CLI / Codex / Other), and the **command name** for this installation (default: the canonical name like `claude`, but user can override — e.g., `claude-work` or `claude-personal` for users with multiple accounts).
3. UI runs the CLI's doctor command (or equivalent probe) against the entered command name to verify it exists, capture version, and detect permission capability.
4. UI asks for an **account label** (optional, free-form string — "Work" / "Personal" / "Org-X"). If the user entered a non-canonical command name like `claude-work`, the label defaults to "Work" but is editable.
5. **For multi-model CLIs** (Claude Code, Gemini CLI, etc.): the registration modal shows all available model variants with checkboxes. **All variants are checked by default** — registering Claude Code gives you Opus, Sonnet, and Haiku as separate handles simultaneously. User can uncheck variants they don't want.
6. Handle names are derived from the account label and model: with no label, you get `@claude-opus`, `@claude-sonnet`, etc. (canonical). With a "Work" label, you get `@claude-work-opus`, `@claude-work-sonnet`, etc. The registration UI shows the resulting handle names so the user can edit if desired.
7. **Fitness inheritance:** for non-canonical handles, the system automatically inherits fitness ratings from the matching canonical handle (e.g., `@claude-work-opus` inherits Opus fitness ratings from `routing-defaults.yaml`). User can override per-handle in the routing settings if their installation has different characteristics (rare).
8. Save → writes rows to `participants.md`, including the optional `account_label` field for UI grouping.
9. UI runs an immediate health check on each newly-registered handle.

This flow naturally supports the **multiple installations case**: a user with separate Claude Code installations for work and personal (`claude-work` and `claude-personal` binaries on their PATH) registers them as two separate batches. The result is e.g. six Claude handles (`@claude-work-opus`, `@claude-work-sonnet`, `@claude-work-haiku`, plus the personal trio) — each with their own quota tracking, each routable independently, each visually grouped in the UI by account label.

When the collab eventually starts, the conductor reads `participants.md` and invokes each handle's CLI command literally — `claude-work --print --model opus` for one, `claude-personal --print --model opus` for another. The handles are distinct from a routing and quota perspective even when they map to the same underlying model, because they map to *different accounts*.

When the collab eventually starts, the conductor reads `participants.md` and invokes each handle's CLI as needed. No long-running processes, no terminal management.

### `quorum doctor`

```bash
quorum doctor
```

Health-checks every registered handle: runs each CLI with a trivial prompt, checks for `command not found`, auth errors, rate-limit responses. Reports green/yellow/red per handle.

Triggered automatically:
- After every new registration
- On `quorum init` once participants are added
- Before transitioning workspace to `READY`

Triggered manually whenever the user wants to verify state. The participants panel in the UI shows the current health state per handle and a "re-check" button.

### The problem-statement document

`/quorum/problem-statement.md` is a special, top-level document that exists from the moment of `quorum init`. It's the seed input for the entire workspace's reasoning.

**Frontmatter:**
```yaml
---
status: DRAFTING | READY
protocol_version: 0.1
created: 2026-04-27
ready_marked_at: null
---
```

While `status: DRAFTING`, the conductor refuses to start. The user writes freely until they mark it ready.

**Light structure (scaffolded sections, all initially empty):**

```markdown
# Problem Statement

## What I'm trying to figure out
<one-paragraph framing — vague is fine, this is the seed>

## What I already know / believe
<context, prior thinking, related work, anything I've already considered>

## What I'm uncertain about
<open questions, things I don't know how to evaluate, decisions I've been avoiding>

## What "done" looks like
<how will I know this is solved? what's the deliverable I want from this collab?>

## Constraints / non-goals
<what's off the table; what I don't want this to become>

## Existing materials
<links, files, related deliberations from other workspaces>
```

Each section can be empty (write "none" or skip), but they're all present. The sections give the user something to push against and they give the bootstrap agent the right shape of information to start a useful first deliberation.

**Soft check on "Mark as Ready":** if "What done looks like" is empty, UI nudges with "Are you sure? A definition of done helps the system know when to stop." Nudge, not block.

**The first-deliberation handoff.** When the workspace transitions `READY → ACTIVE`, the conductor invokes the bootstrap handle (chosen by routing — typically a high-fitness handle for the `bootstrapper` role) with the problem statement. The bootstrap handle reads it and creates deliberation #0001.

Crucially: **if the bootstrap handle finds critical gaps in the problem statement** (success criteria unclear, scope undefined, ambiguities that a human must resolve), it does NOT plow ahead. It issues a `QUESTION` move tagged `@human-rohan` and sets the bootstrap deliberation to `BLOCKED_ON_HUMAN`. The user is pulled back in immediately, before any meaningful cycles are spent. This is the protocol working as designed — agents surface ambiguity, they don't guess at it.

### `READY → ACTIVE` enforcement

Before allowing the Start action, the system verifies:
- Problem statement exists and `status: READY`
- At least one CLI handle is registered AND health = green
- A bootstrapper-fit handle is available (positive fitness rating for the `bootstrapper` role)
- (Optional but recommended) at least one critic-fit handle is available — otherwise premature consensus is structurally guaranteed

If checks fail, the Start button is disabled with a tooltip explaining what's missing. This prevents "I clicked start but nothing happened because I forgot X."

### Working alongside an existing codebase

For the "brainstorm a feature on existing project" use case:

```bash
cd ~/projects/my-app
quorum init
```

This creates `/quorum/` *inside* the project, alongside the existing code. After init, the user opens the UI and adds the codebase via Settings → Context → Repos. They can also add other repos in the same brainstorm (multi-repo product surfaces, common in larger orgs).

Concretely:

- The codebase digest lives in `/quorum/context/repos/<repo-name>/digest.md` after the user adds it (§1.8). Agents read the digest; they read source on-demand only when needed for verification.
- The standing agent prompt (§11) is augmented: agents may **read** files in declared repos but must **never modify** them. Codebase is read-only context, not a participant.
- The hub's outputs (specs, ADRs, tasks) live in `/quorum/` and can be referenced by execution tools (Cursor, Claude Code in IDE mode) when the user is ready to implement.

The full Context Surface design is in §1.8. The key takeaway: codebases are added through UI, not init flags.

### `quorum status`

```bash
quorum status
```

From any terminal inside a workspace, prints:
- Workspace state (INITIALIZED / READY / ACTIVE / PAUSED / ARCHIVED)
- Conductor: running / stopped (PID if running)
- Registered handles + health
- Open deliberations + their statuses
- Any items pending in `@human-rohan`'s inbox

Essential for sanity-checking when something seems off, especially when the UI isn't open.

### Process model: how Quorum runs and survives terminals

The mental model is simple: **the workspace is just a folder.** Nothing about it is tied to a running terminal, a session token, or a daemon registry. You `cd` to the folder, run a `quorum` command, and the system figures out what state things are in.

This means closing your terminal — or your laptop — should not interrupt a long-running brainstorm.

**Daemonization is the default.**

When you run `quorum start`, the conductor process detaches from the terminal and runs in the background. It writes its PID to `/quorum/runtime/conductor.pid`. Closing the terminal does not kill it.

The same applies to `quorum serve` — the UI server daemonizes, PID at `/quorum/runtime/ui.pid`.

For debugging or watching logs live: `quorum start --foreground` keeps the conductor attached to the terminal and streams its logs to stdout. Closing the terminal will kill it. This is opt-in.

**One conductor per workspace.**

The PID file is also a lockfile. If you run `quorum start` on a workspace that already has a live conductor, the second invocation refuses:

```
$ quorum start
✗ Conductor already running (PID 12345, started 2 hours ago)
  → quorum status   to see what it's doing
  → quorum pause    to stop it cleanly
```

Same for the UI server.

**Crash recovery happens automatically.**

Every `quorum` command (other than `init`) does an integrity check before doing its real work:

1. Read `state.yaml`. If state is `ACTIVE`, check whether the recorded conductor PID is still alive.
2. If the PID is dead → conductor crashed (machine restart, power loss, kill signal, OS killed it for memory pressure, etc.). Mark workspace `PAUSED` with `pause.reason: crash_recovery`. Log a `workspace_paused` event with `crash_detected: true`.
3. Sweep `/runtime/active/` for stale markers (older than 15min by default — accommodates legitimate long-running invocations on large contexts). For each: log `agent_failed` with reason `crash_during_invocation`; move the partial stream to `/runtime/streams/failed/` so the user can inspect it later.
4. Then proceed with the user's actual command.

The user never has to think about "did it crash?" The first command after coming back detects, recovers, reports.

**`quorum start` and `quorum resume` are aliases.**

Both transition the workspace to `ACTIVE` from any non-ACTIVE state. The semantics adapt:

| Coming from | Behavior |
|---|---|
| `INITIALIZED` (with READY checks passing) | Run bootstrapper, create deliberation #0001, begin |
| `PAUSED` (any reason) | Show resume briefing, then resume |
| Crash-recovered to PAUSED | Show resume briefing including crash report, then resume |
| `ACTIVE` (already running, lockfile valid) | Refuse — already running |
| `READY` but not yet started | Same as INITIALIZED path |

We keep both names because they read better in different contexts (`start` in tutorials, `resume` after a break), but you don't have to remember which applies to your current state.

### The three "I closed something" scenarios

| Scenario | What happened | What the user does |
|---|---|---|
| Explicit pause + close terminal | Conductor gracefully stopped; state.yaml says PAUSED | `cd <workspace> && quorum resume` |
| Just closed the terminal | Conductor was daemonized — still running. Nothing changed. | Reopen terminal whenever, run `quorum status` to confirm; UI was already accessible the whole time |
| Machine restart / power loss / explicit kill | Conductor died. state.yaml still says ACTIVE; runtime markers may be stale | `cd <workspace> && quorum status` (auto-detects + recovers + reports) → `quorum resume` |

In every case, the entry point is `cd` + a `quorum` command. There's no notion of "the session that was."

### Example: a real long-running brainstorm

**Day 1, morning:**
```
$ cd ~/projects/my-product-idea
$ quorum start
✓ Conductor started (PID 12345, daemonized)
✓ UI server started on http://localhost:3737
  Workspace: ACTIVE
```
User opens UI, sees collab in progress. Closes terminal — conductor keeps running.

**Day 1, evening — closing laptop:**
macOS suspends; on lid open, conductor is still there. UI is still at `localhost:3737`. User picks up where they left off.

**Day 2, morning — explicit pause:**
```
$ quorum pause
✓ Waited for in-flight invocation to complete (1, 14s)
✓ Conductor stopped cleanly
  Workspace: PAUSED (reason: user_initiated)
```

**Day 3, morning — coming back:**
```
$ cd ~/projects/my-product-idea
$ quorum status
  Workspace: PAUSED (since 2 days ago, reason: user_initiated)
  Conductor: not running
  UI: not running
  Pending in your inbox: 2 items in #0007, 1 item in #0011

$ quorum resume
[shows resume briefing — what changed, what's blocked on you]
✓ Conductor started (PID 18290, daemonized)
✓ UI server started on http://localhost:3737
  Workspace: ACTIVE
```

**Day 4 — power outage during active work:**
Machine reboots unexpectedly. User comes back hours later:
```
$ cd ~/projects/my-product-idea
$ quorum status
⚠ Workspace was ACTIVE but conductor is not running.
  Last activity: yesterday 16:42
  Recovery: cleaned 1 stale invocation marker
            (@claude-opus--0007--SYNTHESIS, partial output preserved)
  Workspace: PAUSED (reason: crash_recovery)

$ quorum resume
[resume briefing notes the crash; offers to retry the lost invocation]
✓ Conductor started (PID 21105, daemonized)
  Workspace: ACTIVE
```

In every scenario, the recovery path is the same: `cd` + `quorum status` (optional, just to see) + `quorum resume`. No magic, no remembering which command for which state.

### Pause and resume (multi-day continuity)

Long-running brainstorming is a primary use case. A complex product idea might be worked through over days or weeks. The system is designed for this — workspaces persist across sessions, and resuming should feel like picking up where you left off, not cold-starting.

**Pausing** (`quorum pause`):

A clean pause does more than kill the conductor:

1. Wait for any in-flight agent invocation to complete (or hit a configurable timeout, then mark it as failed and preserve its partial output).
2. Flush pending writes to `events.jsonl`.
3. Update workspace state to `PAUSED` in `state.yaml` (see §7.5), recording: pause reason (manual / blocked / stop condition), timestamp, expected resume time if known.
4. Stop the conductor cleanly; release file locks; remove `conductor.pid`.
5. Optionally keep the UI running (`--keep-ui`) for review, or stop both (`--full`).

**Resuming** (`quorum resume`):

Resuming is not silent. The user gets a **resume briefing** — a structured summary of where things stand, what changed while they were away, and what's blocked on them. This is the difference between resuming a coherent thread and being dropped into a stranger's brain.

```
Welcome back. Last activity: 3 days ago.

Active deliberations:
  #0007 "Pricing model" · SYNTHESIS · waiting on you
    └─ Q3 from @gemini-pro: "Should we differentiate by team size or 
       by usage volume?" — 3 days pending
  #0009 "MVP feature scope" · IN_REVIEW · agents working
    └─ Last move: CRITIQUE@claude-sonnet, 3 days ago
  #0011 "Tech stack" · DECIDED · ready to archive
    └─ Decision made by you, 4 days ago — generated ADR-0003

What changed while you were away:
  ✓ Routing-defaults refreshed — Claude Opus synthesizer fitness 2 → 3
  ⚠ Stale runtime markers cleaned (1 invocation never completed in #0009)
  ⚠ @claude-opus was unavailable for 4 hours yesterday — 0 substitutions
    (workspace was paused, see §10.3 for unavailability handling)

Suggested actions:
  → Answer @gemini-pro's Q3 in #0007 (unblocks SYNTHESIS)
  → Review and archive #0011
```

The briefing is built from frontmatter, inbox state, and `events.jsonl` — no LLM call needed in v1. (An LLM-narrated briefing is logged as a candidate for a future deferred optimization.)

**Auto-resume (off by default, configurable):**

Some unavailability scenarios have known recovery times (e.g., "Opus quota window resets at 4:15 PM"). By default, the conductor does NOT auto-resume — it waits for explicit `quorum resume`. Surprise progress while the user isn't watching is unsettling and risks burning subscription credits without supervision.

For users who want unattended operation, `config.yaml`:

```yaml
resume_policy:
  mode: manual                # manual (default) | auto_on_recovery | auto_scheduled
  auto_resume_window:         # only used when mode != manual
    earliest: "08:00"
    latest: "22:00"            # don't auto-resume in the middle of the night
  notify_on_auto_resume: true  # send a notification when auto-resume fires
```

Three modes:
- **`manual`** (default): conductor stays paused until explicit `quorum resume`.
- **`auto_on_recovery`**: when a known recovery time arrives (e.g., quota refills), conductor resumes automatically — within the configured window.
- **`auto_scheduled`**: cron-like; resume at specific times regardless of unavailability.

**Pause reasons (logged in `state.yaml`):**

| Reason | Trigger |
|---|---|
| `user_initiated` | User ran `quorum pause` |
| `blocked_on_human` | Deliberation entered BLOCKED_ON_HUMAN |
| `blocked_on_unavailable` | Handle unavailability + strict policy (see §10.3) |
| `stop_condition_hit` | Per-deliberation cap, no-progress detector, etc. |
| `crash_recovery` | Conductor restarted after unclean shutdown |

The pause reason informs the resume briefing — "you were paused because @claude-opus hit its quota; it's available again now."

### Workspace teardown / archival

`quorum archive` transitions the workspace to `ARCHIVED`: stops conductor, stops UI, deletes `/runtime/`, marks the workspace read-only. Reversible via `quorum unarchive`. The deliberation files, decisions, tasks, registers, and protocol all stay — the workspace becomes a permanent record of the reasoning that produced its outputs.

### The canonical first-time user flow

```
$ git clone https://github.com/<repo>/quorum.git ~/.quorum
$ ~/.quorum/install.sh
✓ Installed quorum CLI
✓ Installed UI dependencies
✓ Added 'quorum' to PATH

$ mkdir my-product-idea && cd my-product-idea
$ quorum init
✓ Scaffolded ./quorum/ workspace
✓ Fetched latest routing-defaults
✓ Created problem-statement.md (DRAFTING)
✓ Started UI server on http://localhost:3737

  Workspace state: INITIALIZED
  → Open the UI to write your problem statement and register agents.
```

User opens browser. UI shows workspace in `INITIALIZED` state. The problem statement is the prominent surface — large, central, inviting. Sidebar shows "0 deliberations, 0 agents registered."

User writes problem statement (over an hour, or a week — no rush). Registers 3 agents through "Add agent" UI flow; Claude Code registration adds Opus/Sonnet/Haiku as separate handles by default. Health check runs automatically; all green.

User clicks "Mark problem statement ready." Workspace transitions to `READY`. The "Start Collaboration" button activates.

User clicks Start. Workspace transitions to `ACTIVE`. The conductor wakes up, reads the problem statement, invokes the bootstrap handle. UI shows: "@claude-opus is composing a PROPOSAL in #0001 — Outcome Manifest." The collab has begun, and the very first thing being figured out is *what done means* (see §1.7).

---

## 1.7. The Outcome Manifest · 🟢 Settled

This is the design move that makes "when is the end?" answerable precisely. Without it, completion is fuzzy — "are we done yet?" is a feeling, not a check. With it, completion is a machine-checkable state plus a deliberate ratification.

### The core idea

Alongside `problem-statement.md` (which says *what we're working on*), every workspace has `outcome-manifest.md` (which says *what we'll have produced when we're done*). The manifest declares:

1. The **artifacts** the workspace must produce (e.g., `requirements.md`, `ux-requirements.md`).
2. The **completion checks** for each artifact (required sections, content rules, ratification).
3. The **quality gates** for the workspace as a whole (e.g., no unresolved blocking questions, no provisional decisions outstanding).
4. The **production patterns** for each artifact (how it gets written — synthesis-aggregated, specifier-authored, cross-cutting).
5. The **dependency graph** between artifacts (UX requirements depend on functional requirements, etc.).

The workspace's completion criterion becomes: *all manifest checks pass + all quality gates clear + decider issues a DECISION on the closing meta-deliberation.*

### Concrete vs vague users — same protocol

Two classes of users phrase their goals differently. The manifest absorbs both into the same protocol:

**Concrete user:** "I want `requirements.md` covering features X, Y, Z, plus `ux-requirements.md` with page inventory and user flows."
- Their manifest is largely written by them.
- The first deliberation refines it (agents can propose additions like "should we also have a `risks.md`?") but mostly ratifies.
- Fast first-deliberation, work begins.

**Vague user:** "I want complete clarity on this idea."
- Their manifest is mostly empty at first.
- The first deliberation *is* the scoping work — agents propose what artifacts would constitute "complete clarity" for this kind of project.
- The user reviews, edits, narrows.
- Slow first-deliberation, but it's where genuine alignment happens before work begins.

**Both paths produce the same artifact (a locked manifest), and from there the system runs identically.** The vague user gets value from the protocol forcing them to articulate; the concrete user gets value from agents pressure-testing what they specified.

### Why the manifest always goes through deliberation

Even for concrete users, the manifest is established via deliberation #0001 (or whatever ID — typically the first numbered one), not as an off-protocol artifact. Three reasons:

1. **Forces protocol-shaped articulation.** Sloppy specifications get caught when the structure is rigid.
2. **Lets agents propose additions.** "You didn't include a security-considerations doc — given this is a SaaS product, should we?" The user might not have thought of it.
3. **Preserves the protocol's "everything is a deliberation" cleanliness.** No off-protocol decisions floating outside the audit trail.

For concrete users the deliberation is fast (propose, ratify, lock). For vague users it's the genuine scoping conversation. Either way the structure is consistent.

### Manifest schema

`outcome-manifest.md`:

```markdown
---
status: DRAFTING | READY | LOCKED
protocol_version: 0.1
created: 2026-04-27
locked_at: null
template_used: saas-product   # null if hand-crafted
---

# Outcome Manifest

## Required artifacts

### requirements.md
**Purpose:** Complete functional specification of the product.
**Production pattern:** specifier-authored
**Specifier role:** spec-writer
**Production triggers:** when deliberations tagged `feature` are all DECIDED
**Depends on:** none
**Required sections:**
- Product vision (1–2 paragraphs)
- User personas (≥ 2)
- Core features (each with: description, user story, acceptance criteria)
- Non-functional requirements (performance, security, accessibility)
- Out-of-scope (explicit list)
**Completion checks:**
- All required sections present and non-empty
- Core features section has ≥ 3 features
- Each feature has all required sub-elements
- Approved by decider (DECISION move on a `ratifies: requirements.md` deliberation)

### ux-requirements.md
**Purpose:** Layout and interaction specification.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `ux`, `flow`, `component`
**Depends on:** requirements.md
**Becomes eligible for production when:** requirements.md status is `complete`
**Required sections:**
- Page/screen inventory (each with: purpose, key components, navigation)
- Component library
- Critical user flows
- Information architecture
**Completion checks:**
- All pages from requirements.md represented
- Each critical flow traces through specific pages
- Cross-references to requirements.md resolve

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed (not provisional)
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks
- All declared context sources have current digests (none older than user-defined freshness threshold) and have been reviewed by user (§1.8)

## Closing ceremony

When all required artifacts pass completion checks AND all quality gates are clear, the conductor opens a final meta-deliberation (status: `final: true`) for the closing summary. The decider issues a DECISION on this meta-deliberation to transition the workspace to `COMPLETED`.
```

### The three production patterns

How an artifact actually gets written varies by its nature. The manifest specifies one of three patterns per artifact:

**`synthesis-aggregated`** — Content emerges from multiple deliberations, woven together. When a deliberation tagged matching the artifact's contributing tags reaches DECIDED, its synthesis content (or a designated section of it) is appended to the artifact. The artifact grows organically as deliberations conclude. Good for: collections (feature lists, page inventories) where each deliberation contributes one piece.

**`specifier-authored`** — A single agent (in the *specifier* role) reads everything relevant after sufficient deliberation has happened, and writes the artifact end-to-end as a coherent document. Good for: artifacts that need a unified voice and narrative (a vision doc, an ADR, a strategic recommendation).

**`cross-cutting`** — Authored last, by a designated handle, summarizing the entire workspace. Good for: closing summaries, "key insights" docs, follow-up registers.

The manifest's production pattern field is not just documentation — it's read by the conductor to schedule artifact writing.

### Production scheduling

The conductor walks the manifest's dependency graph and schedules artifact production:

1. Find artifacts whose dependencies are satisfied (all listed dependencies are `complete`).
2. Find artifacts whose production triggers fire (e.g., "all deliberations tagged `feature` are DECIDED").
3. Schedule the qualifying artifact for production via its production pattern.
4. When the artifact is written, run its completion checks. If pass: status → `complete`. If fail: status → `needs_revision`, log what failed, route to specifier or relevant deliberation tags.

**Triggering mechanics (concrete):** the conductor evaluates the dependency graph at the end of each loop iteration (i.e., after every batch of agent invocations completes). When an artifact transitions to `complete`, the conductor immediately checks all artifacts that depended on it: if any now have all dependencies satisfied AND their production triggers fire, they're queued. Queue is processed in dependency-depth order (deepest first) with manifest declaration order as tie-breaker. This is event-driven, not polling — the trigger is "an artifact's status changed to complete." No wasted work checking the graph repeatedly when nothing has changed.

This means artifact production isn't a single event at the end — it's interleaved through the workspace's life. Some artifacts complete early; some wait for everything else.

### Artifacts can reopen via ARTIFACT_REVISION

Once an artifact is `complete`, it doesn't stay locked forever. Subsequent deliberations may produce decisions that contradict or extend it. To handle this honestly:

A new move type — `ARTIFACT_REVISION` — supersedes the prior version. Required sections:
- **Targets** (which artifact, which sections)
- **What changes** (additions, removals, modifications)
- **Triggering decisions** (which DECISION moves drove the revision)
- **Backwards-compatible?** (yes/no — does this break things that referenced the prior version?)

The prior version is preserved (versioned in `/artifacts/<name>.v1.md`, `<name>.v2.md`); the current version is `<name>.md`. Audit trail honest about evolution.

This is the same pattern as REVISION on individual moves: explicit, traceable, not erasing history.

### Templated manifests

For users who don't know what artifacts they want, the system ships templates:

- `manifest-templates/saas-product.md` — requirements, ux-requirements, tech-stack, pricing, mvp-scope
- `manifest-templates/research-direction.md` — research-questions, literature-survey, methodology, hypotheses
- `manifest-templates/architecture-decision.md` — adr-set, tradeoff-analysis, migration-plan
- `manifest-templates/coding-plan.md` — task-breakdown, dependency-graph, milestones, risks
- `manifest-templates/strategic-decision.md` — option-analysis, recommendation, rollback-plan

Selected at init time:
```bash
quorum init --manifest-template saas-product
```

Or proposed by the bootstrapper after reading the problem statement: "Your problem statement reads like a SaaS product brainstorm. Should we start from the saas-product manifest template?"

Templates are starting points, not constraints. The first deliberation refines them to fit the actual project.

### The closing ceremony

Completion isn't a state change — it's an event. When manifest checks pass and quality gates clear:

1. Conductor opens a *final meta-deliberation* (typically the next numbered ID, with `final: true` flag in frontmatter).
2. A designated *summarizer* handle is invoked to produce a closing synthesis: what was decided, what artifacts were produced, what was learned, what remains open (yes — even at completion, some things remain open; the system is honest about it).
3. The decider issues a DECISION move on this meta-deliberation.
4. Workspace transitions to `COMPLETED` (interactive) or `COMPLETED_AUTONOMOUS` (autonomous).
5. UI shows the completion view: artifact downloads, decision summary, optional export bundle (zipped artifacts + closing summary + ADRs for sharing).

The closing summary is itself one of the most useful outputs of the entire workspace — a "where this all landed" document for the user's future self or collaborators.

### The "what comes out" view in the UI

While the workspace is ACTIVE, the UI shows manifest progress prominently:

```
Outcome Manifest progress: 3 of 5 artifacts complete

✓ requirements.md          (complete, ratified 2 days ago)
✓ tech-stack-rationale.md  (complete, ratified 1 day ago)
✓ pricing-strategy.md      (complete, ratified yesterday)
○ ux-requirements.md       (in production by @claude-opus)
○ mvp-scope.md             (waiting on: requirements.md ratification done; queued for production)

Quality gates:
✓ No unresolved DEPUTY_DECISIONs
✓ No BLOCKED deliberations
⚠ 2 unresolved blocking questions in #0007 (Open Questions register)
```

This gives the user a real progress signal — not a fuzzy "still going" but a precise "here's what's left." Crucially, it makes the workspace's *purpose* visible at all times.

### Manifest evolution mid-workspace

The manifest itself can change after lock. If a deliberation surfaces something important, an agent can issue a `MANIFEST_PROPOSAL` move (a regular PROPOSAL on a meta-deliberation about the manifest) to add, remove, or modify an artifact requirement. User decides. If accepted, manifest is updated and a new artifact slot opens (or closes).

This means the manifest is a living document, not a contract written in stone. It reflects the workspace's evolving understanding of what completion means.

---

## 1.8. The Context Surface · 🟢 Settled

This is where the design earns or loses its economics. The protocol's commitment to stateless agents means every invocation is a fresh process — no working memory of prior invocations, no Claude-Code-style "I already understand your codebase" state. Naively, this means every invocation re-pays the cost of building context. With 750+ invocations across a workspace's life, that's catastrophic.

The fix isn't to make agents stateful. It's to make context **digested once, reused many times** — an explicit workspace artifact rather than per-invocation rebuilding.

### What counts as context

Four distinct source types. Each with a different "where do I add it" UI surface and a different default policy:

| Source | Examples | Default policy |
|---|---|---|
| **Repos** | Local codebases — single repo or multi-repo product lines | Agent-digested at setup; digest reused; source read on-demand for verification |
| **Documents** | PDFs, Markdown files, Word docs, design specs uploaded by user | Digested if large (>~5K tokens); used raw if small |
| **Web URLs** | Wiki pages, API docs, competitor pages, internal portals (publicly fetchable) | Fetched once, converted to Markdown, cached; refresh per user policy |
| **Notes** | Free-text the user authors directly (org conventions, customer context, hard-won knowledge) | Always raw, always included in standing bundle (small by design) |

The folder layout in §7 mirrors these source types. The user's mental model is: *"My repos go in /repos/, my uploaded docs go in /docs/, URLs I want included go in /web/, notes I want every agent to know go in /notes/."*

### How context flows into invocations

Every agent invocation receives a context bundle assembled by the conductor. The bundle has three layers:

**Layer 1 — Standing context bundle (always included).**
- `problem-statement.md`
- `outcome-manifest.md`
- `registers/glossary.md`
- `registers/open-questions.md` (active items only)
- `summarized-decisions.md` — one line per DECIDED deliberation, **mechanically generated by concatenating the required `Summary line` field of each DECISION move (§5)**. The conductor maintains this file: when a DECISION is appended, its Summary line is appended to `summarized-decisions.md` with the deliberation reference. No LLM call needed to maintain it; no agent involvement; no extra invocation cost. Quality is the responsibility of whoever issues the DECISION (validator enforces non-vacuous summary lines).
- All notes from `/context/notes/` — small, intentionally always-relevant
- `context/index.md` — so the agent knows what other context exists if needed

Total bundle size: bounded — typically 3-5K tokens at workspace start. For mature workspaces with 100+ DECIDED deliberations, summary lines alone account for ~8-10K tokens; combined with growing glossary and open-questions register, the bundle can reach 15-20K tokens. The cost ceiling (this section, below) catches runaway growth.

**Layer 2 — Deliberation-declared context (conditionally included).**
The deliberation's frontmatter explicitly declares what context this deliberation needs:

```yaml
# deliberations/0014-feature-x-api-design.md
relevant_context:
  repos: [backend, ai-qa-backend]
  docs: [product-spec-v3]
  urls: [api-reference-stripe]
  notes: all   # default; override with explicit list to scope
```

For each declared item, the conductor includes the *digest* (not the source) in the invocation context. A backend-focused deliberation pulls backend digest + ai-qa-backend digest; it does not pull frontend digest. Token-efficient by construction.

The bootstrapper proposes `relevant_context` when creating a deliberation, based on its topic; the user can edit before accepting. This becomes routine, not afterthought.

**Layer 3 — On-demand reads (within an invocation).**
When an agent genuinely needs to verify something specific — read a particular function in source, check a doc's exact wording, look at fresh URL data — it reads on-demand within the invocation. The standing prompt is explicit: *"Trust the digests for high-level understanding. Read source files only when you need specific details that the digest doesn't provide. The events log captures which files you read; over-reading is a tunable behavior we can correct."*

Per-invocation `files_read` is logged in events.jsonl. Excessive on-demand reads surface as a signal — either the digest is inadequate (we improve it) or the agent is over-reading (we tune the prompt).

### Repos specifically

Repos are added through the UI (Settings → Context → Repos), not as init flags. The folder picker accepts a directory path; the user adds:

- **Role descriptor** — "user-facing web app; React, TypeScript" — a one-line orientation an agent can use
- **Relevance level** — `high` (detailed digest), `medium` (overview only), `low` (just an index entry)

The conductor invokes a digester agent to produce the digest. **Default model selection scales with the source's relevance level**, since digest quality compounds across every subsequent invocation that reads the digest:

- `relevance: high` → top-tier reasoning model (`@claude-opus`, or `@gemini-pro` for very large repos where context window matters more than reasoning depth)
- `relevance: medium` → mid-tier (`@claude-sonnet`)
- `relevance: low` → cheap model (`@claude-haiku`, `@gemini-flash`) — still fine for "just an index entry" sources

This is the opposite of the obvious cost-minimizing default. The reasoning: a bad digest costs you on every subsequent invocation that reads it. If high-relevance sources drive most deliberations, paying $0.50 for a thoughtful Opus digest beats paying $0.05 for a Haiku digest that misses the analytics layer and quietly produces 500 confused downstream invocations.

**User override at digestion time.** When adding a context source via UI, the proposed digester is shown alongside a "change" link. Click to pick from any registered handle. The decision is logged in `events.jsonl` as `digester_chosen` for audit trail.

**Bulk override via settings.** Settings → Context has a "Default digester per relevance level" config block, so users who always want a specific handle for high-relevance sources don't have to override every time:

```yaml
# config.yaml
context:
  digester_defaults:
    high: "@claude-opus"
    medium: "@claude-sonnet"
    low: "@claude-haiku"
```

The digest covers: file tree with annotations, key entry points, architectural overview, important interfaces, conventions and idioms, places-to-be-careful. Setup cost depends on chosen digester: ~$0.05-0.20 with cheap models, ~$0.30-1.50 with Opus for a medium-sized repo. Worth it for high-relevance sources.

The digest is reviewable. The first deliberation in the workspace formally includes "review and refine context digests" as a step — making digest quality a manifest quality gate (§1.7). If the digest missed something important (e.g., the analytics layer for a feature about analytics), the user notes it and re-digests with focus areas. This is friction, but it's the price of trustworthy automation. A workspace that proceeds on a thin digest will produce thin work.

For multi-repo: each repo is added independently with its own role descriptor and relevance. Deliberations declare which repos they need. The cross-repo overview (`context/index.md`) describes how repos relate.

### Documents specifically

Documents are added through the UI (Settings → Context → Documents). Drag-and-drop onto the panel, or use a file picker.

The conductor decides automatically whether to digest based on token-count threshold (~5K tokens). Small docs (meeting notes, brief specs) are included raw in the relevant_context references. Large docs (product specs, design docs) are digested. User can override the auto-decision per document.

Supported types in v1: PDF (extracted via `pdfplumber` or similar), Markdown, plain text, Word docs (via `python-docx`). For OCR-needed PDFs (scanned documents), v1 surfaces a clear error and the user converts elsewhere; v2 may add OCR.

### Web URLs specifically

URLs are added through the UI (Settings → Context → Web). Each entry has:
- **URL**
- **Optional label** (e.g., "Stripe API reference")
- **Refresh policy** — `never` / `manual` / `weekly` / `monthly`

On add, the conductor fetches and converts to Markdown via standard tooling (something like Readability + trafilatura, then trimmed). The cached version is shown for review; the user can edit or trim further before saving.

Refresh policies handle staleness automatically. `never` means fetch-once; `manual` means user clicks refresh; `weekly`/`monthly` triggers automatic re-fetch on schedule. Every cached entry shows fetch date prominently.

For URLs requiring authentication (internal wikis, paywalled content): v1 doesn't support authenticated fetch. The user can manually save the page content as a doc and upload it via Documents instead. v2 may add credential-managed fetch for common platforms (Confluence, Notion, Google Docs).

### Notes specifically

Notes are user-authored Markdown snippets, added through the UI (Settings → Context → Notes). They're for things every agent should know that don't have a natural home elsewhere:

- "Studio's UX patterns differ from client; all interactions go through the command palette. Don't propose modal dialogs."
- "Our backend team owns the API contract; UX team can suggest changes but cannot decide them."
- "We've previously rejected GraphQL twice; if proposing it, address the prior rejections in your reasoning."

Notes are intentionally short. They live in the standing bundle, included in every invocation. There's no digestion — they're already in the right form. Practical limit: probably ~50K tokens total across all notes (the conductor warns when approaching).

A note can be marked `deliberation-scoped` rather than always-included, but this is rare — most notes earn their place by being broadly useful.

### Freshness and honest acknowledgment

External context goes stale. The system surfaces this honestly rather than hiding it.

**Repos:** `meta.yaml` tracks `last_digested_at`. UI shows freshness indicator (green <7d, yellow <30d, red older). Agent prompts include: *"You're reading a digest produced N days ago. The repo may have evolved. If your move depends on current code state, note this limitation."*

**Web URLs:** cached version shows fetch date; refresh policy controls automatic re-fetching. Same prompt augmentation about potential staleness.

**Documents:** generally don't go stale (a PDF you uploaded is the PDF). User can re-upload if a new version exists; UI surfaces the update.

**Notes:** user-authored, the user manages their own freshness.

Every invocation that reads from a digest logs `digest_age_at_use` in events.jsonl. Post-hoc analysis can reveal "we made this decision based on a 90-day-old digest" — uncomfortable but honest.

### Cost discipline as a first-class concern

The whole design exists to control cost. Concretely:

**Per-invocation token budget tracking.** Every invocation logs `tokens_in / tokens_out`; cost computed from per-handle pricing. UI shows running cost per deliberation and per workspace.

**Context-load monitoring.** Every invocation logs which context artifacts were included and their token sizes. Bloated bundles surface in the events log.

**Digest-vs-source discipline.** Standing prompt instructs agents to trust digests for high-level understanding and read source only for specific verification. Excessive `files_read` per invocation flags potential prompt-tuning issues.

**Relevance-tiered model selection for digestion.** Digestion model defaults scale with relevance: high → Opus (or Gemini-Pro for large repos), medium → Sonnet, low → Haiku/Flash. Routing-defaults encode this. User can override per-source at digestion time or bulk-override via `context.digester_defaults` in `config.yaml`. The reasoning: a bad digest costs you on every subsequent invocation that reads it, so paying more for a thoughtful digest of high-relevance sources is the right trade. Cheap-model defaults remain appropriate for low-relevance sources, glossary maintenance, and other housekeeping.

**Workspace-level cost ceiling (default ON at $50).** A configurable max: "stop the workspace if cumulative cost exceeds $X." **Defaults to enabled at $50.** When the ceiling is hit, conductor pauses the workspace, surfaces a clear notification ("This workspace has spent $50; continue, raise ceiling, or stop"), and waits for explicit user action. The user can raise the ceiling, disable it entirely, or accept the stop.

The reasoning: cost is the kind of thing where surprises destroy trust permanently. The user who opens the bill and sees $300 they didn't expect is unlikely to use Quorum again, even if the work was good. Defaulting the ceiling ON forces an explicit "raise this" decision from the user the first time a substantial workspace approaches it, which is exactly when they should be making that decision consciously. Users running fast exploratory workspaces will hit $50 quickly and raise it immediately; users running modest workspaces never hit it. The ceiling becomes a friction point only when it should be — when costs are accumulating faster than the user expects.

The wizard (§9.8) sets the initial ceiling: question 6 — "Set a cost ceiling for this workspace? (default $50; you can raise it anytime)". One-click options: $25 / $50 / $200 / no ceiling. Most users accept the default.

Real cost data captured in events.jsonl: `tokens_in`, `tokens_out`, `cost_usd_estimate` per invocation. UI shows running cost prominently in the workspace header alongside manifest progress. The user can see at a glance: "spent $32 of $50, 8 deliberations DECIDED."

**Expected economics for a multi-repo brainstorm.** With proper digestion, a feature-X workspace pulling 3 relevant repos sees ~30K input tokens per invocation × 750 invocations ≈ 22M input tokens. At Sonnet pricing, well under $100. Compare to naive design (full source per invocation): 150M+ tokens, $1500+. The digestion approach is 15-40x cheaper.

### What the user actually does — end-to-end scenario

You're brainstorming a cross-product feature touching three of your company's repos. Workflow:

1. `quorum init` in a fresh workspace directory. UI opens.
2. Setup wizard. You complete it.
3. Settings → Context → Repos. "Add repo" three times. For each: folder picker, role descriptor, relevance. Digestion queues; cheap-model invocations run in background. Total elapsed: 5-10 minutes for three medium repos.
4. Settings → Context → Documents. You drag-drop a customer call transcript and an internal product spec PDF. Transcript is small — used raw. PDF is digested.
5. Settings → Context → Web. You add the internal wiki URL describing existing architecture. Refresh policy: manual.
6. Settings → Context → Notes. You type two notes: org conventions and feature-X-specific customer context.
7. You review the digests as they complete. Backend digest is great. Client-frontend digest missed analytics — you add a focus note and re-digest. AI-QA-backend digest is fine.
8. You write the problem statement.
9. You start the workspace.
10. The first deliberation creates the manifest. The bootstrapper proposes `relevant_context` for each deliberation it spawns based on topic. Frontend deliberations pull frontend digest only; backend deliberations pull backend + AI-QA digests; cross-cutting deliberations pull everything.
11. As deliberations progress, agents reference context, on-demand-read source files when needed, and produce moves grounded in your real environment.
12. Total cost is bounded and visible in the UI.

This is "best use of bucks" made concrete. The user adds context once through clean UI affordances; the system reuses it efficiently across the entire collaboration.

### Cross-workspace context (deferred)

A workspace's context lives in that workspace. If you start a new workspace for a different feature in the same company, you re-add the same repos. Tedious for power users.

In v2 this is solved with **cross-workspace context registers** (already noted as DO-4). A user can register a repo or note set globally; new workspaces can inherit them with one click. v1 keeps it simple and per-workspace.

### What this design refuses to do

- **Never silently include unbounded source.** Every byte of context is either digested, declared in the deliberation, or read on-demand with logging. No invocation accidentally pulls 200K tokens.
- **Never claim to "know" things the workspace doesn't contain.** Agents reference the workspace's context explicitly; standing knowledge of an agent (e.g., Claude's prior memory of your repos) is treated asymmetrically and audit-trail-tagged when used.
- **Never let stale context masquerade as fresh.** Digests have ages; URLs have fetch dates; agents acknowledge limitations.
- **Never make context "magic."** Everything is a file the user can inspect. The UI is structured access to those files; nothing is hidden.

---

## 2. Conceptual Model · 🟢 Settled (v0.2)

The right mental model is **code review fused with academic peer-review, mediated by an issue tracker.** Four commitments:

1. **The deliberation is the unit of work, not the message.** A deliberation has a question, a lifecycle, contributors, a status, and an outcome. Proposals, critiques, syntheses are *moves within a deliberation*.

2. **Agents are stateless participants, not stateful actors.** No agent remembers anything between turns. The repo is the memory. Every invocation, agents are handed the relevant slice of the workspace and asked for a specific kind of contribution.

3. **Inboxes are routing notifications, not mailboxes.** Content lives in deliberation files only. Inboxes are pointers ("you've been tagged in #0001") — never duplicated content. One source of truth.

4. **The workspace is the unit of continuity, sessions are just punctuation.** A workspace persists across days, weeks, or months. Pausing and resuming is normal — even encouraged. The reasoning compounds across sessions; nothing is lost when the conductor stops. Most multi-agent demos are session-bound (start a chat, end it, lose context); Quorum's design is the opposite. This is what makes long-running brainstorming actually viable.

---

## 3. Identity & Roles · 🟢 Settled (v0.2)

### Identity

Each participant has a stable handle: `@claude-opus`, `@claude-sonnet`, `@gemini-pro`, `@gemini-flash`, `@codex-gpt5`, `@human-rohan`, etc.

**A handle binds together: a CLI binary + a specific model selection + a role-fitness profile.** This is more granular than "one handle per CLI" — different model variants of the same CLI are *different participants* with different strengths and quotas. This matters because:

- The same CLI often supports multiple models (Claude Code → Opus/Sonnet/Haiku; Gemini CLI → 2.5 Pro / Flash; Codex → GPT-5 variants).
- Routing intelligence depends on knowing which model is on the other end, not just which CLI.
- Quota and budgeting are model-specific, not CLI-specific.

Roles can be expressed via additional handles when desired (e.g., `@claude-opus-architect` and `@claude-opus-critic` could be the same model with different system prompts), but these are advanced configurations — most workspaces use one handle per (CLI, model) pair.

### Roles (assigned per-deliberation, not globally)

| Role | What they do |
|------|--------------|
| **Proposer** | Drafts the initial position |
| **Critic** | Finds flaws, missing cases, weak arguments |
| **Synthesizer** | Reconciles competing views into a coherent recommendation |
| **Specifier** | Turns a synthesis into concrete specs/ADRs/tasks |
| **Reviewer** | Final pass before human approval |
| **Domain expert** | Invoked for narrow expertise (security, UX, perf) |
| **Decider** | Issues the final DECISION move (default: `@human-rohan`) |
| **Bootstrapper** | Reads the problem statement and creates the first deliberation (special; happens once per session) |
| **Explainer** | Responds to CLARIFY moves with grounded EXPLANATION moves (§4, §12.5). Default fitness mirrors `domain_expert`. Standing prompt for explainer invocations is strict about citation and gap acknowledgment. |

A given handle can hold different roles in different deliberations. Roles are declared in deliberation frontmatter, but **the user does not assign specific handles to roles manually** — that's the routing system's job (§3.6). The user's mental model is "this deliberation needs a synthesizer," not "this deliberation needs Opus specifically."

---

## 3.5. Participants Registry Schema · 🟢 Settled

`/quorum/registers/participants.md` is the operational registry the conductor reads at runtime. It's both human-readable Markdown and machine-parseable (YAML frontmatter + a structured table).

### Schema

```markdown
---
schema_version: 0.1
last_updated: 2026-04-27
---

# Participants Registry

| Handle | Display Name | CLI Command | Model | Transport | Quota (daily/per-deliberation) | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @claude-opus | Claude (Opus) | claude --print --model opus | claude-opus-4-7 | cli | 30/5 | fine_grained | (none) | green |
| @claude-work-opus | Claude Work (Opus) | claude-work --print --model opus | claude-opus-4-7 | cli | 30/5 | fine_grained | Work | green |
| @claude-personal-opus | Claude Personal (Opus) | claude-personal --print --model opus | claude-opus-4-7 | cli | 30/5 | fine_grained | Personal | green |
| @claude-sonnet | Claude (Sonnet) | claude --print --model sonnet | claude-sonnet-4-6 | cli | 100/15 | fine_grained | (none) | green |
| @gemini-pro | Gemini Pro | gemini --model gemini-2.5-pro | gemini-2.5-pro | cli | 50/10 | fine_grained | (none) | green |
| @gemini-flash | Gemini Flash | gemini --model gemini-2.5-flash | gemini-2.5-flash | cli | 200/30 | fine_grained | (none) | green |
| @codex-gpt5 | Codex (GPT-5) | codex exec --model gpt-5 | gpt-5 | cli | 50/10 | fine_grained | (none) | green |
| @chatgpt-web | ChatGPT (web) | (manual) | gpt-5 | manual | unlimited | n/a | (none) | n/a |
| @human-rohan | Rohan | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |
```

The above table illustrates a workspace where the user has registered three Claude installations: the canonical `claude` and two account-specific ones (`claude-work`, `claude-personal`). Each becomes its own handle with independent quota tracking even though all three map to the same underlying Claude Opus model — because they map to *different accounts* with separate rate limits. The `Account Label` column drives UI grouping and badging; it has no effect on routing or protocol semantics.

### Field semantics

- **Handle** — primary identifier, used in moves, mentions, frontmatter. Stable; changing breaks history. By convention, multi-account setups suffix the handle with an account hint (e.g., `@claude-work-opus`).
- **Display Name** — what the UI shows. Friendly, can contain spaces.
- **CLI Command** — the exact command template the conductor invokes. The conductor appends prompt-input redirection as needed. **For multiple installations of the same CLI**, this field captures the distinguishing binary name (e.g., `claude-work` vs `claude-personal`).
- **Model** — the model identifier the CLI will use. Source of truth for what's actually running.
- **Transport** — `cli` | `manual` | `mcp` (v2) | `ide` (v2). Determines how the conductor routes work.
- **Quota** — `daily/per-deliberation` invocation caps. Conductor enforces; routing routes around exhausted handles. Note: quota is tracked per-handle, not per-account. If multiple handles share an underlying account, set per-handle quotas conservatively to avoid hitting the account-level rate limit when invoked concurrently.
- **Permission Capability** — `fine_grained` | `coarse` | `none` | `n/a` (for manual handles). Determines eligibility for moves that may need shell access (§10.6). Detected by `quorum doctor` at registration; surfaces in the participants UI with a "limited permission control" badge for `coarse`/`none`.
- **Account Label** — optional free-form string ("Work", "Personal", "Org-X", etc.) for UI grouping/badging in the participants panel. Display-only; nothing in routing or protocol depends on it. Empty for canonical/default registrations.
- **Health** — `green` | `yellow` | `red` | `unknown`. Updated by `quorum doctor` and after each invocation.

### Fitness inheritance for non-canonical handles

`routing-defaults.yaml` (§3.6) ships fitness ratings for canonical handle names: `@claude-opus`, `@claude-sonnet`, `@gemini-pro`, etc. Custom handles like `@claude-work-opus` won't match any of these directly.

The fix: when a non-canonical handle is registered, the system asks the user which canonical handle this should *inherit fitness from* (defaulting to the obvious match — `@claude-work-opus` inherits from `@claude-opus`). This mapping is stored in `participants.md` as an `inherits_fitness_from` field on the handle row. The conductor uses the canonical's fitness ratings when routing, unless the user has overridden per-handle.

This pattern generalizes beyond multi-account: it's also how a fine-tuned model variant, a model accessed through a different provider, or any other custom handle can inherit sensible fitness defaults.

### Fitness ratings (separate file)

Fitness ratings (which handle is good at which role) are kept in `/quorum/registers/routing-defaults.yaml` rather than in `participants.md`. This separation matters because:

- Fitness defaults are *shipped with the system* and refreshed on init (§3.6).
- Per-handle quotas and CLI commands are *user-specific* and never overwritten.

Mixing them in one file would mean refresh either clobbers user data or skips defaults — both bad. Keep them separate.

---

## 3.6. Routing & Model Selection · 🟢 Settled

The user's posture is: **"I came here to solve a problem, not to micromanage models."** Routing is fully automatic by default. The user can override at the workspace level if they want, and there's an undocumented escape hatch for per-deliberation control, but the surface area for routing decisions in normal use is *zero*.

### The layered routing model

When a move is needed for a specific role, the conductor walks these layers in order, taking the first match:

**Layer 1 — Per-deliberation override (escape hatch, not surfaced in UI).**
If a deliberation's frontmatter explicitly names a handle for a role (`synthesizer: @claude-opus`), that's authoritative. This exists for power users who edit frontmatter directly. It is intentionally not exposed in the UI — the default user experience never asks the user to pick handles.

**Layer 2 — Workspace override.**
`/quorum/config.yaml` may contain `routing.overrides` mapping roles to specific handles. Set once, applies workspace-wide. Editable through UI settings (advanced section, not prominent).

**Layer 3 — Fitness-based defaults (the normal path).**
The conductor consults `/quorum/registers/routing-defaults.yaml` for the fitness ratings of each handle on the requested role, picks the highest-fitness handle that's available (under quota, healthy, not rate-limited). Ties broken by lowest cost.

**Layer 4 — Fallback.**
If no handle is fitness-rated for the role, or all rated handles are unavailable, the conductor picks the highest-cost available handle and logs a routing fallback warning.

**Future Layer 0 — Dynamic routing (deferred, see DO-2 in §19).**
Eventually a fast/cheap model reads the deliberation context and picks the best handle dynamically based on what the move actually needs. This is the north-star architecture; static fitness tables are the v1 stepping stone.

### Routing-defaults schema

`/quorum/registers/routing-defaults.yaml`:

```yaml
schema_version: 0.1
generated: 2026-04-27
source: https://github.com/yourname/quorum/blob/main/defaults/routing-defaults.yaml

# Fitness ratings: per-handle, per-role, scale 0-3
# 0 = not suitable, 1 = low, 2 = medium, 3 = high
fitness:
  "@claude-opus":
    proposer: 3
    critic: 2
    synthesizer: 3
    specifier: 3
    reviewer: 3
    domain_expert: 3
    bootstrapper: 3
    explainer: 3
  "@claude-sonnet":
    proposer: 2
    critic: 2
    synthesizer: 2
    specifier: 3
    reviewer: 2
    domain_expert: 2
    bootstrapper: 2
    explainer: 2
  "@gemini-pro":
    proposer: 2
    critic: 3        # Gemini's adversarial framing tends to be sharper
    synthesizer: 2
    specifier: 2
    reviewer: 2
    domain_expert: 2
    bootstrapper: 2
    explainer: 2
  "@gemini-flash":
    proposer: 1
    critic: 1
    synthesizer: 1
    specifier: 2
    reviewer: 1
    domain_expert: 1
    bootstrapper: 1
    explainer: 1
  "@codex-gpt5":
    proposer: 2
    critic: 2
    synthesizer: 2
    specifier: 3        # particularly good at concrete spec output
    reviewer: 2
    domain_expert: 2
    bootstrapper: 2
    explainer: 2

# Cost ratings (relative, for tie-breaking; lower = cheaper)
cost:
  "@claude-opus": 5
  "@claude-sonnet": 2
  "@gemini-pro": 3
  "@gemini-flash": 1
  "@codex-gpt5": 4

# Notes (human-readable, not parsed)
notes: |
  Fitness ratings are our considered defaults based on observed model behavior
  in reasoning workflows. Updated periodically as models evolve.
```

### Refreshing routing defaults

Models evolve. New versions arrive. Capabilities shift. The fitness table must stay current without forcing users to manually re-edit YAML.

**Mechanism:**

1. **On `quorum init`:** the CLI fetches the latest `routing-defaults.yaml` from the source repo (configurable; defaults to the official upstream). Writes it to `/quorum/registers/routing-defaults.yaml`.

2. **On `quorum refresh-defaults`** (explicit command): re-fetches the latest defaults. User can run this whenever they want to pull updates.

3. **Offline fallback:** if the fetch fails (no network, repo unreachable), the CLI uses the version bundled with the install. The user is warned ("using bundled defaults from <date>; run `quorum refresh-defaults` when online").

4. **Notification:** when a refresh changes existing fitness ratings significantly, the UI shows a notification — "Routing defaults updated. Claude Opus's `synthesizer` fitness changed from 2 to 3." This keeps the user informed without forcing review.

5. **User overrides are preserved.** Refresh only writes `/quorum/registers/routing-defaults.yaml`. The user's overrides live in `/quorum/config.yaml` (Layer 2) and are never touched by refresh.

**Cadence:** we (the maintainers) update the upstream `routing-defaults.yaml` when meaningful model changes happen — new model releases, observed shifts in capability, community feedback. Users get the benefit of evolving defaults without lifting a finger.

### Routing decision visibility

Every routing decision is logged. The activity feed shows entries like:

```
2:14:48  @gemini-pro selected for CRITIQUE on #0001
         (fitness: 3, layer: defaults, alternatives: @claude-sonnet [fit:2])
```

The user can see *why* each handle was picked. If routing feels wrong, they know exactly where to override. This is the visibility property that makes automatic routing trustworthy.

---

## 4. The Move Vocabulary · 🟢 Settled (v0.3)

Each contribution to a deliberation is a **move** of a specific type. Moves are the legal verbs of the protocol.

### Core moves (any participant)

| Move | Purpose |
|------|---------|
| `PROPOSAL` | A position being put forward |
| `CRITIQUE` | Structured objections targeting a specific prior move |
| `QUESTION` | An open question requiring an answer |
| `ANSWER` | A response to a question |
| `SYNTHESIS` | Reconciliation attempt over multiple proposals/critiques |
| `DECISION` | A ruling (issued only by the designated decider) |
| `DEPUTY_DECISION` | A provisional decision made by an agent on the human's behalf when the human-timeout policy fires (§10.4). Always reversible; needs confirmation or override on human's return. Never used for `irreversible` stakes. |
| `REVISION` | An updated version of a prior move (does not edit the prior — supersedes it) |
| `ARTIFACT_REVISION` | An updated version of a previously-completed manifest artifact, triggered by subsequent decisions. Supersedes the prior version (kept versioned); never silently overwrites. See §1.7. |
| `ABSTAIN` | Explicit "I have nothing to add" — closes a routing request cleanly |

### Human-initiated moves (the proactive voice — see §12.5)

The human is not just a responder. They can initiate the following move types at any time during ACTIVE state. These exist because the protocol must accommodate the human introducing new information, redirecting effort, or overriding decisions — not just answering questions agents pose.

| Move | Purpose | Who can issue |
|------|---------|---------------|
| `INTERJECTION` | Inject new information mid-stream — a customer conversation, a constraint they forgot, a competitive insight, a budget change. Cascades into in-flight deliberations as prompt augmentation. | Human only |
| `OVERRIDE` | End a deliberation with a unilateral decision. Useful for "stop debating X, I've decided Y, move on." Force-ends in-flight invocations on that deliberation. | Decider only (typically human) |
| `REOPEN` | Re-open a previously DECIDED deliberation. Previous DECISION is preserved as superseded; agents are prompted to re-engage with new context. | Decider only |
| `DROP` | Abandon a deliberation without resolving. Status → ABANDONED. Distinct from DECIDED (resolved) and ARCHIVED (closed-and-kept). | Decider only |
| `STEER` | Provide non-binding advisory guidance to agents on a deliberation — "be more skeptical here," "find more disagreement," "don't converge yet." Affects prompt augmentation for future invocations; does not force outcomes. | Human only (v1) |
| `CLARIFY` | Request explanation about something — a concept the user doesn't understand, the reasoning behind a prior decision, or a section being reviewed later. Does not progress work; does not change deliberation state. Can target any move, any artifact, any text span. Allowed on DECIDED and ARCHIVED workspaces. | Human only (v1) |

### Auxiliary response moves

| Move | Purpose | Who can issue |
|------|---------|---------------|
| `EXPLANATION` | Response to a CLARIFY. Grounded in actual workspace content with required citations to specific sources. Does not change deliberation state. Visually subordinate to core decision-flow moves. | Any agent assigned the `explainer` role |

**Why ABSTAIN matters:** Without it, "no response" is ambiguous between pending, abstained, or agent-failed. The state machine cannot close.

**Why DEPUTY_DECISION matters:** When automation answers on the human's behalf, the audit trail must be honest about what happened. A DEPUTY_DECISION is structurally different from a DECISION — visually distinct in the UI, requiring confirmation, expiring if not reviewed. Automation produces drafts, never finals.

**Why human-initiated moves matter:** Without them, the human is structurally limited to a *responder* role — answering QUESTIONs and ratifying syntheses. Real users have new information mid-stream, change their minds, and want to redirect. The protocol must give them clean expressions for these actions; otherwise users hack around it (manual file edits, conductor restarts) and the audit trail degrades.

**Why CLARIFY/EXPLANATION are distinct from QUESTION/ANSWER:** A QUESTION progresses decision work — the deliberation can't conclude until it's answered. A CLARIFY requests *understanding* — it doesn't ask the workspace to make a decision, just to explain. Treating them as the same move type produces routing problems and pollutes audit trails. The structural distinction matters because agents prompt differently for explanations vs answers (teacher posture vs decision-making posture), the audit trail stays clean (clarification threads visually distinct from decision flow), and clarification can happen on completed work without disturbing it.

---

## 5. Move Block Format · 🟢 Settled (structured, not strict)

**Posture:** Structured — required sections, free prose within. Not strict (no JSON schema), not loose (no convention-only).

### Header line (canonical, parseable)

```
### [MOVE_TYPE] @author · ISO-8601-timestamp [→ targets <REF>, <REF>]
```

### Reference convention

`<MOVE_TYPE>@<author>#<deliberation_id>` — e.g., `PROPOSAL@claude-code#0001`

This makes targets parseable across deliberations, enabling a discussion graph without LLM parsing.

### Section requirements per move type

Each move type has required sections. Sections may contain "none" but **must be present**. Examples:

**PROPOSAL:**
- Position
- Reasoning
- Assumptions
- Risks I see
- **Alternatives I considered** (other approaches weighed; even "none, this is the obvious choice" is data — but should be explicit)
- Tagging (with justification)

**CRITIQUE:**
- Strong objections
- Weak objections
- Agreed points
- Counter-proposal (or "none")

**SYNTHESIS:**
- Reconciles (list of move references)
- Convergent view
- Remaining disagreements (cannot be silently dropped)
- **Alternatives weighed** (consolidated list of all alternatives surfaced in proposals, with brief notes on why each was rejected or set aside)
- Recommendation

The strengthened **Alternatives** sections in PROPOSAL and SYNTHESIS exist to ground future EXPLANATIONs in real data. Without them, an agent asked "what alternatives were considered for this decision?" weeks later might confabulate plausible-sounding answers. With them, the audit trail contains the substance needed to answer truthfully — including, sometimes, the truthful answer that "few alternatives were actually considered."

**QUESTION:**
- Question (the actual question)
- Stakes (one of: `trivial` | `tactical` | `strategic` | `irreversible` — drives human-timeout policy in §10.4)
- Why I'm asking
- What I'd recommend if forced (agent's tentative answer if pressed)
- Information you have that I don't (what context only the human has)

The `Stakes` field is the agent's auditable judgment about how consequential this question is. Misclassification is a protocol violation that surfaces in human review.

**DEPUTY_DECISION:**
- Decision (what was decided)
- Rationale (reasoning grounded in the deliberation context)
- Confidence (low | medium | high)
- Reversibility window (timestamp until which override is straightforward; after this, more disruptive)
- What I'd want the human to confirm (specific points the human should explicitly validate)
- Spawns ADR? (yes/no — but the ADR is also provisional until human confirms)

DEPUTY_DECISION moves carry additional frontmatter:
```yaml
acting_for: @human-rohan
policy_triggered: human_timeout
stakes_classification: tactical    # from the originating QUESTION
can_be_overridden_until: 2026-04-28T08:00:00Z
status: provisional                # provisional | confirmed | overridden | expired
```

**DECISION** (when issued by human after a DEPUTY_DECISION):
- Standard DECISION fields, plus optional reference: `confirms: DEPUTY_DECISION@claude-opus#0007` if the human is ratifying the deputy's call.
- **Path not taken** (optional but encouraged) — the decision-maker's explicit acknowledgment of what they're choosing against. Strengthens the audit trail for future EXPLANATIONs.

**DECISION (all DECISION moves, regardless of issuer):**

Every DECISION move — whether issued by human, agent in autonomous mode, or as confirmation of a DEPUTY_DECISION — has these required sections:

- **Decision** — what was decided (full statement)
- **Summary line** — a one-sentence (≤120 chars) plain-English summary of what was decided. **Required, validator-enforced.** This is the line that gets concatenated into `summarized-decisions.md` (§1.8 standing context bundle), so every subsequent invocation reads it. Quality compounds — write it deliberately, not as an afterthought.
- **Rationale** — reasoning, citing relevant moves
- **Path not taken** (optional but encouraged) — what's being chosen against
- **Spawns ADR?** (yes/no)
- **Spawns task?** (yes/no)

The Summary line is the single most-read sentence the workspace produces. By the time deliberation #50 spins up, every prior DECISION's summary line has been read by every agent invocation since. Vague summaries ("Approved the proposal") tell future agents nothing. Specific summaries ("Pricing tier structure: free / pro $20 / team $50; 14-day pro trial; no annual discounts in v1") give them the actual decision context. Validator rejects summary lines that are obviously generic; "approve always" patterns the validator catches: "approved", "decided yes", "we'll do this", anything under 30 characters.

**DECISION** moves can also carry an optional `contributes_to` field in their frontmatter, declaring which manifest artifact section the decision feeds:
```yaml
contributes_to:
  - requirements.md#pricing
  - mvp-scope.md#in-scope
```
This drives synthesis-aggregated artifact production (§1.7). Decisions without `contributes_to` are still valid — they just don't directly populate artifacts.

**ARTIFACT_REVISION:**
- Targets (artifact filename, optionally specific section refs)
- What changes (additions, removals, modifications — described concretely)
- Triggering decisions (list of DECISION move references that drove the revision)
- Backwards-compatible? (yes/no — does this break references from other artifacts?)
- New version number (e.g., v2)

ARTIFACT_REVISION moves preserve prior versions. The current artifact is `<n>.md`; superseded versions are kept at `/artifacts/versions/<n>.v1.md`, `<n>.v2.md`, etc. Audit trail honest about evolution.

**INTERJECTION:**
- What's new (the new information being introduced)
- Where it applies (`workspace`, `deliberation:<id>`, `deliberation-tag:<tag>`, `artifact:<name>`, or list)
- Force level (`advisory` | `strong` | `overriding`)
  - `advisory` — agents are made aware on next invocation; no required acknowledgment
  - `strong` — affected deliberations' next moves must explicitly acknowledge in their own text
  - `overriding` — affected deliberations pause until a move explicitly addresses the interjection
- Why I'm raising this now (context for why mid-stream)

INTERJECTION moves carry frontmatter:
```yaml
issued_by: @human-rohan
issued_at: 2026-04-29T14:22:00Z
applies_to: [deliberation:0007, deliberation:0011, artifact:requirements.md]
force: strong
```

**OVERRIDE:**
- Decision (what's being decided unilaterally)
- Rationale (why I'm overriding rather than letting deliberation conclude)
- What's being preserved (acknowledgment of unconsidered material — proposals/critiques that were in flight)
- Spawns ADR? (yes/no)
- Cascade (does this contradict prior DECISIONs that should now be reopened?)

OVERRIDE produces a DECISION-equivalent state transition (deliberation → DECIDED) but the move is named differently to preserve audit honesty: anyone reading later sees that this conclusion was force-issued rather than emerging from the deliberation.

**REOPEN:**
- Targets (deliberation ID being reopened)
- Why I'm reopening (new information, changed mind, agents missed something, etc.)
- What changed since the prior DECISION (if applicable)
- Scope (full reopen, or just specific aspects to revisit)

REOPEN transitions deliberation status DECIDED → IN_REVIEW. The prior DECISION is preserved with a `superseded_by_reopen` marker; any artifacts produced from that decision are flagged for ARTIFACT_REVISION cascade.

**DROP:**
- Targets (deliberation ID being abandoned)
- Reason (no longer relevant / out of scope / superseded by other work / etc.)
- Disposition of partial work (preserved as-is / archive separately / discard)

DROP transitions deliberation status to ABANDONED — distinct from DECIDED (resolved) and ARCHIVED (closed). Work stops; partial moves are preserved for record.

**STEER:**
- Direction (e.g., "be more skeptical," "expand exploration," "converge faster," "challenge X harder")
- Targets (which deliberations, which roles, which handles)
- Reason (why I'm nudging)
- Duration (this deliberation only / until I revoke it / for next N moves)

STEER does not change deliberation state. It augments the standing prompt for affected agents on subsequent invocations. The audit trail records steers; if a particular steer materially shaped an outcome, a reader can trace why.

**CLARIFY:**
- Targets — what's being asked about. One of: a move ref (`PROPOSAL@claude-opus#0014`), a text span within a move (move ref + character range or selected text), an artifact section (`requirements.md#pricing`), a deliberation broadly (`#0007`), or a problem-statement section.
- What I'm asking about — the actual clarification request, in plain language
- Why — context for why the user is asking. One of: `knowledge_gap` ("I don't know this concept"), `reasoning_question` ("I want to understand why this was decided this way"), `reviewing_later` ("I'm reading this weeks later and want context"), or `other` with explanation
- Preferred explainer (optional) — a specific handle the user wants to answer; otherwise routing picks based on `explainer` fitness

CLARIFY does not change deliberation state. If the targeted deliberation is in `BLOCKED_ON_HUMAN` waiting on the user's answer, the block is **paused** while the CLARIFY → EXPLANATION exchange happens; once the user issues the actual ANSWER, the block resumes its resolution. CLARIFY is allowed on DECIDED and ARCHIVED workspaces — agents can be invoked to explain even on long-finished work.

**EXPLANATION:**
- Targets — the CLARIFY being responded to (move ref)
- Explanation — the actual content. May contain both general knowledge (legitimately the agent's training) and workspace-specific claims, but the two must be distinguished within the text (e.g., separate paragraphs labeled "**General context:**" and "**In this workspace:**").
- Sources cited — explicit list of all references made in the explanation (move refs, file paths, line ranges within files). Validator checks that every workspace-specific claim has at least one corresponding source.
- What I couldn't find in the workspace — explicit list of things the user might have wanted that the workspace doesn't actually contain. **This is the anti-confabulation field.** When the user asks "what alternatives were considered?" but only one was actually surfaced, this field says so.
- Limitations — optional, surfaces secondary gaps (e.g., "the deliberation cited an external URL I cannot access," "the original author handle is no longer in this workspace's participants")

EXPLANATION moves carry frontmatter:
```yaml
explainer_role: explainer
responding_to: CLARIFY@human-rohan#0014
visually_subordinate: true   # rendered inset/muted in UI
```

The validator runs additional checks on EXPLANATION moves: every paragraph making a workspace-specific claim must contain at least one valid reference; the `What I couldn't find` section must be present (write "nothing relevant was missing" if all clarifications were fully grounded). EXPLANATIONs that fail validation are flagged for revision before being accepted.

Other move types' templates live in `/protocol/templates/`.

### Soft enforcement

A linter (small Python script) flags missing sections after each agent invocation. Bad moves don't get rejected outright — agent gets one retry, then it's flagged for human review.

---

## 6. Status State Machine · 🟢 Settled

```
DRAFT → OPEN → IN_REVIEW → SYNTHESIS → DECIDED → ARCHIVED
                  ↓                       ↑   ↓
              BLOCKED_ON_HUMAN      OVERRIDE  REOPEN (back to IN_REVIEW)
                  ├─ → BLOCKED_ON_UNAVAILABLE  (handle unavailable + strict policy, §10.3)
                  ├─ → BLOCKED_ON_ROUTING     (no available handle for required role, §10)
                  ├─ → BLOCKED_ON_PERMISSION  (agent CLI awaiting user permission for shell op, §10.6)
                  └─ → DECIDED_PROVISIONALLY  (DEPUTY_DECISION resolved, awaiting human ratification, §10.4)
                  
              BLOCKED_ON_EXTERNAL  (needs external info / API / data)
              
Any active state ─DROP→ ABANDONED  (human force-ends without resolution; §12.5)
```

- **DRAFT**: Being authored, not yet circulated.
- **OPEN**: Circulated, accepting first contributions.
- **IN_REVIEW**: Active proposals + critiques.
- **SYNTHESIS**: Synthesizer is consolidating.
- **DECIDED**: Decision made (by human, by deputy-then-confirmed, or by OVERRIDE); downstream artifacts (ADR, tasks) spawned.
- **DECIDED_PROVISIONALLY**: A DEPUTY_DECISION resolved the deliberation but awaits human ratification. Treated as DECIDED for downstream chaining (other deliberations can reference it), but flagged in the UI and counted in `pending_deputy_count`. Transitions to DECIDED on confirmation, regresses to IN_REVIEW on override, becomes effectively DECIDED on expiry (with expired flag preserved in audit trail).
- **ABANDONED**: Human-initiated DROP. Work stopped without resolution. Distinct from DECIDED (resolved) and ARCHIVED (closed-and-kept). Partial moves preserved for record. Cannot transition back to active states without explicit REOPEN.
- **ARCHIVED**: Closed, kept for record.
- **BLOCKED_ON_HUMAN**: Halts the autonomous loop; waits for human input. Sub-states distinguish blocking reasons.
- **BLOCKED_ON_UNAVAILABLE**: Handle needed for next move is unavailable + substitution policy is strict (§10.3).
- **BLOCKED_ON_ROUTING**: No available handle for the required role (§10).
- **BLOCKED_ON_PERMISSION**: An agent CLI is paused awaiting the user's permission decision for an out-of-allowlist shell operation (§10.6). Resolves on user grant/deny (or stakes-based auto-approval if opted in).
- **BLOCKED_ON_EXTERNAL**: Halts pending non-human dependency.

**Human-initiated transitions** (§12.5):
- `OVERRIDE`: any active state → DECIDED (force-end with unilateral decision)
- `REOPEN`: DECIDED → IN_REVIEW (resume work; prior DECISION preserved as superseded)
- `DROP`: any active state → ABANDONED (force-end without resolution)

Each transition is a logged event in the file. Transitions are themselves audit-trailed.

---

## 7. Folder Structure · 🟢 Settled (v0.3)

```
/quorum
  problem-statement.md          # seed input, written by user; gates conductor start
  outcome-manifest.md           # what we'll have produced when done; gates COMPLETED state (§1.7)
  config.yaml                   # workspace-level config: routing overrides, caps, policies
  state.yaml                    # workspace state + metadata
  .gitignore                    # generated; ensures /runtime/ stays uncommitted
  /deliberations
    0001-outcome-manifest.md    # always the first deliberation: what done means
    0002-framework-structure.md
    0003-project-pack-model.md
  /artifacts                    # the manifest's required outputs as produced
    requirements.md
    ux-requirements.md
    /versions                   # superseded versions preserved (ARTIFACT_REVISION targets)
      requirements.v1.md
  /inbox
    @claude-opus.md             # routing notifications, not content
    @claude-sonnet.md
    @gemini-pro.md
    @human-rohan.md
  /decisions
    ADR-0001-core-vs-adapters.md
  /tasks
    TASK-0001-implement-adapter-interface.md
  /registers
    open-questions.md           # cross-deliberation open questions
    glossary.md                 # shared vocabulary
    participants.md             # handle registry — operational, read by conductor
    routing-defaults.yaml       # fitness ratings, refreshed from upstream
  /protocol
    PROTOCOL.md                 # the spec itself, versioned
    templates/
      deliberation.md
      adr.md
      task.md
      proposal-block.md
      critique-block.md
      synthesis-block.md
      ...
    manifest-templates/         # starter manifests for common project shapes (§1.7)
      saas-product.md
      research-direction.md
      architecture-decision.md
      coding-plan.md
      strategic-decision.md
  /prompts
    agent-standing-prompt.md    # base prompt all CLI agents receive
    overrides/
      @claude-opus.md           # per-handle customizations
      @gemini-pro.md
      @codex-gpt5.md
  /context                      # workspace context surface (§1.8); managed via UI
    index.md                    # human-readable map of all context sources, statuses
    context-manifest.yaml       # machine-readable; tracked sources, digest status, freshness
    /repos                      # codebase context — local repos
      backend/
        digest.md               # agent-produced summary
        meta.yaml               # source path, role, relevance, last-digested-at, digest-tokens
      client-frontend/
        digest.md
        meta.yaml
    /docs                       # uploaded files (PDFs, Markdown, Word, plain text)
      raw/
        product-spec-v3.pdf
        meeting-notes-customer-call.md
      digested/
        product-spec-v3.md      # agent-produced digest of the PDF
        # small docs may not have a digested form; meta.yaml says so
      meta.yaml                 # one entry per uploaded doc: source, type, digest status
    /web                        # URL-based context
      cached/
        acme-pricing-page.md    # fetched and converted to Markdown
        api-reference-stripe.md
      meta.yaml                 # one entry per URL: original URL, fetched-at, refresh policy
    /notes                      # free-text user notes — always-included, no digestion
      org-conventions.md
      feature-x-customer-context.md
      meta.yaml
  /conductor
    conduct.py                  # the orchestrator script
  /ui
    server.js / .py             # local web app serving the UI
    web/                        # frontend assets
  /runtime                      # ephemeral, gitignored, conductor-managed
    conductor.pid               # PID + lockfile when conductor is running
    ui.pid                      # PID + lockfile when UI server is running
    /active                     # marker files for currently-running agent invocations
      @claude-opus--0001--PROPOSAL.start
    /streams                    # live-streaming output buffers
      @claude-opus--0001--PROPOSAL.stream
      /failed                   # preserved stream buffers from failed invocations (diagnosis)
    /events
      events.jsonl              # append-only event log (UI activity feed source)
      /archive
        2026-04-26.jsonl        # daily-rotated old events
```

### Why dropped from initial sketch

- **`/agent-outboxes`** — duplicates content with deliberations. An agent's "outbox" is just their contributions inside deliberation files.
- **`/summaries`** — summaries are either ADRs (formal decisions) or syntheses (live inside deliberations). Separate folder duplicates one of those.

### What's added beyond initial sketch

- **`problem-statement.md`** — top-level seed input written by the user; gates conductor start (see §1.6). Has its own DRAFTING/READY status.
- **`outcome-manifest.md`** — top-level declaration of what artifacts the workspace must produce, with completion checks and quality gates; gates the workspace's COMPLETED state (see §1.7).
- **`/artifacts/`** — the manifest's required outputs as they're produced. Distinct from `/decisions/` (which are protocol byproducts) and `/tasks/` (which are derivative). Artifacts are *the intended outputs* of the workspace. Versioning preserved under `/artifacts/versions/`.
- **`config.yaml`** — workspace-level configuration: routing overrides, invocation caps, default decider, log verbosity, unavailability policy (§10.3), resume policy (§1.6), human-timeout policy (§10.4), workspace mode (§1.6). Single source of truth for tunables.
- **`state.yaml`** — workspace runtime state, pause reason, expected resume time, last activity timestamp, mode, manifest satisfaction status. See §7.5.
- **`.gitignore`** — generated by `quorum init`; ensures `/runtime/` and other ephemeral files don't pollute commits.
- **`/registers/`** — cross-deliberation state (open questions, glossary, participants, routing-defaults). Glossary is critical for multi-agent work to prevent vocabulary drift. `routing-defaults.yaml` is refreshed from upstream (see §3.6).
- **`/protocol/`** — the spec is itself a versioned artifact. Changes go through deliberation. This is what makes the system reusable across projects. Includes `manifest-templates/` for common project shapes (see §1.7).
- **`/prompts/`** — the standing prompts each agent receives. The leverage point of the whole system.
- **`/conductor/`** — the orchestrator. ~300 lines of Python (v0.3 estimate).
- **`/ui/`** — the local web UI (ships in v1, see §9). Reads files directly, writes moves through structured forms, displays live activity.
- **`/context/`** — workspace context surface (§1.8). Always present (created at init); populated via UI panels in Settings → Context. Four source types: repos (digested codebases), docs (uploaded files), web (cached URLs), notes (user-authored Markdown).
- **`/runtime/`** — ephemeral conductor state. Marker files signal when an agent invocation starts/ends; stream buffers hold live-streaming agent output; `events.jsonl` is the append-only source of truth for the activity feed; old events archive daily. Always gitignored — never committed.

---

## 7.5. Workspace State (`state.yaml`) · 🟢 Settled

`state.yaml` holds the workspace's runtime state — distinct from individual deliberation statuses, which live in their own files. This is read by the conductor on startup, written on every state transition, and consulted by the UI to render workspace-level indicators.

### Schema

```yaml
schema_version: 0.1
workspace_id: a7f3-...           # generated at quorum init
mode: interactive                 # interactive | autonomous (locked once workspace has activity)
state: ACTIVE                     # INITIALIZED | READY | ACTIVE | PAUSED | COMPLETED_AUTONOMOUS | ARCHIVED
state_changed_at: 2026-04-27T14:32:18Z
last_activity_at: 2026-04-27T14:35:42Z       # any activity (human or agent)
last_human_activity_at: 2026-04-27T13:18:09Z # used for presence inference (§10.4); null in autonomous mode
pending_deputy_count: 3                       # provisional decisions awaiting human review; always 0 in autonomous mode

# Manifest progress (§1.7):
manifest:
  status: LOCKED                             # DRAFTING | READY | LOCKED
  total_artifacts: 5
  artifacts_complete: 3
  artifacts_in_production: 1
  artifacts_pending: 1
  quality_gates_clear: false                 # true when all gates pass
  closing_ceremony_eligible: false           # true when all artifacts complete + gates clear
  final_deliberation_id: null                # set when ceremony begins

# When mode == autonomous and forked from another workspace:
forked_from: /path/to/source/quorum           # absolute path to the source workspace
forked_at: 2026-04-29T10:14:22Z
forked_with_mode_change: interactive_to_autonomous   # null if same mode

# When mode was converted mid-stream:
mode_history:
  - { mode: autonomous, from: 2026-04-27T10:00:00Z, to: 2026-04-29T15:30:00Z }
  - { mode: interactive, from: 2026-04-29T15:30:00Z, to: null }

# When state == PAUSED:
pause:
  reason: blocked_on_unavailable  # see §1.6 pause reasons table
  paused_at: 2026-04-27T14:32:18Z
  expected_resume_at: 2026-04-27T18:30:00Z   # null if unknown
  context: |
    @claude-opus quota window resets at 18:30. Synthesis on #0007
    is blocked under strict policy (see config.yaml).

# When state == COMPLETED_AUTONOMOUS:
autonomous_completion:
  completed_at: 2026-04-27T22:18:42Z
  total_invocations: 87
  deliberations_decided: 8
  deliberations_force_resolved: 0       # if max_invocations hit before all decided
  decider_used: "@claude-opus"          # which one from the panel did most decisions
  
# When state == ARCHIVED:
archive:
  archived_at: 2026-04-30T10:00:00Z
  archived_by: @human-rohan
  reason: completed                # completed | abandoned | other
```

### Why a separate file (not just events.jsonl)

`events.jsonl` is the append-only history. `state.yaml` is the current truth. They're complementary:

- *History* answers: "what happened, when, in what order?" → events.jsonl
- *State* answers: "where are we right now?" → state.yaml

Without state.yaml, every consumer (UI, `quorum status`, conductor restart) has to reconstruct current state by replaying events. With state.yaml, current state is one file read.

### Update discipline

The conductor is the only writer to state.yaml. Updates are atomic (write to temp, fsync, rename) so a crash during write doesn't corrupt the file. The UI is read-only on this file.

---

## 8. Artifact Templates · 🟢 Settled

### Deliberation file skeleton

```markdown
---
id: 0001
title: <one-line question>
status: DRAFT
protocol_version: 0.1
created: 2026-04-27
parent: null
children: []
roles:
  proposer: @claude-code
  critics: [@gemini-cli, @codex-cli]
  synthesizer: @claude-code
  decider: @human-rohan
tags: [architecture, foundational]
relevant_context:
  repos: []
  docs: []
  urls: []
  notes: all
---

## Question
<the precise question this deliberation answers>

## Context
<background, constraints, prior art, links to related deliberations>

## Contributions
<append-only list of moves; never edit a prior move>

## Open Questions
- [ ] Q1: ... (assigned: @gemini-cli)
- [x] Q2: ... (resolved by: ANSWER@codex-cli)

## Decision
<empty until designated decider issues a DECISION move>
```

### ADR template

ADRs (Architecture Decision Records) are spawned automatically by DECISION moves whose `Spawns ADR?` field is yes. Live in `/quorum/decisions/`.

```markdown
---
id: ADR-0001
title: <decision name>
status: confirmed | provisional   # provisional if from DEPUTY_DECISION pending review
protocol_version: 0.1
created: 2026-04-27
spawned_by: DECISION@human-rohan#0014
contributing_deliberations: [0014, 0007]
supersedes: null                  # ADR-XXXX if this overrides a prior decision
superseded_by: null               # set when later ADR overrides this
---

## Context
<the situation that called for a decision; copied/distilled from deliberation context>

## Decision
<what was decided, in plain language>

## Rationale
<reasoning grounded in the deliberation; cites specific moves>

## Consequences
<what becomes easier; what becomes harder; what risks were accepted>

## Alternatives considered
<list of paths-not-taken; from the deliberation's SYNTHESIS "Alternatives weighed" section>

## Cross-references
- Originating deliberation: #0014
- Related ADRs: ADR-0007 (depends on this), ADR-0011 (depended upon by this)
- Affected artifacts: requirements.md#pricing, ux-requirements.md#checkout-flow
```

ADR ID numbering is workspace-scoped, sequential, never reused. Superseded ADRs are kept; their `superseded_by` field points to the replacement, preserving the history.

### Task template

Tasks are spawned automatically when a DECISION move's `Spawns task?` field is yes, or when a manifest artifact's production needs concrete work tracked. Live in `/quorum/tasks/`.

```markdown
---
id: TASK-0001
title: <one-line action>
status: open | in_progress | blocked | done | abandoned
priority: high | medium | low
protocol_version: 0.1
created: 2026-04-27
spawned_by: DECISION@human-rohan#0014   # or null if user-created
assigned_to: <human or external system; not an agent handle>
depends_on: []                          # other TASK IDs
blocks: []                              # other TASK IDs that depend on this
---

## What
<the actual work to be done; specific enough that someone could execute it>

## Why
<the reason this task exists; cites the originating decision or deliberation>

## Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Notes
<anything else useful to whoever picks this up; e.g., references to relevant code, gotchas>
```

Tasks are intended for handoff to *execution* tooling (Cursor, Claude Code in IDE mode, the user's own implementation work) — not for agents within Quorum to execute. The `assigned_to` field is free-form text identifying who picks it up; agents don't self-assign or execute tasks in v1.

### Move templates

Each move type has its own template in `/protocol/templates/`. The required-section specs live in §5; the template files are concrete forms with the section headers pre-populated and brief inline instructions for what each section should contain. The validator uses these as the structural source of truth.

The full template files are produced as part of the v1 build (step 1 in §14). Their contents are fully specified by §5's required-sections lists; no further design needed.

---

## 9. Execution Layers · 🟢 Settled (v0.2)

The protocol is identical across all execution layers. This is the test of whether it's designed right. Layers below are *capabilities*, not strict version milestones — v1 ships a subset of all four.

### v1 ships with:
- **Manual transport** (for web-only agents like Claude.ai, ChatGPT web, Gemini web — paste-and-commit through the UI)
- **CLI transport** (for headless CLI agents like Claude Code, Gemini CLI, Codex CLI — invoked by the conductor)
- **The local UI** (document-first, see §9.5)

### v2 adds:
- **MCP server** exposing `list_pending_for(@handle)`, `read_deliberation(id)`, `append_move(deliberation_id, move)` to any MCP-compatible client. Mostly redundant with CLI transport if agents are CLI-native; matters most for IDE-bound agents (Cursor, Windsurf) and any future MCP-native models.

### Transport types

| Transport | Examples | How they participate |
|---|---|---|
| `cli` | Claude Code, Gemini CLI, Codex CLI, Aider | Conductor invokes the binary headlessly |
| `manual` | Claude.ai web, ChatGPT, Gemini web | Inbox queues for human; human pastes through the UI |
| `mcp` (v2) | MCP-compatible clients | Pull from an MCP server reading the same files |
| `ide` (v2) | Cursor, Windsurf | Agent mode in IDE, reads/writes via filesystem |

A single deliberation can mix transports. Claude Code (cli) does most of the work; you bring in ChatGPT (manual) for one move where GPT-5 is sharper; everyone reads the same files.

---

## 9.5. UI Layer · 🟢 Settled

### Posture: document-first, not chat-first

The UI is structured around the deliberation document — the actual artifact — with a live activity feed alongside. Contributions appear as **structured move cards**, not chat bubbles. This matters: the protocol is built on "the artifact is the unit of work, not the message," and a chat-first UI would quietly contradict that. Users would start thinking of contributions as messages, expect message-like behavior (edit, delete, react, thread), and the structured-move discipline would erode.

We commit to document-first deliberately. Chat affordances (live activity, presence, motion) are layered *on top of* a document interface, not replacing it.

### Three-pane layout

**Left pane — Deliberations list**
- Vertical list of all deliberations
- Per row: ID, title, status badge, participant avatars, attention indicator
- "BLOCKED_ON_HUMAN" deliberations surface to the top with a clear "your turn" marker
- This is home base

**Middle pane — The deliberation itself**
- Header: question, context, frontmatter (status, roles, decider)
- Body: contributions stream chronologically as **structured move cards** (not chat bubbles)
  - Each card: move type, author, timestamp prominently visible
  - Sections within the move (Position, Reasoning, Risks, etc.) shown as labeled blocks
  - Cards stack vertically — chat-like cadence, document-like structure
- Footer: when it's the human's turn, a structured response form appears here (see §9.7)
- Top of pane: a horizontal **deliberation timeline** showing the move chain: `PROPOSAL@claude → CRITIQUE@gemini → ANSWER@human → SYNTHESIS@claude` — clickable nodes jump to that move

**Right pane — Activity & participants**
- *Live activity feed* (top half): real-time log of cross-deliberation events. Token counts and durations visible per completed move. "Your turn" entries visually distinct (colored bar + Respond button). Click any line to jump to the deliberation
- *Participants panel* (bottom half): agent avatars with current status (idle / working on #N / rate-limited until X)

### Tech stack (v1 — minimalist)

- **Local web app**, served by a small Node/Python script. Run `quorum serve`, open `localhost:3000`.
- **No database, no auth, no server.** Reads `/quorum/` directly from disk.
- **File-watcher** (chokidar or equivalent) on `/deliberations/`, `/runtime/active/`, `/runtime/streams/`, `/runtime/events/events.jsonl`, and `/inbox/`.
- **WebSocket push** from the file-watcher to the browser. New move appears, status changes, activity feed updates — all driven by file events.
- **Composing a move = appending to a file.** When the human submits a response form, the UI appends a properly-formatted move block to the deliberation file and updates the relevant inbox. No backend logic.
- **Suggested stack:** Next.js or SvelteKit + chokidar + a Markdown parser + Tailwind. ~1500 lines for v1.

### The decoupling rule

The conductor and the UI are **separate processes that share the file system**. They don't talk to each other directly. Both observe and modify `/quorum/`. Run conductor without UI (headless), or UI without conductor (manual mode) — both work. **The UI does nothing the file system can't already do** — it just makes the workspace pleasant to look at and easier to interact with. If the UI breaks, the workspace is still fully functional via plain file editing.

---

## 9.6. Live Collaboration Affordances · 🟢 Settled

### Floor: instant "started" awareness (always works)

The moment the conductor invokes any agent, it touches a marker file:

```
/quorum/runtime/active/@claude-code--0001--PROPOSAL.start
```

The UI's file-watcher picks this up within ~100ms. The relevant move card immediately appears in the `composing` state — "@claude-code is composing a PROPOSAL." This requires nothing from the agent. **Latency from invocation to visible activity: under one second.** This is your "see when an agent started something as soon as it starts" requirement, and it's effectively free.

### Ceiling: true streaming where the CLI cooperates

Whether token-by-token streaming works depends on how each CLI exposes its output:
- Some CLIs stream stdout token-by-token as they generate (Claude Code, when invoked appropriately)
- Others buffer until the full response is ready (some headless modes)

The conductor pipes agent stdout to a stream buffer file:

```
/quorum/runtime/streams/@claude-code--0001--PROPOSAL.stream
```

The UI tails this file and displays partial output in the move card as it grows. **Where CLIs stream tokens, you see token streaming. Where they buffer, you see chunks arriving.** The user experience degrades gracefully — same UI behavior either way, only the granularity differs.

### Conductor lifecycle responsibilities

For every agent invocation, the conductor must:

1. **At start:** touch `/runtime/active/<agent>--<deliberation>--<movetype>.start`
2. **At start:** append to `events.jsonl`: `{"type": "agent_started", "agent": "@claude-code", "deliberation": "0001", "move_type": "PROPOSAL", "ts": "..."}`
3. **During:** pipe agent stdout to `/runtime/streams/<...>.stream`
4. **On clean exit:** parse the final output, append the formatted move block to the deliberation file, append `{"type": "agent_completed", ..., "tokens": N, "duration_ms": M}` to events.jsonl, remove the active marker and stream buffer
5. **On failure:** append `{"type": "agent_failed", ..., "error": "..."}` to events.jsonl, remove the active marker, leave the partial stream buffer for diagnosis (or move to `/runtime/streams/failed/`)

### Three states of a move card

| State | Trigger | UI shows |
|---|---|---|
| `composing` | active marker exists, stream growing | Header with author/type, body streams content, "composing..." indicator |
| `complete` | active marker gone, deliberation file updated | Structured card with labeled sections |
| `failed` | active marker gone, no move written, failure event in log | Error card with diagnostic, "Retry" button |

### The composing-to-complete transition

There's a moment where the UI is showing raw streaming text that needs to switch to showing structured sections. The transition should be **smooth, not abrupt**: section labels fade in over the streamed text as the conductor identifies them, rather than the card re-rendering all at once. This is the visual cue that "raw thinking just became a structured artifact" — the protocol shaping the output, made visible.

If true streaming isn't possible for a given CLI, the card shows a typing animation or section-by-section reveal until the move is complete, then the structured card snaps in.

### The activity feed

```
2:14:03  @claude-code started PROPOSAL on #0001
2:14:47  @claude-code completed PROPOSAL on #0001 (847 tokens, 44s)
2:14:48  @gemini-cli queued for CRITIQUE on #0001
2:14:51  @gemini-cli started CRITIQUE on #0001
2:15:22  @gemini-cli completed CRITIQUE on #0001 (612 tokens, 31s)
2:15:23  #0001 status changed: IN_REVIEW → SYNTHESIS
2:15:24  @human-rohan queued for DECISION on #0001  ← your turn
```

Sourced from `events.jsonl`. Every line clickable. "Your turn" entries visually distinct — even when looking at a different deliberation, peripheral vision catches the new colored line on the right.

---

## 9.7. Human Response Interface · 🟢 Settled

### Not a chat input box. A structured form.

When it's the human's turn, the response interface is a **structured form matching the expected move type**. If the system is asking a QUESTION, the form is an ANSWER with required fields. If issuing a DECISION, the form has Decision / Rationale / "Spawns ADR?" fields.

This is a feature, not friction. It does three things:

1. **Forces structured contribution.** No "yeah looks good" decisions. The form makes you articulate the decision and rationale.
2. **Keeps human moves first-class.** Your moves are ordinary protocol artifacts — no special-casing for human input.
3. **Makes responses faster.** Fields with placeholders ("State the decision in one sentence...") are easier to fill than a blank text box where you have to remember the structure.

### Form design pattern

Every response form has:
- **A header** identifying the move type being composed and what triggered it ("@gemini-cli asked you to clarify the requirement scope in #0001")
- **Required fields** matching the move type's template sections
- **Placeholders** showing what each field expects
- **An optional "Notes / additional context" field** at the bottom for free-form prose
- **A submit button** that writes the structured move to the deliberation file

### Where the form appears

- **Bottom of the middle pane**, when the currently-viewed deliberation is awaiting human input
- **In the activity feed**, "your turn" entries have a Respond button that scrolls to the form
- **In the deliberations list**, the deliberation badge shows "your turn" — clicking it opens the deliberation with the form ready

### Out of scope for v1

- Move editing after submission (REVISIONs supersede; never edit)
- Drafts (nice-to-have, not essential)
- Rich-text formatting (plain Markdown only)
- Inline suggestions / autocomplete (later)

---

## 9.8. Settings & Configuration UX · 🟢 Settled

By v0.9 the workspace has accumulated 30+ configurable settings spread across `config.yaml`, `participants.md`, `routing-defaults.yaml`, and per-deliberation frontmatter. Asking users to edit YAML for each is hostile. But naively building a "settings UI with everything in it" is worse — it produces a Photoshop-preferences nightmare that overwhelms users and invites unhelpful fiddling.

The right design isn't "show all settings nicely." It's: aggressively hide what should never be seen, group around user intent (not config-file structure), provide presets for common cases, reveal complexity progressively.

### Three-tier settings model

**Tier 1 — Workspace setup wizard** (visible to all, completed before first `start`)

A short, opinionated flow during initial workspace setup. Six questions, drives ~80% of useful configuration via sensible defaults:

1. **What kind of work is this?** *(Drives manifest template selection.)*
   - Build a product
   - Make a decision
   - Synthesize research
   - Brainstorm freely
   - Other / Custom

2. **How involved do you want to be?** *(Drives mode + human-timeout posture.)*
   - Tightly involved (review every key decision) — interactive, no human-timeout
   - Available but flexible (let agents handle small things) — interactive + tactical-and-below auto-decide opt-in
   - Hands off (let agents drive entirely) — autonomous mode

3. **If your top-choice model is unavailable, what should happen?** *(Drives substitution policy.)*
   - Wait until it's back (don't substitute) — `strict`
   - Substitute with similar quality — `substitute_with_floor`
   - Substitute with anything available — `substitute_aggressively`

   This question uses **behavioral framing** rather than abstract values ("quality vs speed") — it's more concrete, matches the actual mechanism, and produces more accurate answers because users reason about scenarios more reliably than about preferences.

4. **Which agents do you want to use?** *(Drives participant registration.)*
   Checkbox list of detected CLIs with model variants. All variants of each CLI checked by default; user can deselect.
   
   **If detection fails** (Claude Code installed but not on PATH, or under unexpected name like `claude-work`): wizard offers a "manually add agent" option for each known CLI type, with a text field for binary name. User enters `claude-work`, wizard runs doctor probe to verify. Same flow as multi-installation registration in §1.6.

5. **Set a cost ceiling for this workspace?** *(Drives `permissions` and cost-discipline behavior.)*
   - $25 (small experiments)
   - **$50** (default — substantial single-feature brainstorm)
   - $200 (large multi-repo work)
   - No ceiling (advanced — explicit opt-out)
   
   Defaults to $50 with the ceiling enabled. The user can raise or disable later in Settings.

6. **Anything you want to specify upfront?** *(Optional, free-text.)*
   Feeds into problem statement context, not configuration.

That's it. Six questions fill ~25 of 30+ knobs with sensible defaults. Most users complete this once and never return to it.

**Tier 2 — Workspace settings panels** (sidebar, organized by user intent)

For users who want to see and adjust settings without touching YAML. Organized into intent-based panels, each showing 4–6 visible settings:

| Panel | Covers |
|---|---|
| **Participants** | Registered handles, quotas, health, permission capability, add/remove agents |
| **Context** | Repos / Documents / Web / Notes — the four context sources (§1.8). Add, edit, refresh, remove. Digest status and freshness indicators per item. |
| **Permissions** | Allowlist patterns, denylist patterns, stakes-based auto-approval policy, recent permission decisions log (§10.6) |
| **How decisions get made** | Decider, decider panel (autonomous), deputy deciders |
| **When agents are unavailable** | Substitution policy, retry behavior, notify-on-substitute |
| **When the human is unavailable** | Human-timeout policy per stakes, presence grace, deputy_deciders ordering |
| **Workspace lifecycle** | Pause/resume policy, auto-resume window |
| **Manifest** | Current artifacts and their completion status (lives in §1.7's manifest UI) |

Each panel shows current values, lets you edit them, displays which are frozen vs editable.

**Panels adapt to context.** Autonomous-mode workspaces hide the "When the human is unavailable" panel entirely (no human to be unavailable). Interactive-mode workspaces hide the autonomous-specific configuration. The UI shows what's relevant.

**Tier 3 — Raw YAML editor** (one click away, escape hatch)

For everything else — operational tunables not surfaced in panels (`presence_grace_minutes`, `max_consecutive_deputies`, etc.), per-deliberation overrides, anything that genuinely needs YAML expressivity.

A single "Edit raw config" button opens the YAML files in a browser-based editor with:
- Schema-aware syntax highlighting
- Inline validation against the documented schema
- Hover tooltips with field documentation
- "Reset to defaults" per section
- Diff view before save

Power users live here when they need to. Most users never see it.

### The editability rules — what can change when

Settings fall into three categories with different rules about when they can be modified:

**Category A — Frozen at first start (immutable after).**

These define the workspace's identity. Changing them mid-stream produces semantic chaos. The UI shows them with a 🔒 indicator and a tooltip: *"Locked when the workspace started. To change, fork the workspace."*

- Workspace mode (interactive / autonomous)
- Manifest template choice (the manifest itself can evolve via MANIFEST_REVISION; the *template it was based on* is historical)
- Workspace ID
- `--with-codebase` flag and the `/context/` directory
- Initial routing-defaults version

**Category B — Live-editable, takes effect immediately, no in-flight work disturbed.**

The vast majority of operational settings. A change applies to the next event of that kind:
- Substitution policy → next unavailability event
- Human-timeout settings → next QUESTION
- Pause/resume policy
- Notify toggles
- Per-handle quotas
- Log verbosity
- Retry config

**Category C — Live-editable, takes effect immediately, but visible effects on in-flight work.**

These can change but produce observable effects on work that's already underway. The UI shows a "this change affects future work; existing decisions stand under their original config" indicator. A confirmation dialog is shown for destructive-leaning changes (e.g., removing a handle that's currently routed):
- Decider / decider panel — next DECISION uses the new decider; prior DECISIONs remain valid
- Routing overrides — applies to next routing decision
- Adding/removing participants — additions are clean; removals affect future routing only

For Category C settings, the UI's posture is: **make the editability rule visible, don't hide it.** Each setting's row has a small icon (live / live-with-effects / frozen) so users always know what they're changing.

### Settings vs lifecycle operations

A subtle but important distinction the UI must enforce: **settings are tunables; lifecycle operations are commands.**

Things that look like they could be settings but are actually lifecycle operations (and remain CLI commands, even if the UI offers buttons that shell out to them):

- **`quorum fork`** — creates a new workspace; filesystem implications
- **`quorum archive`** — destructive; deletes /runtime/, marks read-only
- **`quorum refresh-defaults`** — network operation; updates routing-defaults
- **`quorum doctor`** — diagnostic; runs health checks

The UI can offer buttons that invoke these commands underneath, but they remain commands. This prevents users from accidentally archiving a workspace by toggling a checkbox in settings.

The distinction in plain language: settings change *how the workspace behaves*; lifecycle operations change *what the workspace is or where it lives*.

### What this means for the YAML files

The YAML files (`config.yaml`, `participants.md`, etc.) remain the source of truth. The UI is a structured editor for them. When the UI saves a change, it:

1. Validates the change against schema.
2. Writes the YAML atomically (temp file → fsync → rename).
3. Logs the change to events.jsonl as a `setting_changed` event.
4. If the conductor is running and the setting is live-editable, signals the conductor to reload (file-watcher catches the change).

The user can still edit YAML directly with their text editor — the file-watcher catches that too. UI and CLI/file-editing remain interchangeable. The UI is convenient, not exclusive.

### What ships in v1

All three tiers ship in v1. They're not advanced features — they're the *interface through which v1 becomes usable*. Without them, every user must learn the YAML schema, which kills adoption.

- **Wizard:** part of the `quorum init` flow, runs in the UI immediately after init.
- **Settings panels:** sidebar in the UI shell.
- **Raw YAML editor:** "Edit raw config" button in settings, opens browser-based editor.

Build cost: ~3 additional days on top of the v1 UI shell estimate (forms for ~15 panel settings, schema-validated YAML editor, wizard flow). Worth it — adoption depends on this.

### What's deferred

- **Settings search/filter** — useful when there are 50+ settings, premature at 30
- **Setting presets beyond the wizard's five-question output** — e.g., "load the 'rapid prototyping' preset" as one click. v2.
- **Per-deliberation settings UI** — for now, per-deliberation overrides require Tier 3 (raw YAML). The UI for this is complex (needs to surface in deliberation view, not workspace settings) and rarely used.
- **Settings change history view** — a timeline of "what changed when, by whom" derived from `setting_changed` events. Nice-to-have, v2.

---

## 10. The Conductor (Autonomous Loop) · 🟢 Settled (v0.2)

### What it is

A Python script (~300 lines for v1, up from initial ~200 estimate). **Zero intelligence.** A file-watcher, router, and dispatcher. The intelligence lives in the agents and the protocol.

### Commands

| Command | Behavior |
|---------|----------|
| `quorum init [--autonomous]` | Scaffold workspace (including empty `/context/` source-type subdirectories), fetch latest routing-defaults, start UI; workspace state → INITIALIZED. Context sources (repos, docs, URLs, notes) added via UI. |
| `quorum refresh-defaults` | Re-fetch routing-defaults.yaml from upstream |
| `quorum doctor` | Health-check all registered handles |
| `quorum start` (alias: `quorum resume`) | Transition workspace to ACTIVE from any non-ACTIVE state. Daemonizes conductor by default. From INITIALIZED: runs bootstrapper. From PAUSED: shows resume briefing. Refuses if already ACTIVE. |
| `quorum start --foreground` | Same as `start` but conductor stays attached to terminal (for debugging); closing terminal kills it |
| `quorum step` | Runs the next pending invocation (single-step debug mode) |
| `quorum run` | Foreground equivalent of `start` — loops until a stop condition is hit, attached to terminal |
| `quorum pause [--keep-ui] [--full]` | Stops the conductor cleanly; workspace → PAUSED. Default keeps UI running; `--full` stops UI too |
| `quorum status` | Prints workspace state, conductor/UI status, registered handles, deliberation statuses, pending human inbox items. Auto-detects crashes and recovers. |
| `quorum validate` | Runs move-format linter across the workspace |
| `quorum serve` | Starts the local UI web app (daemonized; separate process from conductor) |
| `quorum archive` | Workspace → ARCHIVED; stops conductor and UI, deletes `/runtime/`, marks read-only |
| `quorum unarchive` | Reverses archive; workspace → INITIALIZED |
| `quorum fork <path> [--autonomous] [--decider-panel ...]` | Create a new workspace seeded from this one's problem statement (and participants/routing-defaults). Fresh deliberations, decisions, tasks. Provenance tracked in new workspace's state.yaml. Useful for comparative experiments and interactive→autonomous escape hatch. |

### Loop algorithm (v0.2 — parallel)

```
while not stop_condition():
    pending = scan_inboxes()                      # all pending items across all inboxes
    if not pending: break
    
    independent_batch = group_independent(pending)  # items that can run in parallel
                                                    # (different deliberations, OR same delib
                                                    #  but only one append per delib at a time)
    
    invocations = []
    for item in independent_batch:
        handle = route(item.role, item.deliberation)  # see §3.6 routing layers
        if handle is None:
            mark_blocked(item, reason="no_available_handle")
            continue
        if handle.transport == 'manual':
            queue_for_human(handle, item)
            continue
        invocations.append((handle, item))
    
    # Spawn all invocations in parallel; each acquires its deliberation lock at append time
    parallel_run(invocations)
    
    validate_new_moves()
    if any_deliberation_blocked_on_human(): break
```

### Per-deliberation locking

Two parallel agents trying to append to the *same* deliberation file is the only real contention case. We handle it with file-level advisory locks:

- Before appending a move, the conductor acquires a lock on the deliberation file (`fcntl.flock` on Linux/Mac, `portalocker` cross-platform).
- Lock is held only during the append (typically <100ms — the agent generation is already complete by this point).
- Other agents waiting to append the same file queue briefly. Imperceptible.

Agents writing to *different* deliberations don't contend. Most parallel work is across-deliberation, so this is rare in practice.

### Stop conditions

- All open deliberations reach `DECIDED` or `ARCHIVED`.
- Any deliberation hits `BLOCKED_ON_HUMAN`.
- Per-deliberation invocation cap reached (default: 20).
- Per-handle daily cap reached (configurable in `participants.md`).
- No-progress detector triggers (no new moves for N steps).

### Invocation model (per single agent invocation)

For each invocation, the conductor:

1. **Resolve handle** — apply routing (§3.6) to pick the handle for this role on this deliberation.
2. **Render prompt** — standing prompt + per-handle override + task framing.
3. **Touch lifecycle marker** — `/runtime/active/<handle>--<deliberation>--<movetype>.start` (UI sees within ~100ms).
4. **Append routing-decision event** — `{"type": "routing_decision", "handle": "@claude-opus", "role": "synthesizer", "layer": "defaults", "fitness": 3, "alternatives": [...]}` to `events.jsonl`.
5. **Append `agent_started` event** — with handle, deliberation, move_type, ts.
6. **Emit progressive status updates** during startup (Solution 3 — latency hiding):
   - "Initializing handle…" → "Reading workspace…" → "Composing <MOVE_TYPE>…"
   - These come from timing markers we add around CLI lifecycle, plus any meaningful stderr lines from the CLI itself.
   - UI shows these in the move card's composing-state header, so the user perceives the system as actively working even during the 2–4s cold start.
7. **Spawn CLI process** with prompt, piping stdout to `/runtime/streams/<...>.stream`.
8. **Wait for completion.**
9. **Acquire deliberation file lock.**
10. **Run validator** on the agent's output.
11. **Append the move** to the deliberation file.
12. **Update tagged inboxes** based on tags in the new move.
13. **Release lock.**
14. **On clean exit:** append `agent_completed` event with token count and duration; remove active marker and stream buffer.
15. **On failure:** append `agent_failed` event with error; remove active marker; preserve stream buffer in `/runtime/streams/failed/` for diagnosis.

### Lifecycle markers (the UI contract)

Steps 3–6 and 14–15 constitute the conductor's contract with the UI. The UI watches `/runtime/` and renders state based on what it sees there. If the conductor crashes mid-invocation, a startup recovery routine cleans stale markers (configurable threshold, default 15 minutes since marker creation — chosen to accommodate 99th-percentile invocation times on large contexts; 5 minutes was too tight for legitimate long-running invocations).

### Routing fallback

If routing returns no handle (all options exhausted/unhealthy), the deliberation transitions to a new sub-state `BLOCKED_ON_ROUTING` and surfaces to the user with the explanation: "No handle available for role <X>. Available: <list with reasons>. Add capacity, raise quotas, or override routing." This is rare but explicit when it happens.

---

## 10.3. Agent Unavailability & Substitution Policy · 🟢 Settled

Long-running brainstorming sessions hit unavailability often — Opus quotas exhaust, services have outages, networks drop. The system needs explicit policy for what to do when a routed handle can't fulfill its task.

### Error classification

The conductor's error classifier maps raw CLI/network errors to categories. Different categories warrant different responses:

| Category | Detection signal | Typical recovery | Default response |
|---|---|---|---|
| `quota_window_exhausted` | Rate-limit error with retry-after hint | Hours (window-based) | Apply substitution policy |
| `daily_cap_hit` | Daily-limit error from CLI | Until next day | Apply substitution policy |
| `subscription_issue` | Auth error, account suspended | User action required | Notify user, block |
| `service_outage` | 5xx errors, timeouts from upstream | Minutes to hours | Retry with backoff (3x), then policy |
| `network_failure` | Connection error, DNS failure | Minutes | Retry with backoff (3x), then policy |
| `cli_hang` | Process timeout exceeded | Immediate | Kill, mark failed, apply policy |
| `cli_bug` | Non-zero exit with parse error | Indeterminate | Log, mark failed, retry once, then policy |

The classifier is a small set of regex/exit-code patterns per CLI. Adding a new CLI means adding its error-pattern mapping.

### The three policy positions

Users (or workspace defaults) declare how unavailability should be handled. Three positions:

**`strict` — preserve exact handle (default).**
> "If the specific handle I requested is unavailable, do not substitute. Pause and notify me. I chose this handle for reasons that matter to this work."

This is Quorum's **default**. The argument: users pay for premium subscriptions specifically for premium output; silent downgrade undermines the value proposition. The user explicitly opted into this tool to compound paid AI quality, not to fall back to whatever's available.

**`substitute_with_floor` — substitute only above a fitness threshold.**
> "Substitute only with handles whose fitness for this role is at least N. If nothing meets the floor, pause and notify me."

For users who want continuity but not at any cost. Fitness floor is a quality guardrail.

**`substitute_aggressively` — keep moving at any cost.**
> "Use whatever's available, even if fitness is low. I'd rather have continuity than perfection."

For exploratory or low-stakes work where momentum beats precision.

### Configuration schema

`config.yaml`:

```yaml
unavailability_policy:
  default: strict                  # global default — strict is the safe choice
  fitness_floor: 2                 # used when policy is substitute_with_floor
  notify_on_substitute: true       # always tell the user when substitution happens
  pause_workspace_on_block: true   # if blocked, transition workspace to PAUSED
  retry:
    transient_categories:          # which error categories to retry before applying policy
      - service_outage
      - network_failure
    max_attempts: 3
    backoff_seconds: [5, 30, 120]  # exponential-ish

  per_role_overrides:              # role-specific policy
    synthesizer: strict             # don't substitute on synthesis — it's high-stakes
    critic: substitute_with_floor   # critique is less sensitive
    proposer: substitute_with_floor

  per_handle_overrides:            # handle-specific policy
    "@claude-opus":
      synthesizer: strict           # specifically: never substitute Opus on synthesis
```

Resolution order: `per_handle_overrides` → `per_role_overrides` → `default`. Most specific wins.

### The substitution flow

When a handle's invocation fails, the conductor:

1. **Classifies the error.** Determines category and whether it's transient.
2. **Retries if transient.** For `service_outage` / `network_failure`, retry with backoff (max 3 attempts by default).
3. **Logs failure.** Appends `agent_unavailable` event with category, handle, deliberation, role.
4. **Resolves policy.** Walks `per_handle_overrides` → `per_role_overrides` → `default`.
5. **If policy = strict OR no qualifying substitute exists:**
   - Deliberation transitions to sub-state `BLOCKED_ON_UNAVAILABLE`.
   - If `pause_workspace_on_block: true`: workspace transitions to `PAUSED`, with `state.yaml.pause.reason = blocked_on_unavailable`.
   - User is notified with: handle, role, deliberation, error category, expected recovery time (parsed from retry-after if available), and one-click options.
6. **If policy permits substitution:**
   - Routing logic finds the next-best handle meeting the fitness floor.
   - Invokes the substitute.
   - The substitute's move includes a frontmatter marker in its move block:
     ```
     ### [SYNTHESIS] @claude-sonnet · 2026-04-27T16:42 → reconciles ...
     **Substituting for:** @claude-opus (quota_window_exhausted)
     ...
     ```
   - This preserves provenance: anyone reading the deliberation later sees that this synthesis was originally meant for Opus. The audit trail is honest about who actually did what.
   - Logs `substitution_applied` event with details.
   - If `notify_on_substitute: true`: surfaces a notification in the activity feed.

### User notification on block

When a deliberation hits `BLOCKED_ON_UNAVAILABLE`, the UI shows:

```
@claude-opus is unavailable for #0007 (synthesizer).
  Reason: quota_window_exhausted
  Estimated recovery: 4 hours, 12 minutes (at 18:30)
  Policy: strict (no substitution)

What you can do:
  → Wait for recovery (default — workspace will stay paused)
  → Switch to substitute (one-time override for this move)
  → Change policy to allow substitution (workspace-wide)
  → Pause and come back later (no auto-resume)
```

Default is "wait" — explicit user action required to substitute. This matches the strict-by-default posture: silent fallback never happens.

### Recovery awareness

For categories with parseable recovery times (`quota_window_exhausted` with retry-after, `daily_cap_hit` with reset time):

- The expected recovery time is stored in `state.yaml.pause.expected_resume_at`.
- The UI shows a countdown.
- If `resume_policy.mode != manual` (see §1.6), the conductor schedules an auto-resume at that time within the configured window.
- For `manual` resume policy: the UI just shows "Opus comes back at 18:30 — run `quorum resume` then to continue."

For unknown recovery times (`subscription_issue`, indefinite outages):

- `expected_resume_at: null`
- UI shows "no estimated recovery — investigate when ready."
- User runs `quorum doctor` to re-check, or manually intervenes.

### Quota awareness as a routing input

A subtle but important extension: the conductor tracks **remaining quota per handle in real time** (counting invocations against the quotas in `participants.md`). Routing logic considers remaining quota as a soft factor:

- If `@claude-opus` has 3 invocations left in its window, the router prefers reserving them for high-fitness-required moves (synthesis on critical deliberations) rather than spending on routine critiques.
- When two handles are equally fitness-rated for a role, the router picks the one with more remaining budget (preserves flexibility for later).
- If a handle is at >90% of quota, the router *prefers* substitutes when fitness allows — not because the handle is unavailable yet, but to avoid hitting the wall.

This makes Quorum **budget-aware**, which is the point — maximizing the value of paid subscriptions across a long session is the core promise.

### Mid-flight invocation failures

Special case: an agent was invoked, started generating (stream buffer growing), then died partway through.

- The partial output in `/runtime/streams/<handle>--<delib>--<move>.stream` is preserved.
- Move is logged as `agent_failed` (not `agent_completed`) — no broken move appended to the deliberation.
- The deliberation's state is unchanged; the failed invocation is as if it didn't happen.
- Substitution policy applies as normal.
- The user can inspect the partial output if curious — UI offers a "view partial output" link on the failure event in the activity feed.

This is important: never let a half-generated move into the deliberation. Either a move completes cleanly and validates, or it doesn't exist.

---

## 10.4. Human-Unavailability Policy · 🟢 Settled

The symmetric problem to §10.3: when an agent issues a question for `@human-rohan` and the human is not around, the deliberation stalls. For long sessions, this can mean hours or days of unnecessary waiting on questions that have obvious answers.

But automating the human gate is fundamentally different from substituting one agent for another, and we design accordingly.

### The asymmetry that shapes this design

Agent substitution is replacing one stateless reasoner with another. Both produce contributions of the same kind; quality may differ but role is preserved.

Human substitution would mean replacing the source of authority on what the project should do with an agent guessing what the human would want. The human plays three distinct roles in a deliberation:

1. **Decider** — the source of authority; an agent isn't a lower-fidelity human, it's a categorically different thing.
2. **Requirements clarifier** — answers about what the user wants; agents would be guessing.
3. **Domain expert / context source** — provides information only the human has; agents literally can't substitute here.

The design refuses to flatten these. Automation produces **drafts marked as drafts**, never finals. The human's role as final arbiter is preserved even when they weren't physically present at the moment.

### The four-stakes classification

Every QUESTION move includes a required `Stakes` field (§5):

| Stakes | Examples | Default policy |
|---|---|---|
| `trivial` | Formatting choice, tool selection where any answer works, naming conventions | Auto-decide after short timeout (if user opted in) |
| `tactical` | Implementation tradeoffs, scope micro-decisions, prioritization within an agreed direction | Notify only after medium timeout |
| `strategic` | Direction-setting calls, scope macro-decisions, anything that shapes the project trajectory | Notify only after long timeout |
| `irreversible` | Public commitments, anything that's hard to undo, externally-binding choices | Never auto-decide; escalate notification urgently |

**Irreversible never auto-decides regardless of policy.** This is a hard constraint baked into the policy engine. A user cannot configure auto-decide for irreversible questions, and validation refuses to accept such configs.

### Configuration schema

`config.yaml`:

```yaml
human_timeout:
  default_enabled: false               # opt-in entirely; defaults preserve current "wait forever" behavior

  # Per-stakes policy. Used only when default_enabled: true (or per-deliberation override).
  trivial:
    wait_minutes: 30
    on_timeout: auto_decide            # auto_decide | notify | escalate
  tactical:
    wait_minutes: 240                  # 4 hours
    on_timeout: notify
  strategic:
    wait_minutes: 2880                 # 48 hours
    on_timeout: notify
  irreversible:
    on_timeout: escalate               # forced; auto_decide is rejected by validator

deputy_deciders:                       # ordered list; first available + healthy + within-quota wins
  - "@claude-opus"
  - "@claude-sonnet"
  - "@gemini-pro"
```

**Validation rules** (enforced by `quorum validate` and on every config load):
- If any stakes level has `on_timeout: auto_decide` and `deputy_deciders` is empty → **config refused, error reported**. The system fails loudly rather than silently degrading. (User must either populate deputies or change the policy to `notify`.)
- If `irreversible.on_timeout: auto_decide` → config refused.
- `wait_minutes` must be positive.
- Deputy handles must exist in `participants.md`.

### The trigger flow

When a QUESTION move is issued tagged `@human-rohan`:

1. Conductor reads its `Stakes` field.
2. Marks deliberation `BLOCKED_ON_HUMAN` as today.
3. Logs `human_timeout_armed` event with stakes, wait_minutes, and projected trigger time.
4. Sets a timer.
5. **If human responds in time:** timer cancelled, normal flow.
6. **If timer fires:**
   - Look up policy for this stakes level.
   - If `on_timeout: notify` or `escalate`: log event, fire notification, do not act. (`escalate` is louder — push notification, multiple channels — but mechanically the same as notify in the protocol.)
   - If `on_timeout: auto_decide`: walk `deputy_deciders` list, find first available handle, invoke it to produce a `DEPUTY_DECISION` move.
7. The DEPUTY_DECISION move enters the deliberation with `status: provisional` and a `can_be_overridden_until` timestamp (default: 7 days).

### Deputy invocation prompt

When invoked for a deputy decision, the agent receives an augmented standing prompt:

> You are acting as a temporary deputy decider for `@human-rohan` because they have not responded within the configured timeout. Your decision is **provisional** — the human will review and either confirm, override, or hold it on their return.
>
> Read the deliberation in full, including the originating QUESTION's `Stakes` classification (which is `<trivial|tactical>`, never higher) and the agent's own "What I'd recommend if forced" suggestion. Read the workspace's `problem-statement.md` and any prior decisions in this workspace to understand intent.
>
> Produce a `DEPUTY_DECISION` move per the template. Be conservative — when uncertain, choose the option that is most reversible. State your confidence honestly. List specifically what you'd want the human to confirm.

### The provisional → confirmed lifecycle

When the human returns, every DEPUTY_DECISION sits in a "needs your review" queue with three actions:

| Action | What happens |
|---|---|
| **Confirm** | DEPUTY_DECISION's `status` becomes `confirmed`. A regular DECISION move is appended referencing the deputy decision (`confirms: DEPUTY_DECISION@<handle>#<delib>`). The audit trail honestly preserves the deputy origin. |
| **Override** | Human issues a normal DECISION move. The DEPUTY_DECISION's `status` becomes `overridden`. Downstream artifacts (ADRs, tasks) generated from the deputy decision are flagged for review. |
| **Hold** | Reviewer extends `can_be_overridden_until` by a configurable amount. Decision stays provisional longer. |

**If the override window expires without action:** `status` becomes `expired`. Provisional outputs become effectively confirmed by inaction — but the audit trail still shows they were never explicitly ratified. The UI surfaces expired-without-review counts prominently as a drift indicator.

### Cascading auto-decisions

When a DEPUTY_DECISION resolves a QUESTION, the deliberation may produce more questions that depend on its answer. These could also become eligible for auto-decision, producing chains like:

```
QUESTION#1 (trivial) → auto-decided → DEPUTY_DECISION#1
                                              ↓
QUESTION#2 (trivial, depends on #1) → auto-decided → DEPUTY_DECISION#2
                                              ↓
... etc
```

If you override DEPUTY_DECISION#1 on return, downstream deputies may need to cascade-revert. This gets messy.

**Mitigation:** the conductor enforces a `max_consecutive_deputies` limit per deliberation chain (default: 3). After the limit, further QUESTIONs in that chain transition to `notify` regardless of stakes. The user gets pulled back in before depth gets out of hand.

### Visible accumulation

A long-term failure mode of automation is the user gradually losing touch with their own project. The system resists this through **visible accumulation**:

- The UI sidebar shows a persistent count: "23 deputy decisions awaiting your review (oldest: 5 days)".
- The resume briefing (§1.6) lists deputy decisions in priority order: confidence-low first, then by stakes, then by age.
- If unreviewed deputy count exceeds a configurable threshold (default: 10), the workspace surfaces a warning in `quorum status` and the UI: *"You have many provisional decisions pending. Consider reviewing them or adjusting human_timeout policy."*

This isn't enforcement — the user can ignore it — but it makes drift visible.

### Presence inference

To detect whether the human is "around," the conductor uses a simple heuristic in v1:

- Track `last_human_activity_at` in `state.yaml` (updated when: human responds to a move, edits any file in `/quorum/`, opens the UI, runs any `quorum` command).
- If a QUESTION's stakes-level wait timer would fire less than `presence_grace_minutes` (default: 15) after last activity, defer the timer by `presence_grace_minutes`. (The user might still be around; don't auto-decide while they're actively working.)
- This is a soft signal, not a hard one — false-positive presence detection is fine; it just delays automation slightly.

OQ-34 captures the future-work question of richer presence detection (UI heartbeat, OS-level activity, etc.).

### Per-deliberation override

A deliberation's frontmatter can override workspace-level human-timeout policy:

```yaml
human_timeout:
  enabled: true                  # override workspace default
  trivial: { wait_minutes: 5, on_timeout: auto_decide }
  # other stakes inherit from workspace config
```

Useful for explicitly-low-stakes deliberations ("brainstorm a tweet thread") where the user wants aggressive automation, while keeping their main workspace conservative.

### What this design refuses to do

- **Never auto-decide on irreversible questions.** Hard constraint.
- **Never produce a move that masquerades as a human DECISION.** DEPUTY_DECISION is structurally distinct.
- **Never silently downgrade quality.** Every deputy decision is logged, marked, and surfaced for review.
- **Never let agents claim information they don't have.** The QUESTION's `Information you have that I don't` field makes context dependencies explicit; high-context questions should classify as strategic+ and not auto-decide.
- **Never accept a config that implies auto-decide without deputies designated.** Validation refuses.

---

## 10.5. Structured Logging for System Improvement · 🟢 Settled

The events log isn't just for the UI activity feed — it's the foundation for evolving the system over time. We design the schema now so future analysis is possible.

### Event types

Each line in `/runtime/events/events.jsonl` is a JSON object with at least `type`, `ts`, and `workspace_id`. Type-specific fields vary.

```jsonl
{"type": "workspace_initialized", "ts": "...", "workspace_id": "...", "init_flags": ["--with-codebase"]}
{"type": "handle_registered", "ts": "...", "handle": "@claude-opus", "model": "claude-opus-4-7"}
{"type": "problem_statement_marked_ready", "ts": "...", "char_count": 1842}
{"type": "session_started", "ts": "...", "bootstrapper_handle": "@claude-opus"}
{"type": "deliberation_created", "ts": "...", "deliberation_id": "0001", "created_by": "@claude-opus", "title": "..."}
{"type": "routing_decision", "ts": "...", "deliberation_id": "0001", "role": "synthesizer", "selected_handle": "@claude-opus", "selected_fitness": 3, "layer": "defaults", "alternatives": [{"handle": "@claude-sonnet", "fitness": 2, "reason_skipped": "lower_fitness"}]}
{"type": "agent_started", "ts": "...", "deliberation_id": "0001", "handle": "@claude-opus", "move_type": "SYNTHESIS"}
{"type": "agent_completed", "ts": "...", "deliberation_id": "0001", "handle": "@claude-opus", "move_type": "SYNTHESIS", "tokens_in": 4200, "tokens_out": 870, "duration_ms": 38400, "cold_start_ms": 2900}
{"type": "agent_failed", "ts": "...", "deliberation_id": "0001", "handle": "@claude-opus", "error_class": "rate_limit", "error_msg": "..."}
{"type": "agent_unavailable", "ts": "...", "handle": "@claude-opus", "deliberation_id": "0001", "role": "synthesizer", "category": "quota_window_exhausted", "expected_recovery_at": "2026-04-27T18:30:00Z"}
{"type": "substitution_applied", "ts": "...", "deliberation_id": "0001", "role": "synthesizer", "original_handle": "@claude-opus", "substitute_handle": "@claude-sonnet", "substitute_fitness": 2, "policy": "substitute_with_floor", "user_notified": true}
{"type": "blocked_on_unavailable", "ts": "...", "deliberation_id": "0001", "role": "synthesizer", "handle": "@claude-opus", "policy": "strict", "expected_recovery_at": "2026-04-27T18:30:00Z"}
{"type": "move_appended", "ts": "...", "deliberation_id": "0001", "move_type": "SYNTHESIS", "author": "@claude-opus", "validator_passed": true, "section_count": 4, "substituting_for": null}
{"type": "move_outcome", "ts": "...", "deliberation_id": "0001", "move_ref": "SYNTHESIS@claude-opus#0001", "outcome": "accepted|revised|abstained_and_superseded|ignored", "outcome_inferred_from": "human_decision|next_move|deliberation_archived"}
{"type": "deliberation_status_changed", "ts": "...", "deliberation_id": "0001", "from": "IN_REVIEW", "to": "SYNTHESIS"}
{"type": "human_response", "ts": "...", "deliberation_id": "0001", "move_type": "ANSWER", "response_time_ms": 184000}
{"type": "deliberation_decided", "ts": "...", "deliberation_id": "0001", "decider": "@human-rohan", "spawned_adr": "ADR-0001", "spawned_tasks": []}
{"type": "routing_defaults_refreshed", "ts": "...", "old_version": "0.1.3", "new_version": "0.1.4", "fitness_changes": [...]}
{"type": "workspace_paused", "ts": "...", "reason": "blocked_on_unavailable", "expected_resume_at": "2026-04-27T18:30:00Z", "pause_initiated_by": "conductor"}
{"type": "workspace_resumed", "ts": "...", "resumed_by": "user|auto", "paused_duration_ms": 14820000}
{"type": "auto_retry_scheduled", "ts": "...", "deliberation_id": "0001", "handle": "@claude-opus", "scheduled_for": "2026-04-27T18:30:00Z"}
{"type": "quota_threshold_crossed", "ts": "...", "handle": "@claude-opus", "threshold": "90_percent", "remaining": 3, "window_resets_at": "2026-04-27T18:30:00Z"}
{"type": "human_timeout_armed", "ts": "...", "deliberation_id": "0007", "question_ref": "QUESTION@gemini-pro#0007", "stakes": "tactical", "wait_minutes": 240, "trigger_at": "2026-04-27T22:30:00Z"}
{"type": "human_timeout_deferred", "ts": "...", "deliberation_id": "0007", "reason": "recent_human_activity", "new_trigger_at": "2026-04-27T22:45:00Z"}
{"type": "human_timeout_triggered", "ts": "...", "deliberation_id": "0007", "stakes": "tactical", "policy": "notify"}
{"type": "deputy_decision_issued", "ts": "...", "deliberation_id": "0007", "deputy_handle": "@claude-opus", "stakes": "trivial", "confidence": "high", "can_be_overridden_until": "2026-05-04T22:30:00Z"}
{"type": "deputy_decision_confirmed", "ts": "...", "move_ref": "DEPUTY_DECISION@claude-opus#0007", "confirmed_by": "@human-rohan", "confirmation_delay_ms": 86400000}
{"type": "deputy_decision_overridden", "ts": "...", "move_ref": "DEPUTY_DECISION@claude-opus#0007", "overridden_by": "@human-rohan", "downstream_artifacts_flagged": ["ADR-0003", "TASK-0012"]}
{"type": "deputy_decision_held", "ts": "...", "move_ref": "DEPUTY_DECISION@claude-opus#0007", "extended_until": "2026-05-11T22:30:00Z"}
{"type": "deputy_decision_expired", "ts": "...", "move_ref": "DEPUTY_DECISION@claude-opus#0007", "elapsed_without_review_ms": 604800000}
{"type": "max_consecutive_deputies_reached", "ts": "...", "deliberation_id": "0007", "depth": 3, "remaining_questions_routed_to": "notify"}
{"type": "mode_set", "ts": "...", "mode": "autonomous", "set_at": "init"}
{"type": "autonomous_run_started", "ts": "...", "decider_panel": ["@claude-opus", "@gemini-pro"], "max_total_invocations": 100, "max_deliberations": 10}
{"type": "autonomous_run_completed", "ts": "...", "total_invocations": 87, "deliberations_decided": 8, "deliberations_force_resolved": 0, "duration_ms": 4302000}
{"type": "autonomous_max_invocations_hit", "ts": "...", "invocations_used": 100, "deliberations_force_resolved": 2, "deliberations_remaining_open": 1}
{"type": "mode_converted", "ts": "...", "from": "autonomous", "to": "interactive", "trigger": "human_issued_move", "move_ref": "REVISION@human-rohan#0003"}
{"type": "workspace_forked", "ts": "...", "source_workspace": "/path/to/source", "fork_path": "/path/to/new", "mode_change": "interactive_to_autonomous"}
{"type": "manifest_drafted", "ts": "...", "deliberation_id": "0001", "artifact_count": 5, "template_used": "saas-product"}
{"type": "manifest_locked", "ts": "...", "deliberation_id": "0001", "ratified_by": "@human-rohan"}
{"type": "manifest_revised", "ts": "...", "deliberation_id": "0014", "changes": "added risk-register.md"}
{"type": "artifact_production_started", "ts": "...", "artifact": "ux-requirements.md", "pattern": "specifier-authored", "specifier": "@claude-opus"}
{"type": "artifact_completion_check_failed", "ts": "...", "artifact": "ux-requirements.md", "failures": ["missing section: information_architecture"]}
{"type": "artifact_completed", "ts": "...", "artifact": "ux-requirements.md", "version": 1, "ratified_by": "@human-rohan"}
{"type": "artifact_revised", "ts": "...", "artifact": "requirements.md", "from_version": 1, "to_version": 2, "triggering_decisions": ["DECISION@claude-opus#0014"]}
{"type": "quality_gate_status_changed", "ts": "...", "gate": "no_unresolved_deputy_decisions", "passing": false, "blocking_count": 2}
{"type": "closing_ceremony_started", "ts": "...", "final_deliberation_id": "0023"}
{"type": "workspace_completed", "ts": "...", "mode": "interactive", "total_deliberations": 22, "total_invocations": 187, "duration_days": 12, "artifacts_produced": ["requirements.md", "ux-requirements.md", "tech-stack-rationale.md", "mvp-scope.md", "risks.md"]}
{"type": "setting_changed", "ts": "...", "path": "unavailability_policy.default", "old_value": "strict", "new_value": "substitute_with_floor", "changed_by": "@human-rohan", "via": "ui_panel", "category": "live_editable"}
{"type": "interjection_issued", "ts": "...", "issued_by": "@human-rohan", "applies_to": ["deliberation:0007", "artifact:requirements.md"], "force": "strong", "in_flight_invocations_pending": 1}
{"type": "override_issued", "ts": "...", "deliberation_id": "0007", "issued_by": "@human-rohan", "cancelled_in_flight": true, "preserved_unconsidered_moves": ["PROPOSAL@gemini-pro#0007"]}
{"type": "reopen_issued", "ts": "...", "deliberation_id": "0011", "issued_by": "@human-rohan", "superseded_decision": "DECISION@claude-opus#0011", "cascade_triggered": ["artifact:requirements.md"]}
{"type": "drop_issued", "ts": "...", "deliberation_id": "0019", "issued_by": "@human-rohan", "reason": "out_of_scope", "partial_moves_preserved": 4}
{"type": "steer_issued", "ts": "...", "issued_by": "@human-rohan", "targets": ["deliberation:0014", "role:critic"], "direction": "be more skeptical, challenge the cost assumptions harder"}
{"type": "agent_cancelled_by_human", "ts": "...", "handle": "@claude-opus", "deliberation_id": "0007", "trigger_move": "OVERRIDE@human-rohan#0007", "partial_output_preserved": true}
{"type": "clarify_issued", "ts": "...", "issued_by": "@human-rohan", "targets": "PROPOSAL@gemini-pro#0014", "why": "knowledge_gap", "paused_block": true}
{"type": "explanation_completed", "ts": "...", "explainer": "@claude-opus", "responding_to": "CLARIFY@human-rohan#0014", "sources_cited": 5, "gaps_acknowledged": 1, "validation_passed": true}
{"type": "explanation_failed_validation", "ts": "...", "explainer": "@claude-opus", "responding_to": "CLARIFY@human-rohan#0014", "failures": ["3 workspace claims lack citations", "What I couldn't find section is empty but user asked about alternatives that weren't covered"], "retry_attempted": true}
{"type": "context_source_added", "ts": "...", "source_type": "repo", "name": "backend", "path": "/Users/rohan/code/backend", "role": "core API; Node, Postgres", "relevance": "high"}
{"type": "digest_started", "ts": "...", "source_type": "repo", "name": "backend", "digester_handle": "@claude-opus", "relevance": "high"}
{"type": "digester_chosen", "ts": "...", "source_type": "repo", "name": "backend", "default_was": "@claude-opus", "user_chose": "@gemini-pro", "reason": "user_override_at_add"}
{"type": "digest_completed", "ts": "...", "source_type": "repo", "name": "backend", "digest_tokens": 8400, "duration_ms": 47000, "cost_usd": 0.0084}
{"type": "digest_review_completed", "ts": "...", "source_type": "repo", "name": "client-frontend", "user_action": "rejected_redigest_with_focus", "focus_areas": ["analytics events module"]}
{"type": "context_source_refreshed", "ts": "...", "source_type": "url", "name": "acme-pricing-page", "previous_fetched_at": "2026-04-01T12:00:00Z", "new_fetched_at": "2026-05-01T09:30:00Z"}
{"type": "digest_age_at_use", "ts": "...", "invocation_id": "...", "source_type": "repo", "name": "backend", "age_days": 12}
{"type": "on_demand_file_read", "ts": "...", "invocation_id": "...", "handle": "@claude-opus", "source_type": "repo", "repo": "backend", "file_path": "src/api/auth.ts", "tokens": 2400}
{"type": "on_demand_fetch", "ts": "...", "invocation_id": "...", "handle": "@codex-gpt5", "url": "https://stripe.com/docs/api/charges", "tokens": 5800, "cached": true}
{"type": "context_bundle_assembled", "ts": "...", "invocation_id": "...", "deliberation_id": "0014", "standing_bundle_tokens": 4200, "deliberation_context_tokens": 18500, "total_input_tokens": 22700}
{"type": "summary_line_appended", "ts": "...", "deliberation_id": "0014", "summary_line": "Pricing: free / pro $20 / team $50; 14-day pro trial; no annual discount in v1", "appended_to": "summarized-decisions.md"}
{"type": "summary_line_rejected", "ts": "...", "deliberation_id": "0007", "rejected_summary": "approved", "reason": "below_minimum_chars", "retry_offered": true}
{"type": "summary_line_revised", "ts": "...", "deliberation_id": "0014", "old_summary": "...", "new_summary": "...", "revised_by": "@human-rohan"}
{"type": "cost_ceiling_warning", "ts": "...", "current_cost_usd": 40.12, "ceiling_usd": 50.00, "percent": 80}
{"type": "cost_ceiling_hit", "ts": "...", "current_cost_usd": 50.18, "ceiling_usd": 50.00, "action_taken": "workspace_paused"}
{"type": "cost_ceiling_raised", "ts": "...", "old_ceiling_usd": 50.00, "new_ceiling_usd": 200.00, "by": "@human-rohan"}
{"type": "cost_ceiling_disabled", "ts": "...", "previous_ceiling_usd": 50.00, "by": "@human-rohan"}
{"type": "broker_state_changed", "ts": "...", "old_state": "disabled", "new_state": "enabled", "by": "@human-rohan"}
{"type": "shell_request_blocked_broker_disabled", "ts": "...", "handle": "@claude-opus", "deliberation_id": "0014", "attempted_command_pattern": "git diff main..feature-x"}
```

### What this log enables (now and future)

**Now:**
- The UI activity feed (filtered subset of these events).
- `quorum status` (current state derived from events).
- Debugging when something goes wrong.

**Future (no extra instrumentation needed):**
- *Fitness re-rating.* Cross-reference `move_outcome` events with `routing_decision` events. "When @gemini-pro was routed for critique, its moves were accepted X% of the time vs @claude-sonnet's Y%." This becomes the data for evolving fitness ratings.
- *Cost analysis per deliberation.* Sum `tokens_in/tokens_out` × per-handle pricing. Tell the user "this deliberation cost approximately $X across N invocations."
- *Routing quality reports.* "Layer 3 (fitness defaults) was used in 87% of routings; Layer 2 (workspace overrides) in 12%; Layer 1 (per-deliberation) in 1%." Validates whether automatic routing is actually serving users.
- *Cold-start overhead measurement.* Aggregate `cold_start_ms` across invocations. Tells us when warm-pool optimization (DO-1) becomes worth building.
- *Human friction signals.* `human_response` durations and `move_outcome: revised` rates. High revision rate on synthesis moves = synthesizer routing is wrong.
- *Dynamic-router training data (DO-2).* The `routing_decision` + `move_outcome` pairs form a labeled dataset for eventual ML-based routing.

### Privacy and locality

All logs are local. Nothing leaves the user's machine. If we ever build aggregated analytics (opt-in, anonymized), the schema is already sufficient.

### Log rotation

`events.jsonl` rotates daily. Old logs go to `/runtime/events/archive/YYYY-MM-DD.jsonl`. This is automatic, no user action needed.

---

## 10.6. Permissions & Tool Authorization · 🟢 Settled

When an agent CLI wants to run a shell command — read a file outside the workspace, search across repos, fetch a URL — it typically pauses and prompts the user for permission. In a stateless multi-agent architecture this breaks naively: the user isn't watching the terminal, the conductor isn't parsing prompts, and the CLI hangs waiting for stdin. We need an explicit permission story.

### v1 posture: broker disabled by default

The permission broker (described in detail below) is the highest-risk piece of v1 infrastructure: it requires reliably parsing each CLI's prompt format, holding processes indefinitely with stdin pipes, and surviving conductor restarts. The doc honestly acknowledges its fragility (see "The fragility I want to be honest about" below).

**v1 ships with the broker disabled by default.** Concretely:

- Default workspace `permissions.broker_enabled: false`
- When disabled: every agent CLI is invoked with the most restrictive permission flags available — Claude Code with `--allowedTools` set to a short safe list and any escalation refused; equivalent flags for Gemini and Codex. If a CLI doesn't support fine-grained restriction, it's invoked with shell access disabled entirely (where supported) or excluded from moves that might require it.
- If an agent attempts a shell operation outside its restricted allowlist, the CLI either silently gives up (best case) or fails the move cleanly (worst case). The failed move surfaces with a clear message: "Agent attempted shell access outside allowlist. Enable permission broker in Settings → Permissions to allow this kind of operation."

The reasoning: as documented later in this section, deliberation work itself rarely needs shell access. Proposing, critiquing, synthesizing, deciding — all read-only against the workspace's context surface. Edge cases (explainer verifying citations, digester reading source) can use the same restrictive read-only allowlist that's already configured for the bundled CLIs. Most users will never notice the broker is off.

For users who do need broker functionality (their workflow involves agents running commands beyond reads), Settings → Permissions has a single toggle: "Enable permission broker (advanced)." Toggling it on shows a dialog explaining the fragility and how to disable it if it misbehaves. After enable, the full four-layer model below applies.

This posture makes v1 robustly shippable. If the broker has real-world bugs, they don't affect the 90% of users who don't need it. The broker matures in v1.x (or v1.1, v1.2) without blocking v1's release.

### When the broker is enabled — the four-layer model

(Everything below applies only when `permissions.broker_enabled: true`.)

#### The shape of the problem

Three concerns tangled together:

1. **Detection.** Knowing that a permission request is being made (not just "still working").
2. **Surfacing.** Getting it in front of the user appropriately — they're in the UI, possibly in another room, possibly asleep.
3. **Routing.** Getting the user's decision back to the paused CLI process so it can proceed.

Each has design choices; the v1 design layers them.

#### When do agents actually need shell access?

A useful framing first: deliberation work itself rarely requires write operations. Proposing, critiquing, synthesizing, deciding — all read-only against the workspace's context surface (digests, deliberations, problem statement). The legitimate v1 cases for shell access:

- **Explainer** verifying a citation by reading actual source
- **Digester** producing initial repo summary at setup
- **Specifier** referencing real code paths in artifacts

All of these are read-only. Write-capable execution (running tests, modifying code, pushing commits) belongs to the *execution* phase after Quorum produces outputs — handed off to Cursor / Claude Code in IDE mode / similar tools that have their own well-developed permission flows.

This means the v1 permission story can be simpler than the worst case: most workspaces will rarely trigger out-of-allowlist requests. We design carefully but optimize for the common case being smooth.

### The four-layer model

**Layer 1 — Default allowlist with sensible patterns.**

Every workspace gets a default allowlist covering read operations agents legitimately need: file reads within `/quorum/` and declared context repos, basic git read commands (`status`, `log`, `diff` without modifications), search tools (`grep`, `find`, `rg`, `ag`), readonly file inspection (`cat`, `head`, `tail`, `less`).

A default denylist covers obvious dangers: `rm -rf` on paths outside the workspace, network operations to unknown hosts, `sudo` anything, write operations to git remotes, anything in `/etc/`, `/usr/`, `~/.ssh/`, etc.

Both are editable via Settings UI before workspace start. Both are also workspace-scoped — different workspaces can have different lists. Org-wide patterns get a deferred-optimization slot (see DO-4 cross-workspace registers).

**Layer 2 — Per-CLI flag passing.**

Each CLI has flags for permission control. Claude Code has `--allowedTools` and config. Gemini and Codex have analogues. The conductor knows each CLI's permission interface (recorded in routing-defaults) and passes the workspace's allowlist when invoking. Routine reads pass through silently; the CLI handles in-band approvals without bothering the conductor.

**Layer 3 — Conductor as broker for out-of-allowlist requests.**

When a CLI prompts for permission on something outside the allowlist, the conductor brokers it:

1. **Detect** — capture the prompt. Where the CLI offers structured output mode (JSON events for prompts), use it; otherwise fall back to stdout pattern matching against known prompt formats.
2. **Pause** — keep the CLI process alive on its end of stdin. Mark the deliberation `BLOCKED_ON_PERMISSION` (a new sub-state of BLOCKED_ON_HUMAN, see §6).
3. **Surface** — emit a `permission_requested` event; UI shows a high-priority notification.
4. **Wait** — for user response (or auto-approval policy, see Layer 4).
5. **Route response** — feed the answer to the CLI's stdin. CLI proceeds; the resulting move (or failure if denied) is logged normally.
6. **Optional persist** — if the user chose "approve always for this pattern," the allowlist is updated for future invocations.

The UI shows: which agent is asking, which deliberation it's working on, the exact command requested, options to approve once / approve always / deny / deny always. Same surfacing infrastructure as "your turn" notifications — it's another thing that needs the human's attention.

**Layer 4 — Stakes-based auto-approval (optional, opt-in).**

Permission requests have stakes too. The same machinery as §10.4 human-timeout applies, with the same four levels:

| Stakes | Examples | Default policy |
|---|---|---|
| `trivial` | Read operations on workspace files; simple greps within declared repos | Auto-approve under any human-timeout opted-in policy |
| `tactical` | Reading files outside declared repos but within user's `~/code/` ; running test commands without write side effects | Notify only; medium timeout |
| `strategic` | Anything that creates/modifies files outside `/quorum/`; commits to feature branches | Notify only; long timeout |
| `irreversible` | Destructive operations; force pushes; network calls to unknown hosts; system file changes | **Never auto-approve regardless of policy** |

The agent CLI doesn't classify stakes — the conductor does, by matching the requested command against pattern rules in `permissions.yaml`. This keeps classification auditable and tunable rather than depending on agent self-report.

Configuration:

```yaml
# config.yaml
permissions:
  broker_enabled: false                     # v1 default OFF; explicit opt-in via Settings → Permissions
  
  # When broker_enabled: false, only allowlist is enforced (via per-CLI flags).
  # Out-of-allowlist requests fail the move cleanly with a "broker is disabled" message.
  
  # When broker_enabled: true, the full four-layer model applies (allowlist + per-CLI flags + broker + auto-approve).
  
  allowlist:                                # patterns auto-approved without prompting
    - read_workspace                        # any read under /quorum/
    - read_declared_repos                   # reads within /context/repos/*/source
    - basic_git_read                        # git status, log, diff (no -m)
    - search_tools                          # grep, find, rg, ag
    - file_inspection                       # cat, head, tail, less, more
  
  denylist:                                 # patterns hard-refused even if user tries to allow
    - destructive_recursive                 # rm -rf outside workspace
    - sudo_anything
    - ssh_modifications
    - system_paths                          # /etc, /usr, /var, /System
  
  auto_approve:                             # only used if broker_enabled AND user opts into stakes-based auto-approval
    trivial:
      enabled: false                        # default OFF; user opts in via wizard or panel
      wait_minutes: 5
    tactical:
      enabled: false
      wait_minutes: 60
    strategic:
      enabled: false                        # generally don't auto-approve
    irreversible:
      enabled: false                        # forced; never auto-approve
```

**Validation rules:**
- `irreversible.enabled: true` → config refused. Hard constraint.
- `auto_approve.*.enabled: true` requires `human_timeout.default_enabled: true` in config (consistency: if you're not OK with stakes-based question auto-decide, you're not OK with stakes-based permission auto-approve).
- Any pattern in the user's `allowlist` that matches a `denylist` pattern → config refused with explanation.

### Capability-aware participants

Not all CLIs support fine-grained allowlists. When a handle is registered, `quorum doctor` probes for capability and tags it:

```yaml
# participants.md
- handle: "@claude-opus"
  cli: "claude"
  permission_capability: fine_grained        # supports --allowedTools
- handle: "@some-cli"
  cli: "somecli"
  permission_capability: coarse              # only all-or-nothing flag
- handle: "@another"
  cli: "anothercli"
  permission_capability: none                # no permission control at all
```

This affects routing for write-capable moves:

- **`fine_grained`** — eligible for any move, including those that may need shell access
- **`coarse`** — eligible for read-only moves only (the conductor refuses to invoke this CLI without permission control)
- **`none`** — eligible for read-only moves only; user is warned at registration

The user sees this clearly in the participants UI. A handle with `coarse` or `none` shows a "limited permission control" badge and a tooltip explaining what it can and can't do.

### BLOCKED_ON_PERMISSION as a deliberation sub-state

When the conductor brokers a permission request, the deliberation enters `BLOCKED_ON_PERMISSION` (a sub-state of `BLOCKED_ON_HUMAN` in §6). Properties:

- Counted toward the workspace's pending-attention metrics (alongside QUESTION-BLOCKED and DEPUTY-pending)
- Surfaces in resume briefing if the user pauses and resumes
- Has its own timeout mechanism (the stakes-based one above) if the user opts in
- Resolves on user decision: approve → block clears, agent proceeds, deliberation returns to its prior state; deny → agent receives denial, may retry differently or fail the move

### UI affordances

**Pending permission badge.** Persistent in the workspace dashboard sidebar — same shape as DEPUTY pending count: "2 permissions awaiting approval." Click to see the queue.

**Permission request card.** When a request arrives, surfaces as a prominent notification card (similar to "your turn" cards but visually distinct):

```
┌─────────────────────────────────────────────────┐
│ 🔐 @claude-opus needs permission                │
│ Working on: SYNTHESIS for #0014 (api-design)    │
│ Wants to run: grep -r "auth_token" ~/code/     │
│ Stakes: tactical (reads outside declared repos) │
│                                                  │
│ [Approve once] [Approve always]                 │
│ [Deny] [Deny always]                            │
└─────────────────────────────────────────────────┘
```

**"Approve always" learns the pattern.** Adds the matching pattern to allowlist; future requests of that shape don't surface. The UI shows a mini-confirmation: "Future requests matching `grep -r .. ~/code/` will auto-approve. Edit in settings."

**Settings panel: Permissions.** New panel under Settings UX (§9.8). Shows:
- Current allowlist (editable, with explanations of what each pattern matches)
- Current denylist (editable)
- Auto-approval policy per stakes (if user opted in)
- History of recent permission decisions (last 50, full history available via raw events.jsonl)
- "Permission capability" of each registered handle

**Resume briefing.** If the user pauses with permissions pending, the resume view lists them prominently — these often block downstream work and need attention before resuming.

### The fragility I want to be honest about

Mechanically, the broker layer is the trickiest piece of v1 infrastructure. The conductor must:

- Spawn each CLI with stdin/stdout pipes it controls
- Watch stdout for permission prompts (in addition to watching for completion and streaming output to UI)
- Hold the CLI process indefinitely while awaiting user response
- Feed the answer through stdin precisely, in the format that specific CLI expects
- Survive the conductor's own potential restart during pending permission

The last point is the hardest: if the conductor crashes or the user runs `quorum pause` while a CLI is suspended awaiting permission, the CLI process is orphaned. v1 acceptance: we kill orphaned CLIs on conductor restart, mark the invocation as failed with reason `interrupted_during_permission_wait`, and the user can re-route the move on resume. Not pretty, but honest.

A subtler issue: stdout pattern matching is fragile across CLI version updates. If Claude Code changes its prompt format slightly, our pattern breaks. Mitigation: prefer structured-output mode where available; record exact CLI version in events.jsonl per invocation so version-related breakage is debuggable; ship a test suite that probes each supported CLI's prompt formats and fails loudly when they shift.

### Events

Events.jsonl gains permission-related entries:

```jsonl
{"type": "permission_requested", "ts": "...", "handle": "@claude-opus", "deliberation_id": "0014", "command": "grep -r auth_token ~/code/", "stakes": "tactical", "matched_patterns": ["read_outside_declared_repos"]}
{"type": "permission_granted", "ts": "...", "request_id": "perm-0014-001", "by": "@human-rohan", "scope": "once", "wait_ms": 142000}
{"type": "permission_granted", "ts": "...", "request_id": "perm-0014-002", "by": "@human-rohan", "scope": "always", "added_to_allowlist": "grep -r ... ~/code/", "wait_ms": 38000}
{"type": "permission_denied", "ts": "...", "request_id": "perm-0014-003", "by": "@human-rohan", "scope": "once", "reason": "user_choice"}
{"type": "permission_auto_granted", "ts": "...", "request_id": "perm-0014-004", "stakes": "trivial", "policy_path": "auto_approve.trivial", "wait_minutes_elapsed": 6}
{"type": "permission_request_orphaned", "ts": "...", "request_id": "perm-0014-005", "reason": "conductor_restart_during_wait"}
```

This gives full audit trail. The user can answer "what did Claude do that I didn't see?" — answer: nothing without recorded permission. The user can also detect patterns in their own behavior — "I keep approving these manually; I should add them to the allowlist."

### What this design refuses to do

- **Never silently grant unbounded shell access.** Every command outside the allowlist surfaces; nothing happens behind the user's back unless explicitly opted into auto-approval.
- **Never auto-approve irreversible operations.** Hard constraint, validation refuses configs that try.
- **Never assume CLIs are stateful enough to pick up from where they paused if conductor restarts.** Orphaned CLIs are killed and invocations marked failed; the user knows.
- **Never use a CLI that has no permission control without explicit user awareness.** Coarse and none capability handles are flagged; only eligible for read-only moves.
- **Never let the audit trail miss a permission decision.** Every grant, denial, auto-approval, orphan is logged.

---

## 11. The Standing Agent Prompt · 🟢 Settled (v0.2)

The leverage point. Every CLI agent invocation gets a variant of this:

> You are `@<handle>` in a multi-agent collaboration system. Your working directory is `/quorum`.
>
> 1. Read `protocol/PROTOCOL.md` for the rules.
> 2. Read `registers/participants.md` to see other agents and their strengths.
> 3. Read `inbox/@<handle>.md` for your pending work.
>
> For each pending item:
> - Read the referenced deliberation file in full.
> - Produce the requested move type, following the template in `protocol/templates/`.
> - Append it to the deliberation file (never edit prior moves).
> - Update the inbox of any agent you tag, with a justification for tagging them specifically.
> - Mark the inbox item as handled.
>
> If you encounter a question only a human can answer (requirement ambiguity, business constraint, scope decision), issue a `QUESTION` move tagged `@human-rohan` and set the deliberation status to `BLOCKED_ON_HUMAN`. Do not guess.
>
> Do not edit other agents' contributions. Do not skip required template sections — write "none" if a section doesn't apply. When all your inbox items are handled, exit cleanly.
>
> **Context discipline (§1.8):** This workspace's context surface is in `/context/`. Trust the digests in `/context/repos/*/digest.md` and `/context/docs/digested/*` for high-level understanding. Read source files only when you need specific details that the digest doesn't provide. The events log captures which files you read; consistent over-reading suggests a digest gap we can fix. Cached URLs in `/context/web/cached/` are point-in-time captures — note their fetch dates if your move depends on current state. Notes in `/context/notes/` are user-authored conventions and context; treat them as authoritative for this workspace.
>
> **Permission discipline (§10.6):** Routine reads within `/quorum/` and declared context repos auto-approve. For anything outside the allowlist, your CLI will prompt — that prompt will be brokered to the user via the conductor; it may take time. Don't request shell access casually. Most of your work (proposing, critiquing, synthesizing, deciding) is reading the workspace's context surface and producing structured Markdown moves; this needs no shell access. If you do need it, request the most narrowly-scoped operation possible.

Per-agent overrides in `/prompts/overrides/` adjust emphasis (e.g., "@gemini-cli — your default posture is adversarial; assume the proposer is wrong until proven otherwise").

### Role-specific prompt augmentations

The standing prompt is augmented based on the role being invoked. Notable augmentations:

**For `explainer`-role invocations (responding to CLARIFY):**

> The user has asked for clarification on [specific text/move/concept]. They are NOT asking you to make a decision or take a position. They want to understand. Produce an EXPLANATION move:
>
> - Explain the concept in accessible terms.
> - If relevant, reference what was decided here and why.
> - If alternatives were considered in the deliberation, surface them.
> - If the user has a knowledge gap rather than a decision-context question, teach them.
> - Do not propose changes to the existing decision unless asked.
> - Length: as much as needed to actually explain, not artificially brief.
>
> **Grounding requirements (anti-confabulation):**
> - Every substantive claim about *this workspace* must cite a specific source (e.g., `PROPOSAL@claude-opus#0014`, `problem-statement.md`, `DECISION@human-rohan#0014`).
> - General knowledge about a concept (e.g., what RAG means in general) is welcome but must be visually distinguished from workspace-specific claims (use separate paragraphs labeled accordingly).
> - If the user asks about something that was NOT covered in the deliberation (e.g., "what alternatives were considered?" but only one alternative was discussed), say so explicitly in the `What I couldn't find in the workspace` section: "The deliberation only considered X; alternatives Y and Z were not raised."
> - You may not invent reasoning that isn't present in the workspace. The validator will reject EXPLANATIONs whose workspace claims lack citations.

**For `bootstrapper`-role invocations:**

> You are creating the workspace's first deliberation, which is always about the outcome manifest (§1.7). Read `problem-statement.md` and any selected manifest template. Propose a complete manifest specifying what artifacts the workspace must produce, with completion checks and quality gates. Tag the human (in interactive mode) or the decider panel (in autonomous mode) for review.

**For autonomous-mode invocations:**

> This workspace has no human participant. Do not ask a human to clarify or decide. If the problem statement is ambiguous, document your assumption explicitly in `Assumptions` and proceed. If a decision is required, the designated decider panel will resolve it. Never issue a QUESTION tagged at a human; never set status to BLOCKED_ON_HUMAN.

**For deputy decider invocations (interactive mode, human-timeout fired):**

> You are acting as a temporary deputy decider for `@human-rohan` because they have not responded within the configured timeout. Your decision is **provisional** — the human will review and either confirm, override, or hold it on their return.
>
> Read the deliberation in full, including the originating QUESTION's `Stakes` classification (which is `<trivial|tactical>`, never higher) and the agent's "What I'd recommend if forced" suggestion. Read the workspace's `problem-statement.md` and any prior decisions in this workspace to understand intent.
>
> Produce a `DEPUTY_DECISION` move per the template. Be conservative — when uncertain, choose the option that is most reversible. State your confidence honestly. List specifically what you'd want the human to confirm.

These augmentations are applied additively on top of the base standing prompt. A single invocation may have multiple augmentations active (e.g., an autonomous-mode bootstrapper invocation gets both the autonomous-mode augmentation and the bootstrapper augmentation).

---

## 12. Human-in-the-Loop Gates · 🟢 Settled (v0.2)

### When the human is invoked

1. **Requirement ambiguity** — agent issues a QUESTION tagged `@human-rohan`, status → `BLOCKED_ON_HUMAN`.
2. **Designated decider** — when a deliberation reaches SYNTHESIS and the decider is `@human-rohan` (default).
3. **Manual override** — human can issue moves at any time.
4. **Validator escalation** — repeated malformed moves get queued for human review.
5. **Deputy review** — DEPUTY_DECISIONs awaiting confirmation appear in the human's review queue (§10.4).

### How the human responds

The human handles their inbox the same way agents do — by writing moves into deliberations. The interface is just `/quorum/inbox/@human-rohan.md` + a text editor. Run `quorum resume` when done.

### The "ask once" principle

After the seed input, the system runs autonomously until it genuinely needs the user. "Genuinely needs" means: a question only the user can answer (business context, priority, requirement clarification) or a final decision gate. It does not mean "is uncertain about a technical tradeoff" — those go through critique/synthesis, not the human.

### Optional automation of the human gate

For users who want to reduce stalls on small questions, §10.4 describes the **Human-Unavailability Policy**. By default this is fully off — the system waits for human input indefinitely (the original "ask once" behavior). When opted in, agents can issue provisional DEPUTY_DECISIONs on the user's behalf for low-stakes questions; the user reviews and confirms or overrides on their return. **Automation produces drafts, never finals** — the human's role as final arbiter is structurally preserved.

Irreversible-stakes questions never auto-decide regardless of policy. Configuration that implies auto-decide without designated deputies is refused at validation time.

---

## 12.5. The Proactive Human Voice · 🟢 Settled

§12 covers the human as *responder* — agents ask, human answers; deliberation reaches synthesis, human decides. But real users have new information mid-stream, change their minds, want to redirect. The protocol must accommodate the human as *peer initiator*, not just responder.

This is the response to what would otherwise be a structural limitation: a human who wants to change course has no clean way to do so within the protocol, and ends up hacking around it (manual file edits, conductor restarts) — degrading the audit trail.

### Three categories of proactive human action

**1. Interjection — adding new information mid-stream.**
The user has new context that didn't exist when work started: a customer conversation, a forgotten constraint, a competitive insight, a budget change. The information needs to land such that ongoing deliberations can incorporate it.

Move type: `INTERJECTION` (§4 / §5).

When issued, the conductor:
- Logs the interjection prominently in events.jsonl
- Identifies affected deliberations from the move's `Where it applies` field
- Augments the next agent invocation prompt for affected deliberations: *"The human just added new information mid-stream: [interjection]. Consider whether this affects your move, and explicitly acknowledge if force level requires it."*
- For `force: strong`: affected deliberations' next moves must explicitly acknowledge in their text
- For `force: overriding`: affected deliberations pause until a move explicitly addresses the interjection

**2. Redirection — changing direction on existing work.**
Different from interjection: the human is *changing course*, not just adding context.

Move types:
- `OVERRIDE` — end a deliberation early with a unilateral decision ("I've decided X, stop debating"). Force-ends in-flight invocations on that deliberation. Audit trail preserves unconsidered moves.
- `REOPEN` — resume work on a previously DECIDED deliberation. Prior DECISION preserved as `superseded_by_reopen`. Triggers ARTIFACT_REVISION cascade on artifacts that referenced the old decision.
- `DROP` — abandon a deliberation without resolving. Status → ABANDONED. Distinct from DECIDED and ARCHIVED.

A common combined pattern is **pivot**: user issues OVERRIDE producing a new DECISION that contradicts a prior one; conductor detects the contradiction and triggers cascading ARTIFACT_REVISION on dependent artifacts.

**3. Steering — guiding without forcing.**
Sometimes the human doesn't want to override; they want to *push*. "Don't let this conclude too quickly" / "find more disagreement here" / "be more skeptical."

Move type: `STEER` — provides advisory direction. Affects prompt augmentation for affected agents on subsequent invocations. Does not change protocol state. Recorded in audit trail; if a particular steer materially shaped an outcome, a reader can trace why.

In v1, STEER is human-only. Agent-to-agent steering (e.g., a synthesizer steering a critic) is logged as a deferred optimization — we don't yet know whether it adds value beyond what regular CRITIQUE captures.

**4. Clarification — asking for understanding without progressing decisions.**
The user encounters a concept they don't know ("what is RAG?"), wants to understand the reasoning behind a prior decision ("why was Cassandra chosen over PostgreSQL?"), or is reviewing the workspace later and needs context on something. None of these are decision-progressing questions; they're requests for explanation.

Move type: `CLARIFY` (with paired response `EXPLANATION`). Distinct from QUESTION/ANSWER because:
- **It doesn't progress work** — it requests explanation, not a decision.
- **It doesn't block deliberation conclusion** — though it can pause an existing block.
- **It can target any prior content** — including DECIDED deliberations, ARCHIVED workspaces, completed artifacts, specific concepts mentioned anywhere.
- **It expects an EXPLANATION response, not an ANSWER** — answers commit to positions; explanations educate.

When CLARIFY arrives during BLOCKED_ON_HUMAN (the user is asking for clarification on a question they were supposed to answer), the block is **paused** while the CLARIFY → EXPLANATION exchange happens. Once the EXPLANATION is delivered, the user can issue the actual ANSWER and the original block resumes. This handles the "I don't understand the question well enough to answer it yet" scenario cleanly.

CLARIFY is allowed on DECIDED and ARCHIVED workspaces — agents can be invoked to explain even on long-finished work. The deliberation stays in its current state; the clarification thread is auxiliary, not part of the decision flow.

**Anti-confabulation: grounded explanations.** EXPLANATION moves are bounded by what the workspace actually contains. The explainer agent's prompt is strict: every workspace-specific claim must cite a real source (move ref, artifact section, file path); general knowledge must be visually distinguished from workspace claims; and the required `What I couldn't find in the workspace` field forces explicit acknowledgment when the user asks about things not actually in the audit trail. The validator enforces citation requirements; explanations failing validation are flagged for revision.

This is why §5 strengthens PROPOSAL with a required `Alternatives I considered` section, SYNTHESIS with `Alternatives weighed`, and DECISION with optional `Path not taken` — these convert future EXPLANATIONs from "agent guesses what alternatives were considered" into "agent reads what alternatives were actually considered." A future user asking "why was Cassandra chosen over alternatives?" gets a real answer cited to specific moves, or an honest "the deliberation only considered Cassandra; no alternatives were surfaced."

The user gets two-tier honesty: explanations clearly distinguish (a) general knowledge the agent legitimately has from training, from (b) workspace-specific claims grounded in the audit trail, with (c) explicit gaps when the workspace doesn't contain what the user wants to know.

### Disruption strategy for in-flight invocations

When the human intervenes on a deliberation that's mid-invocation (an agent is currently composing a move), what happens? Different move types, different policies:

| Move | Disruption strategy | Why |
|---|---|---|
| `INTERJECTION` (advisory/strong) | Wait for current invocation to complete, incorporate in next | The current move can still be useful; let it finish |
| `INTERJECTION` (overriding) | Wait for current, then pause | Force level demands explicit acknowledgment before more work |
| `OVERRIDE` | Cancel current invocation immediately | The user has decided this work is no longer wanted; finishing wastes credits |
| `REOPEN` | N/A — applies to DECIDED state, no in-flight invocation | — |
| `DROP` | Cancel current invocation immediately | Same logic as OVERRIDE |
| `STEER` | Wait for current, augment next invocation's prompt | Advisory only |
| `CLARIFY` | Wait for current; spawn EXPLANATION as parallel work (doesn't block deliberation flow unless deliberation was BLOCKED_ON_HUMAN, in which case block pauses) | Auxiliary; in-flight work remains useful |

Cancellation is clean: the in-flight CLI process is killed, partial output is preserved in `/runtime/streams/failed/` for inspection, and an `agent_cancelled_by_human` event is logged. No broken move is appended to the deliberation.

### UI affordances

This earns its keep when users can act without remembering move types. The UI provides:

**The "Speak up" button** — persistent in the top-right during ACTIVE state. Clicking opens a contextual menu based on what the user is viewing:

- Viewing a deliberation:
  - "Add input" → INTERJECTION targeting this deliberation
  - "Override" → OVERRIDE (if user is decider)
  - "Reopen" → REOPEN (if deliberation is DECIDED)
  - "Drop" → DROP (if deliberation is active)
  - "Steer" → STEER targeting this deliberation
  - "Ask for clarification" → CLARIFY targeting this deliberation broadly
- Viewing a specific move within a deliberation:
  - "Ask for clarification on this move" → CLARIFY targeting that move
- Viewing the workspace dashboard:
  - "Add input" → workspace-wide INTERJECTION
  - "Add to manifest" → MANIFEST_REVISION proposal
  - "Pause and edit problem statement" → guided pause + edit flow
- Viewing an artifact:
  - "Trigger revision" → ARTIFACT_REVISION proposal
  - "Add note" → INTERJECTION scoped to the artifact's source deliberations
  - "Ask for clarification" → CLARIFY targeting an artifact section
- Viewing a DECIDED or ARCHIVED workspace:
  - "Ask for clarification" remains available — clarification doesn't require active state

Each option opens the structured form for the appropriate move type. The user thinks "I want to understand this" — the UI handles "this is a CLARIFY move."

**Text-selection clarification** — similar to how Google Docs lets you select text and add a comment, the user can select any text in any move or artifact and click "Ask for clarification on selection." The CLARIFY targets that exact text span. The resulting EXPLANATION is anchored visually next to it. This is a richer UX than just deliberation-level clarification — useful for "what does this specific term mean?" cases.

**Inline quick-action on deliberation cards** — small "Add input" button on every deliberation card. Click, type a sentence, submit. Becomes a small INTERJECTION (force: advisory, scoped to that deliberation). A separate small "?" button on each move card opens a CLARIFY form with that move pre-targeted. Frictionless for the most common cases.

**Settings panel: Default disruption posture** — under §9.8 settings, a tunable for advanced users: "When I issue interjections mid-deliberation, default force level is..." (advisory / strong). Most users use the default.

### Visual treatment of EXPLANATION moves

EXPLANATION moves are visually distinct from core decision-flow moves. The signal: *this is auxiliary context for understanding, not part of the decision itself.*

- **Layout:** Inset or recessed style — narrower than core moves, with a lighter border and academic-citation aesthetic (footnote-like).
- **Color:** Muted compared to PROPOSAL/CRITIQUE/SYNTHESIS/DECISION cards. Where decision-flow moves use full saturation, EXPLANATIONs use a desaturated variant of the same palette.
- **Iconography:** Small "?" or info icon in the move-card header.
- **Citations as links:** References within EXPLANATION text (`PROPOSAL@claude-opus#0014`, `requirements.md#pricing`) render as clickable links that scroll to the cited source. This is the payoff of structured citations — users can verify any claim with one click.
- **"Hide explanations" toggle** — at the deliberation top, lets a reader scanning the actual decision flow suppress the meta-conversation. Default: shown.
- **The "What I couldn't find" section** — visually emphasized when non-empty; this is the honesty signal that there were gaps in what the agent could ground its claims in.

Future readers can engage with the deliberation at two levels: the actual decision-making path (core moves), and the explanatory layer above it (clarifications and explanations).

### The human's role, structurally

Pulling this together: the human is now structurally a **peer participant**, not a constrained responder. They can issue any move type the protocol defines, including six reserved exclusively for human (or decider) initiation.

This changes what the human's `participants.md` row means. It's not just "where the human can be tagged" — it's "the human as a full participant in deliberation, with both responsive and initiative capabilities."

The audit trail honestly reflects whose voice introduced what. A deliberation might show:

```
PROPOSAL@claude-opus → CRITIQUE@gemini-pro → INTERJECTION@human-rohan
  → SYNTHESIS@claude-opus (acknowledging interjection) → DECISION@human-rohan
```

A reader sees exactly when and how the human shaped the deliberation, beyond just the final decision.

---

## 13. Failure Modes & Mitigations · 🟢 Settled (v0.3)

| Failure | Mitigation |
|---------|------------|
| Malformed moves | Validator + one-retry policy; persistent failures → human queue |
| Premature consensus (agents agree too easily) | Required `critic` role with adversarial standing prompt; routing prefers high-fitness critics (often Gemini Pro by default) |
| Tag-spam (everyone tagged on everything) | `Tagging` field requires per-agent justification |
| Infinite loops (politeness ping-pong) | No-two-consecutive-moves rule; STOP heuristic at N moves |
| Rate limit / cost runaway | Per-deliberation invocation cap; per-handle daily cap; quota-aware routing reserves high-cost handles for high-value moves (§10.3) |
| File contention (parallel agents same deliberation) | Per-deliberation file locks (fcntl/portalocker); brief wait, imperceptible |
| File contention across deliberations | None needed — different files don't contend |
| Authorship corruption | Append-only rule, never edit prior moves; REVISION supersedes |
| Vocabulary drift | Shared `glossary.md` register; agents propose additions via deliberation |
| Self-reference paradoxes (debating the protocol while bound by it) | Protocol changes go through normal deliberation; current protocol applies until DECIDED |
| Routing returns no available handle | Status BLOCKED_ON_ROUTING; surface to user with explanation and remediation options |
| Handle quota window exhausted mid-deliberation | Substitution policy applies (§10.3); default `strict` blocks the deliberation and pauses workspace; user notified |
| Daily cap hit | Same handling as quota window; recovery time = next day |
| Service outage (5xx, timeouts) | Retry with backoff (3 attempts) before applying substitution policy |
| Network failure | Retry with backoff; if persistent, treat as service outage |
| Subscription/auth issue | Always blocks regardless of policy (no substitute can save it); user notified to investigate |
| CLI hang (process timeout) | Kill process, mark failed, apply substitution policy |
| Mid-flight invocation failure | Partial output preserved in `/runtime/streams/failed/`; no broken move appended; substitution policy applies as if fresh |
| CLI cold-start latency perception | Solution 3: progressive status messages during startup ("Initializing…" → "Reading…" → "Composing…") |
| Conductor crashes mid-invocation | Startup recovery cleans stale markers >15min old; affected deliberation surfaces to user; pause reason logged as `crash_recovery` |
| Routing-defaults file fetch fails on init | Fall back to bundled defaults; warn user; allow `quorum refresh-defaults` later |
| Routing decision feels wrong to user | Activity feed shows reason + alternatives; workspace overrides in `config.yaml` change behavior |
| Long-running session, resume after days | `quorum resume` shows resume briefing (§1.6) — what changed, what's blocked on user, suggested actions |
| Auto-resume disrupts user (resumed while away) | Default `resume_policy.mode: manual` — auto-resume is opt-in only |
| Substitution silently degrades quality | Default `unavailability_policy.default: strict` — substitution is opt-in only; even when enabled, every substitution is logged + frontmatter-marked + user-notified |
| User closes terminal during `quorum start` | Conductor is daemonized by default — closing terminal is a non-event; process keeps running |
| User runs `quorum start --foreground` and closes terminal | Conductor dies; next `quorum status` detects (PID dead) and auto-recovers to PAUSED state |
| Machine restart / power loss during ACTIVE state | Next `quorum` command detects PID-dead, sweeps stale runtime markers, marks workspace PAUSED with reason `crash_recovery`, preserves partial outputs in `/runtime/streams/failed/` |
| User runs `quorum start` twice on same workspace | Second invocation refuses with PID lockfile message; offers `quorum status` and `quorum pause` as next steps |
| User can't remember whether to use `start` or `resume` | They're aliases — both work from any non-ACTIVE state |
| OS killed conductor (memory pressure, etc.) | Same as power-loss path — auto-detected and recovered on next command |
| Human-timeout: agent misclassifies stakes (e.g., classifies strategic question as trivial to get fast resolution) | DEPUTY_DECISION review surfaces it; user can flag misclassifications; future routing can prefer better-calibrated agents for question authoring |
| Human-timeout: cascading deputy decisions create override-cascade mess | `max_consecutive_deputies` per deliberation chain (default: 3); after limit, all further QUESTIONs route to `notify` regardless of stakes |
| Human-timeout: user gradually loses touch with their own project | Visible accumulation in UI sidebar (pending count), resume briefing prioritizes review queue, threshold warnings in `quorum status` |
| Human-timeout config has auto_decide but no deputies designated | Config validation refuses to load — fail loud, not silent |
| Human-timeout config attempts auto_decide for irreversible | Config validation refuses — irreversible never auto-decides |
| Human is briefly away, timer fires unnecessarily | Presence grace window — if last human activity within `presence_grace_minutes` (default 15), defer timer |
| DEPUTY_DECISION expires without review | `status: expired`; downstream artifacts already in use; UI surfaces drift indicator; not technically a failure but the system is honest about it |
| Human overrides DEPUTY_DECISION but downstream artifacts already generated | Override event flags downstream ADRs/tasks for review; UI shows them in a "review for consistency" queue |
| Autonomous mode: hit max_total_invocations before all deliberations DECIDED | Per `on_max_invocations` setting: `best_effort` force-resolves remaining via decider panel with current state (output marked incomplete); `block` leaves remaining open and surfaces in completion view |
| Autonomous mode: all decider panel handles unavailable simultaneously | Hard block — workspace transitions to PAUSED (reason: `blocked_on_unavailable`); user notified; can manually convert to interactive or wait for recovery |
| Autonomous mode: agent issues QUESTION tagged at human despite mode | Treated as protocol violation; question is auto-redirected to the decider panel for an ANSWER move; logged for review |
| Autonomous mode: config has `mode: autonomous` and `human_timeout` enabled | Config validation refuses to load — semantically incompatible |
| Autonomous mode: empty decider_panel | Config validation refuses — no deciders means no DECISIONs possible |
| Mode-conversion: user issues a move in an autonomous workspace | Converts workspace to interactive mode; standing prompt updates on next agent invocation; `mode_history` recorded in state.yaml |
| Fork: source workspace is corrupt or partially written | Fork command refuses with diagnostic; user must repair source first |
| Fork: target path already exists | Fork refuses unless `--force` (which still won't overwrite, just creates a sibling with timestamp suffix) |
| Manifest: user paralysis on what they want | Templated manifests (§1.7) provide starting points; bootstrapper can propose template based on problem statement; user can lock minimal manifest and revise later via MANIFEST_REVISION |
| Manifest: artifact never reaches completion (deliberations endlessly spawn without converging) | No-progress detector at deliberation level; per-workspace max_deliberations cap; artifact production triggers ensure spec-writer attempts even with imperfect deliberation coverage |
| Manifest: quality gates can't be satisfied (open questions multiply faster than they resolve) | UI surfaces gate status persistently; user can manually flag open questions as `non_blocking` to allow completion; closing summary honestly notes unresolved items |
| Manifest: agent fails completion check repeatedly | Specifier role escalates to next-best handle; if no handle satisfies, artifact stays in `needs_revision` and surfaces to human |
| ARTIFACT_REVISION: revised artifact breaks references in other artifacts | `Backwards-compatible: no` flag triggers cascade-check; affected artifacts marked `needs_revision`; user notified |
| ARTIFACT_REVISION: rapid-fire revisions cause artifact churn | Per-artifact revision rate limit (e.g., max 3 revisions per 24h) — beyond that, revisions queue and require manual approval |
| Manifest evolution: new artifact added late in workspace life | Manifest revised via MANIFEST_REVISION; new artifact slot opens; production scheduled per its dependencies; doesn't disrupt completed artifacts |
| Closing ceremony: user disputes summarizer's closing synthesis | Treated as any other move — user can issue REVISION on the closing synthesis or override the DECISION; ceremony can re-run |
| Settings: user attempts to change a Category A (frozen) setting on an active workspace | UI shows 🔒 with tooltip "Locked when workspace started — fork to change"; CLI/YAML edit refused with same message |
| Settings: user changes Category C setting that disrupts in-flight work (e.g., removes routed handle) | Confirmation dialog shows what's affected; on accept, future routing avoids removed handle; in-flight invocations using that handle complete normally |
| Settings: user edits YAML directly while UI is open | File-watcher catches the change; UI re-renders with new values; conductor reloads if running; events.jsonl logs `setting_changed` with `via: file_edit` |
| Settings: invalid YAML saved via raw editor | Schema validation refuses save; UI shows error inline; YAML file unchanged |
| Settings: wizard completed but user wants to redo it | Wizard reachable from settings panel as "Re-run setup"; but only fills empty/default values, never overwrites explicit changes |
| Settings: conflict between UI panel edit and concurrent file edit | Last-write-wins at file level; UI re-renders on file-watcher event; user sees the latest state. Brief race window (sub-second) is acceptable for v1; v2 may add optimistic locking |
| INTERJECTION arrives during in-flight invocation | Wait for current invocation, augment next prompt (advisory/strong) or pause after current completes (overriding); never disrupt mid-generation for non-overriding force levels |
| OVERRIDE arrives during in-flight invocation | Cancel immediately; preserve partial output in `/runtime/streams/failed/`; log `agent_cancelled_by_human`; transition deliberation to DECIDED with the OVERRIDE as decision |
| Race: human issues OVERRIDE on a deliberation that just transitioned to DECIDED a moment earlier | OVERRIDE is rejected with "this deliberation is already DECIDED — use REOPEN instead"; UI offers REOPEN as the fix |
| REOPEN on deliberation whose downstream artifacts already exist | ARTIFACT_REVISION cascade triggered automatically; affected artifacts marked `needs_revision`; user notified of cascade scope before issuing |
| Repeated rapid INTERJECTIONs faster than agents can process | Conductor queues interjections per deliberation; before each agent invocation, all pending interjections are bundled into the prompt augmentation. Agent sees them all at once; protocol violation only if force levels conflict |
| User accidentally clicks DROP on wrong deliberation | Confirmation dialog before commit; ABANDONED state is reversible via REOPEN if caught quickly (within a configurable window, e.g., 5 minutes) — beyond that, REOPEN works but is treated as standard |
| STEER conflicts with another active STEER (e.g., "be more skeptical" + "converge faster") | Most recent STEER wins for affected agents; older STEER is logged as superseded; user notified if contradiction is detected by the prompt-augmentation layer |
| Human issues moves they're not authorized for (e.g., non-decider tries OVERRIDE) | Validator refuses; UI's "Speak up" menu only shows options the user is authorized for — based on their role in the workspace |
| Cancellation of in-flight invocation costs credits already spent | Acknowledged tradeoff — partial generation has been billed; conductor logs `cancelled_invocation_cost_estimate` so the user can see what was spent on cancelled work |
| Agent confabulates explanation despite prompt guardrails | Validator catches missing/invalid citations and absent `What I couldn't find` field; rejects move; agent retries (one attempt) before flagging for human review |
| EXPLANATION cites a move/file that doesn't exist or has been moved | Validator detects broken reference; flags for revision; if persistent, falls back to "the source I tried to cite was not found in the current workspace state" with explicit acknowledgment |
| User asks CLARIFY about deliberation that referenced an external URL no longer accessible | EXPLANATION acknowledges in Limitations: "the deliberation cited [URL] which I cannot access" |
| User asks CLARIFY about a decision made by a handle no longer in participants | EXPLANATION proceeds with available context from move text; acknowledges in Limitations that follow-up with original author isn't possible |
| Cascading CLARIFYs create deep nesting (CLARIFY on EXPLANATION on CLARIFY...) | Cap at 5 levels of nesting; beyond that, user is prompted to consolidate or open a new deliberation if a real concept needs exploration |
| User asks CLARIFY mid-BLOCKED_ON_HUMAN; while waiting, original question becomes stale (e.g., other deliberations have moved on) | When EXPLANATION arrives, conductor checks whether the original blocking context is still valid; if not, surfaces a notification: "the question you wanted to clarify is now part of a deliberation that has moved forward — review before answering" |
| EXPLANATION on a workspace that's been ARCHIVED for so long that participants config or routing-defaults have evolved significantly | Validator notes the temporal gap; EXPLANATION's Limitations section flags potential staleness in the workspace's grounding |
| Context: digest is stale but agent is unaware | Standing prompt augmentation includes digest age; agent must acknowledge in moves that depend on current code state. `digest_age_at_use` event logged. UI surfaces stale digests (red indicator >30 days) |
| Context: URL fetch fails (network issue, page removed, paywall) | UI shows fetch error; user can retry, replace URL, or remove. Cached version (if any) remains usable but is flagged as last-known-state |
| Context: uploaded doc is too large for raw inclusion or naive digestion | Conductor warns at upload time; suggests chunked digestion (digest sections separately) or refusal. User can split into multiple smaller doc uploads |
| Context: user adds many large repos and digestion queue grows | Queue is FIFO and runs in background; UI shows queue status. User can start workspace before all digests complete; deliberations declaring not-yet-digested repos block on `BLOCKED_ON_EXTERNAL` until ready |
| Context: agent over-reads source despite digest availability | `files_read` per invocation logged; pattern of high read-counts surfaces in events log; prompt-tuning iteration to reduce |
| Context: digest missed something important and agents proceed on wrong assumption | Caught when user reviews digest (manifest quality gate) or when an EXPLANATION later surfaces the gap. Re-digest with focus areas; affected deliberations may need REOPEN |
| Context: 500MB repo added | Conductor refuses by default with "repo exceeds size threshold"; user can override with `--allow-large` and accept the digestion cost (typically 5-10x normal) |
| Context: user adds notes that grow beyond practical limit (e.g., 100K tokens of notes) | Conductor warns at ~50K total notes tokens; suggests moving content to docs (digestible) or scoping notes to specific deliberations |
| Context: cross-repo references in code that the digest doesn't capture | Acknowledged limitation; on-demand reading handles specific cases; if pattern repeats, user adds explicit cross-repo notes |
| Permission: agent CLI prompts on stdout for shell operation outside allowlist | Conductor detects (structured-output where available; stdout pattern match otherwise), pauses CLI with stdin held, transitions deliberation to BLOCKED_ON_PERMISSION, surfaces request in UI; user grants/denies; conductor routes response back to CLI's stdin |
| Permission: conductor restarts while CLI is paused awaiting permission | Orphaned CLI killed; invocation marked failed with reason `interrupted_during_permission_wait`; user can re-route the move on resume |
| Permission: stdout pattern match fails because CLI version updated prompt format | Test suite probes each supported CLI's prompt format and fails loudly when it shifts; fallback heuristics + version recorded in events.jsonl per invocation for debuggability; user notified to update Quorum |
| Permission: CLI requested has `permission_capability: none` and the move requires shell access | Routing refuses the handle for that move; reroutes to a fine_grained handle; logged so user can see the asymmetry |
| Permission: user attempts to put a denylist-matching pattern in their allowlist | Config validation refuses with explanation of which deny pattern conflicts |
| Permission: user opts into auto-approve for `irreversible` stakes | Config validation refuses; hard constraint |
| Permission: user opts into auto-approve but human_timeout is disabled | Config validation refuses with explanation (consistency: stakes-based auto-approve requires the same human-timeout machinery be on) |
| Permission: many auto-approvals fire while user is asleep, and user disputes one in the morning | Audit trail (events.jsonl) shows full record per request; UI surfaces "23 permissions auto-approved overnight" prominently in resume briefing; user can click any to inspect what was approved and why |
| Permission: agent's command output produces a follow-up command that the agent runs through CLI's own internal shell loop without re-prompting | Limitation acknowledged — CLIs that batch operations within a single approved session may run several commands under one approval. Mitigation: prefer CLIs that prompt per-command; document this asymmetry per supported CLI in routing-defaults |
| Multi-account: two handles share an underlying account and concurrent invocations hit account-level rate limit | Per-handle quotas don't see account-level limits. v1 mitigation: set per-handle quotas conservatively (e.g., 50% of account capacity) when multiple handles share an account. Events log captures rate-limit failures so user can detect when this hits. v2 (OQ-74): account-level quota grouping. |
| Multi-account: user routes a sensitive deliberation to wrong account (e.g., work content sent to personal account by accident) | UI participants panel groups handles by Account Label visually; deliberation cards show which handle authored each move with account badge; workspace can register only the account-relevant handles to prevent cross-account routing |
| Multi-account: account labels diverge from underlying binary intent (e.g., user mistakenly tags `claude-personal` binary as "Work") | Display-only field; no functional impact, just confusing UI. User can edit at any time in participants panel |
| Cost: workspace approaches $50 default ceiling | UI surfaces warning at 80% ($40); at 100%, conductor pauses and shows "spent $50; raise ceiling, disable, or stop" dialog. User explicitly chooses. No silent overrun. |
| Cost: user disables ceiling entirely, then runs unattended | User opted out explicitly; warned at disable time about runaway risk; events.jsonl still tracks per-invocation cost so user can audit later. No automatic re-enable. |
| Cost: cost estimate diverges from actual provider billing | Per-invocation `cost_usd_estimate` is approximate (uses published per-token pricing × token counts from CLI output); real billing may differ by ~5-15% for various reasons (cached tokens, batch discounts, etc.). UI surfaces this as "estimated cost" not "actual cost"; user reconciles against real bill when needed. |
| DECISION Summary line is vacuous ("approved", "yes", "decided") | Validator rejects on character count (<30) or against a small denylist of obviously-generic patterns; decider gets one retry with explicit feedback. Persistent failures flag for human review. |
| DECISION Summary line is misleading (passes validator but doesn't reflect actual decision) | Caught in EXPLANATION when an agent or user asks about the decision later — the discrepancy between Summary line and actual Decision text surfaces. User can edit the Summary line via raw-YAML editor; revision logged as `summary_line_revised` event. |
| `summarized-decisions.md` grows unbounded in long-running workspaces | Bounded by DECISION count × ~120 chars + reference. 200 decisions ≈ 25K chars ≈ 6K tokens. The cost ceiling catches runaway scenarios before this dominates context cost. |
| Permission broker is disabled and an agent legitimately needs shell access | Move fails cleanly with "shell access blocked; broker disabled; enable in Settings → Permissions to allow." User can enable broker per-workspace, or fall back to manual handle for that move. Never silent failure. |
| Permission broker is enabled but the prompt-detection fails on a specific CLI version | Invocation hangs until the 15-min timeout; conductor kills, marks failed, surfaces "broker may have failed to detect prompt; consider disabling broker for this CLI." User can disable broker per-handle in advanced settings. |
| Vertical slice (build step 5) reveals fundamental protocol issues | Treated as success of the milestone — the whole point is to find problems before building UI on top. Findings update PROTOCOL.md, standing prompt, and conductor before proceeding to step 6. Schedule has buffer for this. |
| Wizard's CLI auto-detection misses an installed CLI | Question 4 offers manual-add path with binary name input + doctor probe. User adds `claude-work` (or similar) by typing the name. |

---

## 14. Build Order · 🟢 Settled (v0.7)

**Distribution v0.1:** git clone + `install.sh` (see §1.6). Defer package distribution until protocol surface stabilizes.

**Build sequence:**

1. **`PROTOCOL.md` v0.1** + move templates + artifact templates (§8) + manifest templates (§1.7). ~1.5 days.
2. **The CLI scaffolding** — `quorum init`, `quorum status`, `quorum doctor` (with permission-capability probing), `install.sh`. Includes `.gitignore` generation, `routing-defaults.yaml` fetch with offline fallback, problem-statement.md scaffolding, outcome-manifest.md scaffolding, participants.md stub generation, empty `/context/` source-type subdirectory scaffolding, default `permissions.yaml` with allowlist/denylist patterns and `broker_enabled: false`. ~1.5 days.
3. **Manual protocol exercise (NO code)** — before building anything else, run the protocol manually for one real deliberation. Three CLI agents, real problem, manually scheduling invocations, manually running validator checks against move structure. Minimum viable test: does the protocol produce useful work? Do the standing-prompt augmentations actually shape agent behavior? Does the validator catch what we want it to catch? ~1 day.
   - This is the cheapest possible reality check before committing 3+ weeks of build effort. If the protocol doesn't behave well manually, no amount of UI polish saves us. Findings feed back into PROTOCOL.md and the standing prompt before we proceed.
4. **The conductor core** (Python, ~400 lines): `start`, `pause`, `step`, `run`, `resume`, `validate`, `serve`. Includes routing engine (§3.6), parallel invocation with per-deliberation locks, lifecycle marker management (writes to `/runtime/`), move-format validator (now Summary-line-aware), structured event emission to `events.jsonl`, manifest-satisfaction checks, artifact production scheduling, context bundle assembly per invocation. **Permission broker is NOT in scope for this step** — it's deferred to step 11 as an opt-in feature. ~1 weekend.
5. **VERTICAL SLICE MILESTONE — first end-to-end deliberation.** Use the simplest possible UI (literally a Markdown file viewer + a "run next step" button). Run one real deliberation through the conductor. The point is to learn — not to ship. Specifically validate:
   - Standing prompt actually produces structurally-correct moves
   - Validator catches the right things and misses the right things
   - Routing produces sensible handle selections
   - Digest-then-deliberate flow preserves enough context for good outcomes
   - Required Alternatives sections produce real reasoning vs vacuous fills
   - Summary line field produces useful one-liners
   ~2-3 days of focused testing and prompt iteration. Findings update PROTOCOL.md, standing prompt, validator, and conductor before we build the "real" UI on top.
6. **Context surface implementation (§1.8)** — repo digester (relevance-tiered model selection), document upload + auto-digest threshold logic, URL fetch + Markdown conversion + cache, notes editor. Background job queue for digestion tasks. Freshness tracking. Cost ceiling enforcement (default $50). ~3 days.
7. **The UI shell** — three-pane layout, reads files, renders deliberations, manifest progress view, move cards as static views. **Includes the workspace setup wizard** (§9.8 Tier 1). Suggested stack: Next.js or SvelteKit + Tailwind. ~3 days.
8. **UI live updates + streaming composition** — file-watcher, WebSocket push, three move-card states (composing/complete/failed), activity feed sourced from events.jsonl, deliberation timeline, routing-decision visibility, cost ceiling progress display. ~2 days. (Permission request cards deferred to step 11.)
9. **Settings UI panels (§9.8 Tier 2)** — eight intent-organized panels (Permissions panel shows broker-disabled state with toggle; Context with sub-panels), schema-validated forms, frozen/live/live-with-effects indicators, confirmation dialogs for Category C edits. ~3 days.
10. **Raw YAML editor (§9.8 Tier 3)** — browser-based editor with schema validation and inline help. ~0.5 days.
11. **Permission broker (opt-in feature)** — stdin/stdout pipe management, prompt detection across supported CLIs, response routing, BLOCKED_ON_PERMISSION state, permission request cards in UI, auto-approval policy. Substantial standalone prototype recommended before integration. ~2-3 days. Ships disabled by default; users opt in via Settings → Permissions toggle.
12. **The structured response form** for human moves (§9.7), including the human-initiated move forms (§12.5). ~1.5 days.
13. **Standing agent prompt iteration — DEDICATED WEEK.** Per-handle overrides for the first 3-5 handles (`@claude-opus`, `@claude-sonnet`, `@gemini-pro`, `@codex-gpt5`). Mode-specific augmentations (autonomous, deputy invocation, explainer, context-discipline, permission-discipline). **Iteration is the work, not a side-effect.** Specifically test:
    - Does the agent fill required Alternatives sections vacuously, or with real reasoning? Tune until consistently real.
    - Does the agent classify question stakes accurately, or game them to get faster resolution? Tune.
    - Does the agent acknowledge gaps specifically in EXPLANATIONs, or generically? Tune.
    - Does the standing prompt's accumulated augmentations cause instruction-skipping at length? Measure token count; refactor if approaching limits.
    
    ~5 days. This is the highest-leverage week of v1. Treating it as "step 13 also iterate" produces brittle agents.
14. **Real-world testing on 3-5 representative workspaces** — different problem types (saas product, research direction, architecture decision). Observe failures across the full cycle. Fix protocol/prompts/UI. ~3 days.
15. **Iterate** — add MCP layer only after 5–10 real deliberations have surfaced clear shortcomings of the manual+CLI path.

**Total: ~5-6 weeks for v1.** Up from ~4 weeks in v0.6 estimate, but with much higher confidence in v1 actually working when real users try it.

The key changes from v0.6: the manual protocol exercise (step 3) and vertical slice milestone (step 5) catch problems early, before they're built on top of. The dedicated prompt-iteration week (step 13) treats prompt quality as the load-bearing concern it is. The permission broker is deferred to step 11 and ships disabled by default — it's the highest-risk piece of v1 infrastructure for the smallest fraction of actual deliberation work.

The conductor + UI are the only real code. Everything else is Markdown, prompts, templates, and YAML.

---

## 15. Open Questions Register · 🟢 Settled (v0.2 — bucketed)

The register is organized into three buckets reflecting status as of v0.16. Resolved questions retain their entries with the resolution noted; v2 deferrals state the explicit reason and revisit trigger.

### A. Resolved (decisions committed; entries kept for audit)

| ID | Question | Resolution |
|----|----------|------------|
| OQ-1 | Exact section list per move type | **Resolved.** Documented in §5 as of v0.12; templates pending in §8 but the section structures are settled. |
| OQ-7 | How does the validator handle structurally-correct-but-substantively-empty moves? | **Resolved.** Validator runs section-presence check only in v1; emptiness/quality is escalated to human review through the "two retries then flag for review" path (§5 soft enforcement). Substantive emptiness becomes a human-review queue item, not a protocol violation. |
| OQ-9 | Cross-project reuse mechanism for `/protocol` | **Resolved.** Git submodule is discouraged (sync complexity); the answer is `quorum fork` for new workspaces from a template, plus `quorum refresh-defaults` for routing-defaults. For the protocol files themselves, users start fresh per workspace; protocol stability is a v1 priority. |
| OQ-10 | Rollback when an agent violates a prohibition | **Resolved.** Validator catches via `move_outcome: rejected`; agent gets one retry with explicit feedback; second failure flags for human review. The original deliberation file is not rolled back — invalid moves never get appended. See §5 soft enforcement. |
| OQ-12 | UI detection of conductor running / not / crashed | **Resolved.** PID file at `/runtime/conductor.pid` is the source of truth (§1.6). UI polls PID file existence + `kill -0 <pid>` health check via filesystem watcher. Status indicator: green / yellow / red in workspace header. |
| OQ-13 | Multiple workspaces — switch between, or one per UI instance? | **Resolved.** One workspace per UI instance in v1. Each workspace has its own UI server on its own port. Users who want multiple workspaces open run multiple UI instances. v2 may add a workspace switcher. |
| OQ-14 | User edits a deliberation file in text editor while UI is open | **Resolved.** UI's file-watcher detects the change and re-renders; if conductor is mid-invocation on that deliberation, the human edit lands and is preserved (file system is the source of truth). Race window is sub-second; v2 may add optimistic locking. |
| OQ-15 | UI "draft" mode for human responses | **Resolved.** Submit-only in v1. Drafts add UI complexity and edit-during-draft race conditions; not worth it for first version. The text editor in the response form holds local state until submit. |
| OQ-16 | Upstream URL for routing-defaults.yaml | **Resolved.** Anthropic-hosted GitHub repo (`anthropic-quorum/routing-defaults`), versioned releases with semver. `quorum init` and `refresh-defaults` fetch the latest release tag. v1 ships an offline fallback bundled with the install. |
| OQ-17 | How frequently to prompt user for `quorum refresh-defaults` | **Resolved.** On `quorum init` only by default. The defaults file ages slowly; user-driven refresh is the right v1 posture. v2 may add age-based nudges if usage shows defaults drift matters. |
| OQ-18 | Mixed-transport batches (CLI + manual) — proceed or wait? | **Resolved.** CLI invocations proceed in parallel; manual handles enter their inbox immediately and the deliberation tracks each independently. The deliberation transitions to its next state when *all* expected moves arrive, regardless of when each was authored. |
| OQ-19 | `move_outcome` events: auto-inferred or explicitly recorded? | **Resolved.** Hybrid. Validator emits explicit `move_outcome: validated` / `rejected` immediately. "Used in synthesis" / "ignored in synthesis" is auto-inferred from subsequent SYNTHESIS moves' `Reconciles` field. |
| OQ-20 | Override mechanism for fitness ratings | **Resolved.** Both. Settings → Routing panel surfaces fitness as a sortable matrix (handle × role) with editable cells; raw YAML editor is also available. Edits write to a per-workspace override file that takes precedence over routing-defaults (so refreshes don't clobber). |
| OQ-21 | Bootstrap blocks immediately on requirements gaps — fix problem statement or answer in #0001? | **Resolved.** Answer in #0001 by default. The problem statement is the *seed*, not a contract; clarifications belong in deliberation. UI shows a soft hint "you might also want to update problem-statement.md" as an option, not a requirement. |
| OQ-23 | User edits problem-statement.md after starting | **Resolved.** Edit logged as `problem_statement_modified` event. System does NOT re-bootstrap. If the change is material, the user issues an INTERJECTION (§12.5) referencing the edit. The audit trail honestly preserves the change with timestamp. |
| OQ-24 | Default UI port | **Resolved.** Port 3737. Configurable via `config.yaml` under `ui.port` for users with conflicts. `quorum init` probes the port and picks a free one in the 3700-3799 range if 3737 is taken. |
| OQ-25 | Archive includes events.jsonl? | **Resolved.** Yes by default; events log is debugging context the user usually wants. `quorum archive --no-logs` strips it for users who consider it private. |
| OQ-32 | Cloud-sync compatibility | **Resolved.** Warn against in v1. `quorum init` detects common cloud-sync paths (Dropbox, iCloud, Google Drive) and prints a warning recommending a non-synced location. User can proceed; the warning is not a refusal. |
| OQ-36 | Deputy can also issue QUESTIONs? | **Resolved.** Yes. A deputy might genuinely need clarification before deciding. The cascading-deputies cap (§10.4 `max_consecutive_deputies: 3`) bounds the depth. |
| OQ-37 | DECIDED_PROVISIONALLY allowed for downstream chaining? | **Resolved.** Yes — but downstream deliberations that depend on a provisional decision are flagged for cascade review on override. UI shows the dependency chain. |
| OQ-40 | Partial forks (fork including some prior decisions) | **Resolved.** No in v1. `quorum fork` copies problem statement + participants + routing-defaults; deliberations and decisions are fresh. Partial forks are an interesting v2 feature triggered by user demand. |
| OQ-42 | Manifest templates: shipped curated set or user-created? | **Resolved.** Both. v1 ships five curated templates (saas-product, research-direction, architecture-decision, coding-plan, strategic-decision). User-created templates can be saved to `/protocol/manifest-templates/` for workspace reuse; cross-workspace template registration is v2 (DO-4). |
| OQ-43 | Competing MANIFEST_REVISIONs | **Resolved.** Through normal deliberation. The meta-deliberation about the manifest can have multiple PROPOSAL moves; standard critique/synthesis/decision flow applies. |
| OQ-44 | Closing summary as artifact or meta-artifact? | **Resolved.** Meta-artifact. Always produced regardless of manifest contents; lives at `/quorum/closing-summary.md`. The closing ceremony's DECISION on the final meta-deliberation produces it. |
| OQ-45 | Artifact production scheduling order | **Resolved.** Dependency depth first (deepest dependencies first), tied by manifest declaration order. Specifier handle availability is a tie-breaker only when scheduling is otherwise ambiguous. |
| OQ-46 | Artifact completion checks: scripts or natural-language? | **Resolved.** Hybrid. Common checks (sections present, length thresholds, references resolve) are machine-runnable; substantive quality ("does this actually answer the question?") is agent-verified through a `reviewer` invocation. Manifest declares both per artifact. |
| OQ-47 | Export bundle format | **Resolved.** Zip containing the artifacts directory + closing summary + ADRs + a generated INDEX.html for browsing. Standalone-HTML site is overkill for v1; users who want richer publishing convert the bundle themselves. |
| OQ-48 | Wizard runs every init or only without template? | **Resolved.** Always runs. If `--manifest-template` was specified, question 1 is pre-filled but the rest still runs. This keeps wizard behavior consistent. |
| OQ-49 | Category C settings: always confirmation dialog? | **Resolved.** Conditional. Only edits affecting currently-running invocations show the dialog; edits to Category C settings while no invocations are mid-flight commit silently with a toast notification. Reduces friction for the common case. |
| OQ-50 | Raw YAML editor: behind toggle or as panel option? | **Resolved.** Visible as a panel option labeled "Raw config (advanced)". Honest about what it is; users who don't want it ignore it. |
| OQ-51 | Multi-tab settings sync via WebSocket | **Resolved.** Yes, in scope for v1. Same WebSocket infrastructure as activity feed; settings changes broadcast to all open tabs. |
| OQ-52 | Wizard re-run overwriting Category A settings | **Resolved.** Refused. Wizard shows but disables Category A questions on re-run; user must fork to change them. |
| OQ-53 | INTERJECTION cascade propagation order | **Resolved.** Sequential by deliberation ID with parallel within independent dependency chains. Conductor walks the dependency graph: deliberations with no dependencies between them process the interjection in parallel; chained dependencies process in chain order. |
| OQ-54 | "Soft override" — agents push back before finalizing | **Resolved.** No in v1. Adds expressive power but complicates the model and user mental model. If the user wants pushback before deciding, they REOPEN after seeing agent input. v2 may revisit if usage shows demand. |
| OQ-56 | DROP on a deliberation with dependents | **Resolved.** Block the DROP unless `--cascade` flag is added (UI offers it as a "drop and flag dependents for revision" option). Prevents accidental orphaning. |
| OQ-58 | Validator citation strictness | **Resolved.** Strict by default. Every workspace-specific claim in EXPLANATION must cite. Lenient mode is a per-workspace setting for users who find the rejection rate too high; default stays strict. |
| OQ-59 | Multiple sequential CLARIFYs mid-BLOCKED | **Resolved.** Yes, allowed. Each CLARIFY → EXPLANATION cycle pauses the original block; user issues ANSWER when ready. |
| OQ-60 | EXPLANATION's "What I couldn't find" — machine-actionable? | **Resolved.** Yes. The field's contents are surfaced as suggested follow-up actions in the UI: "spawn a new deliberation about this gap" or "add a context source covering this." User-driven, not automatic. |
| OQ-61 | CLARIFY text-span anchoring | **Resolved.** Hybrid: selected text + nearest stable anchor (move ID + section heading + character offset within section). Validator detects when source text changes and notes anchor drift in the EXPLANATION. |
| OQ-63 | Documents panel: third-party connectors in v1? | **Resolved.** No. v1 is upload-only. Auth complexity for Google Docs / Notion / Confluence is substantial; deferred to v2 where it deserves proper design. |
| OQ-65 | Oversize repo handling | **Resolved.** v1: refuse repos >250MB by default; `--allow-large` override at registration accepts the digestion cost. Smarter handling (sample-based digestion, sub-repo selection) is a v2 enhancement (logged: OQ-65v2). |
| OQ-66 | URL caching: respect robots.txt? | **Resolved.** Yes. Conservative — respect robots.txt and add a per-domain rate limit (1 req/sec default, configurable). |
| OQ-67 | Asymmetric standing context citation | **Resolved.** Yes. Same anti-confabulation logic as EXPLANATION: workspace-specific claims need citations; standing knowledge is permitted but must be tagged as such ("based on my prior knowledge of your environment, X" vs "based on workspace context, Y"). |
| OQ-68 | Mid-stream context addition retroactive? | **Resolved.** Only future invocations. Prior moves stand under their original context. UI shows "added on date X" badge on context sources to make this visible. |
| OQ-69 | Manifest-template-tunable allowlists | **Resolved.** Yes. Manifest templates ship with permission-allowlist hints (e.g., coding-plan template suggests richer read-allowlist for source verification). User can accept or modify during setup. |
| OQ-71 | Permission denials count against quota? | **Resolved.** Yes. The invocation consumed tokens to produce the request; counts against per-handle daily quota. |
| OQ-75 | `quorum doctor` warns on duplicate binary paths | **Resolved.** Yes. Doctor compares resolved binary paths across registered handles and warns if two handles point to the same binary (likely accidental duplicate registration rather than distinct accounts). |

### B. Open — needs design before v1 ship

These are genuinely open and need design work before v1, not deferrable.

| ID | Question | Direction / status |
|----|----------|--------|
| OQ-2 | How does the conductor handle CLI agents that don't cleanly exit (long-running, interactive)? | **Direction:** conductor enforces a per-invocation timeout (default 5 min, configurable). On timeout, SIGTERM then SIGKILL after grace; partial output preserved in `/runtime/streams/failed/`; `agent_invocation_timeout` event logged; substitution policy applies as per §10.3. Refinement of the existing failure-handling mechanism. |
| OQ-3 | Exact format of `participants.md` (CLI command, flags, env vars) — full spec | **Direction:** §3.5 specifies columns; the CLI command field is a literal command-line string with `{prompt_file}` placeholder substitution. Env vars come from the parent shell environment by default; per-handle overrides go in an optional `env` field. Full spec written as part of build step 1. |
| OQ-4 | Deliberation sub-deliberations: simple parent/child, or richer DAG? | **Direction:** simple parent/child for v1 via the `parent` and `children` frontmatter fields (already in §8 template). Richer DAG (a deliberation referencing multiple parents) is plausible later but adds rendering and dependency-resolution complexity not justified for v1. |
| OQ-5 | Agent goes offline mid-loop (network drops) — how does conductor detect and recover? | **Direction:** same path as agent timeout (OQ-2). Network drops manifest as the CLI process either failing fast (clean exit with error) or hanging until timeout. Both cases produce an `agent_failed` event and trigger §10.3 substitution policy. |
| OQ-8 | `BLOCKED_ON_EXTERNAL` sub-states — distinguish further? | **Direction:** not in v1. The state captures "halted pending non-human dependency"; the deliberation's text explains what specifically. Sub-states (waiting on data fetch vs API vs background job) add machinery for marginal benefit. Revisit if usage shows a recurring pattern that benefits from machine-actionable distinction. |
| OQ-11 | Move card visual design — typography, density, color treatment | Pending §9.5 visual spec — to be addressed during UI shell build (step 3 of §14). Not blocking; the visual designer iterates against real moves once the shell is up. |
| OQ-22 | Repo tech-stack detection for digestion quality | **Direction:** layered heuristic. Layer 1: detect manifest files (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, etc.) and infer language/framework. Layer 2: pass detected tech stack as context to the digester agent so it knows what conventions to look for. Layer 3: digester reads top-level README if present. The digester agent is doing the actual quality work; the heuristic just orients it. Concrete spec written during build step 5. |
| OQ-31 | User moves workspace folder while conductor is running | **Direction:** conductor records absolute paths in `state.yaml` at startup. Periodic check (every command) verifies the workspace folder is at its expected path; if moved, conductor pauses with reason `workspace_folder_moved` and surfaces an error: "workspace was at X, now at Y; restart conductor from new location." User restarts; new path is recorded. PID file is recreated cleanly. |

### C. Deferred to v2+ (need usage data or are explicit v2 features)

| ID | Question | Why deferred |
|----|----------|--------------|
| OQ-6 | MCP auth model — per-agent tokens? | MCP is v4 design; auth model designed then |
| OQ-26 | LLM-narrated resume briefing | DO-6; needs usage data on whether structured briefing alone suffices |
| OQ-27 | Auto-resume firing while user is away | Needs usage to see if this matters in practice |
| OQ-28 | "Soft" unavailability handling (handle slow but available) | Needs usage data on degraded performance frequency |
| OQ-29 | "Substituting_for" annotations propagation forward | Needs usage to see if downstream agents benefit |
| OQ-30 | Quota tracking accuracy (token-based vs invocation-based) | Needs cross-CLI usage data |
| OQ-33 | Multi-user same-machine | Needs to actually become a use case |
| OQ-34 | Richer presence detection | Heartbeat / OS / calendar — premature without usage signal |
| OQ-35 | Override-as-learning-signal for deputy thresholds | DO-7; needs ~100 deputy decisions to calibrate |
| OQ-38 | Decider panel: sequential vs voting | Voting is richer but expensive; sequential works for v1 |
| OQ-39 | Max wall-clock for autonomous mode | Logged for after testing |
| OQ-41 | Autonomous → interactive: retroactive deputy review | Needs usage data on conversion patterns |
| OQ-55 | STEER influence tracking in audit trail | Needs usage data on whether steers materially shape outcomes |
| OQ-57 | Agent-to-agent STEER | DO candidate; needs usage data on cross-agent quality complaints |
| OQ-62 | Multi-user shared workspaces | Explicit v2 feature |
| OQ-70 | Permission shim for coarse-capability CLIs | Substantial extra code; v2 if demand emerges |
| OQ-72 | Cross-workspace allowlist reuse | Part of DO-4 (cross-workspace registers) |
| OQ-73 | Agent-declared vs pattern-classified permission stakes | Pattern-based is auditable; revisit if usage shows pattern is too rigid |
| OQ-74 | Multi-account quota grouping | v2; needs `account_id` schema work |
| OQ-76 | Workspace tag-based handle filtering | v2 nice-to-have for multi-account UX |
| OQ-65v2 | Smart oversize-repo handling (sample-based, sub-repo selection) | v2 enhancement once v1's refuse-by-default reveals real demand patterns |

---

## 16. Glossary (in-doc, mirrors `/registers/glossary.md` once instantiated) · 🟢 Settled

To be populated as terms stabilize. Initial entries:

- **Deliberation** — a single question being worked through to a decision; one file, one lifecycle.
- **Move** — a typed contribution within a deliberation.
- **Conductor** — the dispatcher script that invokes CLI agents based on inbox state.
- **Decider** — the participant authorized to issue DECISION moves on a given deliberation.
- **Standing prompt** — the base prompt every CLI agent invocation receives.
- **Move card** — the UI representation of a move: structured, labeled-section card. Not a chat bubble.
- **Lifecycle marker** — a file in `/runtime/active/` that signals an agent invocation is in progress. The UI watches these to render "composing" state.
- **Activity feed** — the right-pane chronological log of cross-deliberation events, sourced from `events.jsonl`.
- **Composing state** — a move card rendered while its agent is still generating (marker exists, content streaming).
- **Handle** — a stable identifier for a participant binding a CLI binary, a specific model, and a fitness profile (e.g., `@claude-opus`).
- **Routing** — the conductor's process of selecting which handle should make the next move for a given role.
- **Fitness rating** — a 0-3 score per (handle, role) pair indicating how well-suited a handle is for that role.
- **Routing-defaults** — the system-shipped fitness ratings file, refreshed from upstream on `quorum init` or explicit `quorum refresh-defaults`.
- **Bootstrapper** — the special role for the agent that reads the problem statement and creates the first deliberation.
- **Deferred optimization (DO-N)** — a deliberately postponed enhancement, tracked with explicit revisit triggers in §19.
- **Workspace** — a single `/quorum/` directory and everything in it; one workspace per problem/project.
- **Workspace state** — INITIALIZED / READY / ACTIVE / PAUSED / ARCHIVED. Distinct from individual deliberation status.
- **Problem statement** — `/quorum/problem-statement.md`, the seed input that gates conductor start.
- **Health check** — `quorum doctor`'s test of whether each registered handle is actually invokable.
- **Resume briefing** — the structured summary shown when a workspace is resumed, listing active deliberations, what changed while paused, and suggested next actions. Built from frontmatter, inbox, and events.jsonl — no LLM needed.
- **Substitution** — when an unavailable handle is replaced by an alternative under the unavailability policy. Always logged, always frontmatter-marked in the resulting move (`substituting_for: @original-handle`), always preserves provenance.
- **Unavailability policy** — user-configured rules for what happens when a routed handle can't fulfill its task. Three positions: `strict` (default — block, don't substitute), `substitute_with_floor` (substitute above fitness threshold), `substitute_aggressively` (any qualified handle).
- **Resume policy** — user-configured rules for whether the conductor auto-resumes when blocking conditions clear. Default `manual` (explicit `quorum resume` only); options `auto_on_recovery` and `auto_scheduled`.
- **Error classifier** — the conductor's mapping from raw CLI/network errors to actionable categories (quota_window_exhausted, service_outage, network_failure, etc.). Drives substitution and retry behavior.
- **Quota awareness** — routing logic considers remaining quota per handle, not just fitness. Reserves expensive handles for high-fitness-required moves; prefers substitutes when budget is tight.
- **Daemonized** — `quorum start` runs the conductor detached from the terminal by default. Closing the terminal does not affect it. `--foreground` opts out for debugging.
- **Lockfile / PID file** — `/quorum/runtime/conductor.pid` (and `/runtime/ui.pid`) hold the running process's PID. Used both to find the running process and to refuse double-start. Cleaned up on graceful shutdown.
- **Crash recovery** — automatic detection (on every `quorum` command) that the conductor is not running despite `state.yaml: ACTIVE`. Marks workspace PAUSED with reason `crash_recovery`, sweeps stale runtime markers, preserves partial outputs.
- **Stakes** — required field on every QUESTION move classifying its consequence: `trivial`, `tactical`, `strategic`, or `irreversible`. Drives human-timeout policy.
- **DEPUTY_DECISION** — a provisional decision made by a designated agent on the human's behalf when the human-timeout policy fires. Always reversible; needs confirmation on the human's return; never used for `irreversible` stakes.
- **Deputy decider** — a handle authorized to issue DEPUTY_DECISION moves on the human's behalf. Configured as an ordered list in `config.yaml`; first available + healthy + within-quota wins.
- **Provisional / confirmed / overridden / expired** — the four lifecycle states of a DEPUTY_DECISION. Provisional on creation; confirmed/overridden by explicit human action; expired by inaction past the override window.
- **Visible accumulation** — the design principle that automation must never become invisible; pending deputy decisions surface persistently in the UI to prevent gradual drift from user intent.
- **Presence inference** — the conductor's heuristic for whether the human is "around," based on `last_human_activity_at` plus a configurable grace window. Defers timers when presence is recent.
- **DECIDED_PROVISIONALLY** — deliberation status when a DEPUTY_DECISION has resolved it but awaits human ratification.
- **Interactive mode** — default workspace mode; human is the source of authority, agents collaborate, human is decider and final ratifier.
- **Autonomous mode** — opt-in workspace mode with no human in the loop; agents drive entirely; a designated decider panel issues real (not provisional) DECISIONs. Used for sanity-check brainstorms, calibration runs, comparative experiments, throwaway/fun work.
- **Decider panel** — ordered list of agent handles authorized to issue DECISION moves in autonomous mode; first available + healthy + within-quota wins.
- **COMPLETED_AUTONOMOUS** — workspace state when an autonomous run has finished; open for review, can convert to interactive or archive.
- **Fork** — `quorum fork` creates a new workspace seeded from another's problem statement and configuration. Fresh deliberations and decisions; provenance recorded. Enables comparative experiments and the interactive→autonomous escape hatch.
- **Mode conversion** — autonomous → interactive is allowed (human engages with autonomous output); interactive → autonomous is not allowed mid-stream (must fork instead).
- **Outcome manifest** — the workspace's declaration of what artifacts must exist when work is done, with completion checks, quality gates, dependencies, and production patterns. The answer to "when is the end?" Lives in `outcome-manifest.md`. Always established via deliberation #0001.
- **Artifact** — an intended output of the workspace, declared in the manifest. Distinct from decisions (protocol byproducts) and tasks (derivative work items). Lives in `/artifacts/`.
- **Production pattern** — how a manifest artifact gets written: `synthesis-aggregated` (woven from multiple deliberations' syntheses), `specifier-authored` (single agent in specifier role writes it end-to-end), or `cross-cutting` (authored last, summarizing the whole workspace).
- **Quality gates** — workspace-wide completion criteria beyond per-artifact checks (no unresolved DEPUTY_DECISIONs, no BLOCKED deliberations, no provisional ADRs, etc.). All must clear before closing ceremony.
- **Closing ceremony** — the deliberate transition `ACTIVE → COMPLETED` via a final meta-deliberation with closing synthesis and decider DECISION. Not a silent state change.
- **Manifest template** — starter manifest for common project shapes (saas-product, research-direction, architecture-decision, coding-plan, strategic-decision). Selected at init or proposed by bootstrapper. Edited to fit the actual project.
- **ARTIFACT_REVISION** — move type that supersedes a previously-completed artifact when subsequent decisions warrant changes. Prior version preserved; audit trail honest about evolution.
- **Workspace setup wizard** — five-question opinionated flow at workspace init that fills ~80% of useful configuration via sensible defaults.
- **Settings panels** — sidebar UI organized by user intent (Participants / How decisions get made / When agents are unavailable / etc.), not by config-file structure. Adapts to context (autonomous vs interactive shows different panels).
- **Frozen / Live / Live-with-effects** — three categories of setting editability. Frozen = locked at first start, requires fork to change. Live = takes effect immediately, no in-flight disruption. Live-with-effects = takes effect immediately but observable on in-flight work; UI shows confirmation/indicators.
- **Settings vs lifecycle operations** — settings change *how the workspace behaves* (substitution policy, decider, quotas); lifecycle operations change *what the workspace is or where it lives* (fork, archive, refresh-defaults). Settings live in UI; lifecycle operations remain CLI commands (UI buttons may invoke them but they're not toggles).
- **Raw YAML editor** — Tier 3 escape hatch for power users; schema-validated browser-based editor for everything not surfaced in panels.
- **INTERJECTION** — human-initiated move to inject new information mid-stream into one or more deliberations or artifacts. Force levels: advisory / strong / overriding.
- **OVERRIDE** — human-initiated move (decider only) that ends a deliberation early with a unilateral decision. Cancels in-flight invocations on that deliberation. Preserves unconsidered moves for audit trail.
- **REOPEN** — human-initiated move (decider only) that resumes work on a previously DECIDED deliberation. Prior decision preserved as superseded; triggers ARTIFACT_REVISION cascade on dependent artifacts.
- **DROP** — human-initiated move (decider only) that abandons a deliberation without resolving. Status → ABANDONED.
- **STEER** — human-initiated advisory move that augments prompts for affected agents without changing protocol state. v1: human-only.
- **ABANDONED** — deliberation status resulting from DROP. Distinct from DECIDED (resolved) and ARCHIVED (closed-and-kept). Partial moves preserved.
- **Proactive human voice** — the capability for the human to *initiate* (not just respond to) protocol activity through INTERJECTION, OVERRIDE, REOPEN, DROP, and STEER. Structurally treats the human as a peer participant rather than a constrained responder.
- **Disruption strategy** — per-move-type policy for what happens to in-flight invocations when the human intervenes. Advisory/strong INTERJECTION and STEER wait; OVERRIDE and DROP cancel immediately.
- **CLARIFY** — human-initiated move requesting explanation about a concept, prior decision, or text span. Does not progress decision work. Allowed on DECIDED and ARCHIVED workspaces. Pauses BLOCKED_ON_HUMAN if the user is seeking clarification on a question they were supposed to answer.
- **EXPLANATION** — agent response to a CLARIFY. Grounded in actual workspace content with required citations. Visually subordinate to core decision-flow moves. Required `What I couldn't find` section forces honest acknowledgment of gaps.
- **Explainer** (role) — agent role for responding to CLARIFY moves; default fitness mirrors `domain_expert`. Standing prompt is strict about grounding (citation per claim) and gap acknowledgment.
- **Grounded explanation** — an EXPLANATION whose workspace-specific claims are each cited to specific moves, files, or artifacts; whose general knowledge is visually distinguished from workspace claims; and whose gaps are explicitly enumerated. The protocol's anti-confabulation guarantee.
- **Alternatives capture** — the strengthened required sections in PROPOSAL ("Alternatives I considered"), SYNTHESIS ("Alternatives weighed"), and DECISION ("Path not taken"). Exists to ground future EXPLANATIONs in real data about what was actually weighed.
- **Visual subordination** — the design pattern for EXPLANATION (and similar auxiliary moves): rendered inset, muted, with citations as links and a "Hide explanations" toggle. Signals "this is meta context, not part of the decision flow."
- **Context surface** — the `/quorum/context/` directory and the four source types it accepts (repos, documents, web, notes). Managed via UI panels, not CLI args. The economic foundation that makes stateless agents affordable.
- **Context digest** — agent-produced summary of a repo, large doc, or other context source. Produced once, reused across many invocations. **Default model scales with source relevance** (high → Opus, medium → Sonnet, low → Haiku/Flash) since digest quality compounds across all downstream invocations. User can override at digestion time per-source or globally via `context.digester_defaults`.
- **Standing context bundle** — the small, always-included set of context every invocation sees: problem statement, manifest, glossary, active open questions, summarized decisions, all notes. Bounded in size (~3-10K tokens).
- **Relevant context** — deliberation-scoped declaration of which repos / docs / URLs / notes the deliberation needs. Bootstrapper proposes; user can edit. Drives per-invocation context bundling.
- **Raw vs digested context** — small docs and notes are included raw; large repos and docs are digested to summaries. Threshold is roughly 5K tokens (configurable).
- **Freshness indicator** — UI signal of how stale a digest or cached URL is (green <7d, yellow <30d, red older). Surfaced in agent prompts to enable honest acknowledgment of staleness.
- **On-demand reading** — when an agent reads a specific source file or fetches a specific URL within an invocation, scoped to immediate need. Logged in events.jsonl for monitoring.
- **Cost discipline** — design principle: every byte of context is digested, declared, or on-demand with logging. No invocation accidentally pulls unbounded source. Cheap-model defaults for housekeeping work. Per-workspace cost ceiling available.
- **Permission allowlist / denylist** — pattern lists in `config.yaml` that drive in-band auto-approval (allowlist) and hard refusal (denylist) of agent CLI shell operations. User-editable via Settings → Permissions panel.
- **Permission broker** — the conductor's role in handling out-of-allowlist requests: detect (parse CLI stdout or structured output), pause CLI, surface in UI, await user response, route response back to CLI stdin.
- **Permission capability** — per-handle attribute (`fine_grained` / `coarse` / `none` / `n/a`) recording whether a CLI supports allowlist control. Affects move-routing eligibility.
- **BLOCKED_ON_PERMISSION** — deliberation sub-state when an agent CLI is awaiting user permission for a shell operation. Sub-state of BLOCKED_ON_HUMAN.
- **Stakes (permission)** — same four-level classification as §10.4 questions (trivial / tactical / strategic / irreversible), but classified by pattern-matching the requested command rather than agent self-report. Drives auto-approval policy. Irreversible never auto-approves.
- **Account label** — optional free-form string ("Work", "Personal", "Org-X") on a handle for UI grouping and badging when multiple installations of the same CLI are registered. Display-only; no effect on routing or protocol.
- **Multi-account registration** — registering the same CLI multiple times against different account-specific binaries (e.g., `claude-work` and `claude-personal`). Each becomes its own batch of handles with independent quota tracking, distinguishable by Account Label in the UI.
- **Fitness inheritance** — when a non-canonical handle is registered (e.g., `@claude-work-opus`), it inherits routing fitness ratings from a designated canonical handle (`@claude-opus`) via the `inherits_fitness_from` field. Generalizes to multi-account, fine-tuned variants, alternative providers, etc.
- **Summary line** — required ≤120-char field of every DECISION move; validator-enforced; mechanically concatenated into `summarized-decisions.md` for inclusion in every subsequent invocation's standing context bundle. The single most-read sentence the workspace produces; quality compounds across the workspace's life.
- **Cost ceiling** — workspace-level cap on cumulative inference cost, default $50, default ON. Conductor pauses workspace when hit; user explicitly raises, disables, or stops. Prevents cost surprises.
- **Permission broker (v1 default OFF)** — the conductor's mechanism for handling out-of-allowlist shell access requests from agent CLIs. v1 ships with this disabled by default; users opt in via Settings → Permissions if their workflow requires it. When disabled, agents have only allowlist-restricted access and out-of-allowlist requests fail cleanly.
- **Vertical slice milestone** — build step 5: the first end-to-end deliberation run, using minimal UI, against a real problem. Purpose is to validate the protocol behaves as designed before building UI on top of it. Findings update PROTOCOL.md, standing prompt, validator, and conductor before proceeding.
- **Manual protocol exercise** — build step 3: running the protocol manually for one deliberation before any conductor code is written. Cheapest possible reality check; catches design issues before they're encoded in software.

---

## 19. Deferred Optimizations Register · 🟢 Settled

A permanent register of optimizations we've deliberately deferred, with the explicit conditions under which we'd revisit them. This prevents re-litigating closed decisions while preserving the reasoning.

### DO-1: Warm-pool process management

**Description:** Pre-started CLI processes idling, ready for instant invocation. Eliminates the 2–4 second cold-start latency per turn.

**Why deferred:** Most CLI agents don't cleanly support "send a single prompt to an already-running process" — each invocation requires a new process. Solution 3 (UX-level latency hiding via progressive status messages) covers most of the perceptual cost. Solution 2 (parallel invocation) reduces wall-clock impact further.

**Triggers for revisit:**
- (a) Deliberations consistently exceed 50 invocations, OR
- (b) Aggregated `cold_start_ms` from logs exceeds 20% of total wall-clock time, OR
- (c) User-reported friction with system responsiveness despite §9.6 latency hiding, OR
- (d) Long-running brainstorming sessions (multi-hour, hundreds of invocations) become a primary use case (this is the trigger Rohan's gut points to).

**Cost when revisited:** Substantial. Requires per-CLI implementation work (each CLI behaves differently), plus new failure modes (what if the warm process dies, gets stale, misbehaves). Worth it only when the savings are large.

### DO-2: Dynamic per-move routing (LLM-driven)

**Description:** Replace static fitness tables (Layer 3 in §3.6) with a fast/cheap model that reads each deliberation's context and picks the best handle for the next move dynamically. **This is the north-star architecture for routing.** Static fitness is the v1 stepping stone; dynamic routing is the long-term destination.

**Why deferred:** Adds an LLM call per turn. Adds a new failure mode (router picked badly). Static tables are 80% as good with 0% of the complexity. We need observation data before we can train or tune a router properly.

**Triggers for revisit:**
- (a) Sufficient log data accumulates (~500 deliberations across diverse problem types) to evaluate routing quality, OR
- (b) Static fitness defaults are demonstrably suboptimal — high `move_outcome: revised` rates correlated with specific (role, handle) pairs, OR
- (c) Models proliferate beyond what static tables can reasonably cover (>20 handles), OR
- (d) Users frequently override workspace routing, suggesting the static defaults aren't matching real preferences.

**Path forward:** The events.jsonl schema (§10.5) is designed to make `routing_decision` × `move_outcome` cross-referencing easy. When the trigger fires, the data is already there.

### DO-3: Context-source automatic staleness detection and quality scoring

**Description:** v1 implements digestion (§1.8) — every repo, doc, and URL is digested once and reused. The deferred piece is the *automatic* layer: detecting when a digest has materially diverged from current source (without re-digesting), scoring digest quality before it's used, and surfacing "this digest looks thin for the question being asked" warnings to the user.

**v1 has:** Manual freshness indicators (last-digested-at), user-triggered re-digestion, prompt-side acknowledgment that digests may be stale.

**v1 does not have:** Automatic comparison of digest vs current source to detect drift; quality scoring of digests against deliberation needs; suggestions to re-digest based on observed agent behavior (e.g., "agents keep on-demand-reading these specific files — your digest is missing what they need").

**Why deferred:** The signals needed (events.jsonl on `on_demand_file_read`, `digest_age_at_use`) exist in v1; we don't yet know which patterns predict trouble. Need real usage data.

**Triggers for revisit:**
- (a) Users report making decisions on stale digests without realizing it, OR
- (b) Patterns of high `on_demand_file_read` correlate with low-quality moves (catchable in events log), OR
- (c) Multi-month workspaces become common and digest-staleness is a recurring pain point.

### DO-4: Cross-workspace shared registers and context

**Description:** Allow multiple workspaces to share `glossary.md`, `participants.md`, `routing-defaults.yaml`, and **context sources** (especially repos and notes) via symlinks or a "user profile" directory. Useful for power users running many parallel workspaces in the same organizational context.

**v1 has:** Per-workspace context. If a user starts three workspaces in their org, they re-add the same repos three times.

**Why deferred:** Premature. Most users will have one or two workspaces in v1. Sharing introduces sync complexity (when one workspace's view of a repo digest evolves, what happens to the others?) that isn't worth it yet.

**Triggers for revisit:**
- (a) Users report friction re-adding the same context across many workspaces, OR
- (b) A "global config" or "org profile" concept emerges naturally from usage patterns, OR
- (c) The "many parallel brainstorms in the same org" use case becomes common.

### DO-5: Agent-driven protocol evolution

**Description:** Agents can issue moves that propose changes to PROTOCOL.md itself, going through normal deliberation. Currently protocol changes are author-driven.

**Why deferred:** The protocol needs to stabilize before it can evolve through its own mechanisms. Premature self-reference is a source of confusion (see the OQ about debating the protocol while bound by it).

**Triggers for revisit:**
- After PROTOCOL.md reaches v0.3 or later (i.e., it's been through real revisions), AND
- Users start wanting to extend it themselves.

### DO-6: LLM-narrated resume briefing

**Description:** Augment the structured resume briefing (§1.6) with an LLM-generated narrative summary: "Your last session focused on pricing. Three agents converged on usage-based pricing, but Gemini raised a concern about competitor positioning that wasn't resolved. You were about to answer Q3 when you paused."

**Why deferred:** The structured briefing covers 90% of the value with no LLM call. Narrative summary is icing. Adds an LLM call at every resume — minor cost, but unnecessary in v1.

**Triggers for revisit:**
- (a) Users report the structured briefing isn't enough to mentally re-engage after long pauses (>1 week), OR
- (b) Sessions routinely span weeks/months and the activity log becomes too long to scan, OR
- (c) The system gets used by collaborators-onboarding-into-an-existing-workspace use case, where someone needs to "catch up" without having lived through prior sessions.

### DO-7: Adaptive stakes classification & deputy thresholds

**Description:** Currently agents self-classify QUESTION stakes (`trivial`/`tactical`/`strategic`/`irreversible`), and the human implicitly grades that classification through confirm/override decisions on resulting deputy moves. Build a learning loop: track per-handle stakes-misclassification rates and override rates on deputy decisions, then adjust either (a) which handles are trusted to author questions, (b) per-stakes wait timers, or (c) a per-user threshold that biases deputy decisions toward conservative classification.

**Why deferred:** No data yet. The events.jsonl schema (§10.5) is designed to make this feasible — `human_timeout_armed`, `deputy_decision_issued`, `deputy_decision_overridden` events plus QUESTION stakes form a labeled dataset. We need real usage to calibrate.

**Triggers for revisit:**
- (a) Users report deputy decisions getting overridden too often (low confidence in automation), OR
- (b) Users report deputy decisions feeling too conservative (waiting too long on questions they didn't care about), OR
- (c) Sufficient log data accumulates (~100 deputy decisions across a user's workspaces) to evaluate calibration meaningfully.

**Path forward:** Like DO-2 (dynamic routing), this is a learning-from-logs feature. The schema is already prepared.

---

## 20. Changelog

- **2026-04-27 · v0.1** — Initial structure created from brainstorming session. Sections 1–7, 9, 12–14 settled. Sections 8, 10, 11 in progress. Section 15 (open questions) seeded. Sections 16 (glossary) pending.
- **2026-04-27 · v0.2** — Major revision after niche clarification and UI commitment.
  - **§1** refined: niche tightened to collaborative reasoning; use cases reordered (brainstorming/spec-derivation primary, secondary applications surfaced).
  - **§1.5** added: explicit niche & scope statement (own reasoning, don't own code-execution coordination), comparison table to coding-coordination tools, growth path, handoff to execution.
  - **§7** updated: `/ui/` and `/runtime/` directories added; `/runtime/` is gitignored ephemeral state.
  - **§9** restructured: layers reframed as capabilities not version milestones; UI promoted to v1 (was v3). Transport-type table added.
  - **§9.5** added: UI Layer — document-first posture, three-pane layout, tech stack, decoupling rule.
  - **§9.6** added: Live Collaboration Affordances — lifecycle markers, streaming buffers, three move-card states, the activity feed.
  - **§9.7** added: Human Response Interface — structured forms (not chat input), form design pattern.
  - **§10** updated: invocation model now includes lifecycle marker management as a contract with the UI; `serve` command added; conductor crash recovery for stale markers noted.
  - **§14** updated: build order revised to ship UI in v1; ~2 weeks of focused build for v1.
  - **§15** updated: OQ-11 through OQ-15 added (UI-related open questions).
  - **§16** updated: new glossary terms (Move card, Lifecycle marker, Activity feed, Composing state).
- **2026-04-27 · v0.3** — Latency, parallelism, model selection, and routing.
  - **§3** rewritten: handles now bind (CLI + model + fitness profile); `bootstrapper` role added; explicit non-manual-routing principle.
  - **§3.5** added: full Participants Registry Schema with field semantics and rationale for separating from fitness data.
  - **§3.6** added: Routing & Model Selection — four-layer routing model (per-deliberation override / workspace override / fitness defaults / fallback), routing-defaults.yaml schema, refresh mechanism with offline fallback, routing decision visibility in activity feed.
  - **§10** rewritten: parallel invocation in v1 (Solution 2); per-deliberation file locks; routing integration in invocation algorithm; progressive status messages during cold start (Solution 3); `BLOCKED_ON_ROUTING` sub-state.
  - **§10.5** added: Structured Logging for System Improvement — full event schema, downstream analysis use cases (fitness re-rating, cost analysis, routing quality, dynamic-router training data).
  - **§13** updated: new failure mode rows for parallel contention, routing exhaustion, quota fallback, defaults-fetch failure.
  - **§19** added (Deferred Optimizations Register): DO-1 through DO-5, each with explicit revisit triggers.
  - **§16** updated: glossary entries for Handle, Routing, Fitness rating, Routing-defaults, Bootstrapper, Deferred optimization.
- **2026-04-27 · v0.4** — User workflow consolidation + scan-and-capture pass.
  - **§1.6** added: User Workflow & Workspace Lifecycle — distribution choice (git clone v0.1, package later), workspace state machine (INITIALIZED/READY/ACTIVE/PAUSED/ARCHIVED), `quorum init` semantics, agent registration ≠ invocation distinction, `quorum doctor`, problem-statement document with light structure (6-section template) and DRAFTING/READY status, READY → ACTIVE enforcement checks, --with-codebase mode (read-only context), `quorum status`, archive/unarchive lifecycle, canonical first-time user flow walkthrough.
  - **§2 heading restored** — `## 2. Conceptual Model` was accidentally deleted in a prior edit; content was orphaned. Fixed.
  - **§7** updated: added `problem-statement.md`, `config.yaml`, `.gitignore` as top-level files; added `routing-defaults.yaml` to /registers/; added `/context/` for codebase mode; added `/runtime/streams/failed/` and `/runtime/events/archive/`.
  - **§10 commands table** unified under `collab` prefix (was mixed `collab`/`conduct`); added `pause`, `archive`, `unarchive`.
  - **§14** updated to v0.3: distribution choice surfaced; CLI scaffolding step added between protocol and UI shell; build estimate revised to ~2.5 weeks.
  - **§15** updated: OQ-21 through OQ-25 added (workflow-related open questions).
- **2026-04-27 · v0.5** — Project named.
  - **Name locked: Quorum.** Reasoning captured in new §0.5 Project Identity. Doc title changed from "Multi-Agent Collaboration Hub" to "Quorum."
  - **§0.5** added: Project Identity — name, rationale (a quorum encodes both "multiple voices required" and "decisions get made"), CLI command, workspace directory convention, tagline, repo.
  - **All CLI command references** renamed: `collab init` → `quorum init`, `collab status` → `quorum status`, `conduct serve` → `quorum serve`, etc.
  - **Repo URL examples** updated: `collab-hub.git` → `quorum.git`, `~/.collab-hub/` → `~/.quorum/`.
- **2026-04-27 · v0.5.1** — Workspace directory renamed.
  - **`/collab/` → `/quorum/` everywhere.** Branding consistency with the CLI command — `quorum init` produces `/quorum/`, not `/collab/`. Initial reasoning for keeping the folder generic was overruled: the folder is the primary user surface (not hidden metadata), so it deserves the product name. Precedent: `node_modules/`, `.terraform/`, `target/` (Cargo), `vendor/` (Composer) — tool-specific folders inside projects are normal.
  - **All path references updated** throughout the doc (folder structure §7, prompts, examples, runtime paths, etc.).
  - **Event type rename:** `collab_started` → `session_started` (the prefix was just leftover branding).
- **2026-04-27 · v0.6** — Session longevity & agent unavailability.
  - **§2** updated: added fourth conceptual commitment — *the workspace is the unit of continuity, sessions are just punctuation.*
  - **§1.6** expanded: full pause-and-resume design — clean pause hygiene, resume briefing (structured summary of what changed while away, what's blocked on user, suggested actions — built from frontmatter + events.jsonl, no LLM call), `resume_policy` config (manual/auto_on_recovery/auto_scheduled, manual is default), pause-reason enumeration.
  - **§7** updated: added `state.yaml` as top-level workspace state file.
  - **§7.5** added: Workspace State (`state.yaml`) — schema, why it's separate from events.jsonl (current truth vs append-only history), update discipline.
  - **§10.3** added: Agent Unavailability & Substitution Policy — error classifier (7 categories with detection signals and default responses), three policy positions (`strict` is default — preserves quality, opt-in substitution), config schema with per-role and per-handle overrides, full substitution flow with provenance markers (`substituting_for: @claude-opus` in move frontmatter), recovery-aware blocking, quota-aware routing as new soft factor, mid-flight failure handling.
  - **§10.5** updated: new event types — `agent_unavailable`, `substitution_applied`, `blocked_on_unavailable`, `workspace_paused`, `workspace_resumed`, `auto_retry_scheduled`, `quota_threshold_crossed`. `move_appended` now includes `substituting_for` field.
  - **§13** updated to v0.3: 8+ new failure mode rows for unavailability scenarios (quota window, daily cap, service outage, network failure, subscription issue, CLI hang, mid-flight failure), pause/resume edge cases, and the "silent quality degradation" threat (mitigated by strict-by-default + always-logged-substitutions).
  - **§16** updated: glossary entries for Resume briefing, Substitution, Unavailability policy, Resume policy, Error classifier, Quota awareness.
  - **§19** updated: DO-6 added (LLM-narrated resume briefing) with revisit triggers.
  - **§15** updated: OQ-26 through OQ-30 added (resume LLM narration, auto-resume safety, soft unavailability, substitution-mark propagation, quota tracking accuracy).
- **2026-04-27 · v0.6.1** — Process model & reconnection.
  - **§1.6** expanded: new "Process model" subsection covering daemonization-by-default, PID-file lockfiles, single-conductor-per-workspace, crash recovery on every command, `quorum start`/`resume` aliasing. New "Three 'I closed something' scenarios" table. Full multi-day example walkthrough including pause, machine restart, and power-loss recovery.
  - **§7** updated: `/runtime/conductor.pid` and `/runtime/ui.pid` added to folder structure.
  - **§10 commands table** updated: `start` and `resume` documented as aliases; `--foreground` flag added; `pause` flags `--keep-ui` and `--full` documented; `serve` clarified as daemonized.
  - **§13** updated: 6 new failure mode rows for terminal close, foreground variant, machine restart, double-start lockfile, OS-killed conductor, command confusion.
  - **§15** updated: OQ-31 through OQ-33 added (workspace folder moved while running, cloud-sync compatibility, multi-user same-machine).
  - **§16** updated: glossary entries for Daemonized, Lockfile / PID file, Crash recovery.
  - **Mental model committed:** the workspace is just a folder; `cd` + `quorum <command>` is the entire reconnection mechanism. No session tokens, no daemon registry, no out-of-folder state.
- **2026-04-27 · v0.7** — Human-unavailability policy & DEPUTY_DECISION.
  - **§4** updated to v0.2: added `DEPUTY_DECISION` move type for provisional decisions made by agents on the human's behalf when human-timeout policy fires.
  - **§5** updated: required `Stakes` field added to QUESTION moves (trivial/tactical/strategic/irreversible); full DEPUTY_DECISION required-sections spec including provisional-status frontmatter.
  - **§6** Status state machine extended: BLOCKED_ON_HUMAN now has explicit sub-states; new `DECIDED_PROVISIONALLY` status for deliberations resolved by deputy pending human ratification.
  - **§7.5** state.yaml schema updated: `last_human_activity_at` (presence inference) and `pending_deputy_count` added.
  - **§10.4** added: full Human-Unavailability Policy — the asymmetry argument (why humans aren't substitutable like agents are), four-stakes classification, configuration schema with strict validation rules (auto_decide without deputies → config refused; auto_decide for irreversible → refused), trigger flow, deputy invocation prompt augmentation, four-state DEPUTY_DECISION lifecycle (provisional/confirmed/overridden/expired), max_consecutive_deputies cap (default 3) for cascading-decision protection, visible-accumulation pattern, presence inference with grace window, per-deliberation overrides.
  - **§10.5** updated: 9 new event types (human_timeout_armed/deferred/triggered, deputy_decision_issued/confirmed/overridden/held/expired, max_consecutive_deputies_reached).
  - **§13** updated: 9 new failure mode rows covering misclassified stakes, cascading deputies, drift, validation refusals, presence false-positives, expired-without-review, override-with-downstream-artifacts.
  - **§19** updated: DO-7 added (adaptive stakes classification & deputy thresholds via learning-from-logs).
  - **§15** updated: OQ-34 through OQ-37 added (richer presence detection, override-as-learning-signal, deputy-can-also-issue-questions, downstream-work-on-provisional-decisions).
  - **§16** updated: glossary entries for Stakes, DEPUTY_DECISION, Deputy decider, Provisional/confirmed/overridden/expired, Visible accumulation, Presence inference, DECIDED_PROVISIONALLY.
  - **Core principle committed:** automation produces drafts, never finals. The human's role as final arbiter is structurally preserved through the DEPUTY_DECISION → DECISION confirmation flow. Irreversible questions never auto-decide. Configuration that implies auto-decide without deputies is refused at validation time, not silently degraded.
- **2026-04-27 · v0.8** — Autonomous workspace mode + `quorum fork`.
  - **§1.6** added new "Workspace modes" subsection: `interactive` (default) vs `autonomous`. Autonomous mode has no human inbox, panel of deciders (ordered list, first available wins) issuing real DECISIONs (not provisional), make-and-document-assumptions semantics for ambiguity, hard caps on invocations and deliberations, standing prompt augmentation. Validation refuses incompatible configs (autonomous + human_timeout, empty decider_panel).
  - **§1.6** added `--autonomous` flag to `quorum init`. State machine extended with `COMPLETED_AUTONOMOUS` workspace state. Mode conversion rules: autonomous→interactive allowed (any human-issued move converts); interactive→autonomous mid-stream not allowed (use fork instead).
  - **§1.6** added `quorum fork` as first-class command — seed a new workspace from another's problem statement, with optional mode change. Provenance tracked. Enables comparative experiments and interactive→autonomous escape hatch.
  - **§7.5** state.yaml schema updated: `mode` field (locked once active), `forked_from`/`forked_at`/`forked_with_mode_change`, `mode_history` for conversions, `autonomous_completion` block when state=COMPLETED_AUTONOMOUS.
  - **§10 commands table** updated: `quorum fork` added.
  - **§10.5** updated: 7 new event types — `mode_set`, `autonomous_run_started`, `autonomous_run_completed`, `autonomous_max_invocations_hit`, `mode_converted`, `workspace_forked`.
  - **§13** updated: 9 new failure mode rows for autonomous-mode edge cases (max invocations, decider panel exhaustion, agent-asks-human protocol violations, validation refusals, mode conversion, fork edge cases).
  - **§15** updated: OQ-38 through OQ-41 added (decider panel voting vs sequential, max wall-clock, partial forks, mode-conversion historical-decision treatment).
  - **§16** updated: glossary entries for Interactive mode, Autonomous mode, Decider panel, COMPLETED_AUTONOMOUS, Fork, Mode conversion.
  - **Core principle committed:** autonomous mode is structurally distinct, not "extreme settings of interactive." Real DECISIONs in autonomous mode (no provisional state, no review queue), no human inbox, mode locked once workspace has activity. Forking is the path for "let me try this differently" — preserves the source workspace untouched.
- **2026-04-27 · v0.9** — Outcome Manifest: answering "when is the end?"
  - **§1.7** added (the foundational answer): the Outcome Manifest. Workspace declares what artifacts must exist for completion, with required sections, completion checks, production patterns, dependency graph, and quality gates. Manifest is always established via deliberation #0001 (concrete users ratify quickly, vague users do real scoping work). Templated manifests for common project shapes (saas-product, research-direction, architecture-decision, coding-plan, strategic-decision). Closing ceremony as deliberate event, not silent state change. Manifest can evolve mid-workspace via MANIFEST_REVISION.
  - **§4** updated: `ARTIFACT_REVISION` move type added.
  - **§5** updated: optional `contributes_to` frontmatter on DECISION moves drives synthesis-aggregated artifact production. Full ARTIFACT_REVISION required-sections spec.
  - **§6** Status state machine updated: `COMPLETED` workspace state added (interactive counterpart to `COMPLETED_AUTONOMOUS`); ACTIVE → COMPLETED transition explicitly tied to closing ceremony.
  - **§7** updated: `outcome-manifest.md` and `/artifacts/` (with `/versions/`) added at workspace root; `manifest-templates/` added under `/protocol/`.
  - **§7.5** state.yaml schema extended with `manifest` block (status, total/complete/in-production/pending counts, quality gate status, ceremony eligibility, final deliberation ID).
  - **§10.5** updated: 11 new event types — `manifest_drafted/locked/revised`, `artifact_production_started/completion_check_failed/completed/revised`, `quality_gate_status_changed`, `closing_ceremony_started`, `workspace_completed`.
  - **§13** updated: 9 new failure mode rows for manifest edge cases (paralysis, non-converging deliberations, gate-impossibility, completion-check failures, revision cascades, churn, late additions, ceremony disputes).
  - **§15** updated: OQ-42 through OQ-47 (template extensibility, competing manifest revisions, closing-summary as artifact-or-meta, scheduling artifact production, completion checks as scripts vs natural language, export bundle format).
  - **§16** updated: glossary entries for Outcome manifest, Artifact, Production pattern, Quality gates, Closing ceremony, Manifest template, ARTIFACT_REVISION.
  - **Core principle committed:** completion is *machine-checkable + human-ratified*, never one alone. Without machine checks, "done" is hand-wavy feeling. Without human judgment, the system would ship vacuous outputs that pass checks. Both required. The manifest exists from workspace day one — establishing what done means is the first work, before any product work begins.
- **2026-04-27 · v0.10** — Settings UX & configurability story.
  - **§9.8** added: Settings & Configuration UX. Three-tier model — Setup wizard (Tier 1, five questions, drives 80% of useful config), Settings panels (Tier 2, intent-organized sidebar), Raw YAML editor (Tier 3, escape hatch). Editability categories (Frozen / Live / Live-with-effects) with visual indicators. Settings-vs-lifecycle-operation distinction (settings change behavior; lifecycle operations like fork/archive/refresh-defaults remain commands).
  - **§9.8 wizard question 3** uses **behavioral framing** ("If your top-choice model is unavailable, what should happen?") rather than abstract values framing — concrete questions produce more accurate answers.
  - **§10.5** updated: `setting_changed` event type added with via/category metadata for audit trail.
  - **§13** updated: 7 new failure mode rows for settings UX (frozen-setting edit attempts, Category C disruption, concurrent YAML edits, invalid YAML, wizard re-run, multi-tab sync, schema validation refusals).
  - **§14** Build Order updated to v0.4: settings panels (~2 days) and raw YAML editor (~0.5 days) added as explicit build steps; total v1 build estimate revised to ~3 weeks. Wizard now part of UI shell scope (already in week 1).
  - **§15** updated: OQ-48 through OQ-52 added (wizard re-run conditions, Category C confirmation policy, raw YAML labeling, multi-tab settings sync, wizard overwriting Category A).
  - **§16** updated: glossary entries for Workspace setup wizard, Settings panels, Frozen/Live/Live-with-effects, Settings vs lifecycle operations, Raw YAML editor.
  - **Bug fix:** removed duplicate header line in §10 commands table.
  - **Core principle committed:** the YAML files remain source of truth; the UI is a structured editor for them. UI and direct file editing remain interchangeable. The settings UX hides complexity by default, reveals it progressively, and never imposes 30 knobs on users when 5 wizard questions plus sensible defaults serve 80% of needs.
- **2026-04-27 · v0.11** — The proactive human voice.
  - **§4** updated to v0.3: vocabulary split into "Core moves (any participant)" and "Human-initiated moves (the proactive voice)". Five new move types — `INTERJECTION`, `OVERRIDE`, `REOPEN`, `DROP`, `STEER` — each with explicit purpose and authorization rules.
  - **§5** updated: required-sections specs for all five new move types, including INTERJECTION's force-level field (advisory/strong/overriding), OVERRIDE's preservation-of-unconsidered-moves field, REOPEN's cascade detection, STEER's duration field.
  - **§6 Status state machine** updated: `ABANDONED` deliberation status (result of DROP); explicit OVERRIDE and REOPEN transitions. State diagram updated.
  - **§10.5** updated: 7 new event types — `interjection_issued`, `override_issued`, `reopen_issued`, `drop_issued`, `steer_issued`, `agent_cancelled_by_human`, plus disruption-strategy bookkeeping.
  - **§12.5** added: The Proactive Human Voice. Three categories of proactive action (interjection / redirection / steering). Disruption strategies per move type (wait vs cancel). UI affordances ("Speak up" persistent button with contextual menu, inline quick-action on deliberation cards). Structural framing: the human is a peer participant, not a constrained responder.
  - **§13** updated: 9 new failure mode rows for proactive-human edge cases (mid-flight INTERJECTION timing, OVERRIDE-DECIDED race, REOPEN cascades on existing artifacts, rapid interjection bundling, DROP undo window, STEER conflicts, authorization checks, cancellation cost transparency).
  - **§15** updated: OQ-53 through OQ-57 added (cascade propagation order, soft override, STEER influence tracking, DROP-with-dependents, agent-to-agent STEER triggers).
  - **§16** updated: glossary entries for INTERJECTION, OVERRIDE, REOPEN, DROP, STEER, ABANDONED, Proactive human voice, Disruption strategy.
  - **Core principle committed:** the human is a peer participant, not a constrained responder. The protocol must accommodate the human as initiator, not just answerer. Without this, users hack around the protocol (manual file edits, conductor restarts) and degrade the audit trail. The five new move types give the user a clean structural expression for the things they actually want to do mid-collab.
- **2026-04-27 · v0.12** — Clarification flow with grounded explanations.
  - **§3** updated: `Explainer` role added with default fitness mirroring `domain_expert`. Routing-defaults fitness ratings extended with `explainer` for all five default handles (Opus: 3, Sonnet: 2, Gemini-Pro: 2, Gemini-Flash: 1, Codex-GPT5: 2).
  - **§4** updated: `CLARIFY` (human-initiated) and `EXPLANATION` (auxiliary response) added to the move vocabulary. Vocabulary now organized into three groups: Core moves (any participant), Human-initiated moves (proactive voice), and Auxiliary response moves. Section explains why CLARIFY/EXPLANATION are structurally distinct from QUESTION/ANSWER (they don't progress decisions; they request understanding; they have different audit-trail semantics; agents prompt differently for them).
  - **§5** updated with three sets of changes:
    - **Strengthened existing moves for grounding.** PROPOSAL gains required `Alternatives I considered`. SYNTHESIS gains required `Alternatives weighed`. DECISION gains optional but encouraged `Path not taken`. These convert future EXPLANATIONs from "agent guesses what alternatives were considered" into "agent reads what alternatives were actually considered."
    - **Full required-sections spec for CLARIFY:** Targets, What I'm asking about, Why (knowledge_gap / reasoning_question / reviewing_later / other), Preferred explainer (optional). Allowed on DECIDED and ARCHIVED workspaces.
    - **Full required-sections spec for EXPLANATION:** Targets, Explanation (with general-knowledge vs workspace-claim distinction baked in), Sources cited (with validator enforcement), `What I couldn't find in the workspace` (the anti-confabulation field), Limitations. Frontmatter includes `visually_subordinate: true`.
  - **§11** updated to v0.2 (no longer "in progress"): role-specific prompt augmentations now documented — explainer (with strict anti-confabulation rules), bootstrapper, autonomous-mode, deputy-decider. Augmentations are additive; a single invocation may have multiple active.
  - **§12.5** expanded: 4th proactive category (Clarification) added alongside Interjection / Redirection / Steering. UI affordances expanded — "Ask for clarification" in Speak up menu, text-selection clarification (Google-Docs-comment-style), per-move "?" button, DECIDED/ARCHIVED workspace support. New disruption-strategy row for CLARIFY (waits for in-flight; spawns EXPLANATION as parallel work; pauses BLOCKED_ON_HUMAN). New visual treatment subsection: inset, muted, citations-as-links, "Hide explanations" toggle, "What I couldn't find" emphasized when non-empty. "Five reserved" → "six reserved" updated.
  - **§10.5** updated: 3 new event types — `clarify_issued`, `explanation_completed` (with sources-cited and gaps-acknowledged counts), `explanation_failed_validation` (with failure reasons and retry tracking).
  - **§13** updated: 8 new failure mode rows for confabulation despite guardrails, broken citation refs, dead URLs, deprecated handles, recursive nesting, stale BLOCKED context, archived-workspace temporal gaps, validation-rejection cycles.
  - **§15** updated: OQ-58 through OQ-62 added (validator strictness, multiple sequential clarifications mid-block, machine-actionable gap-tracking, text-span anchoring fragility, multi-user clarification interactions).
  - **§16** updated: 7 new glossary entries — CLARIFY, EXPLANATION, Explainer (role), Grounded explanation, Alternatives capture, Visual subordination.
  - **Core principle committed:** EXPLANATIONs are bounded by what the workspace actually contains. Agents may add general knowledge clearly distinguished from workspace-specific claims, but workspace claims must cite real sources, and gaps must be explicitly acknowledged. The strengthened Alternatives sections in PROPOSAL/SYNTHESIS/DECISION exist precisely so that future explanations can ground claims about reasoning in real data — including the truthful answer that "alternatives weren't actually considered" when that's the case. Honest audit trails extend to honest acknowledgment of what the audit trail *doesn't* contain.
- **2026-04-28 · v0.13** — The Context Surface: solving the stateless-agent economics problem.
  - **§1.8** added: The Context Surface. Four source types (Repos / Documents / Web / Notes) with distinct UI surfaces, lifecycle policies, and reuse patterns. Three context layers per invocation (standing bundle / deliberation-declared / on-demand). Cost-discipline as a first-class concern with concrete economics ("digest once, reuse many times" — 15-40x cost reduction vs naive approach).
  - **§1.6** updated: `--with-codebase` flag removed from `quorum init`; replaced by UI-driven context addition. "Working alongside an existing codebase" subsection rewritten to point at §1.8.
  - **§1.7** updated: outcome manifest's quality gates now include "all declared context sources have current digests and have been reviewed by user."
  - **§5** updated: `relevant_context` deliberation frontmatter (repos / docs / urls / notes lists). Bootstrapper proposes; user can edit before accepting.
  - **§7** updated: `/context/` folder structure expanded to four-source-type layout (repos / docs / web / notes), each with its own meta.yaml and digest/cache subdirectories. `index.md` and `context-manifest.yaml` at top level.
  - **§9.8** updated: Settings panels list now includes "Context" panel with four sub-panels (Repos / Documents / Web / Notes), each with add/edit/refresh/remove and digest-status indicators.
  - **§10.5** updated: 9 new event types — `context_source_added`, `digest_started`, `digest_completed`, `digest_review_completed`, `context_source_refreshed`, `digest_age_at_use`, `on_demand_file_read`, `on_demand_fetch`, `context_bundle_assembled`.
  - **§10 commands table** updated: `--with-codebase` removed from `init` signature.
  - **§11 standing prompt** updated: context-discipline augmentation added — trust digests for high-level understanding, read source on-demand only when needed, acknowledge digest staleness.
  - **§13** updated: 9 new failure mode rows for context-related edges (stale digest unawareness, URL fetch failures, oversize docs, queue management, agent over-reading, missed-content in digest, oversize repos, oversize notes, cross-repo references in code).
  - **§14 Build Order** updated to v0.5: Context Surface implementation as ~3 day step in build sequence; total v1 estimate revised to ~3.5 weeks.
  - **§15** updated: OQ-22 reframed for new model; OQ-63 through OQ-68 added (third-party connectors, deliberation-scoped notes, oversize-repo handling, robots.txt policy, asymmetric standing context citation, mid-stream context additions).
  - **§19** updated: DO-3 reframed (was "auto-summarization" since v1 already digests; now "automatic staleness detection and quality scoring"); DO-4 expanded to include cross-workspace context, not just registers.
  - **§16** updated: 9 new glossary entries — Context surface, Context digest, Standing context bundle, Relevant context, Raw vs digested context, Freshness indicator, On-demand reading, Cost discipline.
  - **§21** updated: "Bringing richer context" removed (now committed as §1.8); replaced by next-priority items (templates, visual spec, OQ-22 for digest detection, OQ-65 for oversize repos).
  - **Core principle committed:** stateless agents are economically catastrophic without explicit context architecture. The Context Surface makes context an explicit first-class workspace input — added through UI, digested once, reused across all invocations — with honest staleness signaling and per-deliberation scoping. The economic difference between this design and the naive "include everything per invocation" approach is 15-40x. Without §1.8, Quorum is a research toy; with it, Quorum is economically viable for serious multi-day, multi-repo use.
- **2026-04-28 · v0.14** — Permissions & Tool Authorization.
  - **§10.6** added: full Permissions section. Three-concern model (detect / surface / route response). Four-layer design: default allowlist + per-CLI flag passing + conductor as broker for out-of-allowlist + stakes-based auto-approval (opt-in). Concrete `permissions.yaml` schema with validation rules (`irreversible.enabled: true` refused; allowlist-denylist conflict refused; auto-approve requires human_timeout enabled). Capability-aware participants (`fine_grained` / `coarse` / `none`). UI affordances (permission request cards, "Approve always" pattern learning, settings panel). Honest acknowledgment of broker fragility (orphaned CLIs on conductor restart, stdout pattern brittleness across CLI version updates).
  - **§3.5** updated: `Permission Capability` column added to participants schema; field semantics documented.
  - **§6** Status state machine extended: `BLOCKED_ON_PERMISSION` sub-state of BLOCKED_ON_HUMAN added.
  - **§9.8** Settings panels updated: new "Permissions" panel added; total now 8 panels.
  - **§11 Standing prompt** updated: permission-discipline augmentation added — agents instructed to request narrowly-scoped operations only when needed, knowing that out-of-allowlist requests will be brokered to the user via the conductor.
  - **§13** updated: 9 new failure mode rows for permission edges (out-of-allowlist detection, conductor-restart-during-wait, CLI version drift, capability mismatch routing, denylist conflicts, irreversible auto-approve refusal, consistency validation, audit trail surfacing, batched-command CLI limitation).
  - **§14** Build Order updated to v0.6: ~1 extra day for permission-capability probing in `quorum doctor`, ~1 day for permission broker in conductor core, ~0.5 day for permission request cards in UI, ~0.5 day for Permissions panel in settings. Total v1 estimate revised to ~4 weeks. Recommendation: prototype the broker standalone before committing the conductor architecture around it.
  - **§15** updated: OQ-69 through OQ-73 added (template-tunable allowlists, permission shim for coarse-capability CLIs, denial-quota counting, cross-workspace allowlist reuse, agent-declared vs pattern-classified stakes).
  - **§16** updated: 6 new glossary entries — Permission allowlist/denylist, Permission broker, Permission capability, BLOCKED_ON_PERMISSION, Stakes (permission).
  - **Core principle committed:** statelessness doesn't excuse opacity. Every shell operation an agent performs is either pre-approved by the user (allowlist), brokered through the user (out-of-allowlist), or auto-approved under explicit policy the user opted into (stakes-based with hard ceiling at irreversible). Nothing happens behind the user's back. The audit trail records every grant, denial, auto-approval, and orphan. The framing also matters: most deliberation work doesn't need shell access at all — proposing/critiquing/synthesizing/deciding are read-only against the workspace's context surface — so the permission story can stay simple in the common case while remaining principled for edge cases.
- **2026-04-28 · v0.15** — Multi-account / multi-installation registration support.
  - **§1.6** updated: Add agent flow now explicitly supports multiple installations of the same CLI (e.g., `claude-work` and `claude-personal` binaries for users with separate work/personal accounts). Modal asks for command name (default canonical, editable), runs doctor probe against entered binary, asks for optional account label, derives handle names from label + model. Walks user through registering each installation as a separate batch.
  - **§3.5** updated: `Account Label` column added to participants schema (optional free-form string for UI grouping; display-only, no effect on routing/protocol). Field semantics expanded with multi-account note on quota tracking. New "Fitness inheritance for non-canonical handles" subsection — custom handles inherit fitness ratings from a designated canonical handle via `inherits_fitness_from` field; user picks at registration with sensible default.
  - **§13** updated: 3 new failure mode rows for multi-account scenarios — concurrent invocations across handles sharing an underlying account hitting account-level rate limit (v1 mitigation: conservative per-handle quotas; v2 OQ-74); accidental cross-account routing (UI grouping mitigates); diverging account labels (display-only, user-editable).
  - **§15** updated: OQ-74 (account-level quota grouping for v2), OQ-75 (duplicate binary detection in `quorum doctor`), OQ-76 (workspace tag-based handle filtering for account preference) added.
  - **§16** updated: 4 new glossary entries — Account label, Multi-account registration, Fitness inheritance, plus expanded Stakes (permission) cross-reference.
  - **Validation outcome:** the data model and protocol cleanly support multi-account scenarios without redesign. The handles abstraction was already independent of binary identity. Two refinements were needed: registration UX walks users through the multi-installation case explicitly, and fitness inheritance allows custom handles to leverage shipped routing-defaults. The one operational gap (account-level rate-limit awareness) is logged for v2 — the design accommodates it in principle, just not built in v1.
- **2026-04-28 · v0.16** — Relevance-tiered digester model selection.
  - **§1.8** updated: digester default model now scales with source relevance (high → Opus / Gemini-Pro, medium → Sonnet, low → Haiku/Flash) — reversing the earlier cost-minimizing default. Reasoning: digest quality compounds across every subsequent invocation reading it; paying more for high-relevance digests is the right trade. User override at digestion time (per-source) and bulk override via `context.digester_defaults` config block.
  - **§10.5** updated: `digester_chosen` event added; `digest_started` now records relevance level for analysis.
  - **§16** glossary updated: Context digest entry reflects relevance-tiered defaults and override mechanism.
  - **Reasoning behind the change:** original design defaulted to cheap models for digestion to minimize setup cost (~$0.10-0.20/repo). But a thin digest costs the user on every subsequent invocation that reads it (potentially hundreds). For high-relevance sources, paying $0.50-1.50 for a thoughtful Opus digest is dramatically cheaper than 500 confused downstream invocations driven by a digest that missed something important. The new default reflects this; the user can still opt for cheap if they want.
- **2026-04-28 · v0.17** — Open items pass; doc moves to implementation-ready state.
  - **§15** restructured into three buckets: A. Resolved (decisions committed; entries kept for audit), B. Open — needs design before v1 ship (with stated directions), C. Deferred to v2+ (with explicit reasons and revisit triggers). 47 of 76 OQs moved to Resolved with documented decisions; 8 moved to "Open with direction stated"; 21 deferred to v2 with revisit triggers. The register changes status from 🔴 Tracked to 🟢 Settled (v0.2 — bucketed).
  - **§8** Templates moved from 🟡 In progress to 🟢 Settled. Added full ADR template (with frontmatter, sections, supersession tracking) and full task template (with status, priority, dependencies). Move templates explicitly noted as build-time deliverables fully specified by §5 required-section lists.
  - **§16** Glossary status updated from ⚪ Not yet addressed to 🟢 Settled — the glossary has accumulated to 80+ entries through v0.16; it's substantive, not stale.
  - **§21** Next Reasoning Targets rewritten to reflect implementation-ready state. Build-time concretizations (no further design needed): §8 templates as files, participants.md full format, routing-defaults seeding, manifest template contents. Open with stated direction: §9.5 visual spec, tech-stack detection, conductor timeout/recovery handling. Genuine v2 deferrals tracked in §15.C.
  - **No new failure modes, events, or moves added.** This pass is consolidation: turning accumulated discussion into committed decisions, and moving deferrable concerns into a clearly-marked v2 bucket.
  - **Outcome:** the doc is implementation-ready. There are no remaining 🟡 or 🔴 markers in section headers. The OQ register has been honest about which items are decided vs which need usage data; nothing is hand-waved as "open" when there's actually a clear lean. v1 implementation can begin.
- **2026-04-28 · v0.18** — Critical-review pass: derisking v1 implementation.
  - **§5** updated: every DECISION move now requires a `Summary line` field (≤120 chars, validator-enforced, mechanically extracted into `summarized-decisions.md`). Replaces the previous unspecified mechanism for maintaining the standing context bundle's decision summary file. Validator rejects vacuous summaries (<30 chars or matching obvious-generic patterns).
  - **§1.8** updated: standing context bundle's `summarized-decisions.md` is now mechanically generated from DECISION Summary lines — no LLM call, no agent involvement, no extra invocation cost. Bundle size estimate revised upward (3-5K at start, 15-20K mature) to reflect honest accounting; cost ceiling catches runaway growth.
  - **§1.8 cost ceiling** is now ON by default at $50 (was optional before). Reasoning: cost surprises destroy user trust permanently; defaulting ON forces explicit "raise this" decision when warranted. Wizard adds question 6 for ceiling configuration.
  - **§9.8 wizard** updated to 6 questions: question 4 adds CLI-detection-fallback (manual binary entry path when auto-detect fails); question 5 (new) sets cost ceiling.
  - **§10.6** restructured: permission broker now ships **disabled by default** in v1. Default config `permissions.broker_enabled: false`. When disabled, agents are restricted to allowlist via per-CLI flags; out-of-allowlist requests fail cleanly with clear messaging. Users opt in via Settings → Permissions if their workflow requires the broker. Reasoning: broker is the highest-risk piece of v1 infrastructure (stdin/stdout pipe management, prompt-detection fragility, conductor-restart edge cases) for the smallest fraction of actual deliberation work. Most workspaces won't need it.
  - **§14 build order** restructured to v0.7 with two new milestones:
    - **Step 3: Manual protocol exercise** — run the protocol manually with three CLI agents on one real problem, before any conductor code is written. Cheapest possible reality check.
    - **Step 5: Vertical slice milestone** — first end-to-end deliberation through the conductor with minimal UI. Validate that prompt-driven behavior, validator, routing, and digest flow actually work before building UI on top. ~2-3 days.
    - **Step 11: Permission broker** moved out of conductor core, ships as standalone opt-in feature.
    - **Step 13: Standing prompt iteration** — explicitly budgeted as a dedicated 5-day week. Specifically tests against gaming behavior (vacuous Alternatives sections, stakes misclassification, generic gap acknowledgment, prompt-length instruction-skipping).
    - **Step 14: Real-world testing** on 3-5 representative workspaces of different problem types.
    - Total v1 estimate revised to **5-6 weeks** (up from 4) with much higher confidence v1 actually works for real users.
  - **§10 conductor**: stale-marker threshold raised from 5 to 15 minutes (5 was too tight for legitimate long-running invocations on large contexts).
  - **§1.6 / §10.4 autonomous mode**: clarified decider panel scope — panel members are *only* deciders, not synthesizers; synthesis routing applies normally per §3.6 fitness; decider role is per-DECISION, not per-handle.
  - **§1.7 manifest production scheduling**: dependency-graph triggering specified as event-driven (artifact status change), not polling. Removes ambiguity about when production fires.
  - **§13** updated: 11 new failure mode rows covering cost ceiling behavior (warning at 80%, hit at 100%, raised, disabled, estimate vs actual divergence), DECISION Summary line edges (vacuous, misleading, file growth), permission broker disabled-state handling, vertical-slice findings as expected outcome, wizard CLI-detection fallback.
  - **§10.5** updated: 9 new event types — `summary_line_appended`, `summary_line_rejected`, `summary_line_revised`, `cost_ceiling_warning`, `cost_ceiling_hit`, `cost_ceiling_raised`, `cost_ceiling_disabled`, `broker_state_changed`, `shell_request_blocked_broker_disabled`.
  - **§16** glossary: 6 new entries — Summary line, Cost ceiling, Permission broker (v1 default OFF), Vertical slice milestone, Manual protocol exercise.
  - **Core principle reaffirmed:** v1 should be cautious about its load-bearing claims and explicit about its risks. Defaulting cost ceiling ON, defaulting permission broker OFF, requiring Summary lines for compounding context fidelity, inserting protocol-exercise milestones before UI build — these are not pessimism, they're honesty about which assumptions need real-world validation. v1 succeeds if it produces useful work for real users on representative problems; v1 fails if it produces mediocre output that users can't easily diagnose or fix. The changes in v0.18 specifically target the second failure mode.

---

## 21. Next Reasoning Targets (what to deepen next)

As of v0.17, the doc is largely settled. The remaining work is implementation, not design. The few open items below are either build-time concretizations (where design is sufficient and the work is writing) or genuine open questions that benefit from real usage data.

**Build-time concretizations (no further design needed):**

1. **§8 templates as actual files** — the template *contents* are specified by §5 required-section lists; the work is producing the actual `/protocol/templates/*.md` files during build step 1.
2. **`participants.md` full format spec** (OQ-3) — columns are settled; the build produces the literal file format with placeholder substitution rules.
3. **Routing-defaults.yaml seeding** — empirical fitness ratings for the first batch of supported handles, including the `explainer` row, calibrated against observed model behavior. Data-gathering during early dogfooding.
4. **Manifest template contents** (§1.7) — the actual contents of `saas-product.md`, `research-direction.md`, etc. Each is a small Markdown file; produced during build step 1.

**Open with stated direction (refinement during build):**

5. **§9.5 Visual spec** (OQ-11) — move card typography, density, color treatment, "your turn" affordance, composing-to-complete transition, EXPLANATION's visually-subordinate styling. Iterated by the UI builder against real moves.
6. **Tech-stack detection layering** (OQ-22) — concrete heuristic + digester prompt augmentation, finalized during build step 5.
7. **Conductor timeout / network-failure / process-recovery handling** (OQ-2, OQ-5) — directions stated in §15.B; concretized during conductor build (step 4).

**Genuine open questions deferred to v2** — fully tracked in §15.C with revisit triggers. No design work needed pre-v1.

The doc is in implementation-ready state.
