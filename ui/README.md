# Quorum UI

The Next.js 15 + Tailwind v4 web app that fronts the Python conductor.
This is the operator's window into a live workspace — Simple mode for
non-technical viewers, Advanced mode for the audit trail.

For the project as a whole, start at the repo root: [`README.md`](../README.md),
[`docs/quickstart.md`](../docs/quickstart.md), [`CLAUDE.md`](../CLAUDE.md).

---

## Stack

- **Next.js 15** (App Router) + **React 19**
- **Tailwind CSS v4** with project tokens in [`app/globals.css`](app/globals.css)
- **TypeScript strict** (no `any`)
- **shadcn-derived primitives** in [`components/ui/`](components/ui)
- **`@xyflow/react`** for the live system-flow diagram
- **Biome** for lint + format
- **Playwright** for self-verification snapshots (dev only)

No Redux, no React Query, no global state library. Components fetch
through [`lib/api/conductor.ts`](lib/api/conductor.ts) and rely on a
short interval poll plus the SSE `/api/stream` for liveness.

---

## Setup

```bash
# from repo root
scripts/install.sh        # one-shot: installs conductor + UI deps
# or, manually for the UI only:
cd ui
pnpm install
pnpm dev                  # http://localhost:3000
```

The UI assumes the conductor is running at `http://127.0.0.1:8500`.
Start it from a serving workspace:

```bash
cd conductor
uv run python -m quorum_conductor serve --workspace ~/quorum-test/quorum
```

> Always run the conductor from source. The `~/.local/bin/quorum`
> binary is a uv-installed snapshot from an earlier source state and
> will silently run old code. (See `.claude/rules/non-negotiables.md`.)

---

## Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Next.js dev server with HMR |
| `pnpm build` | Production build |
| `pnpm start` | Run the production build |
| `pnpm lint` | Biome lint check |
| `pnpm lint:fix` | Biome lint with autofix |
| `pnpm format` | Biome formatter |
| `npx tsc --noEmit` | TypeScript type-check |
| `node scripts/snap-flow.mjs` | Snapshot the live system-flow diagram (see below) |

---

## Project layout

```
app/
  workspace/              The main operator surface (Simple / Advanced)
  setup/                  Five-step setup wizard
  settings/               Eight-panel settings + raw editor
  permissions/            Broker request inbox
  globals.css             All design-system tokens + custom keyframes

components/
  ui/                     Primitives: button, card, dialog, tooltip, …
  workspace/              Workspace shell pieces (header, ask cards, etc.)
  flow/                   Live system-flow diagram (see below)
  design-system/          Theme toggle and friends

lib/
  api/conductor.ts        Typed HTTP wrapper over the conductor's REST + SSE
  flow/                   Pure-data derivation that feeds the diagram
  utils.ts                cn() + small helpers

scripts/
  snap-flow.mjs           Playwright snapshot of the live flow diagram

biome.json                Lint + format config
tailwind.config + postcss Tailwind v4 plumbing
```

---

## Conventions (read these before touching .tsx)

The codebase has a deliberate visual language. Three rule files are
auto-loaded by Claude Code and apply equally to humans:

- [`.claude/rules/ui-design-system.md`](../.claude/rules/ui-design-system.md) — primitives, design tokens, segmented controls, status pills, the tooltip rule for icon-only elements
- [`.claude/rules/terminology.md`](../.claude/rules/terminology.md) — Simple-mode vs. protocol vocabulary
- [`.claude/rules/non-negotiables.md`](../.claude/rules/non-negotiables.md) — auto-loop policy, protocol invariants, server lifecycle, workflow rules
- [`.claude/rules/visual-flow.md`](../.claude/rules/visual-flow.md) — drift defence for the live system-flow diagram

Quick highlights:

- Use existing primitives in [`components/ui/`](components/ui) before
  rolling new shapes. If you need a new primitive, ask first.
- Use design tokens (`bg-canvas`, `text-fg-secondary`, `accent-primary`,
  …). **Never** raw Tailwind palette colours (`text-blue-600`, etc.).
- All Angular-isms aside, components are standalone, prefer
  `useMemo` / `useCallback` for stable identity, and dependency-inject
  primitives via props rather than context where possible.
- Every icon-only interactive element wraps in `<Tooltip>` AND carries
  an `aria-label`. Native `title` is too slow.
- Simple mode never leaks protocol words ("deliberation", "DECISION",
  "ratifies"). Advanced mode is where they live.

---

## The live system-flow diagram

Renders in the right half of `/workspace` Simple mode. The architecture
is two layers:

1. **Derivation** — [`lib/flow/derive.ts`](lib/flow/derive.ts) is a
   pure function from API responses to a typed `SystemFlowState`. No
   React, no fetching. Easy to test.
2. **Rendering** — [`components/flow/system-flow-diagram.tsx`](components/flow/system-flow-diagram.tsx)
   takes that state and lays out a React-Flow graph. Stage badges
   stack vertically; the active stage's sub-flow expands inline.

Per-stage sub-flows:

- **S2 Setup** → checklist (problem statement, participants, context)
- **S3 Draft plan** → Propose → Critique → Synthesise → Decide row
- **S4 Work the artifacts** → same row, plus a horizontal artifact
  strip below it. The artifact in progress sits on the spine; siblings
  spread to either side. When all artifacts are decided, the cursor
  advances to S5 (we don't fake activity).
- **S5 Wrap up** → same Propose → Critique → Synthesise → Decide row
- **S6 Archived** → terminator pill

> **Drift contract**: changes to the master flow must update *all five*
> anchors at once: `docs-specs/system-flow-stages.md`,
> `docs-specs/flow.yaml`, `lib/flow/types.ts`, `lib/flow/derive.ts`,
> `components/flow/system-flow-diagram.tsx`. The full list lives in
> [`.claude/rules/visual-flow.md`](../.claude/rules/visual-flow.md).

### Verifying the diagram visually

`scripts/snap-flow.mjs` is a Playwright loop that saves a PNG of the
current diagram plus a JSON dump of every node's bounding box. Use it
to verify layout numerically without eyeballing screenshots.

```bash
# default — snapshots the live workspace state
node scripts/snap-flow.mjs

# expand a past stage's sub-flow before snapping
node scripts/snap-flow.mjs --click=S3

# force one artifact deliberation OPEN (active) to test S4 anchored row
node scripts/snap-flow.mjs --mock-active=0005 --out=/tmp/flow-active.png
```

Output:

- PNG → `/tmp/flow-snapshot.png` (or `--out`)
- JSON of every node's screen-space bbox + center → stdout

The mock works by intercepting `/api/deliberations` and `/api/manifest`
via Playwright's request routing, so you can validate any state
without changing the live workspace.

---

## Workflow rules (don't ship without these)

1. `npx tsc --noEmit` — clean
2. `npx @biomejs/biome check .` — clean
3. If you touched the system-flow diagram, also `node scripts/snap-flow.mjs`
   and read the PNG before committing.
4. Don't add deps without checking — every dep change is reviewed.
5. Don't commit unless the user (or maintainer) asked.

---

## Getting unstuck

- **Diagram is blank / says "Loading flow…"** — the conductor isn't
  reachable at `http://127.0.0.1:8500`. Start it (see Setup above).
- **Stage badge clicks do nothing** — hard reload; the React-Flow
  `onNodeClick` wiring lives in `system-flow-diagram.tsx`.
- **Layout looks lopsided** — likely the centred-vs-anchored row
  detection in `lib/flow/derive.ts`. Re-snap with `snap-flow.mjs`.
- **CSS tokens missing in dark mode** — confirm `app/globals.css`
  defines the `--color-…` token under both `:root` and the dark
  selector. PostCSS won't warn.
- **Tooltip wrapper collapses to content width** — pass
  `triggerClassName="!flex w-full"`; never substitute `title=`.

---

## Where to file things

- Bug in the diagram → issue with a `snap-flow.mjs` PNG attached
- Visual regression → screenshot in [`docs/issues-ss/`](../docs/issues-ss)
- Design / spec changes → `docs-specs/` (AI-authored allowed),
  `docs/` (humans only — see the doc convention in `CLAUDE.md`)
