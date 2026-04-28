# Quorum — Implementation Bootstrap

> **You are Claude Code, working inside the user's local clone of the `quorum` repo.** This document is your operating instruction set for building Quorum from scratch. Read it fully before doing anything else.

---

## 0. Read this first — the contract

You have two source documents in this repo:

- **`multi-agent-collab-hub-design.md`** — the design doc (v0.18). 3800+ lines of decided architecture, protocol, UX, and lifecycle. **This is the spec.** It is the source of truth for *what to build*. It is not a starting point for further design. It is implementation-ready. Decisions in it are not for you to revisit.
- **`IMPLEMENTATION_BOOTSTRAP.md`** — this document. The source of truth for *how to build* — phasing, validation, quality bar, conventions, design system, working agreements.

Where the two conflict (rare), this document defers to the design doc. If something feels under-specified to you in the design doc, it is almost certainly *intentionally* delegated to implementation discretion (e.g., specific Tailwind class choices, exact wording of error messages). Use your judgment.

**Critical boundaries:**

1. **You do not redesign the system.** v0.18 is the result of 17+ rounds of deliberate design work with the user. Your role is to implement it faithfully, not to "improve" it.
2. **You never commit or push to git without explicit user approval.** Stage changes for review. Make commits ready (with messages) but do not run `git commit` or `git push`. The user will run those commands themselves after reviewing.
3. **You build in phases with manual validation gates.** After each phase, you stop, summarize what's done, surface what to verify, and wait for the user to give the next "go." This is the most important working agreement — do not violate it.
4. **You ask before making decisions that aren't in the design doc and aren't trivial.** "Should this button be 8px or 12px tall" is trivial — pick one. "Should we use Postgres or SQLite" would be non-trivial but is already decided in this doc. If you genuinely encounter a non-trivial gap, surface it before proceeding.

If you are tempted to do "just one more thing" past the phase boundary because it seems related, **stop**. Phase boundaries exist for the user's review process. Cross them only on explicit "next phase" approval.

---

## 1. The tech stack — locked

**Backend / conductor:**
- Python 3.11+
- `uv` for package management (lockfile: `uv.lock`)
- `pyproject.toml` for project config
- Async where natural (subprocess management, file watching, websocket); sync where simpler is better
- Type hints everywhere (`mypy --strict` clean)
- Standard library where possible; minimal external deps

**Frontend / UI:**
- Next.js 15+ (App Router)
- TypeScript (strict mode)
- Tailwind CSS v4 (using `@theme` for design tokens)
- **shadcn/ui** as the component foundation (copy-paste, owned by us, customized to our design system)
- `next-themes` for light/dark mode
- `lucide-react` for icons (consistent stroke-width family)
- `cmdk` for command palette (we'll need one eventually)

**Why Next.js over SvelteKit:** Claude Code (and LLMs generally) handle React with much higher fidelity than Svelte. For an LLM-built project this is the dominant consideration.

**Why shadcn/ui over Material/Mantine/Chakra:** unstyled-by-default, components live in our codebase as files we own and modify, perfect for an opinionated minimalist design system, no version-lock drama.

**Communication:**
- Conductor exposes a small HTTP + WebSocket server for the UI
- WebSocket pushes file-change events; HTTP for command actions
- File system is the actual source of truth; the server is a window into it

**Database:** none. Everything is files (Markdown, YAML, JSONL). This is a Quorum design commitment — preserve it.

**Testing:**
- Python: `pytest`, `pytest-asyncio`
- TypeScript: `vitest` for unit tests, Playwright for end-to-end UI flows (added in later phases)

**Lint/format:**
- Python: `ruff` (formatter + linter, replaces black/flake8/isort)
- TypeScript: `biome` (formatter + linter, replaces prettier/eslint) — chosen for speed and zero-config

**Repo layout (top-level after Phase 1):**

```
/quorum
├── README.md                              # what is Quorum, how to install, status
├── LICENSE                                # MIT
├── .gitignore
├── multi-agent-collab-hub-design.md       # the spec — kept in repo, never edited by you
├── IMPLEMENTATION_BOOTSTRAP.md            # this document — kept in repo, never edited by you
├── PHASES.md                              # high-level phase plan you produce in Phase 0
├── DESIGN_SYSTEM.md                       # the design system spec you produce in Phase 2
├── docs/
│   ├── architecture.md                    # one-page system overview you produce
│   └── decisions/                         # implementation ADRs (different from runtime ADRs)
├── conductor/                             # Python package
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/quorum_conductor/
│   │   ├── __init__.py
│   │   ├── cli.py                         # entry point: `quorum` command
│   │   ├── core/                          # conductor loop, routing, validator
│   │   ├── transport/                     # CLI invocation, stdin/stdout management
│   │   ├── context/                       # digester, doc/url/note handling
│   │   ├── workspace/                     # state.yaml, lifecycle, paths
│   │   ├── server/                        # HTTP + WebSocket
│   │   └── events/                        # events.jsonl emission, event schemas
│   └── tests/
├── ui/                                    # Next.js app
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── biome.json
│   ├── app/                               # App Router pages
│   ├── components/
│   │   ├── ui/                            # shadcn primitives (owned, modified)
│   │   ├── design-system/                 # tokens, theme provider, base atoms
│   │   ├── deliberation/                  # move cards, deliberation timeline
│   │   ├── workspace/                     # layout, sidebar, header
│   │   ├── settings/                      # the eight panels
│   │   └── permissions/                   # permission request cards (Phase 11)
│   ├── lib/
│   │   ├── api/                           # client for conductor's HTTP/WS
│   │   ├── theme/                         # theme provider, tokens
│   │   └── utils.ts                       # shadcn's cn() lives here
│   └── public/
├── protocol/                              # the actual /protocol/ contents from the design doc
│   ├── PROTOCOL.md                        # v0.1 protocol spec (you write this in Phase 1)
│   ├── templates/
│   │   ├── deliberation.md
│   │   ├── proposal.md
│   │   ├── critique.md
│   │   ├── synthesis.md
│   │   ├── decision.md
│   │   ├── question.md
│   │   ├── answer.md
│   │   ├── deputy_decision.md
│   │   ├── revision.md
│   │   ├── artifact_revision.md
│   │   ├── abstain.md
│   │   ├── interjection.md
│   │   ├── override.md
│   │   ├── reopen.md
│   │   ├── drop.md
│   │   ├── steer.md
│   │   ├── clarify.md
│   │   ├── explanation.md
│   │   ├── adr.md
│   │   └── task.md
│   └── manifest-templates/
│       ├── saas-product.md
│       ├── research-direction.md
│       ├── architecture-decision.md
│       ├── coding-plan.md
│       └── strategic-decision.md
├── prompts/                               # standing prompts and overrides
│   ├── agent-standing-prompt.md
│   └── overrides/                         # per-handle (filled in Phase 13)
├── routing-defaults/
│   └── routing-defaults.yaml              # bundled defaults for offline init
├── scripts/
│   ├── install.sh                         # the user-facing installer
│   └── dev.sh                             # local dev convenience
└── tests/
    └── integration/                       # cross-component integration tests
```

You will produce most of this. Some directories start empty and fill in later phases — note them as you go.

---

## 2. The phase plan — locked

You will work through these phases in order. After each, **stop, summarize, wait for "next phase" approval.** Do not chain phases.

The phases below correspond to (and refine) the build order in §14 of the design doc. Where the design doc says "5-6 weeks for v1" — that's an estimate for a focused human builder. Your wall-clock will be different; the user will gate progression.

### Phase 0 — Plan & repo skeleton

**Goal:** produce the planning artifacts and the bare repo structure. No code yet.

Produce:
- `PHASES.md` — high-level phase descriptions, what each delivers, validation criteria for each
- `docs/architecture.md` — one page summarizing the system at a high level (conductor, UI, file system, agents, MCP-future). Aimed at someone who hasn't read the design doc.
- `README.md` — what Quorum is (lifted from §0.5 of the design doc), what state the project is in (under construction), how to install (placeholder for now), license note.
- `LICENSE` — MIT, copyright "the user" (write `Copyright (c) 2026 Quorum Contributors` — let the user edit if they want their name).
- `.gitignore` — Python, Node, IDE files, OS files, `/runtime/` (per design doc), `__pycache__/`, `node_modules/`, `.next/`, etc.
- The empty directory structure from §1 above (use `.gitkeep` files for empty dirs).

**Validation gate:** user reads `PHASES.md` and `docs/architecture.md` and confirms direction.

### Phase 1 — Protocol artifacts (no code)

**Goal:** produce all the static protocol files. These are pure Markdown / YAML.

Produce:
- `protocol/PROTOCOL.md` v0.1 — distilled from §4, §5, §6 of the design doc. The actual spec agents will be told to follow.
- `protocol/templates/*.md` — one file per move type (~20 files), each containing the canonical structure with placeholder text and inline `<!-- guidance -->` comments showing what each section should contain. Source: §5 and §8.
- `protocol/manifest-templates/*.md` — five templates listed in §1.7. Each is a starter manifest for a project archetype.
- `prompts/agent-standing-prompt.md` — the core standing prompt from §11, including all augmentations (context-discipline, permission-discipline, explainer-specific, autonomous-mode, deputy-mode). Use clear sectioning so we can extract subsets per invocation.
- `routing-defaults/routing-defaults.yaml` — fitness ratings matrix for canonical handles. Base this on §3.6's specs. Include Opus, Sonnet, Haiku, Gemini Pro, Gemini Flash, GPT-5, and an `explainer` row per design.

**Validation gate:** user spot-checks 2-3 templates and the standing prompt. Confirms protocol artifacts feel right.

### Phase 2 — Design system specification

**Goal:** produce `DESIGN_SYSTEM.md` and the foundational design tokens. No application UI yet.

Produce:
- `DESIGN_SYSTEM.md` — the full spec (see §3 of this document). Tokens, type ramp, spacing, components, motion, accessibility.
- `ui/components/design-system/tokens.css` — CSS custom properties for both light and dark modes
- `ui/components/design-system/theme-provider.tsx` — `next-themes` wrapper with our defaults
- `ui/tailwind.config.ts` — wired to consume our tokens via `@theme`
- A single demo route `ui/app/_design-system/page.tsx` (private, dev-only path) that renders every atom and component variant with both light and dark mode visible. **This is the design system showcase** — it lets the user verify the system before any product UI is built on top.

**Validation gate:** user runs `cd ui && pnpm dev` (or equivalent), navigates to `/_design-system`, and confirms the system feels right in both modes.

### Phase 3 — Manual protocol exercise (NO code, but you write notes)

This corresponds to step 3 of the design doc's build order. It's not strictly your work to do — the *user* is the one who would manually exercise the protocol. But you can *prepare* for it:

Produce:
- `docs/manual-protocol-exercise.md` — a guide the user can follow to manually exercise the protocol with three CLI agents on a small problem. Lists exact commands, what to look for, what to record. Includes a worked example (a fictional simple problem with sample agent invocations).

**Validation gate:** user reviews the guide and decides whether they want to actually do the exercise (their call). Skipping is allowed — but the guide exists for when they (or a future contributor) want it.

### Phase 4 — Conductor core (Python)

**Goal:** the conductor as documented in §10. Working CLI commands, no UI yet, no permission broker, no fancy context surface.

This phase is large. Subdivide internally:

- 4a: scaffolding — `pyproject.toml`, `uv` lockfile, package layout, `quorum` entry point, `quorum --help`
- 4b: workspace lifecycle — `init`, `status`, `doctor`, `archive`, `unarchive`, file scaffolding
- 4c: routing engine — read participants.md and routing-defaults, score handles for roles, log decisions
- 4d: invocation — spawn CLI process, render prompt, capture stdout, append validated move, lifecycle markers
- 4e: validator — move structure validation per §5; reject vacuous Summary lines; one-retry on failure
- 4f: loop — `start`/`pause`/`step`/`run`/`resume`, parallel invocations with per-deliberation locks
- 4g: events — events.jsonl emission with full schema from §10.5
- 4h: bootstrapper — handles deliberation #0001 (manifest creation)
- 4i: cost ceiling — per-invocation cost tracking, per-workspace ceiling enforcement (default $50, ON)
- 4j: tests — pytest suite covering each module

Permissions in this phase: pass restrictive `--allowedTools` flags to CLIs that support it. Out-of-allowlist requests fail the move cleanly. **Broker is not built in this phase** — it's Phase 11.

**Validation gate:** user runs `quorum init` in a test directory; sees scaffolding; runs `quorum status`; sees clean state. We can't actually run end-to-end yet without the UI for problem statement entry, so this phase ends with a "scaffolding works, conductor commands respond correctly" check.

### Phase 5 — Vertical slice (first end-to-end deliberation)

This is the design doc's mandated milestone (build order step 5). Use the *minimum viable* UI — literally a Markdown file viewer with a "run next step" button. Goal is to validate the protocol works before building real UI.

Produce:
- `ui/app/_dev-vertical-slice/page.tsx` — minimal UI: shows current deliberation file rendered as Markdown, has a "step" button that calls conductor's `step` endpoint, refreshes view. Uses the design system but is intentionally crude.
- A test scenario: user creates a workspace, fills in a tiny problem statement (provide a sample), registers two real CLI agents, and runs `step` repeatedly. Observes whether the protocol behaves.
- `docs/vertical-slice-findings.md` — *you* fill this in after the user runs the slice and reports back. Capture any prompt issues, validator gaps, routing issues, etc.

**Validation gate:** user runs the slice end-to-end on a small real problem. Reports findings. You update PROTOCOL.md, standing prompt, validator, conductor as needed before proceeding to Phase 6. **Do not skip this gate, and do not proceed to Phase 6 without addressing what came out of it.**

### Phase 6 — Context surface

§1.8 of the design doc, fully. Repos, documents, web URLs, notes. The digester (relevance-tiered model selection). Background job queue. Freshness tracking. Conductor's context bundle assembly per invocation.

UI for this phase: still minimal. CLI commands and back-end logic working; UI panels will be built in Phase 9.

**Validation gate:** user adds a repo to a workspace via CLI command (we'll add a `quorum context add-repo` etc. for now); digestion runs; bundle assembly is verified by inspecting an invocation's context via events.jsonl.

### Phase 7 — UI shell (the real one)

The three-pane layout from §9.5. Workspace setup wizard from §9.8 Tier 1. Move card primitives. Manifest progress view. Theme provider integrated. All using the design system from Phase 2.

**Validation gate:** user opens the UI in browser; sees the empty workspace shell; can navigate panels; design system feels right; light/dark mode works.

### Phase 8 — UI live updates + streaming

File-watcher (server-side, pushes via WebSocket), composing/complete/failed move-card states, activity feed sourced from events.jsonl, deliberation timeline, routing-decision visibility, cost ceiling progress display.

**Validation gate:** user runs a deliberation and watches it unfold live in the UI.

### Phase 9 — Settings UI panels

The eight panels from §9.8 Tier 2. Each panel's full functionality. Frozen / live / live-with-effects indicators. Confirmation dialogs. Permissions panel shows broker-disabled state with toggle (broker itself comes in Phase 11).

**Validation gate:** user navigates each panel, edits a few settings, verifies behavior matches design doc.

### Phase 10 — Raw YAML editor + human response forms

§9.8 Tier 3 raw editor. The structured response form (§9.7) and human-initiated move forms (§12.5) — INTERJECTION, OVERRIDE, REOPEN, DROP, STEER, CLARIFY.

**Validation gate:** user issues each human-initiated move type; verifies it round-trips correctly.

### Phase 11 — Permission broker (opt-in feature)

§10.6, the full broker. stdin/stdout pipe management, prompt detection per CLI, response routing, BLOCKED_ON_PERMISSION state, permission request cards in UI, auto-approval policy, capability-aware routing.

**Build standalone first** (per design doc): a small Python prototype that wraps a single CLI and validates the pipe pattern works, before integrating into the conductor.

**Validation gate:** user enables broker in Settings, triggers an out-of-allowlist request, approves it, sees the agent proceed. Disables broker, triggers another request, sees it fail cleanly.

### Phase 12 — Standing prompt iteration (dedicated week)

§14 step 13 of design doc. Test each prompt augmentation against gaming behavior. Specifically:
- Vacuous Alternatives sections → tune until consistently real
- Stakes misclassification → tune
- Generic gap acknowledgment in EXPLANATIONs → tune
- Prompt-length instruction-skipping → measure tokens, refactor if approaching limits
- Summary line vacuousness → tune the validator and the prompt's framing

This phase is heavy on iteration with real CLI invocations. Costs real money (LLM calls). The user should monitor the cost ceiling closely during this phase — it's the most token-intensive phase.

**Validation gate:** user agrees the agents behave well across the test scenarios.

### Phase 13 — Real-world testing

Run 3-5 representative workspaces of different types (saas product, research direction, architecture decision, etc.). Observe failures across full cycle. Fix protocol/prompts/UI as issues surface.

**Validation gate:** user is confident v1 works well enough to share.

### Phase 14 — Polish, documentation, packaging

- README finalization
- Installation script polish
- Quickstart guide
- Troubleshooting doc
- Final pass on UI consistency
- Final pass on error messages

**Validation gate:** v1 ships.

---

## 3. The design system — locked

This is the design system spec. Codify it in `DESIGN_SYSTEM.md` during Phase 2 with this as the source. Do not deviate without explicit permission.

### 3.1 Aesthetic principles

The user's directive: *minimalist, simple, primarily black-and-white, thoughtful accent colors only where they add meaning, lighter tones that work in both light and dark modes*.

Apple's Pro design language (Jony Ive era) is the closest reference point. Specifically:

- **Restraint over decoration.** Whitespace earns its keep. Borders are 1px when present at all. Drop shadows are rare and subtle (used to elevate, not to embellish).
- **Type over chrome.** Typography carries the weight. Buttons can be just text in many cases. Cards are defined by spacing more than by visible borders.
- **Neutral first, color as signal.** Color isn't decoration; it's communication. A button is colored because it represents an action with consequence. A status badge is colored because it conveys state. Decorative color is forbidden.
- **Calm motion.** Transitions are 150-200ms with `ease-out`. No bouncing, no flourishes. The system feels considered, not playful.
- **Grid-disciplined spacing.** 8px base unit. Everything is a multiple. Even when the user can't see the grid, they feel it.

### 3.2 The neutral scale

Use a 9-step neutral scale (`neutral-50` through `neutral-950` in Tailwind's naming). These are the workhorses. Both light and dark modes use the same scale; mode just inverts which end of the scale is foreground.

- True extremes: `neutral-50` = `#FAFAFA`, `neutral-950` = `#0A0A0A`. Not pure white/pure black — pure values produce harsh contrast and reduce legibility especially in dark mode.
- Intermediate steps follow Tailwind's natural neutral progression but **skewed slightly cool** (a subtle blue undertone, ~2% saturation in HSL). This produces a more "engineered" feel than warm grays. Cool grays read as precise and intentional; warm grays read as friendly and approachable. We want precise.

**Light mode mapping:**
- Background: `neutral-50` (canvas), `neutral-100` (recessed surface), `white` for elevated cards
- Foreground: `neutral-950` (primary text), `neutral-700` (secondary), `neutral-500` (tertiary/disabled)
- Borders: `neutral-200` (default), `neutral-300` (emphasized)

**Dark mode mapping:**
- Background: `neutral-950` (canvas), `neutral-900` (recessed surface), `neutral-800` for elevated cards
- Foreground: `neutral-50` (primary text), `neutral-300` (secondary), `neutral-500` (tertiary/disabled)
- Borders: `neutral-800` (default), `neutral-700` (emphasized)

The principle: the relationship between layers should feel similar in both modes. If light mode goes canvas→recessed→elevated as `50 → 100 → white`, dark mode mirrors it as `950 → 900 → 800`. Visual hierarchy is preserved.

### 3.3 The accent palette — restraint

**Five accents only.** No more. Each has a job. Each has a light-mode tone and a dark-mode tone, designed so contrast and feel stay consistent across modes.

| Token | Job | Light tone | Dark tone | Use only for |
|---|---|---|---|---|
| `accent-primary` | Primary action / linkable | `#3B82F6` (blue-500) | `#60A5FA` (blue-400) | Primary buttons, focused inputs, active links, the user's avatar |
| `accent-success` | Decided / completed / green-light | `#10B981` (emerald-500) | `#34D399` (emerald-400) | DECISION badges, COMPLETED status, "yes" affirmations |
| `accent-warning` | Blocked / pending / attention-needed | `#F59E0B` (amber-500) | `#FBBF24` (amber-400) | BLOCKED states, "your turn" indicators, pending permissions |
| `accent-danger` | Failed / refused / destructive | `#EF4444` (red-500) | `#F87171` (red-400) | Failed invocations, denied permissions, destructive action confirmations |
| `accent-muted` | Auxiliary / informational | `#8B5CF6` (violet-500) | `#A78BFA` (violet-400) | EXPLANATION moves (visually subordinate), INTERJECTION origin marker, audit-trail metadata |

**Light tone choices** are mid-saturation, mid-lightness (Tailwind's `-500` for most). They work on white-ish backgrounds without being harsh.

**Dark tone choices** are one step lighter (Tailwind's `-400`). On near-black backgrounds, slightly lighter accents read more clearly without being neon.

**Critically: every accent has a "weak" variant** for backgrounds, badges, and tinted surfaces. E.g., `accent-primary-weak` is `blue-100` (light mode) / `blue-950` (dark mode) — used to tint a button's hover state, the background of a "your turn" callout, etc. The weak variants are what lets us use color *systemically* without it ever feeling loud.

### 3.4 Typography

**Two typefaces, three roles:**

- **`Inter`** — primary UI. Variable font; we use weights 400, 500, 600, 700 only. Variable axes for optical sizing.
- **`JetBrains Mono`** — code, agent handles, IDs, timestamps, keyboard shortcuts. Wherever the user is looking at "machine text."

**Type ramp** (mobile-respecting, but UI is desktop-primary):

| Token | Size / line-height / weight | Use |
|---|---|---|
| `text-xs` | 12 / 16 / 500 | Metadata, timestamps, tertiary labels |
| `text-sm` | 14 / 20 / 400 | Body, table cells, most UI |
| `text-base` | 15 / 24 / 400 | Reading content (deliberation prose) |
| `text-md` | 16 / 24 / 500 | Medium-emphasis labels, button text |
| `text-lg` | 18 / 28 / 600 | Section titles, card headings |
| `text-xl` | 22 / 32 / 600 | Page subheadings |
| `text-2xl` | 28 / 36 / 700 | Page titles, deliberation titles |
| `text-3xl` | 36 / 44 / 700 | Workspace name (rarely used) |

**Mono ramp** is one step smaller than the prose equivalent (e.g., when prose is `text-sm`, mono inline code is `text-xs`). Mono is naturally heavier; the size offset compensates.

**Letter-spacing:** default 0 for body, `-0.01em` for headings (subtle tightening for cleanliness), `0.02em` for all-caps labels (necessary for legibility).

**Numerals:** all numerals are tabular (`font-variant-numeric: tabular-nums`). This matters more than people realize — counts, costs, timestamps, durations align vertically in tables and lists.

### 3.5 Spacing & layout

**8px base.** Spacing tokens: `1` = 4px (only for tight intra-component cases), `2` = 8px, `3` = 12px, `4` = 16px, `5` = 20px, `6` = 24px, `8` = 32px, `10` = 40px, `12` = 48px, `16` = 64px, `20` = 80px, `24` = 96px.

**Container widths:** content reads best at 65-75 characters per line. For deliberation prose pane, max-width is `60ch`. Settings panels max at `48rem`. The activity feed has no max — it's a list.

**The three-pane layout (§9.5):**

- **Left rail (sidebar)**: 280px fixed, collapsible to 60px (icon-only). Contains workspace switcher (later), deliberation list, manifest progress.
- **Center pane (main):** flexible, this is where the active deliberation lives. Reading-width capped per above.
- **Right rail (activity / context):** 360px, collapsible to 0. Activity feed, "your turn" cards, permission requests, settings panel when open.

**Responsive:** desktop-primary. At <1024px width, right rail collapses to a slide-over. At <768px, left rail also collapses. We don't pretend this is a mobile app, but it doesn't break.

### 3.6 Border, radius, shadow

**Borders:** 1px, never thicker. Color: `neutral-200` light / `neutral-800` dark for default; `neutral-300` light / `neutral-700` dark for emphasized.

**Radius:** four steps only.
- `radius-none` (0) for tables, code blocks
- `radius-sm` (4px) for inputs, small buttons
- `radius-md` (8px) for cards, modals, larger buttons
- `radius-lg` (12px) for the workspace shell, large surfaces

**Shadow:** three steps, all very subtle.
- `shadow-sm` — barely-there, used for subtly-elevated cards on hover
- `shadow-md` — popovers, dropdowns
- `shadow-lg` — modals, sheets

In dark mode, shadows are barely visible (dark on dark). Compensate with a 1px border on elevated surfaces to keep them legibly separated.

### 3.7 Component contracts

The shadcn primitives we use (and customize in `ui/components/ui/`):

- `Button` — variants: `default` (filled neutral), `primary` (filled accent-primary), `outline` (1px border, transparent fill), `ghost` (no border, no fill), `destructive` (filled accent-danger). Sizes: `sm`, `md` (default), `lg`. Icon-only variant has square aspect ratio.
- `Card` — basic surface. Variants: `default` (1px border, no shadow), `elevated` (shadow-sm + 1px border), `recessed` (background `neutral-100`/`neutral-900`, no border).
- `Input`, `Textarea`, `Select`, `Combobox` — all share the same focused state: 1px border becomes `accent-primary`, plus a 2px outer ring at `accent-primary-weak`.
- `Badge` — pill-shaped, `text-xs`, padding `1.5/3`. Variants per accent: `primary`, `success`, `warning`, `danger`, `muted`, `neutral`. Each uses the *weak* variant of the accent for background, the strong variant for text.
- `Tooltip` — appears on hover, 200ms delay. Mono font for keyboard shortcuts, sans for prose tooltips.
- `Dialog`, `Sheet`, `Popover`, `DropdownMenu` — standard shadcn behaviors with our radius and shadow tokens.
- `Tabs` — underline style, not pill style. Active tab has a 2px bottom border in `accent-primary`; inactive tabs have 1px in `neutral-200`/`neutral-800`.
- `Separator` — 1px, `neutral-200`/`neutral-800`. Vertical separators have `mx-3`; horizontal have `my-3`.

**Custom components (we build, not from shadcn):**

- `MoveCard` — the central artifact. Header line per §5 reference convention, body sections rendered as Markdown subtypes. Composing state has a subtle pulsing left border in `accent-primary`. Failed state has a strikethrough on the header and a `accent-danger-weak` background. Variants for each move type with subtly different left-border colors using the accent palette per move category.
- `DeliberationTimeline` — vertical thread of move cards. Compact (150px) and expanded (full) modes.
- `ManifestProgressBar` — the "outcome manifest progress" view from §1.7's UI mockup. Progress bar uses `accent-success` for complete, `accent-warning` for in-progress.
- `YourTurnCallout` — the affordance when the user's input is needed. `accent-warning-weak` background, small `accent-warning` icon, sticky-top-of-pane positioning.
- `PermissionRequestCard` — Phase 11. Visually distinct from regular move cards: `accent-warning-weak` outer ring, lock icon prominently, action buttons inline.
- `CostChip` — running cost display in the workspace header. Mono numerals, `accent-warning` text when >80% of ceiling.
- `HandleAvatar` — small circular badge with the handle's first letter and a deterministic accent color from a fixed palette (independent of the 5 accents — these are *avatar* colors, allowed to be slightly more varied: 8 colors, all desaturated mid-tones). The same handle always gets the same color.

### 3.8 Motion

- All transitions: 150ms `cubic-bezier(0.16, 1, 0.3, 1)` — Framer's "ease-out-expo." Decelerates into rest.
- Page transitions: 200ms. Slightly slower for spatial coherence.
- Modal/sheet enter: 250ms. The longer time signals "this is now a focused context."
- Composing dot-pulse on move cards: 1.5s loop, 60% opacity at minimum (never invisible — always reads as "still working").
- Hover transitions on buttons: 100ms (immediate response to user input).
- No bounces. No springs. No spinning loaders unless absolutely necessary (use a subtle dot-pulse instead).

### 3.9 Iconography

Lucide icons, stroke width `1.5` (slightly lighter than default `2`). Sizes: `16px` (inline), `20px` (button-icons), `24px` (nav), `32px` (large states like empty-states).

Standard mappings (so icon usage is consistent):
- Status: `CircleCheck` (success), `CircleAlert` (warning), `CircleX` (error), `Circle` (idle), `CircleDot` (active/in-progress)
- Actions: `Play` (start), `Pause` (pause), `RotateCw` (refresh), `Copy` (copy), `Download` (export), `Settings2` (settings)
- Navigation: `ChevronRight`/`ChevronDown` (disclosure), `ArrowRight` (proceed)
- Object types: `MessageSquare` (deliberation), `FileText` (artifact), `Users` (participants), `BookOpen` (context), `KeyRound` (permissions), `Clock` (timeline)

Avoid icon-only buttons except for tightly-constrained spaces (toolbars, table actions). Always pair with tooltip.

### 3.10 Accessibility

- Color contrast: all text-on-background combinations pass WCAG AA at minimum. Primary text on canvas: AAA.
- Focus indicators: 2px ring in `accent-primary-weak`, never relying on color alone — also a 1px shift to `accent-primary` on the bordered edge.
- Keyboard navigation: every interactive element is reachable via Tab. Visible focus order matches visual order. Skip-to-content link at top of pages.
- Screen reader labels: every icon-only button has `aria-label`. Move cards have a hidden `aria-describedby` summarizing the move.
- Reduced motion: respect `prefers-reduced-motion`. Composing pulse becomes a static dot. Page transitions become instant.

### 3.11 Light/dark mode handling

- System preference is the default (`next-themes` with `defaultTheme="system"`).
- User can override via a toggle in the workspace header — three states: `light`, `dark`, `system`.
- Preference persists in localStorage.
- **No flash of incorrect theme** — `next-themes` handles the SSR/CSR mismatch via the `suppressHydrationWarning` pattern.
- Every component must be tested in both modes during development. The `_design-system` page (Phase 2) is the verification surface.

### 3.12 Empty states & error states

Every list, panel, and pane has a designed empty state. The pattern:

- Centered vertical layout
- 32px icon at top, in `neutral-400`/`neutral-600`
- One-line title, `text-md`, `neutral-700`/`neutral-300`
- One sentence of explanation, `text-sm`, `neutral-500`
- Action button if applicable, primary variant

Error states use the same layout with `accent-danger` for the icon and a more constructive title ("Something went wrong" → too vague; "Couldn't load deliberation #0014" → specific). Always include a recovery action.

### 3.13 Forbidden patterns

These are off-limits regardless of how convenient they seem:

- **No skeuomorphism.** No fake-paper textures, no gradients meant to look like physical material. Flat surfaces only.
- **No emoji as UI.** Emoji can appear in user-authored content (notes, problem statements). They do not appear in chrome.
- **No animated gradients, glows, parallax.** Anything that draws attention without conveying information is decoration. Decoration is forbidden.
- **No more than the 5 accents.** Tempting to add a sixth for "info" or "neutral-positive" — resist. The constraints produce the calm.
- **No nested cards.** A card inside a card is almost always a sign that two things should be combined or that the inner card should be a recessed surface.
- **No round-corner-on-some-sides-only** (unless tabs, where it's intentional). All corners of a surface get the same radius.
- **No icon-spamming.** If three list items in a row have decorative icons that aren't communicating different states, drop them.

### 3.14 The two design tests

For any UI you build, two checks:

1. **The grayscale test.** Convert your screen to grayscale (or just imagine it). Does the hierarchy still read clearly? If the only thing distinguishing two elements is color, the design is fragile. Re-do with type weight, spacing, or position carrying the hierarchy; reserve color for the *additional* signal.

2. **The whisper test.** If every element on the screen is shouting (bold text, colored backgrounds, strong borders), nothing is heard. Designed UI has a few things that draw the eye and many things that recede. Look at any screen you produce and ask: *what should the user see first? second? third?* If everything is competing equally, demote 80% of it.

These tests are how you catch over-design before the user has to.

---

## 4. Working agreements

### 4.1 Phasing

- **Stop at every phase boundary.** Summarize, list what's done, list what to verify, await "next" approval.
- **Within a phase, you may chain sub-tasks freely** — you don't need to ask for permission to write the next file in a phase. But never cross a phase boundary on your own.
- **If a phase's scope feels too big mid-work,** propose splitting it. Don't silently expand or shrink scope.

### 4.2 Git discipline (the firm rule)

You **never** run `git commit` or `git push`. Period. Even if it seems obviously fine. Even if the user said "go nuts." That referred to building, not committing.

What you do instead, after each phase:
1. Stage all your changes (`git add -A` is fine — the user has reviewed `.gitignore`)
2. Run `git status` to show what's staged
3. Print a proposed commit message in the format below
4. **Stop.** Wait for the user to either commit, ask for changes, or say "commit it for me" (which would be the only condition under which you'd run `git commit`, and even then you'd not push).

**Commit message format:**

```
<phase>: <short imperative summary>

<one or two paragraph body explaining what's in this commit and why>

Phase: <N> — <phase name>
Validates: <what the user can verify after this commit>
```

Example:

```
phase-2: design system spec and foundational tokens

Adds DESIGN_SYSTEM.md with full design system specification, the
neutral-and-five-accent palette, type ramp, spacing system, and
component contracts. Wires up CSS custom properties, theme provider
(light/dark/system), and Tailwind config to consume tokens. Adds a
private /_design-system showcase route renderring every atom and
component variant in both modes.

Phase: 2 — Design system specification
Validates: Run `cd ui && pnpm dev`, navigate to /_design-system,
verify the system feels right in both light and dark modes.
```

If the user says "commit and push," you may run `git commit`. You **still don't push**. Pushing is the user's call always — they may want to review the commit on their machine before pushing.

### 4.3 Decisions log

Anything you decide that isn't already in the design doc, log to `docs/decisions/NNN-<slug>.md` as a tiny ADR:

```markdown
# NNN: <decision title>

**Date:** YYYY-MM-DD
**Phase:** <N>
**Status:** active

## Context
<the situation that called for a decision>

## Decision
<what you decided>

## Reasoning
<why>

## Alternatives considered
- <option A>: <why rejected>
- <option B>: <why rejected>
```

These are *implementation* ADRs, separate from the runtime ADRs Quorum produces during deliberations. Keeping them as files lets the user audit your judgment after the fact.

If a decision feels load-bearing (would change architecture or tech stack), **ask before deciding**. If it's trivial (which font weight to use for a label), just decide and log.

### 4.4 When you're stuck

If you encounter something genuinely ambiguous in the design doc that blocks progress, the order of operations:

1. **Re-read the relevant section.** Often the answer is there and you missed it on first pass.
2. **Check the OQ register (§15).** The question may be explicitly resolved.
3. **Make a "best lean" decision and document it as an implementation ADR.** Most ambiguities have a clearly-better answer; don't paralyze on them.
4. **Surface to the user only if (a) the answer materially changes architecture, or (b) genuinely no clear lean exists.** Don't ask the user about font weights.

When you do ask the user, ask in a structured way: *"Phase X requires a decision on Y. The relevant context is Z. The two options are A and B. I lean A because [reason]. Which would you like?"* Make it easy for them to say "go with A" without having to research the question themselves.

### 4.5 Quality bar

This project's quality bar is high. The user has been explicit: *premium quality*. What that means concretely:

- **Code that I would be embarrassed to leave for someone else to maintain is not allowed.** Names are clear. Structure is intentional. Comments explain *why*, never *what*.
- **No dead code.** No commented-out blocks "in case we need them." Either delete or document.
- **No `// TODO` without an issue number or a `docs/decisions/` reference.**
- **Tests for the things that matter.** Conductor's routing, validator, lifecycle — tested. UI components — visual verification via the design system page is sufficient for v1; deeper testing in Phase 13.
- **Design system consistency.** Every UI element comes from the design system. New patterns added to the design system before being used in product UI. No one-off styles.
- **Honest naming.** A function that "tries" to do something is named `try_X`. A function that may fail is documented as may-fail. A function that mutates state is named with a verb that implies mutation.
- **Error messages that help.** "Error" is not an error message. "Couldn't read /path/to/file: permission denied. Fix: chmod +r the file or run with appropriate permissions" is.

### 4.6 What you don't do

- **You don't add features not in the design doc.** "It would be cool to also have X" — log it as a future consideration in `docs/future-considerations.md` and move on.
- **You don't refactor pre-emptively.** Refactor when there's clear benefit *now*; not for some imagined future.
- **You don't add dependencies casually.** Each new dependency (Python or JS) is logged as a decision with a one-line justification. The bar is "we genuinely couldn't do this acceptably without it." Most things we can.
- **You don't write speculative interfaces** (e.g., "a generic plugin system" when only one plugin exists). YAGNI. The design doc has explicit deferrals — honor them.
- **You don't use AI-generated code that you don't fully understand.** This sounds funny coming from an AI to an AI, but the principle: if you're tempted to copy a snippet from training data without understanding it, write the simpler version you do understand.

### 4.7 Cost awareness

You're going to use real model invocations during Phases 4-13 (the digester runs in Phase 6, the vertical slice runs real CLIs in Phase 5, the prompt iteration uses real CLIs in Phase 12). The user pays for these.

- The cost ceiling protects against runaway. Don't disable it during testing — exercise the ceiling, that's the point.
- For testing, use the cheapest model that exercises the path. Don't use Opus to test "does the validator catch a malformed move" — Haiku will do.
- For the dedicated prompt-iteration phase (12), expect real Opus invocations. Budget accordingly.

### 4.8 Cadence

This is a long project (5-6 weeks of focused work for the design's intended scope). Do not rush. The validation gates are not bureaucracy — they're the user's chance to catch direction issues early, when they're cheap to fix.

If you're moving fast and confident, that's good. If you're moving fast and the user's last review was three phases ago, slow down and surface a checkpoint.

---

## 5. Final words

You're being given a great deal of latitude. The trade for that latitude is rigor at the boundaries: phase gates honored, git discipline absolute, decisions logged, design system followed.

The user trusts the design doc to be right. Your job is to make the implementation *deserve* that trust. When you finish a phase and the user runs the verification, the response you want isn't "looks fine" — it's "this is exactly right."

That's the bar. Build to it.

When in doubt, the answer is usually:
- Less code, not more
- Less color, not more
- Less abstraction, not more
- Less feature, not more
- More restraint, not less

Begin Phase 0 when you're ready. Produce `PHASES.md`, `docs/architecture.md`, `README.md`, `LICENSE`, `.gitignore`, and the empty directory structure. Then stop and check in.

Good luck.
