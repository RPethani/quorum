<!--
File-level template for a task. Tasks are spawned automatically when a
DECISION's "Spawns task?" field is yes, or when a manifest artifact's
production needs concrete work tracked. Live in /quorum/tasks/.

Tasks are intended for handoff to *execution* tooling (Cursor, Claude Code
in IDE mode, the user's own implementation work) — NOT for agents within
Quorum to execute. The `assigned_to` field is free-form text identifying
who picks it up; agents do not self-assign or execute tasks in v1.
-->
---
id: TASK-0001
title: <one-line action>
status: open                  # open | in_progress | blocked | done | abandoned
priority: medium              # high | medium | low
protocol_version: 0.1
created: 2026-04-28
spawned_by: DECISION@<decider>#<deliberation_id>   # or null if user-created
assigned_to: <free-form text — human, team, or external system>
depends_on: []                # other TASK ids
blocks: []                    # other TASK ids that depend on this
---

## What

<!-- The actual work to be done. Specific enough that someone could pick
     this up and execute it without reading the originating deliberation.
     If you find yourself writing "see deliberation #N for details", pull
     the details into this section instead. -->

## Why

<!-- The reason this task exists. Cites the originating decision or
     deliberation. Helps future executors understand what's load-bearing
     about the task and what is not. -->

## Acceptance criteria

<!-- Checkable criteria. Concrete:
       - [ ] Endpoint /api/v1/foo returns 200 for valid input
       - [ ] Documented in /docs/api.md
       - [ ] Reviewed by @<reviewer>
     "Done when it works" is not an acceptance criterion. -->

## Notes

<!-- Anything else useful to whoever picks this up. References to relevant
     code, gotchas, links to similar prior work. Write "none" if not
     applicable. -->
