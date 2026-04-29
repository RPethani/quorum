# 005: Phase 13 real-world testing — deferred to user-driven sessions

**Date:** 2026-04-29
**Phase:** 13
**Status:** active

## Context

`PHASES.md` Phase 13 is *"Run 3-5 representative workspaces of different types (saas product, research direction, architecture decision, etc.). Observe failures across full cycle. Fix protocol/prompts/UI as issues surface."* The validation gate is *"User is confident v1 works well enough to share."*

This phase is fundamentally interactive: the workspaces are real (the user's actual problems), the failures emerge over the full deliberation cycle (potentially days of real time), and the *grading* of "does this output feel right for my actual use case" is calibrated by the user's domain expertise.

The autonomous overnight pass that completes phases 6-14 cannot run this phase usefully. A single autonomous run would either burn a meaningful chunk of the cost cap on a synthetic scenario whose results I cannot evaluate, or produce a thin "I ran one more slice and the protocol still works" report that adds little to Phase 5b's findings.

## Decision

Phase 13 is deferred to user-driven sessions. Mark as 🟡 in `PHASES.md`. The conductor and UI are ready to run real workspaces; the user picks the scenarios.

What's in place from prior phases:

- Phase 5b's `docs/vertical-slice-findings.md` is the template for capturing per-run findings. Future Phase-13 sessions should append a section per workspace to that file (or a new `docs/phase-13-findings.md`).
- Phase 12's anti-gaming augmentation is in the standing prompt, so the most likely failure modes (vacuous Alternatives, stakes misclassification, generic gap acknowledgment, vacuous Summary lines) get one more nudge toward not happening.
- The cost ceiling enforcement and `quorum status` cost display let the user watch real spend during a Phase-13 run.
- The /workspace UI's SSE-driven activity feed makes it possible to watch a multi-hour deliberation unfold without staring at logs.

Recommended workspace archetypes for Phase-13 sessions, one each:

1. **saas-product** — already exercised in Phase 5b. Repeat with the user's actual product.
2. **architecture-decision** — picks up patterns specific to a single high-stakes technical call.
3. **research-direction** — exercises the literature-survey + methodology shape that the design doc pitches as a non-coding use case.
4. **coding-plan** — exercises the dependency-graph + milestones shape; tests the handoff-to-execution claim.
5. **strategic-decision** — exercises the rollback-plan structure under real ambiguity.

## Reasoning

The autonomous-overnight approach values phases that produce code, docs, or fixes the user can review on a calm reading. Phase 13's outputs are *findings* whose value is the user's reaction to them in real time. That reaction can't be pre-recorded.

A small extra slice run autonomously would also duplicate Phase 5b's data with weak diversity (same agent, similar size, same protocol surface). Phase-13's value is *across-archetype* evidence; one more slice doesn't close that gap.

## Alternatives considered

- **Run one slice per archetype autonomously**: ~$0.50-1.00 of cost burned on synthetic data. Rejected — the user would still need to grade them, and the cost-per-insight is poor compared to one user-driven session.
- **Skip Phase 13 entirely**: rejected; it's the most informative testing phase in the plan and the gate before "share-able v1."
- **Mark Phase 13 ✅ on the strength of Phase 5b's slice**: rejected as dishonest. Phase 5b is one slice on one archetype; Phase 13's gate is multiple workspaces of different types.

## Consequences

- Phase 14 (polish, packaging) ships with the explicit caveat that v1 is "feature-complete pending Phase-13 real-world validation." A fresh `docs/phase-13-findings.md` should land before any "share v1" announcement.
- The protocol may need adjustment when Phase 13 runs find issues. The codebase is structured to absorb this — most adjustments should be standing-prompt edits, validator threshold tweaks, or new ADRs documenting deferred features.
