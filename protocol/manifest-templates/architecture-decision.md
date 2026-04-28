<!--
Manifest template — architecture-decision

Starter manifest for a workspace whose goal is a single, well-reasoned
architecture decision (or a tightly-coupled set of decisions). Output is
typically one or more ADRs plus a tradeoff analysis and migration plan.

This is a STARTING POINT, not a constraint.
-->
---
status: DRAFTING
protocol_version: 0.1
created: 2026-04-28
locked_at: null
template_used: architecture-decision
---

# Outcome Manifest — Architecture Decision

## Required artifacts

### adr-set.md
**Purpose:** The set of architecture decisions this workspace is producing.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `architecture`, `decision`
**Required sections:**
- Decision index (one bullet per ADR with one-line summary)
- Cross-decision dependencies (which decisions presuppose others)
- Index of superseded prior decisions (if revisiting an existing architecture)
**Completion checks:**
- ≥ 1 ADR has been spawned and is `confirmed`
- All listed ADRs have status `confirmed` (none `provisional`)
- Cross-decision dependencies form a DAG (no cycles)

### tradeoff-analysis.md
**Purpose:** The structured comparison of options that led to the decisions.
**Production pattern:** specifier-authored
**Depends on:** adr-set.md
**Required sections:**
- Options considered (each: short description, key properties)
- Comparison matrix (options × evaluation criteria)
- Sensitivities (which assumptions, if changed, would flip the decision)
- Why each rejected option was rejected (one paragraph each)

### migration-plan.md
**Purpose:** How to move from the current state to the decided architecture.
**Production pattern:** specifier-authored
**Depends on:** adr-set.md
**Required sections:**
- Current state (one paragraph)
- Target state (one paragraph)
- Phased migration (each phase: scope, dependencies, validation criteria)
- Rollback plan (how to undo each phase if it fails)
- Out-of-scope (work that's explicitly NOT part of this migration)

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks

## Closing ceremony

When all required artifacts pass and quality gates clear, the conductor opens a final meta-deliberation. The closing summary identifies the decisions made, the tradeoffs accepted, and any architectural debt the migration accrues.
