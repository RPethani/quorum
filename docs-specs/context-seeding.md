# Context seeding — planning doc

> Status: design draft, **decisions locked, not yet implemented**.
> All Q1–Q10 below have been answered by the user; this doc is the
> reference for the four-phase implementation that follows.

---

## What this is

Right now a fresh canvas workspace has zero project context. If the
user wants to brainstorm v2 architecture for an existing repo at
`~/Projects/v2-app`, every agent starts blind: "what does your project
look like?" "what's the current architecture?" — wastes turns,
wastes tokens, agents can't anchor their suggestions in real code.

**Context seeding** lets the user pre-populate the workspace with
pointers to local folders and documents so every agent invocation
has them available *without the user having to repeat them every
turn*. The user explicitly does **not** want URL handling here —
they'll paste those in chat as needed.

The previous (protocol-era) version had this. It's been retired
along with the protocol surface; we need to bring it back, redesigned
for the canvas's "agents read the workspace" model.

---

## What the previous version did (and what we're keeping vs. dropping)

### Mechanism

- CLI: `quorum context add-repo /path`, `add-doc`, `add-note`,
  `add-url`.
- Storage:
  ```
  workspace/context/
    repos/<name>/digest.md            # AI-generated summary
    docs/raw/<file>.md                # raw doc copies
    docs/digested/<file>.md           # AI summary of long docs
    notes/<note>.md
    web/cached/<url-hash>.md
  workspace/context/context-manifest.yaml
  ```
- A "digester" agent role was configured in the participants
  registry; on `add-repo` the conductor invoked it to produce
  `digest.md`.
- The standing prompt sent to every agent referenced the context
  manifest so agents knew to look in `context/`.

### What worked

- Repo digestion let agents work with code bases too big to fit in
  a single context window.
- Per-doc raw + digested twin let agents pick fidelity vs. brevity.
- The single `context-manifest.yaml` was a clean source of truth.

### What didn't

- Add was synchronous and slow (digestion can take 30s–2min).
  No "added in background" feedback.
- The manifest grew without pruning UX — old repos lingered.
- URL fetching had its own caching subsystem that wasn't worth its
  complexity for v1 (the user's call to drop URLs entirely
  vindicates that).
- The CLI was the only add path. Power users liked it; non-CLI
  users had no surface.

### Carry-overs vs. throw-aways

- **Carry over**: folder layout under `workspace/context/`,
  digest-by-default for repos, raw-copy for docs, single
  manifest file as source of truth.
- **Throw away**: URL handling and its cache, the protocol-era
  digester role machinery (replace with a much simpler
  per-workspace `digester_handle` setting).

---

## Proposed canvas-era model

### Workspace layout

```
workspace/
  state.yaml
  canvas.md
  artifacts/
  registers/
    participants.md
  context/                          ← NEW
    index.md                        # human-+-agent-readable index
    context-manifest.yaml           # machine-readable source of truth
    repos/<slug>/digest.md          # one-pager summary + file-tree
    repos/<slug>/source -> /real/repo  # symlink for deep dives
    docs/<slug>.md                  # raw doc copy
    notes/<slug>.md                 # human-typed scratch
  events.jsonl
  .trash/
```

The slug is derived from the source path's basename, slugified, with
a counter suffix on collision.

### Agent visibility

The agent system prompt (rendered in `canvas/transport_adapter.py`)
adds one line:

> *"Project context is in `context/`. Read `context/index.md` for an
> overview of what's available; deep-dive by reading any individual
> file under `context/repos/*/digest.md`, `context/docs/*.md`, etc."*

`context/index.md` is auto-maintained by the conductor each time the
manifest changes. Format:

```markdown
# Context

## Repos
- **v2-app** (`/Users/rakesh/Projects/v2-app`, 1,247 files)
  → `context/repos/v2-app/digest.md`
  → live tree at `context/repos/v2-app/source/`

## Docs
- **product-spec.md** (`/Users/rakesh/Documents/specs/product-spec.md`)
  → `context/docs/product-spec.md`

## Notes
- *Quick observation about routing edge case* — added 2026-05-04
  → `context/notes/note-0001.md`
```

So agents have one place to look first (`index.md`) and clear
pointers to the full content.

### Manifest shape

`context/context-manifest.yaml`:

```yaml
schema_version: 1
entries:
  - id: ctx-0001
    kind: repo
    name: v2-app
    source: /Users/rakesh/Projects/v2-app
    added_at: 2026-05-04T18:30:00Z
    digest_status: ready          # pending | running | ready | failed
    digest_summary: 1,247 files; TypeScript + Python; …
  - id: ctx-0002
    kind: doc
    name: product-spec.md
    source: /Users/rakesh/Documents/specs/product-spec.md
    added_at: 2026-05-04T18:31:00Z
  - id: ctx-0003
    kind: note
    name: routing-observation
    added_at: 2026-05-04T18:32:00Z
    body: |
      The conductor's @mention dispatch is sequential …
```

Server is the only writer. Manifest entries are addressable by `id`
so the UI can render a list with delete buttons.

### Digestion

A repo entry is *not* useful raw — too many files, too big. We need
a one-page digest. Strategy:

- A new `state.yaml` field `digester_handle: "@claude-opus"` (or
  whichever participant the user picks). Settable from the
  Settings dialog (new section: "Default agents → Digester").
- On `add-repo`, conductor:
  1. Symlinks the source folder to `context/repos/<slug>/source`.
  2. Spawns the digester via the existing transport adapter,
     piping a fixed digester prompt + `cd` to `context/repos/<slug>/source`.
  3. Captures stdout, writes to `context/repos/<slug>/digest.md`.
  4. Updates manifest `digest_status: ready` and `digest_summary`.
- This runs **in the background**. The dialog shows the entry as
  `pending → running → ready` so the user can keep using the
  workspace while it finishes. SSE notifies the UI on each
  status change.

For docs: no digestion. Raw copy to `context/docs/<slug>.md`. If
the doc is huge, the user can ask any agent in chat to summarize it
and `artifact:` the summary into a managed artifact — same primitive
we already have, no new machinery.

For notes: just a markdown file in `context/notes/`. No digestion,
no source.

### CLI surface

```
quorum context add <path>            # auto-detects: dir → repo, file → doc
quorum context add --kind=note <name> [--body=<text>]
quorum context list
quorum context remove <id>
quorum context refresh <id>          # re-digest a repo
```

`add` is one verb that DTRT based on the input. Old version's
`add-repo` / `add-doc` / `add-note` are still findable via `--kind=`
flag for explicitness.

### UI surface

A new icon button in the header (between Participants and Settings)
opens a **Context dialog**:

- **Tabs or sections**: Repos · Docs · Notes
- Each entry: name, source path (mono), status pill, delete button
- "+ Add context" button at the bottom that opens a small add
  flow:
  - Step 1: pick type (Repo / Doc / Note)
  - Step 2: paste path or click "Browse" (uses native file picker
    via `<input type="file" webkitdirectory>` for repos)
  - Step 3: optional name override
  - Add → entry shows up immediately with `pending` status if
    digestion is needed
- Below the list: "Configured digester: @claude-opus · change in
  Settings →"

### HTTP API

```
GET    /api/canvas/context              # list of entries
POST   /api/canvas/context              # body: {kind, source, name?}
DELETE /api/canvas/context/<id>
POST   /api/canvas/context/<id>/refresh # re-digest
```

SSE event: existing `state_changed` already fires on state.yaml
mtime changes; the manifest write triggers an update too if we
bump state.yaml's `context_revision` counter on every manifest
change. (Avoids a new SSE event type.)

---

## Decisions locked

User has signed off on all ten questions. Decisions, in implementation
order:

| # | Decision | Implementation note |
|---|---|---|
| Q1 | **Explicit `digester_handle` setting** in `state.yaml`; surfaced in Settings dialog as "Default agents → Digester" dropdown listing every CLI participant. | Settings dialog gains a new section "Default agents". Default value = first available CLI participant; user can change anytime. |
| Q2 | **Symlink only**, no copy. | `context/repos/<slug>/source -> /real/path`. Plus a `.contextignore` file in `context/repos/<slug>/` listing `node_modules/`, `.git/`, `dist/`, `build/`, `.next/`, `__pycache__/` (and a few more) — both the digester prompt and any agent reading the tree honour it. |
| Q3 | **Manual refresh + stale badge.** | The digester records the source repo's `git rev-parse HEAD` in the manifest entry. A small background poll (or the next-on-mention hook) compares; if moved, the manifest entry flips to `stale: true` and the dialog shows a "stale" pill with a "Refresh" button. No auto-rerun. |
| Q4 | **New header icon**, sitting between Participants and Settings. | Mirrors the Settings gear pattern — Tooltip-wrapped icon button → opens Context dialog. |
| Q5 | **Inline `@file` mentions deferred** to v1.1. | No changes to composer. User pastes paths inline if they want one-off context. |
| Q6 | **Always copy raw for docs** (no auto-digest). | If a doc is huge the user can ask any agent to summarize it into a managed artifact — same primitive we already have. |
| Q7 | **Notes via the Context dialog's add flow** — textarea step when "Note" is the kind. | Chat-right-click "Save as note" deferred as future work. |
| Q8 | **Reuse remediation-card pattern** for failures. | A failed-status entry shows a yellow card with one-line reason + "Retry" / "Open settings" button, exactly like the canvas's existing inline error remediation cards. |
| Q9 | **Shared context** — same `context/` for all agents. | No per-agent scoping. Each agent decides what it reads. |
| Q10 | **Honor `.gitignore`** when digesting and when listing the repo tree. | Combine the repo's `.gitignore` with our default `.contextignore` (Q2). Anything in either is invisible to the digester and to ad-hoc reads through the index. |

These map cleanly into the four phases in the next section.

---

## Implementation phases

Each phase is a discrete PR-sized chunk. Phases 1 and 2 land before
the UI even exists — the user can drive everything from the CLI and
see context entries by asking agents to read them.

### Phase 1 — Data + CLI

- New module `quorum_conductor/context/` with:
  - `manifest.py` — typed model + read/write for `context-manifest.yaml`
  - `index.py` — auto-render `context/index.md` whenever the manifest
    changes
  - `add.py` — `add_repo(path)`, `add_doc(path)`, `add_note(name, body)`,
    each returning the new manifest entry
  - `remove.py` — drop an entry, clean up its files / symlinks
  - `gitignore.py` — `.gitignore` + `.contextignore` matcher (Q10/Q2)
- CLI:
  - `quorum context add <path>` — auto-detects: dir → repo, file → doc
  - `quorum context add --kind=note <name> [--body=<text>]`
  - `quorum context list`
  - `quorum context remove <id>`
  - `quorum context refresh <id>` (stub for phase 2)
- Repo entries get a symlink only at this phase; digestion lands in
  phase 2. The `digest_status` field is set to `pending`.

### Phase 2 — Digester

- New `state.yaml` field `digester_handle: <handle | null>`. Helper
  `canvas/state.py` exposes a `digester` accessor.
- New module `quorum_conductor/context/digester.py`:
  - Background-runs a digest by spawning the configured handle via
    the existing `transport_adapter`.
  - Reads `.gitignore` + `.contextignore`, passes the merged ignore
    list to the digester prompt.
  - Captures stdout, writes `digest.md`, updates manifest entry
    (`digest_status`, `digest_summary`, `digest_at`,
    `source_git_ref`).
  - On failure, sets `digest_status: failed` with a `digest_error`
    string; reuses the same remediation-card payload format the
    canvas dispatcher uses (Q8) so the UI render is uniform.
- Stale detection: a small probe that re-runs `git rev-parse HEAD`
  in each repo entry on every state-poll tick; if moved, set
  `stale: true` on the manifest entry.

### Phase 3 — UI

- Header gets a new icon button (between Participants and Settings)
  → opens **Context dialog**.
- Dialog:
  - Three sections (Repos / Docs / Notes), each with a list of rows
    (name, source path in mono, status pill, delete button).
  - Bottom: "+ Add context" button → small wizard with:
    - Step 1: pick type (Repo / Doc / Note)
    - Step 2: paste path or click "Browse" (HTML
      `<input type="file" webkitdirectory>` for repos)
    - Step 3: optional name override (textarea for notes)
  - Footer: "Configured digester: @claude-opus · change in
    Settings →" linking to the new Settings section (also added in
    this phase).
- New SSE-driven hook `useCanvasContext` for the entry list +
  status updates; relies on the `context_revision` counter we bump
  in `state.yaml` on every manifest change.
- Settings dialog gains a "Default agents → Digester" dropdown.

### Phase 4 — Polish

- Stale-badge UX in the dialog (Q3): per-repo "stale" pill +
  "Refresh" button that POSTs to
  `/api/canvas/context/<id>/refresh`.
- Failure remediation cards (Q8) — reuse the same component used
  in chat for `gemini-trust` / `codex-trust` / etc.
- `.contextignore` defaults: shipped pattern list, with a
  per-workspace override at `context/.contextignore` if the user
  wants to add globs.
- HTTP API:
  - `GET    /api/canvas/context`
  - `POST   /api/canvas/context`
  - `DELETE /api/canvas/context/<id>`
  - `POST   /api/canvas/context/<id>/refresh`
