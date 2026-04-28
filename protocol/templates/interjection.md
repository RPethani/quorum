<!--
INTERJECTION — human-initiated. Inject new information mid-stream:
a customer conversation, a constraint that was forgotten, a competitive
insight, a budget change. Cascades into in-flight deliberations as prompt
augmentation on subsequent invocations.

Frontmatter on this move (required):
  issued_by: "@human-<name>"
  issued_at: 2026-04-28T14:22:00Z
  applies_to: [deliberation:0007, deliberation:0011, artifact:requirements.md]
  force: strong              # advisory | strong | overriding
-->
### [INTERJECTION] @<human-handle> · <ISO-8601-timestamp>

## What's new

<!-- The actual new information. One paragraph. Be specific — vague
     interjections produce vague follow-up moves. -->

## Where it applies

<!-- One of, or a list:
       - workspace                          (applies everywhere)
       - deliberation:<id>                  (specific deliberations)
       - deliberation-tag:<tag>             (all deliberations with this tag)
       - artifact:<name>                    (a specific artifact)
     The conductor uses this to decide whose subsequent invocations include
     the interjection in their prompt augmentation. -->

## Force level

<!-- One of:
       advisory   — agents are made aware on next invocation; no required
                    acknowledgment
       strong     — affected deliberations' next moves must explicitly
                    acknowledge the interjection in their own text
       overriding — affected deliberations PAUSE until a move explicitly
                    addresses the interjection -->

## Why I'm raising this now

<!-- Context for why mid-stream rather than as a fresh QUESTION or
     deliberation. Examples: "talked to a customer this morning",
     "legal updated the constraint yesterday", "I forgot this matters until
     I saw the synthesis". -->
