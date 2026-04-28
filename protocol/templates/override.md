<!--
OVERRIDE — decider-initiated (typically the human). End a deliberation
with a unilateral decision. Useful for "stop debating X, I've decided Y,
move on." Force-ends in-flight invocations on the targeted deliberation.

OVERRIDE produces a DECIDED state but is named differently from DECISION
to preserve audit honesty: anyone reading later sees that this conclusion
was force-issued rather than emerging from the deliberation.
-->
### [OVERRIDE] @<decider> · <ISO-8601-timestamp> → targets deliberation #<deliberation_id>

## Decision

<!-- What is being decided unilaterally. -->

## Rationale

<!-- Why you're overriding rather than letting the deliberation conclude.
     Honest reasons: "we don't have time to converge here", "I have
     external information that ends the debate", "the deliberation is
     stuck and unlikely to converge". -->

## What's being preserved

<!-- Acknowledgment of unconsidered material — proposals, critiques, or
     synthesis fragments that were in flight. The fact that they're being
     overridden does not mean they were wrong; the audit trail records
     that they existed. -->

## Spawns ADR?

<!-- yes | no
     OVERRIDE-spawned ADRs note in their Rationale that the decision was
     force-issued. -->

## Cascade

<!-- Does this contradict prior DECISIONs that should now be reopened?
     If yes, list them. The conductor does not auto-reopen — explicit
     REOPEN moves are required. Write "none" if no cascade. -->
