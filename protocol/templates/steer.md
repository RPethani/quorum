<!--
STEER — human-initiated. Non-binding advisory guidance to agents on a
deliberation. Affects prompt augmentation for subsequent invocations; does
NOT force outcomes.

STEER does not change deliberation state. The audit trail records steers;
if a steer materially shapes an outcome, a reader can trace why.

Use STEER when:
- Agents are converging too fast and the user wants more skepticism
- Agents are diverging and the user wants them to converge
- A specific role's posture should be adjusted ("be more adversarial")
- A specific concern should get more weight ("challenge the security
  assumptions harder")
-->
### [STEER] @<human-handle> · <ISO-8601-timestamp>

## Direction

<!-- The advisory direction. Examples:
       - be more skeptical of the proposed approach
       - expand exploration before converging
       - converge faster — we have a deadline
       - challenge the security assumptions harder -->

## Targets

<!-- Which deliberations, roles, and/or handles this applies to:
       deliberations: [#0007, #0011]    (or `all`)
       roles: [critic, synthesizer]      (or `all`)
       handles: [@gemini-pro]            (or `all`)
     The conductor narrows prompt augmentation to matching invocations. -->

## Reason

<!-- Why you're nudging. Brief is fine. -->

## Duration

<!-- One of:
       this deliberation only
       until I revoke it
       for next <N> moves -->
