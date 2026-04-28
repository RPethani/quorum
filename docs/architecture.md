# Quorum — System Architecture (one page)

This page summarises Quorum at a high level for someone who hasn't read the 3,800-line design doc. Authoritative details live in `multi-agent-collab-hub-design.md`; this page paraphrases.

## What Quorum does

Quorum coordinates multiple paid AI assistants (Claude, ChatGPT, Gemini, …) so they collaborate on a hard reasoning problem and produce a *decided* artifact — a spec, an ADR, a product brief, a research direction. The unit of progress is a typed *move* (PROPOSAL, CRITIQUE, SYNTHESIS, DECISION, …) appended to a Markdown deliberation file. The user is editor-in-chief: they pose the question, intervene when needed, and approve the final outcome.

Quorum scopes itself to **collaborative reasoning**, not concurrent code execution. Output specs are designed to flow into separate execution tools (Cursor, Aider, etc.).

## The five moving parts

```
                    ┌──────────────────────────────────────────────┐
                    │  Workspace folder  (the source of truth)     │
                    │  /quorum/                                    │
                    │   ├── deliberations/*.md   (move log)        │
                    │   ├── decisions/*.md        (ADRs)           │
                    │   ├── tasks/*.md            (specs/briefs)   │
                    │   ├── context/              (digested input) │
                    │   ├── participants.md       (agent registry) │
                    │   ├── config.yaml + state.yaml               │
                    │   ├── events.jsonl          (audit trail)    │
                    │   └── runtime/              (volatile)       │
                    └────────────────┬─────────────────────────────┘
                                     │  files are the API
            ┌────────────────────────┼────────────────────────────┐
            │                        │                            │
   ┌────────▼─────────┐    ┌─────────▼──────────┐    ┌────────────▼────────────┐
   │  Conductor (Py)  │    │     UI (Next.js)   │    │   Agent CLIs            │
   │  routing,        │◄──►│  three-pane shell, │    │   claude, codex, gemini │
   │  invocation,     │ WS │  live timeline,    │    │   spawned by conductor, │
   │  validation,     │HTTP│  settings panels,  │    │   prompted with         │
   │  lifecycle,      │    │  human response    │    │   standing prompt +     │
   │  events, locks   │    │  forms             │    │   per-handle overrides  │
   └──────────────────┘    └────────────────────┘    └─────────────────────────┘
```

1. **The workspace folder** is the actual source of truth — Markdown, YAML, JSONL. No database. Files compound; outputs accumulate; history is auditable in git.
2. **The conductor** (Python, ~300 lines for v1) is the autonomous loop. It scans inboxes, routes each pending role to a handle (per §3.6 fitness matrix), spawns the corresponding CLI process, captures stdout, validates the move structure, and appends it to the deliberation file under a per-deliberation file lock. It emits structured events to `events.jsonl` and writes lifecycle markers to `/runtime/` so the UI can show "agent started / composing / completed / failed" within ~100ms.
3. **The UI** (Next.js 15, App Router, shadcn/ui on Tailwind v4) is a local web app speaking HTTP + WebSocket to the conductor. It watches the workspace via the conductor's file-change push, renders the active deliberation, exposes the eight settings panels, and provides the human's response form and the human-initiated move forms (INTERJECTION, OVERRIDE, REOPEN, DROP, STEER, CLARIFY).
4. **The agent CLIs** are the existing paid assistants the user already has installed (Claude Code, Codex, Gemini, …). The conductor invokes them with a rendered prompt; they reply over stdout. Quorum has zero model intelligence of its own — the intelligence is in the agents, the protocol, and the standing prompt.
5. **The protocol** is a fixed Markdown vocabulary of typed moves. Agents are told to follow `protocol/PROTOCOL.md` and use the templates under `protocol/templates/`. The validator enforces structural compliance; semantic quality is enforced by prompting and by the human's editorial role.

## How a deliberation runs (happy path)

1. User runs `quorum init` in their project, registers a few handles in `participants.md`, fills in a problem statement, and runs `quorum start`.
2. The conductor's bootstrapper opens deliberation #0001 to draft the *outcome manifest* — what artifacts a "done" state requires.
3. With a manifest in place, the conductor opens further deliberations as needed, routing roles (proposer, critic, synthesizer, decider, explainer) to the most fit handle.
4. Agents append PROPOSAL → CRITIQUE → SYNTHESIS → DECISION moves to the deliberation files. The conductor validates and locks; the UI renders live.
5. When the protocol surfaces a question only the human can answer, the deliberation transitions to BLOCKED_ON_HUMAN; the user answers via the UI's structured response form.
6. Decisions become ADRs under `/decisions/`; specs and briefs become tasks under `/tasks/`; the manifest's progress bar fills as required artifacts are produced.
7. When all required artifacts exist and quality gates pass, the closing ceremony runs and the workspace transitions to COMPLETED.

## Permissions, cost, and safety

- **Permissions.** In v1, the conductor passes restrictive `--allowedTools` flags to CLIs that support it; out-of-allowlist actions fail the move cleanly. Phase 11 introduces an opt-in *permission broker* that proxies stdin/stdout, surfaces requests in the UI, and lets the user approve or deny live.
- **Cost ceiling.** A per-workspace dollar ceiling (default $50, ON) is enforced from Phase 4. Crossing 80% turns the cost chip amber; hitting 100% pauses the workspace.
- **Locks and recovery.** Per-deliberation `flock` advisory locks prevent concurrent appends to the same file. Stale lifecycle markers are reaped after 15 minutes by `quorum status` / `doctor`.

## What is *not* in scope

- Concurrent code editing or merge-conflict mediation.
- Server-hosted multiplayer mode. Quorum is local-first.
- A model API. Quorum exclusively wraps existing user-installed CLIs.
- A database. The file system is authoritative by design.

## Where to look next

- **Protocol:** `protocol/PROTOCOL.md` (v0.1 lands in Phase 1).
- **Conductor algorithm:** design doc §10.
- **UI layout & panels:** design doc §9.5–§9.8.
- **Routing and fitness:** design doc §3.6.
- **Move vocabulary and block format:** design doc §4–§5.
- **Workspace lifecycle and folder structure:** design doc §1.6, §7, §7.5.
