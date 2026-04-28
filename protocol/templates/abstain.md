<!--
ABSTAIN — explicit "I have nothing to add."
Closes a routing request cleanly. Without it, the absence of a move is
ambiguous between pending, abstained, and agent-failed; the state machine
cannot close.

Use ABSTAIN when:
- You were routed for a role but the deliberation has nothing in your
  zone of competence to contribute
- Your would-be move would duplicate an existing move
- You were routed but the request is genuinely outside your remit

Do NOT use ABSTAIN to avoid hard work. If you have a position, propose it.
-->
### [ABSTAIN] @<handle> · <ISO-8601-timestamp> → targets <role>

## Reason

<!-- One short paragraph explaining why you have nothing to add. Honest:
     "I would duplicate CRITIQUE@gemini-pro#0014" is fine. "Outside my
     remit" is fine. "Tired" is not fine — abstain because of structural
     reasons, not effort. -->

## Suggestion

<!-- Optional: who might be a better fit for this role on this
     deliberation, and why. Helps routing without overriding it.
     Write "none" if you have no suggestion. -->
