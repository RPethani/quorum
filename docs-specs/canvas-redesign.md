# Canvas redesign — running design doc

A living spec for the pivot away from the deliberation/manifest protocol
toward a **collective canvas**: one chronological conversation between
the human and N AI participants, with live artifacts maintained
alongside it.

This doc grows as we brainstorm. Each round adds a short section. We
keep open questions visible at the bottom so nothing gets lost.

---

## Brainstorming meta-rules

These apply to **how we work on this redesign together**, and several
of them are also product requirements for the system we're designing.

1. **One topic per turn.** Each response from Claude (or any AI) stays
   short — a few sentences, never a wall of text. If a turn feels too
   long to absorb, the user pushes back.

2. **Live design doc, side-by-side.** This file is the canvas for our
   redesign brainstorm. After each round, the agreed point lands here
   in one short paragraph; the user can read it side-by-side with the
   chat and bring forgotten thoughts back in. (We are dogfooding the
   pattern we're designing.)

3. **Bite-sized info delivery is a product requirement.** The new
   system should encourage short turns from agents, not encyclopedic
   ones — and should make it easy for the user to absorb the system's
   own output without re-reading.

4. **Freeze is phase-2.** In practice the user has never needed to
   freeze an artifact (AIs ask before edits, or the user explicitly
   asks for an update). We won't build freeze v1; we'll model
   artifacts as files so adding a `frozen: true` flag later is cheap.

5. **MVP first, polish on feedback.** The biggest mistake last time
   was designing too many details up front before living with any of
   them. Every round of this brainstorm asks "is this needed for
   MVP?" first; nice-to-haves go to a "Future enhancements" list.

---

## Decisions locked

### D1 — Workspace layout: two panes, side by side

When the user opens a workspace they see two full-height panes:

- **Left (~60%)**: the **conversation canvas** — chronological thread
  of messages from the human and the AI participants. This is the
  dominant element; it scrolls.
- **Right (~40%)**: **one live artifact at a time**. When multiple
  artifacts exist, a small tab strip at the top of the pane switches
  between them. When no artifact exists yet, the pane shows a simple
  "create the first artifact" prompt.

A header sits above both panes; a status bar (cost, participants
online) sits below.

Reinforced UX constraint surfaced this round: long agent responses
cause the user to lose the bigger picture even when reading a single
message — they retain only the bit that resonated. The system must
therefore *constrain message length* (not just encourage short turns
between participants, but also keep individual messages digestible).
How exactly we enforce / encourage this lands later when we design
the chat pane internals.

### D2 — Chat pane: free-form, no chunking, no message compression

The chat is **free-form**, like a Slack/Discord/ChatGPT thread.
Messages stack chronologically; agents respond at whatever length
they naturally would; no UI chunking, no truncation, no auto-collapse.

The "long messages lose the user" constraint is solved at a
**different layer**: the chat carries the *thinking* (long, messy,
exploratory) and the artifact pane on the right carries the
*crystallized answer* (short, refined, scannable). Two channels,
two purposes — when an agent writes 30 lines, the user reads what
catches them and trusts the artifact will absorb the durable parts.

Performance: virtual scrolling (e.g. `react-virtuoso`) once message
counts grow. Real cost but solved problem; we'd need it for
multi-day sessions regardless.

### D3 — Dispatch: `@mention`-only for MVP

When the user sends a message:

- If it contains no `@mention`, **no AI responds**. The message just
  lands in the canvas as a thought.
- If it contains `@<name>`, that participant alone is invoked.
- No defaults, no broadcasts, no auto-replies. Maximum control,
  zero surprise.

This keeps the v1 mental model trivially explainable. "Default
participant per workspace" and `@all` broadcast can layer on top
later without changing the dispatch core.

### D3-future — AI roles (deferred, research-driven)

A later feature: assign each participant a **brainstorming role**
(e.g. *Main Brain* / *Critique* / *Researcher* / …). Roles bias how
the dispatcher routes turns and what context each agent receives.
Role list is **not invented now** — it'll come from real research on
effective multi-perspective brainstorming. Captured here so the MVP
dispatch model leaves room for it.

### D4 — Per-participant visual identity: brand glyph + colour ring

Each AI participant is rendered with **its vendor's brand glyph** in
a small circular avatar plus a per-vendor colour (Claude orange,
Gemini blue, Codex green, …). The same colour tints the message's
left border or background so the user can scan the canvas and see
*who said what* at a glance without reading names. The current
Quorum UI already ships brand glyphs in `components/workspace/
participant-avatar.tsx`; reuse rather than reinvent.

The human's own messages are rendered with a neutral avatar and a
distinct accent so "you vs them" is also a glance-level cue.

### D5 — Artifact creation: conversational, AI-spawned

Artifacts come into existence **conversationally**, not via a UI
control. The user asks an AI ("maintain a doc tracking the
requirements as we go") and the AI declares creation as part of its
response. The artifact appears as a new tab in the right pane.

No "+ new artifact" button in MVP — keep the user away from
bookkeeping. If an AI creates something unwanted, the user dismisses
it with a small `×` on the tab. Deletion is cheap and reversible:
the file moves to a `.trash/` folder under the workspace for a
grace period (e.g. 7 days) so we never silently destroy work.

How an AI *technically* declares "I am creating / updating
artifact X" is a separate question (text convention vs. tool-call,
parsed by the conductor). Captured in Open questions below.

### D6 — Artifact updates: diff view, not silent replace, not live streaming

When an AI lands an update, the right pane briefly renders a
**line-level diff** (red strike-through removals, green additions)
before settling to the clean version. Author + timestamp in the
pane header (`updated 3s ago by @gemini`).

Why diff vs. silent replace: brainstorming hinges on catching
subtle drift — "did the AI actually preserve my objection, or paper
over it?" — and a diff makes that visible at a glance without
re-reading the whole doc. Why diff vs. live streaming: the rewrite
animation is visually overwhelming for multi-page docs and adds
nothing the diff doesn't already give.

Implementation note: this is cheap. Mature React libraries
(`react-diff-view`, `react-diff-viewer-continued`) accept old vs
new text and emit GitHub-style diffs. ~1–2 hours of integration.

### D7 — Artifact editing: AI-only in MVP

The right pane is **read-only for the human**. Every change to an
artifact comes through chat — the user asks an AI ("update the
requirements doc to add the merge-conflict bit") and the AI lands
the edit. No pencil icon, no inline editor in MVP.

Rationale (user-stated): in real brainstorming sessions the user
never edits docs themselves — the AI articulates and structures
better than the human will under flow. Direct human editing is a
"fix this typo" feature we can layer on later if real friction
shows up; today it would only add merge-conflict complexity for
near-zero gain. Massively simplifies MVP: no inline editor, no
clashing-edit detection, no save vs. cancel UX.

### D8 — AI "thinking" state: typing indicator (MVP), streaming later

When an `@mention`ed agent is generating, the chat shows a small
"Claude is thinking…" placeholder card with the participant's
avatar. When the response arrives the placeholder is replaced
in-place by the full message. No mid-response visibility.

Rationale: the conductor already invokes CLI agents as a single
stdout-capture; switching to streaming chunks over SSE is real
work and not the right MVP investment. **Streaming is the obvious
v1.1 polish** — staring at "Claude is thinking…" for 30 seconds
feels dead — but we ship typing-indicator first to validate the
whole loop, then come back for the aliveness.

### D9 — Workspace start: no problem statement, optional title

A new workspace is **empty by default**: no problem statement, no
required pre-flight. The user just adds participants and starts
typing. The topic emerges from the conversation; structure is not
imposed up front.

The user may set an **optional one-line title** for the workspace
(e.g. *"v2 architecture ideas"*) — purely a human-readable label
to disambiguate workspaces in a list. Defaults to *"Untitled
brainstorm"*; renameable anytime; never used as a constraint on
what gets discussed.

This is a deliberate departure from current Quorum, which refuses
to start without a problem statement. The user's stated style is
"as and when I remembered things" — pre-flight scope-locking
fights that style for zero gain.

### D10 — Adding participants: dedicated panel

Participants are added via a **dedicated "Participants" panel**
(small sidebar section or settings-page entry). User clicks
"+ Add", fills a tiny form (handle name, CLI command, optional
display name), saves. Reuse the current Quorum participant model
(`registers/participants.md` row format) since it works.

Adding a participant is rare (do it once, brainstorm forever); the
explicit panel is the most predictable place for it. Inline-add on
unknown `@mention` would be cute but is a complication we don't
need for MVP.

The panel also exposes per-participant **enable/disable**, **edit**
and **remove**. Disabled participants don't appear in `@mention`
autocomplete.

### D11 — Composer: multi-line, button-to-send

The chat input at the bottom of the canvas:

- **Multi-line textarea**, auto-grows up to ~6 lines then scrolls.
- **Enter inserts a newline.** Send is **only via the send button**
  (or its keyboard equivalent if we add one later). This is a
  deliberate flip from the Slack default — brainstorming users
  type lists, paragraphs and code blocks, and "send on Enter"
  cuts them off mid-thought.
- **`@` opens an autocomplete popover** listing enabled
  participants; arrows to navigate, Enter or Tab to insert.
  Mentions render as styled pills both in the composer and in the
  sent message.
- **Plain text input.** No live markdown preview; markdown
  renders correctly once the message is sent.
- **Send button** sits at the bottom-right of the composer.
- **No file attachments, no slash commands** in MVP.

### D12 — One workspace at a time

The conductor serves **one workspace folder** at a time, exactly
like current Quorum. No multi-workspace sidebar; switching topics
means pointing the conductor at a different folder.

Multi-workspace UI is a v1.1 problem — when "switching takes too
long" actually annoys real users, we'll add a sidebar.

### D13 — Empty state of a fresh workspace

A brand-new workspace with no participants and no messages renders:

- **Top bar**: *"Untitled brainstorm"* (clickable to rename); a
  "Participants" button on the right showing *"0 participants —
  add one"* in a soft warning tone.
- **Left pane** (chat): a single centred hint — *"Add a
  participant to start. Then type a message and `@mention` them."*
  The composer at the bottom is rendered but **disabled** until at
  least one participant exists.
- **Right pane** (artifacts): a faint hint — *"Artifacts will
  appear here when an AI starts maintaining one."* No "create"
  button (per D5, artifact creation is conversational).
- **Status bar** at the bottom: cost spend (`$0.00 / $50`) and the
  conductor connection indicator.

The whole frame nudges the user toward one action — add a
participant. Once they do, the chat hint flips to *"type a message
and `@mention` someone"*; once they do that, the canvas comes
alive.

### D14 — Errors: inline in the canvas with retry

When an AI fails to respond (rate-limit, CLI binary missing,
timeout, non-zero exit), the typing-indicator placeholder is
replaced **in place** by a small red-tinted system message in the
chat:

> ⚠️ `@gemini` couldn't respond — rate-limited. **[Retry]**

Errors stay in the scrollback so the user can see at a later
moment "ah, Gemini was down at 3pm". The Retry button re-invokes
the same agent on the same turn (re-using the user's last message
that triggered it).

No toasts, no silent retries, no popups. Failure is just another
event in the canvas.

### D15 — Markdown rendering: standard CommonMark + GFM

Messages and artifacts both render markdown via a standard library
(`react-markdown` + `remark-gfm`). Headings, lists, links, fenced
code blocks, tables, blockquotes — everything users expect from
Discord/GitHub/Slack. Code blocks use a basic syntax highlighter
(`shiki` or `highlight.js`).

No custom block types in MVP. The "artifact emit" sentinel (Open
question Q1) plugs in here as a custom code-block renderer when we
get to it.

### D16 — Cost ceiling: inherit current Quorum behaviour

The conductor already enforces a default `$50` cost ceiling and
pauses the workspace when hit. Keep it as-is.

UI surfaces:
- The status bar shows `cost / cap` (per D13).
- When the cap is hit during a turn, the failure renders as a D14
  inline error in the chat: *"⚠️ Cost ceiling reached. Raise the
  cap in Settings to continue."*
- Settings exposes the cap as a numeric input (or "off").

### D17 — Settings access: gear icon, three-panel page

A gear icon in the workspace's top bar opens a Settings page with
just three panels for MVP:

1. **Participants** — same panel as D10's add/edit/remove flow.
2. **Cost ceiling** — numeric input + on/off toggle (D16).
3. **Appearance** — theme toggle (light/dark) only.

Everything else (advanced agent options, raw editor, permissions
broker, etc.) waits until real demand surfaces. The panel list is
intentionally short so the user is never lost in settings.

### D18 — Persistence: file-first, refresh-survives-everything

State **lives on disk in the workspace folder**, not in memory:

- `canvas.md` — the chronological conversation (one markdown file).
- `artifacts/*.md` — each live artifact is its own file.
- `registers/participants.md` — participants (existing format).
- `state.yaml` — workspace metadata (title, cost spend, etc.).

The UI is a *view* over these files — it never holds authoritative
state. Browser refresh, second tab, kill-and-restart conductor all
re-render from the same disk; no surprises, no lost messages, no
"my brainstorm vanished".

This also means: every artifact the user ever sees is already
"exported" — it's a markdown file in their project. No export
button needed (for MVP).

---

## System sketch (reverse-engineered from UX)

Each section below derives a system-layer commitment from the UX
decisions above. Same bite-sized cadence.

### S1 — Workspace folder layout

```
my-brainstorm/
  state.yaml              # title, created_at, cost spend
  canvas.md               # full chronological conversation, one file
  artifacts/<name>.md     # one file per live artifact
  registers/participants.md   # existing Quorum format, reused
  events.jsonl            # append-only event log, reused
  .trash/                 # deleted artifacts (D5 grace period)
```

`canvas.md` uses author-timestamped section headings:

```markdown
## @rakesh · 2026-05-03T10:00:00Z
Let's brainstorm v2 architecture.

## @claude-opus · 2026-05-03T10:00:15Z
Sure — what's your starting hypothesis?
```

Performance: a multi-day brainstorm is ~500 messages ~500KB. Trivial
to parse and serve. The conductor reads once at startup, holds the
parsed array in memory, appends on each new message. The UI uses
virtual scrolling (per D2) so DOM size never explodes. If single-
file growth ever hurts (10K+ messages), we'd split monthly
(`canvas/2026-05.md`); not an MVP concern.

### S2 — Agent invocation: agents read the workspace, conductor doesn't pipe context

Modern coding CLIs (Claude Code, Gemini CLI, etc.) are designed to
read files in their cwd. We exploit this — the conductor doesn't
hand-assemble context, it just lets agents read what they need.

End-to-end flow when the user `@mentions` an agent:

1. UI `POST /api/messages` → conductor appends to `canvas.md`,
   parses the `@mention`, identifies the participant.
2. Conductor **spawns the CLI in the workspace folder as cwd**
   with a short system prompt:

   > *"You're `@claude-opus` in a multi-AI brainstorm workspace.
   > The full conversation is in `canvas.md`. Live artifacts are
   > in `artifacts/*.md`. Read what's relevant and reply. To
   > create/update an artifact, emit a fenced code block with
   > `artifact:filename.md` as the language tag (the conductor
   > will write its body to that file)."*

3. The actual prompt is tiny — typically *"respond to the latest
   message in canvas.md"*.
4. Conductor captures stdout when the CLI exits, parses any
   artifact-emit blocks, appends the reply to `canvas.md`, writes
   updated artifacts to disk.
5. Conductor emits an SSE event; UI re-renders.

Why this is the right choice:

- Conductor becomes a thin orchestrator, not a context-builder.
- Token cost reflects what the agent *actually* read, not what we
  preemptively shipped.
- The "context distiller" we'd planned for a long-session future
  becomes mostly unnecessary — agents read selectively themselves.

**MVP scope, agent compatibility**: target file-aware CLIs only.
Per-participant config gets a `read_strategy: filesystem | stdin`
field; default `filesystem`. Stdin-piping is a fallback for older
CLIs and not needed in MVP if we set up with Claude Code / Gemini
CLI / similar.

**Other commitments tied to this round (per UX side):**
- Whole-canvas context (no tail trimming) for MVP — agents decide.
- No transparent retries on CLI failure — all errors surface as
  D14 inline messages.

### S3 — Artifact-emit convention: fenced code block with `artifact:` language tag

When an AI creates or updates an artifact, it emits a fenced
markdown code block whose language tag starts with `artifact:`:

````markdown
```artifact:requirements.md
# Requirements
- ...
```
````

The conductor parses every reply for these blocks and:

1. Writes the block body to `artifacts/<filename>` (whole-file
   replace; previous version moves to `.trash/` for the D5 grace
   period).
2. Strips the raw block from the agent's reply before appending
   to `canvas.md`; replaces it with a single line:
   *"📝 updated `requirements.md`"*. The diff lives in the right
   pane (D6).
3. Emits an SSE event so the UI swaps the artifact pane to the
   diff view.

**Whole file, every time** — no patch/diff emission for MVP.
Artifacts are typically a few KB; the cost is fine and the
simplicity is worth a lot. Patch emission is v1.1 polish.

**Why this convention** vs. function calls or HTML tags: every CLI
agent emits fenced blocks reliably; it's their native format. The
`artifact:` prefix is unambiguous (no real language is named that),
and even if our parser fails, the raw block is still readable
markdown in `canvas.md`. The system-prompt note (per S2) tells the
agent the convention; no per-vendor adaptation needed.

### S4 — API surface (UI ↔ conductor)

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | workspace title, participants, cost, conductor health |
| `GET /api/canvas` | message list (`[{ id, author, ts, body }]`) |
| `POST /api/messages` | send a user message; conductor appends + dispatches if `@mention` |
| `POST /api/messages/:id/retry` | re-invoke the same agent on the same turn (D14 retry) |
| `GET /api/artifacts` | list of artifact names + last-modified |
| `GET /api/artifacts/:name` | artifact body (markdown) |
| `DELETE /api/artifacts/:name` | move to `.trash/`, emit SSE |
| `GET /api/participants` | enabled/disabled list |
| `POST /api/participants` | add via D10 panel |
| `PATCH /api/participants/:id` | enable/disable, edit |
| `DELETE /api/participants/:id` | remove |
| `GET /api/stream` | SSE: `message_appended`, `artifact_updated`, `artifact_deleted`, `agent_failed` |

**Liveness model**: UI does an initial GET on each resource, then
listens to `/api/stream` to know when to re-fetch. No polling.

Most endpoints already exist in current Quorum (`/api/state`,
`/api/participants`, `/api/stream`); the new ones are
`/api/canvas`, `/api/messages*`, `/api/artifacts*`. The protocol-era
endpoints (deliberations, asks, manifest, plan, next-actions,
permissions, etc.) all retire.

### S5 — Migration: what stays, changes, dies in the existing codebase

**Keep (the harness):**

- Conductor's CLI invocation transport (`transport/`) — spawns the
  agent process in cwd and captures stdout. Heart of S2.
- Participants register format and storage
  (`registers/participants.md`, parsing helpers).
- Cost tracking + ceiling enforcement.
- HTTP server scaffold + SSE plumbing (`server/http_app.py`).
- Workspace folder convention, `state.yaml`, `events.jsonl`.
- The `quorum` CLI lifecycle commands (`init`, `serve`, `pause`,
  `resume`, `archive`).
- UI design system: tokens, primitives, Settings shell, theme
  toggle, participant avatars, header layout.

**Change (adapt):**

- The HTTP API: drop deliberation/manifest/ask/plan/next-actions
  endpoints; add `canvas`, `messages`, `artifacts` per S4.
- Setup wizard: simplify drastically — just "name the workspace
  (optional)" and "add participants". No problem statement, no
  manifest archetype, no context surface, no ratifier.
- Participants panel: gain enable/disable toggle (D10).

**Die (retire):**

- Move-type protocol: `protocol/templates/`, `protocol/manifest-
  templates/`, all the typed-move parsers and validators.
- Routing engine four-layer chain (replaced by the trivial
  `@mention` dispatcher in S2).
- Bootstrapper (`workspace/bootstrapper.py`).
- Outcome manifest model + locking + ratification.
- Auto-loop / planner / `next-actions` engine.
- Asks / pick_one / pick_any UX surfaces.
- Permissions broker plumbing (kept on a side branch if revived
  later; not in MVP).
- Current system-flow diagram (`components/flow/`,
  `lib/flow/derive.ts`) — we modeled the protocol; it goes with it.
- DROP rule, REOPEN/STEER/CLARIFY/REVISION move types.

**New (build):**

- `canvas.md` parser + writer (single file, header-delimited
  messages).
- `@mention` parser + dispatcher (one-line route: extract handle,
  invoke that participant; that's it).
- Artifact-emit block parser (S3) + atomic file writer with
  `.trash/` archival.
- Right-pane component: tabs + read-only markdown view + diff
  overlay on update (using `react-diff-viewer-continued` per D6).
- Composer with `@mention` autocomplete (D11).
- Empty-state component (D13).

This list is the implementation backlog for the MVP. A reasonable
phasing: data model first (`canvas.md` + parser + writer), then
the dispatcher (S2 + S3 plumbing), then UI swap, then artifacts.

---

## Status

The doc is **implementation-ready**. UX is locked in 14 decisions
(D1–D14 + supporting notes); system layer is sketched in 5 (S1–S5);
all open questions are resolved. Future enhancements deliberately
deferred are listed below.

The existing protocol-era code is **not** removed by this doc — it's
the migration target. The implementation can land as a parallel
surface and retire the old one when feature parity is real.

---

## Open questions

- ~~**Q1** — How does an AI emit artifact content over the wire?~~
  Resolved by S3.

---

## Future enhancements (deferred from MVP)

- Per-message "tl;dr" affordance — a button to ask an AI to distil
  a long message into one pinned line. Skipped for MVP because the
  artifact pane absorbs the "scannable answer" role. Revisit once we
  see whether long messages actually hurt usability in practice.

- **Concurrent workspaces — no port conflicts, no manual bookkeeping.**
  Today (per D12) only one workspace runs at a time: `quorum init`
  binds 8500/3000 by default and a second `quorum init` from another
  folder collides on those ports. Future shape:

  - Each workspace owns its own conductor + UI process pair.
  - On `quorum init`, if a port is taken the launcher picks the next
    free one (e.g. 8500 → 8501 → 8502 …, 3000 → 3001 …) and records
    the chosen ports in that workspace's `state.yaml` (or
    `runtime/services/*.json` as today).
  - The UI dev server is told its conductor's URL via env var
    (`NEXT_PUBLIC_QUORUM_API`) at spawn time, so each UI talks only
    to its own conductor — no cross-workspace bleed.
  - `quorum status` / `up` / `down` / `restart` / `logs` resolve the
    workspace from `--path` (or cwd walk-up) and read the
    per-workspace port records — never assume the default.
  - The user can run several brainstorms at once: each opens at its
    own URL printed by `init`. Stopping one doesn't touch the others.

  Captured as a future enhancement; out of scope for MVP. The
  underlying record format (`runtime/services/server.json` carries
  `port`) and the ad-hoc `_port_is_free` check today already point
  the right direction — what's missing is the auto-bump-on-busy
  logic, the per-workspace UI→conductor wiring, and dropping the
  D12 single-workspace assumption.
