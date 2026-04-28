<!--
DROP — decider-initiated. Abandon a deliberation without resolving.
Status transitions to ABANDONED, distinct from DECIDED (resolved) and
ARCHIVED (closed-and-kept). Partial moves are preserved for record;
work on this deliberation stops.

Use DROP when:
- The deliberation is no longer relevant
- It was superseded by another deliberation that absorbed its scope
- The user has decided not to pursue this question

Do NOT use DROP to escape a hard decision — that's what OVERRIDE is for.
-->
### [DROP] @<decider> · <ISO-8601-timestamp> → targets deliberation #<deliberation_id>

## Targets

<!-- The deliberation id being abandoned. -->

## Reason

<!-- Why this deliberation is being abandoned rather than decided. One of:
       no longer relevant
       out of scope
       superseded by deliberation #<id>
       redundant with artifact <name>
       other (explain) -->

## Disposition of partial work

<!-- One of:
       preserved as-is     — moves stay; deliberation just stops accepting
                             new ones (default)
       archive separately  — moves preserved; deliberation moved out of
                             active list (use sparingly)
       discard             — DO NOT USE in v1; reserved for future
                             review-and-strip workflow
     The conductor honors the choice; the audit trail records it. -->
