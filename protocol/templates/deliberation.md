<!--
File-level template for a single deliberation. New deliberations are
scaffolded from this template by `quorum` (via the bootstrapper or by an
agent opening a child deliberation). The Contributions section is the
append-only log of moves; the rest of the file is largely metadata.
-->
---
id: "0001"              # quoted: YAML 1.1 reads bare 0001 as octal
title: <one-line question this deliberation answers>
status: DRAFT
protocol_version: 0.1
created: 2026-04-28
parent: null            # parent deliberation id, if this is a child
children: []            # child deliberation ids, populated as they're opened
roles:
  proposer: null        # @handle or null (routing fills this in)
  critics: []
  synthesizer: null
  decider: "@human-rohan"
tags: []                # e.g., [architecture, ux, pricing]
relevant_context:
  repos: []             # repo ids declared in /context/repos
  docs: []              # doc ids declared in /context/docs
  urls: []              # url ids declared in /context/web
  notes: all            # `all` or a list of note ids
final: false            # true only for the closing meta-deliberation
ratifies: null          # artifact name if this deliberation ratifies an artifact (manifest)
---

## Question

<!-- The precise question this deliberation answers. One paragraph max.
     If the question can't be stated cleanly here, the deliberation is too
     broad — split it. -->

## Context

<!-- Background, constraints, prior art, and links to related deliberations
     and artifacts. Cite by reference convention: <MOVE_TYPE>@<author>#<id>
     for moves; relative file paths for artifacts and notes. -->

## Contributions

<!-- Append-only list of moves. Never edit a prior move; supersede via
     REVISION instead. Each move follows protocol/templates/<move_type>.md. -->

## Open Questions

<!-- Tracked open questions specific to this deliberation. Cross-deliberation
     questions live in /registers/open-questions.md.
     Format: - [ ] Q1: <question> (assigned: @handle)
             - [x] Q2: <question> (resolved by: ANSWER@handle) -->

## Decision

<!-- Empty until the designated decider issues a DECISION move. The DECISION
     move itself lives in Contributions; this section is a pointer plus the
     Summary line for quick scanning. -->
