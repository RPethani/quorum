<!--
Manifest template — coding-plan

Starter manifest for a workspace whose goal is to take a feature or
project from "we know we need to build it" to "here's a complete,
sequenced, dependency-aware plan an execution agent (Cursor, Claude Code,
the user) can pick up and run."

NOTE: Quorum does NOT execute coding tasks. The output of this manifest
is a plan for handoff to execution tooling.

This is a STARTING POINT, not a constraint.
-->
---
status: DRAFTING
protocol_version: 0.1
created: 2026-04-28
locked_at: null
template_used: coding-plan
---

# Outcome Manifest — Coding Plan

## Required artifacts

### task-breakdown.md
**Purpose:** The full set of tasks needed to deliver the work.
**Production pattern:** specifier-authored
**Required sections:**
- Scope summary (what's in / out of this plan)
- Tasks (each: one-line title, what, why, acceptance criteria, estimated size)
- Cross-cutting concerns (tasks that affect multiple areas)
- Out-of-scope tasks (explicit list, with reason)
**Completion checks:**
- ≥ 1 task entry exists
- Each task has all required sub-elements
- Tasks are spawned as TASK files under /quorum/tasks/

### dependency-graph.md
**Purpose:** The order tasks can run in.
**Production pattern:** specifier-authored
**Depends on:** task-breakdown.md
**Required sections:**
- Edges (`TASK-A blocks TASK-B`, one per line)
- Identified cycles (with proposed resolution; should be empty in final form)
- Critical path (the longest chain of dependent tasks)
- Independent task groups (sets that can run in parallel)
**Completion checks:**
- Graph is a DAG
- Every task in task-breakdown.md is represented

### milestones.md
**Purpose:** Coarser checkpoints than individual tasks.
**Production pattern:** specifier-authored
**Depends on:** task-breakdown.md, dependency-graph.md
**Required sections:**
- Milestones (each: name, included tasks, success criteria, target ordering)
- Demo-able state at each milestone (what someone could try after this)
- Risks per milestone

### risks.md
**Purpose:** What could go wrong and what to do about it.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `risk`, `unknown`
**Required sections:**
- Identified risks (each: description, likelihood, impact, mitigation)
- Open questions that, if answered wrong, invalidate the plan
- Assumptions the plan rests on

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks

## Closing ceremony

When all required artifacts pass and quality gates clear, the conductor opens a final meta-deliberation. The closing summary is a "ready for handoff" statement: which tasks are well-specified, which dependencies are crisp, and which risks remain that the executor should track.
