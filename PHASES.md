# Quorum — Phase Plan

This document is the working ledger of the build. Each phase has a goal, a deliverable list, and a validation gate the user runs before the next phase begins. Phases are executed strictly in order; phase boundaries are not crossed without explicit "next" approval.

The plan refines the build order in §14 of the design doc and the phase list in §2 of `IMPLEMENTATION_BOOTSTRAP.md`. Where they differ, this document defers to the bootstrap.

**Status legend:** ⬜ not started · 🟡 in progress · ✅ complete · ⏸ paused

---

## Phase 0 — Plan & repo skeleton ✅

**Goal.** Produce planning artifacts and the bare repo structure. No code.

**Deliverables.**
- `PHASES.md` (this file).
- `docs/architecture.md` — one-page system overview for someone who hasn't read the design doc.
- `README.md` — what Quorum is, current status, install placeholder, license note.
- `LICENSE` — MIT.
- `.gitignore` — Python, Node, IDE/OS files, `/runtime/`.
- Empty directory tree per §1 of the bootstrap (`.gitkeep` files in empty dirs).

**Validation gate.** User reads `PHASES.md` and `docs/architecture.md` and confirms direction.

---

## Phase 1 — Protocol artifacts (no code) ✅

**Goal.** Produce all static protocol files (Markdown / YAML).

**Deliverables.**
- `protocol/PROTOCOL.md` v0.1, distilled from §4–§6 of the design doc.
- `protocol/templates/*.md` — one file per move type (~20 files), each with canonical structure and inline `<!-- guidance -->`. Source: §5, §8.
- `protocol/manifest-templates/*.md` — five templates per §1.7: saas-product, research-direction, architecture-decision, coding-plan, strategic-decision.
- `prompts/agent-standing-prompt.md` — core standing prompt from §11 plus all augmentations (context-discipline, permission-discipline, explainer-specific, autonomous-mode, deputy-mode), clearly sectioned for subset extraction.
- `routing-defaults/routing-defaults.yaml` — fitness matrix for canonical handles per §3.6 (Opus, Sonnet, Haiku, Gemini Pro/Flash, GPT-5, explainer).

**Validation gate.** User spot-checks 2–3 templates and the standing prompt.

---

## Phase 2 — Design system specification ✅

**Goal.** Codify the design system and ship the foundational tokens. No application UI yet.

**Deliverables.**
- `DESIGN_SYSTEM.md` — full spec per §3 of the bootstrap (tokens, type ramp, spacing, components, motion, accessibility, forbidden patterns).
- `ui/components/design-system/tokens.css` — CSS custom properties for both modes.
- `ui/components/design-system/theme-provider.tsx` — `next-themes` wrapper with our defaults.
- `ui/tailwind.config.ts` — wired to consume tokens via `@theme`.
- `ui/app/design-system/page.tsx` — showcase route rendering every atom and component variant in both modes. (The bootstrap suggested `_design-system`, but Next.js App Router treats `_`-prefixed folders as non-routable private folders; renamed per `docs/decisions/001-design-system-route-name.md`.)

**Validation gate.** User runs the UI dev server, opens `/design-system`, and confirms the system feels right in light and dark modes.

---

## Phase 3 — Manual protocol exercise (notes only) ✅

**Goal.** Prepare the user to manually exercise the protocol with three CLI agents on a small problem (design doc build-order step 3).

**Deliverables.**
- `docs/manual-protocol-exercise.md` — guide with exact commands, what to look for, what to record, and a worked example with sample agent invocations.

**Validation gate.** User reviews the guide. Doing the exercise is optional — but the guide must be runnable.

---

## Phase 4 — Conductor core (Python) ✅

**Goal.** Conductor as documented in §10. CLI commands, no UI yet, no permission broker, no fancy context surface.

**Sub-phases.**
- 4a · scaffolding — `pyproject.toml`, package layout, `quorum` entry point, `quorum --help`. ✅
- 4b · workspace lifecycle — `init`, `status`, `doctor`, `archive`, `unarchive`, file scaffolding. ✅
- 4c · routing engine — read `participants.md` and `routing-defaults.yaml`, score handles, log decisions. ✅
- 4d · invocation — spawn CLI process, render prompt, capture stdout, append validated move, lifecycle markers. ✅
- 4e · validator — move structure validation per §5; reject vacuous Summary lines; one-retry on failure. ✅
- 4f · loop — `start`/`pause`/`step`/`run`/`resume`, parallel invocations with per-deliberation locks. ✅
- 4g · events — `events.jsonl` emission with the §10.5 schema. ✅
- 4h · bootstrapper — handles deliberation #0001 (manifest creation). ✅
- 4i · cost ceiling — per-invocation cost tracking; per-workspace ceiling enforcement (default $50, ON). ✅
- 4j · tests — pytest suite covering each module. ✅

**Permissions in this phase.** Pass restrictive `--allowedTools` flags where supported. Out-of-allowlist requests fail moves cleanly. Broker comes in Phase 11.

**Validation gate.** User runs `quorum init` in a test directory; sees scaffolding; runs `quorum status`; sees clean state. End-to-end deliberation isn't possible until the slice in Phase 5.

---

## Phase 5 — Vertical slice (first end-to-end deliberation) ✅

**Goal.** Validate the protocol end-to-end with the minimum viable UI (design doc build-order step 5).

**Deliverables.**
- `ui/app/_dev-vertical-slice/page.tsx` — minimal Markdown viewer of the active deliberation with a "step" button calling the conductor's `step` endpoint.
- A test scenario with a small problem statement and two real CLI agents.
- `docs/vertical-slice-findings.md` — populated after the user runs the slice and reports back.

**Validation gate.** User runs the slice on a small real problem and reports findings. Protocol, prompts, validator, and conductor are updated to address findings before Phase 6 starts. Do not skip.

---

## Phase 6 — Context surface ✅

**Goal.** §1.8 in full: repos, documents, web URLs, notes; relevance-tiered digester; background job queue; freshness tracking; conductor's per-invocation context-bundle assembly. UI panels still come later.

**Validation gate.** User adds a repo via CLI; digestion runs; bundle assembly is verified by inspecting an invocation's context via `events.jsonl`.

---

## Phase 7 — UI shell (the real one) ✅

**Goal.** Three-pane layout (§9.5), workspace setup wizard (§9.8 Tier 1), move card primitives, manifest progress view, theme provider — all on the design system from Phase 2.

**Validation gate.** User opens the UI; sees the empty workspace shell; navigates panels; light/dark mode works.

---

## Phase 8 — UI live updates + streaming ✅

**Goal.** Server-side file watcher pushing via WebSocket; composing/complete/failed move-card states; activity feed sourced from `events.jsonl`; deliberation timeline; routing-decision visibility; cost ceiling progress display.

**Validation gate.** User runs a deliberation and watches it unfold live in the UI.

---

## Phase 9 — Settings UI panels ✅

**Goal.** All eight panels from §9.8 Tier 2 with full functionality, frozen / live / live-with-effects indicators, confirmation dialogs. Permissions panel shows broker-disabled state with a toggle (broker itself ships in Phase 11).

**Validation gate.** User navigates each panel, edits a few settings, verifies behavior.

---

## Phase 10 — Raw YAML editor + human response forms ✅

**Goal.** §9.8 Tier 3 raw editor; structured response form (§9.7); human-initiated moves (§12.5): INTERJECTION, OVERRIDE, REOPEN, DROP, STEER, CLARIFY.

**Validation gate.** User issues each human-initiated move type and verifies it round-trips correctly.

---

## Phase 11 — Permission broker (opt-in feature) 🟡 (data plane + UI shipped; live proxy deferred — ADR-003)

**Goal.** §10.6 in full: stdin/stdout pipe management, prompt detection per CLI, response routing, BLOCKED_ON_PERMISSION state, permission request cards, auto-approval policy, capability-aware routing.

Build a standalone Python prototype wrapping a single CLI to validate the pipe pattern before integrating into the conductor.

**Validation gate.** User enables the broker, triggers an out-of-allowlist request, approves it, sees the agent proceed. Disables the broker, triggers another request, sees it fail cleanly.

---

## Phase 12 — Standing prompt iteration (dedicated week) 🟡 (anti-gaming augmentation shipped; empirical iteration deferred — ADR-004)

**Goal.** §14 step 13. Tune each prompt augmentation against gaming behavior:

- Vacuous Alternatives sections
- Stakes misclassification
- Generic gap acknowledgment in EXPLANATIONs
- Prompt-length instruction-skipping (measure tokens; refactor if approaching limits)
- Summary line vacuousness

This phase is heavy on real CLI invocations and costs real money. Watch the cost ceiling.

**Validation gate.** User agrees the agents behave well across the test scenarios.

---

## Phase 13 — Real-world testing 🟡 (deferred to user-driven sessions — ADR-005)

**Goal.** Run 3–5 representative workspaces of different types (saas product, research direction, architecture decision, …). Observe failures across the full cycle. Fix protocol/prompts/UI as issues surface.

**Validation gate.** User is confident v1 works well enough to share.

---

## Phase 14 — Polish, documentation, packaging ⬜

**Goal.** Ship v1.

**Deliverables.**
- README finalization.
- Installation script polish.
- Quickstart guide.
- Troubleshooting doc.
- Final pass on UI consistency.
- Final pass on error messages.

**Validation gate.** v1 ships.
