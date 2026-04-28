<!--
REOPEN — decider-initiated. Re-open a previously DECIDED deliberation.
The previous DECISION is preserved with a `superseded_by_reopen` marker;
agents are prompted to re-engage with new context.

REOPEN transitions deliberation status: DECIDED → IN_REVIEW. Any
artifacts produced from the prior decision are flagged for ARTIFACT_REVISION
cascade.
-->
### [REOPEN] @<decider> · <ISO-8601-timestamp> → targets deliberation #<deliberation_id>

## Targets

<!-- The deliberation id being reopened. -->

## Why I'm reopening

<!-- The reason: new information, changed mind, agents missed something,
     external constraint shifted, etc. Specific is better than vague. -->

## What changed since the prior DECISION

<!-- The new information or shifted context. Cite if applicable: a recent
     INTERJECTION, a new context source, a downstream finding. -->

## Scope

<!-- One of:
       full           — the entire decision is reopened
       aspect:<name>  — only a specific aspect is up for revision
                        (e.g., aspect:pricing within a broader product DECISION)
     If aspect-scoped, the rest of the prior DECISION stands. -->
