# Quorum

*Where premium AI subscriptions deliberate together.*

## What Quorum is

A quorum is the minimum number of members of a deliberative body needed to make valid decisions. Quorum (the project) is a local, file-first hub that lets multiple paid AI assistants — Claude, ChatGPT, Gemini, and others you already pay for — collaborate on hard problems through structured, auditable artifacts rather than ad-hoc copy-pasting.

The canonical journey: **vague thought → deliberation → critical human questions → synthesis → decided spec, ADR, or brief.**

Agents take turns appending typed *moves* (PROPOSAL, CRITIQUE, SYNTHESIS, DECISION, …) to Markdown files in a workspace folder under your project. A small Python *conductor* routes work to the right agent for each role, and a local Next.js UI lets you watch deliberations unfold, intervene, and approve the outcome. The repo is the medium; Markdown is the lingua franca; you are editor-in-chief.

Quorum's niche is **collaborative reasoning** — turning vague product ideas, architecture questions, research directions, and rough drafts into well-reasoned, decided artifacts. It is not a code-execution coordinator; tools like Cursor, Aider, and Windsurf already address that space.

## Status

**v1, feature-complete with two interactive phases pending.** Phases 0-12 + 14 are shipped; phases 11 (live permission-broker proxy) and 13 (real-world cross-archetype validation) are intentionally deferred to user-driven sessions and tracked in `docs/decisions/003-permission-broker-deferral.md` and `docs/decisions/005-phase-13-real-world-testing-deferral.md`. The conductor and UI are runnable today — see [Quickstart](docs/quickstart.md).

## What v1 ships

**Conductor (Python, `quorum` CLI):**

- `quorum init` — scaffolds a workspace with the §7 folder layout, copies the protocol templates and standing prompt, installs sane `config.yaml` defaults.
- `quorum doctor` — health-checks every registered handle's CLI binary on PATH.
- `quorum status` — workspace state, deliberation/artifact/decision counts, cost spend, stale lifecycle markers.
- `quorum start` / `quorum pause` / `quorum resume` — daemonised loop with `runtime/conductor.pid`.
- `quorum run` — foreground loop equivalent.
- `quorum step` — single-step debug invocation; useful when a CLI agent is misbehaving.
- `quorum serve` — local HTTP + SSE API the UI consumes.
- `quorum context add-repo / add-doc / add-note / list` — populate the §1.8 context surface.
- `quorum archive` / `quorum unarchive` — workspace lifecycle.

**Protocol:**

- 17 move types with templates under `protocol/templates/`.
- 5 manifest archetypes under `protocol/manifest-templates/` (saas-product, architecture-decision, research-direction, coding-plan, strategic-decision).
- The four-layer routing engine (per-deliberation pin → workspace override → fitness-based defaults → highest-cost fallback).
- Full per-section validator with anti-vacuousness rules (DECISION Summary line ≥30 / ≤120 chars and not in the reject-pattern list, PROPOSAL Alternatives required, EXPLANATION anti-confabulation).
- One-retry on validation failure with agent-readable feedback.
- Per-deliberation `flock` advisory locking for concurrent appends.
- `summarized-decisions.md` auto-maintenance for the standing context bundle.
- Cost ceiling enforcement (default $50, ON; pauses workspace when cumulative spend reaches the cap).

**UI (Next.js 15 + Tailwind v4 + shadcn-derived primitives):**

- `/workspace` — three-pane shell: deliberations list (left) + selected deliberation (center) + activity feed + participants (right). Live SSE updates; composing-state badges; cost-percent in the header.
- `/setup` — five-step setup wizard.
- `/settings` — eight panels per design-doc §9.8 Tier 2.
- `/settings/raw` — Tier-3 raw editor over the workspace's whitelisted YAML / Markdown files.
- `/permissions` — broker request inbox (data plane + decisions; live proxy deferred).
- `/dev-vertical-slice` — minimal step-by-step UI used by the Phase-5 vertical slice.
- `/design-system` — design-system showcase (light / dark in both modes).

**Tests:** 162 passing across the conductor (workspace lifecycle, routing, validator, retry, events, loop, bootstrapper, cost, server endpoints, context bundle, decisions summary). `mypy --strict` clean. `ruff` and `biome` clean.

## Install

```bash
git clone https://github.com/<owner>/quorum.git ~/.quorum
~/.quorum/scripts/install.sh
```

Or manually:

```bash
cd conductor
uv sync                      # creates .venv, installs Python deps
uv run quorum --help

cd ../ui
pnpm install                 # or npm / bun install
pnpm dev                     # starts the Next.js dev server on :3000
```

You also need at least one CLI agent on PATH (Claude Code, Gemini CLI, Codex, etc.). See [Quickstart](docs/quickstart.md) for the end-to-end setup.

## Repository layout

```
quorum/
├── README.md
├── LICENSE                                     MIT
├── multi-agent-collab-hub-design.md            v0.18 design — what to build
├── IMPLEMENTATION_BOOTSTRAP.md                 v0.1 build instructions
├── PHASES.md                                   phase ledger with statuses
├── DESIGN_SYSTEM.md                            UI tokens / components / motion
├── docs/
│   ├── architecture.md                         one-page system overview
│   ├── quickstart.md                           runnable end-to-end recipe
│   ├── troubleshooting.md                      common failure modes
│   ├── manual-protocol-exercise.md             dry-run guide w/ three CLIs
│   ├── vertical-slice-findings.md              Phase-5 findings record
│   └── decisions/                              implementation ADRs (5)
├── conductor/                                  Python conductor
│   ├── pyproject.toml
│   └── src/quorum_conductor/                   163 source files in 9 modules
├── ui/                                         Next.js 15 + Tailwind v4
│   ├── app/                                    workspace, setup, settings, …
│   ├── components/                             design-system + workspace primitives
│   └── lib/api/conductor.ts                    typed HTTP client
├── protocol/
│   ├── PROTOCOL.md
│   ├── templates/                              17 move templates
│   └── manifest-templates/                     5 manifest archetypes
├── prompts/
│   └── agent-standing-prompt.md
├── routing-defaults/
│   └── routing-defaults.yaml                   fitness, cost, USD-per-invocation
└── scripts/
    └── install.sh
```

## What's not in v1

- **Cross-workspace context registers** — every workspace re-adds repos / docs / URLs. (Design-doc §1.8 deferred to v2.)
- **MCP transport for agents** — v1 ships CLI + manual transports only.
- **Web URL ingestion** — `add-url` and trafilatura-based fetching are deferred per ADR-002.
- **Document digestion** for PDF / Word — `add-doc` copies in raw; markdown-only in v1 per ADR-002.
- **Async digestion** — `add-repo` blocks on the digester invocation. Async lands when the UI shows progress.
- **Live permission-broker proxy** — pty-based stdin/stdout interception of agent permission prompts. Per ADR-003.
- **Cross-archetype real-world testing** — the Phase-13 sweep is user-driven. Per ADR-005.

## License

MIT. See `LICENSE`.
