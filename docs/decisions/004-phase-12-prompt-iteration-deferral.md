# 004: Phase 12 prompt iteration — anti-gaming hardening shipped; empirical iteration deferred

**Date:** 2026-04-29
**Phase:** 12
**Status:** active

## Context

Design-doc §14 step 13 and `PHASES.md` Phase 12 frame this as "a dedicated week" of empirical iteration with real LLM invocations against five gaming-behavior scenarios:

1. Vacuous `Alternatives` sections,
2. Stakes misclassification,
3. Generic gap acknowledgment in EXPLANATIONs,
4. Prompt-length instruction-skipping,
5. DECISION Summary line vacuousness.

The phase explicitly costs real money — the bootstrap warns it's "the most token-intensive phase." With the user-imposed $10 cap on phases 12 + 13 combined, a thorough empirical sweep (Opus invocations across multiple scenarios per failure mode) would consume that cap on Phase 12 alone with no iteration headroom.

Phase 5b's vertical slice already produced one round of empirical findings; the four issues it surfaced were fixed in code before this phase started.

## Decision

Phase 12 ships an `anti-gaming` augmentation as part of the always-applied standing-prompt section, addressing the five concerns above with concrete in-prompt guidance:

- Named alternatives required (or explicit "none — obvious choice given <reason>").
- Stakes-classification rules of thumb spelled out with examples.
- Anti-confabulation language for EXPLANATIONs reinforced ("if Y and Z were not raised, name them").
- DECISION Summary line guidance reiterated with a worked example.
- `Path not taken` framed as generosity to future self.

Empirical iteration — running real LLM invocations against the five gaming scenarios, observing actual failure rates, tightening per-augmentation as needed — is **deferred** to user-driven sessions where the cost cadence can be controlled in real time.

Phase 12 is marked partial (🟡) in `PHASES.md`. The cap on Phases 12 + 13 is preserved for Phase 13 (real-world testing), which has more direct user-visible value per dollar at this stage.

## Reasoning

The five concerns the bootstrap names are real but they are also concerns I already saw partial evidence for in Phase 5b's slice — Sonnet there produced substantive Alternatives, accurate stakes, and a non-vacuous Summary line on its second attempt. The most likely-to-fail case (vacuous Alternatives) responded to template-level instruction in that one trial.

Embedding the guidance in the standing prompt is therefore high-leverage: every future invocation gets the reminder, and we can re-test its effect when the user is awake to catch regressions in real time. Doing the empirical sweep autonomously would burn money on test scenarios whose results I cannot evaluate critically without the user's calibration on what counts as "vacuous" in their specific context.

`anti-gaming` joins `context-discipline` and `permission-discipline` as always-applied. Token cost: ~600 chars (~150 tokens) per invocation. Against typical 20-30K-token invocations on the Sonnet path, this is rounding error.

## Alternatives considered

- **Run a 5-scenario × 3-attempts test sweep on Sonnet (~$0.75)**: viable but still requires user judgement to grade results, and grading "is this Summary line vacuous?" is calibrated by domain context the user has and I don't.
- **Skip the prompt edits, defer everything to user sessions**: rejected. The augmentation costs nothing to add and embeds the lessons of Phase 5b's findings doc directly into every invocation.
- **Add per-augmentation telemetry (count vacuous-section incidents, generic-gap incidents)**: rejected as scope creep for v1. Phase 13 + 14 can earn this if real-world testing surfaces specific gaming behavior.

## Consequences

- The Phase-12 validation gate ("user agrees the agents behave well across the test scenarios") stays open. The augmentation reduces the prior probability of those failure modes; verification is still the user's call.
- Phase 13's real-world testing now serves double duty: it produces the kind of empirical evidence Phase 12 wants. Findings from that phase will feed back into prompt tuning.
- If real-world testing surfaces a specific failure mode the augmentation didn't help with, the right move is to extend the augmentation in place (it's a single Markdown section in `prompts/agent-standing-prompt.md`).
