<!--
DEPUTY_DECISION — a provisional decision issued by an agent on the human's
behalf when the human-timeout policy fires (§10.4). NEVER used for
`strategic` or `irreversible` stakes. Always reversible. The human will
review on their return and either confirm (issuing a DECISION with
`confirms:` set) or override.

Frontmatter on this move (required):
  acting_for: "@human-rohan"
  policy_triggered: human_timeout
  stakes_classification: tactical          # from the originating QUESTION
  can_be_overridden_until: 2026-04-28T08:00:00Z
  status: provisional                      # provisional | confirmed | overridden | expired
-->
### [DEPUTY_DECISION] @<deputy> · <ISO-8601-timestamp> → targets QUESTION@<asker>#<deliberation_id>

## Decision

<!-- What is being decided, provisionally. State plainly. -->

## Rationale

<!-- Reasoning grounded in the deliberation context. Cite the originating
     QUESTION's "What I'd recommend if forced" suggestion if you used it. -->

## Confidence

<!-- low | medium | high
     Be honest. The human reads this. -->

## Reversibility window

<!-- The timestamp until which override is straightforward (no cascade into
     downstream artifacts). After this, override becomes more disruptive
     because subsequent moves may have built on this decision. Match the
     value in frontmatter `can_be_overridden_until`. -->

## What I'd want the human to confirm

<!-- Specific points the human should explicitly validate on their return.
     One bullet per point. The more specific, the easier the human's
     review. -->

## Spawns ADR?

<!-- yes | no
     If yes, the spawned ADR's status is `provisional` until the human
     confirms; it transitions to `confirmed` on ratification. -->
