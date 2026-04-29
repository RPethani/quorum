# Quorum quickstart

End-to-end recipe for running your first deliberation. Assumes you've already cloned the repo and run `scripts/install.sh` (or `uv sync` + `pnpm install` manually). About 10 minutes.

## 1. Decide where the workspace lives

A workspace is a folder under your project. The conductor scaffolds it; you fill in the problem statement.

```bash
cd ~/projects/my-project   # or wherever you want
~/.quorum/conductor/.venv/bin/quorum init quorum
# Or, if you exported PATH:
quorum init quorum
```

Output:

```
initialised workspace at /Users/you/projects/my-project/quorum
mode: interactive

next steps:
  1. edit problem-statement.md with your problem statement
  2. add at least one cli handle to registers/participants.md
  3. run `quorum doctor` to verify your handles
  4. run `quorum start` to begin the conductor
```

## 2. Write the problem statement

Open `quorum/problem-statement.md` in your editor. The default template has the right shape; replace the placeholders with the actual question. The conductor will refuse to start with the placeholder content intact.

## 3. Register at least one agent CLI

Open `quorum/registers/participants.md`. The default file ships with `@human-rohan` only. Add a row per CLI agent you want to use. Example for Claude Code:

```markdown
| @claude-sonnet | Claude (Sonnet) | claude --print --model sonnet --add-dir . | claude-sonnet-4-6 | cli | 50/10 | fine_grained | (none) | green |
```

The `--add-dir .` matters — agents read protocol templates from their cwd, which the conductor sets to the workspace root.

## 4. Doctor

```bash
cd quorum
quorum doctor
```

This verifies each CLI binary is on PATH. Fix anything red before continuing.

## 5. (Optional) Run the setup wizard

Two terminals:

```bash
# Terminal 1
cd quorum
quorum serve

# Terminal 2
cd /path/to/quorum-repo/ui
pnpm dev
```

Open `http://localhost:3000/setup`, walk the five questions, click Apply.

If you'd rather edit `config.yaml` by hand, skip this step.

## 6. Run the conductor

```bash
quorum start         # daemonised; logs at runtime/conductor.log
# or
quorum run           # foreground; Ctrl-C to stop
```

The first thing that happens: the bootstrapper opens deliberation #0001 and routes it to your highest-fitness `bootstrapper`-eligible CLI agent. The agent reads `problem-statement.md` and the manifest archetypes under `protocol/manifest-templates/`, then proposes a complete outcome manifest. Review in the UI, then issue a DECISION via the "Compose move" form (or by editing the deliberation file directly).

## 7. Watch it unfold

`http://localhost:3000/workspace`:

- Left pane: deliberations list. Click to switch.
- Center: the active deliberation, contributions visible chronologically.
- Right: live activity feed (SSE-driven), participants below.
- Header: state badge, cost (`$X.XX / $50.00 (NN%)`), composing badge when an agent is running.

The header `●live` indicator says SSE is connected; `○polling` means the connection dropped and we're falling back to manual refresh.

## 8. Add context

Once the manifest is decided, add the context the deliberations need:

```bash
quorum context add-repo /path/to/your/repo --name backend --relevance medium
quorum context add-note conventions --text "We never propose modal dialogs."
quorum context add-doc /path/to/spec.md --name product-spec
```

Repos are agent-digested at registration (cost varies; medium-relevance Sonnet digest is typically $0.05–$0.20 for a small repo). Notes are always raw; docs are copied in raw and digested via the agent on use.

## 9. Step the loop or let it run

The loop scans your deliberations and routes the next pending role. Auto-bootstrapper aside, the typical flow is:

```
PROPOSAL  →  CRITIQUE  →  SYNTHESIS  →  DECISION (you, via the UI)
```

The deliberation transitions through OPEN / IN_REVIEW / SYNTHESIS / DECIDED. The Summary line you write on each DECISION compounds into `registers/summarized-decisions.md`, which is included in every later invocation's standing context.

## 10. When the workspace is done

The closing-ceremony deliberation is opened automatically when the manifest's checks clear. Issue the closing DECISION; the workspace transitions to `COMPLETED`. To put it on ice but keep the artifacts:

```bash
quorum archive --reason completed
```

Reverse with `quorum unarchive`.

## See also

- `docs/troubleshooting.md` — common failure modes and how to recover.
- `docs/architecture.md` — one-page overview of the conductor + UI + protocol.
- `docs/manual-protocol-exercise.md` — dry-run guide for exercising the protocol with three CLIs by hand (no conductor).
- `docs/vertical-slice-findings.md` — findings from the Phase-5 real-CLI vertical slice.
- `docs/decisions/` — implementation ADRs.
- `multi-agent-collab-hub-design.md` — the v0.18 design doc, the source of truth for *what* Quorum is.
