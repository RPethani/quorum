<!--
Manifest template — strategic-decision

Starter manifest for a workspace whose goal is to make a single
high-stakes strategic call (a market entry, a pivot, a major partnership,
a build-vs-buy, etc.) with a defensible audit trail and a recovery plan
if the bet doesn't pay off.

This is a STARTING POINT, not a constraint.
-->
---
status: DRAFTING
protocol_version: 0.1
created: 2026-04-28
locked_at: null
template_used: strategic-decision
---

# Outcome Manifest — Strategic Decision

## Required artifacts

### option-analysis.md
**Purpose:** The structured analysis of the options on the table.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `option`, `analysis`
**Required sections:**
- The decision (the actual question being answered, framed precisely)
- Options (each: description, expected outcome if chosen, evidence base, key uncertainties)
- Comparison criteria (what the options are being judged on)
- Comparison matrix (options × criteria)
- Path-dependence notes (how each option constrains future options)
**Completion checks:**
- ≥ 2 options analyzed
- Each option has all required sub-elements

### recommendation.md
**Purpose:** The recommended option and the case for it.
**Production pattern:** specifier-authored
**Depends on:** option-analysis.md
**Required sections:**
- Recommendation (which option, in one sentence)
- Why this option (anchored in option-analysis criteria)
- Why not the alternatives (one paragraph each)
- Confidence (low | medium | high) with calibration notes
- Decision-maker brief (a one-pager the actual decision-maker can read)

### rollback-plan.md
**Purpose:** What to do if the chosen option turns out to be wrong.
**Production pattern:** specifier-authored
**Depends on:** recommendation.md
**Required sections:**
- Leading indicators (what signals would tell us early that the bet is failing)
- Decision points (when to formally reassess)
- Rollback steps (how to undo the strategic move, ordered)
- Sunk costs accepted (what won't be recoverable even with rollback)
- Pre-mortem (the most likely failure mode, narrated)

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed (this template typically produces ≥ 1 ADR for the strategic call)
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks
- The recommendation has been ratified by the decider via a DECISION move (not OVERRIDE — the audit trail should show emergence, not force-issue)

## Closing ceremony

When all required artifacts pass and quality gates clear, the conductor opens a final meta-deliberation. The closing summary states the decision, the confidence level, and the leading indicators the decision-maker has committed to watching.
