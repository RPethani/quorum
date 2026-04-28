<!--
EXPLANATION — response to a CLARIFY. Grounded in actual workspace content
with required citations. Visually subordinate to core decision-flow moves.
Does NOT change deliberation state.

Frontmatter on this move (required):
  explainer_role: explainer
  responding_to: CLARIFY@<human-handle>#<deliberation_id>
  visually_subordinate: true

VALIDATOR RULES (anti-confabulation):
- Every paragraph making a workspace-specific claim must contain at least
  one valid reference (move ref, file path, or line range).
- The "What I couldn't find in the workspace" section must be present.
  Write "nothing relevant was missing" if all clarifications were fully
  grounded.
- General-knowledge paragraphs and workspace-specific paragraphs must be
  visually distinguished (separate paragraphs, labeled).
-->
### [EXPLANATION] @<explainer-handle> · <ISO-8601-timestamp> → targets CLARIFY@<human-handle>#<deliberation_id>

## Explanation

<!-- The actual content. May contain BOTH general knowledge (legitimately
     the agent's training) and workspace-specific claims, but the two MUST
     be distinguished within the text:

       **General context:**
       <general-knowledge paragraph(s) — no citation required>

       **In this workspace:**
       <workspace-specific paragraph(s) — every claim cites a source>

     Length: as much as needed to actually explain, not artificially
     brief. -->

## Sources cited

<!-- Explicit list of every reference made in the explanation. Move refs,
     file paths, line ranges within files. The validator cross-checks
     this list against citations in the prose; missing entries cause
     rejection. Examples:
       - PROPOSAL@claude-opus#0014
       - DECISION@human-rohan#0014
       - problem-statement.md (section: what-done-looks-like)
       - /context/notes/org-conventions.md -->

## What I couldn't find in the workspace

<!-- The anti-confabulation field. Required.

     If the user asked about something the workspace does NOT actually
     contain (e.g., "what alternatives were considered?" but only one
     alternative was discussed), say so explicitly:
       "The deliberation only considered X; alternatives Y and Z were not
        raised."

     If everything in the clarification was fully grounded, write:
       "Nothing relevant was missing — the workspace covers what was
        asked." -->

## Limitations

<!-- Optional. Surfaces secondary gaps. Examples:
       - "The deliberation cited an external URL I cannot access."
       - "The original author handle is no longer in this workspace's
          participants register."
     Write "none" if not applicable. -->
