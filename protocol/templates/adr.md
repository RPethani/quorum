<!--
File-level template for an Architecture Decision Record. ADRs are spawned
automatically when a DECISION (or DEPUTY_DECISION, OVERRIDE) move's
"Spawns ADR?" field is yes. They live in /quorum/decisions/.

ADR ID numbering is workspace-scoped, sequential, never reused. Superseded
ADRs are kept; their `superseded_by` field points to the replacement.

Status:
  confirmed    — issued by a DECISION (or human-confirmed DEPUTY_DECISION)
  provisional  — issued by a DEPUTY_DECISION pending human ratification
-->
---
id: ADR-0001
title: <decision name in plain language>
status: confirmed             # confirmed | provisional
protocol_version: 0.1
created: 2026-04-28
spawned_by: DECISION@<decider>#<deliberation_id>
contributing_deliberations: []
supersedes: null              # ADR-XXXX if this overrides a prior decision
superseded_by: null           # set when a later ADR overrides this
---

## Context

<!-- The situation that called for a decision. Distilled from the
     originating deliberation's Context section. Keep brief — link to the
     deliberation for full background. -->

## Decision

<!-- What was decided, in plain language. Mirrors the DECISION move's
     "Decision" section. -->

## Rationale

<!-- Reasoning grounded in the deliberation; cite specific moves. Mirrors
     the DECISION move's "Rationale" section. -->

## Consequences

<!-- What becomes easier; what becomes harder; what risks were accepted.
     Required: the consequences of a decision often matter more than the
     decision itself for future readers. -->

## Alternatives considered

<!-- The paths-not-taken. Lifted from the SYNTHESIS move's "Alternatives
     weighed" section in the originating deliberation. One alternative per
     bullet, with a brief note on why it was set aside. -->

## Cross-references

- Originating deliberation: #<id>
- Related ADRs: <list, or "none">
- Affected artifacts: <list, or "none">
