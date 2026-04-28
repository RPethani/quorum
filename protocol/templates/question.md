<!--
QUESTION — an open question requiring an answer.
Stakes is the agent's auditable judgment about how consequential the
question is. Misclassification is a protocol violation flagged in human
review. Stakes drives the human-timeout / deputy-decider policy.
-->
### [QUESTION] @<handle> · <ISO-8601-timestamp> → tagged @<answerer>

## Question

<!-- The actual question. One sentence preferred; if longer, lead with the
     question and follow with elaboration. -->

## Stakes

<!-- One of: trivial | tactical | strategic | irreversible

     trivial      — wrong answer is cheap to fix; deputy can answer freely
     tactical     — wrong answer costs some rework; deputy can answer
     strategic    — wrong answer materially shapes outcome; deputy may NOT
                    answer; human-only
     irreversible — wrong answer cannot be undone; human-only, no timeout
                    policy applies -->

## Why I'm asking

<!-- Why this needs answering before progress can continue. Anchor in the
     deliberation context. -->

## What I'd recommend if forced

<!-- The agent's tentative answer if pressed. Required: the deputy decider
     reads this when human timeout fires. Even "I would lean X but with
     low confidence" is more useful than "I don't know". -->

## Information you have that I don't

<!-- What context only the human (or other answerer) has. Helps the answerer
     focus their reply on the genuinely-missing information rather than
     re-explaining what's already in the workspace. -->
