<!--
CLARIFY — human-initiated. Request explanation about a move, an artifact
section, or a deliberation broadly. Does NOT progress decision work; does
NOT change deliberation state.

CLARIFY is allowed on DECIDED and ARCHIVED workspaces — agents can be
invoked to explain even on long-finished work. If the targeted deliberation
is in BLOCKED_ON_HUMAN waiting on the user's answer, that block is paused
while the CLARIFY → EXPLANATION exchange happens; once the user issues the
actual ANSWER, the block resumes its resolution.
-->
### [CLARIFY] @<human-handle> · <ISO-8601-timestamp>

## Targets

<!-- What is being asked about. Use exactly one of:
       - move ref:        PROPOSAL@claude-opus#0014
       - text span:       PROPOSAL@claude-opus#0014 (range: "we'll use vector store" through "consistent reads")
       - artifact section: requirements.md#pricing
       - deliberation:    #0007
       - problem-statement section: problem-statement.md#what-done-looks-like -->

## What I'm asking about

<!-- The actual clarification request, in plain language. Phrased as you
     would phrase it to a knowledgeable colleague. -->

## Why

<!-- One of (with optional explanation):
       knowledge_gap        — "I don't know this concept"
       reasoning_question   — "I want to understand why this was decided
                              this way"
       reviewing_later      — "I'm reading this weeks later and want
                              context"
       other:<explanation>  — anything else -->

## Preferred explainer

<!-- Optional. A specific handle the user wants to answer. If omitted,
     routing picks based on `explainer` fitness. Write "none" to defer to
     routing. -->
