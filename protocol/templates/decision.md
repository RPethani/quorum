<!--
DECISION — a ruling, issued only by the designated decider.
The Summary line is validator-enforced: ≤120 chars, ≥30 chars, plain
English. It is the single most-read sentence the workspace produces — every
later invocation reads it via summarized-decisions.md. Generic summaries
("Approved the proposal", "Decided yes") are rejected.

Optional frontmatter on this move:
  contributes_to:
    - requirements.md#pricing
    - mvp-scope.md#in-scope
  confirms: DEPUTY_DECISION@<handle>#<id>     # if ratifying a deputy
-->
### [DECISION] @<decider> · <ISO-8601-timestamp> → targets SYNTHESIS@<handle>#<deliberation_id>

## Decision

<!-- The full decision, stated as plainly as possible. -->

## Summary line

<!-- ONE sentence, ≤120 characters, plain English. This is the line that
     gets concatenated into summarized-decisions.md so every future
     invocation reads it. Write it deliberately.

     Bad:  "Approved the proposal."
     Good: "Pricing tier structure: free / pro $20 / team $50; 14-day pro
            trial; no annual discounts in v1." -->

## Rationale

<!-- The reasoning, citing specific moves. Brief is fine if the synthesis
     is comprehensive — point at it rather than re-litigating. -->

## Path not taken

<!-- Optional but encouraged: explicit acknowledgment of what you're
     choosing against. Strengthens the audit trail for future EXPLANATIONs. -->

## Spawns ADR?

<!-- yes | no
     If yes, the conductor auto-creates /decisions/ADR-<n>-<slug>.md
     populated from this DECISION. -->

## Spawns task?

<!-- yes | no
     If yes, the conductor auto-creates /tasks/TASK-<n>-<slug>.md
     populated from this DECISION. -->
