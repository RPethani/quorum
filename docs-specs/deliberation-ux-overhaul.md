# Deliberation UX overhaul — placeholder

**Status:** queued. Picked up after the live system-flow diagram
ships.

**Owner:** Claude (will draft brainstorm), @rakesh (decides)

---

## Why this is on the list

Once `system-flow-stages.md` made the deliberation concept clear,
@rakesh said:

> "I now totally understand the concept around deliberation. And I
> also see the issue in why I have been struggling with it. I have
> 0 clue in UI what I am supposed to do here and what all things I
> am capable of."

In other words: the protocol layer is solid, but the user-facing
surface around a single deliberation is bad. Users don't know
what they can do, what they should do, or how to do it.

This is the next major UX overhaul after the live system-flow
diagram is done.

---

## What we know about the problem (from this session)

- **The Compose dialog drops the user into raw protocol land** —
  11 move types, structured sections, manual frontmatter editing
  via the Raw editor. The Ask abstraction we shipped covers
  DECISION/ANSWER but the deeper deliberation surface (when the
  user wants to *participate* mid-flight, not just decide at the
  end) is still raw.
- **Users have no map of their capabilities inside a deliberation.**
  They don't know they can OVERRIDE, INTERJECTION, STEER,
  CLARIFY, REOPEN, REVISION. Each of those is a power; none of
  them are discoverable in the current UI.
- **Reading a deliberation is hard.** It's a long markdown file
  with stacked move blocks, each containing structured H2
  sub-sections. Even with the Activity feed in plain English,
  the deliberation file itself is dense.
- **There's no per-deliberation "status / what's next" surface.**
  The user has to read the whole file to figure out where the
  conversation is.
- **The seed deliberation #0001 is special** (it ratifies the
  manifest) but the UI doesn't differentiate it. Same with
  artifact deliberations.

---

## What's NOT in scope here (covered elsewhere)

- The Ask abstraction for "your turn to decide" — already
  shipped.
- The Home view's plain-English activity feed — already shipped.
- The high-level system flow — covered by the live system-flow
  diagram (`visual-flow-diagram.md`).

This document is specifically about **the experience of one
deliberation, from "the user opens it" to "the user contributes
something."**

---

## Likely scope (preliminary, not committed)

When we pick this up, the brainstorm will probably cover:

1. **Plain-language framing of the deliberation.** What's the
   question? Who's the decider? What's the current state of the
   conversation? What does the user need to do next, if anything?
2. **Discoverability of user capabilities.** When can the user
   INTERJECT? STEER? OVERRIDE? CLARIFY? REOPEN? Each becomes a
   visible affordance with a plain-English label, not a
   move-type pick-list.
3. **A readable view of the conversation.** Threaded? Card-based?
   Collapsed-by-default with expand? The current `<pre>` markdown
   block is unreadable.
4. **Per-role guidance.** When the user IS the decider and an Ask
   is open: clear next-action. When the user is just observing:
   read-only with a "drop in" affordance for the rare cases they
   want to interject mid-flight.
5. **Differentiating the seed (#0001) from artifact
   deliberations.** Different question shape, different stakes,
   different framing.
6. **Closing & post-decision view.** Once a deliberation is
   DECIDED, what does the surface look like? Read-only? Can the
   user REOPEN from here? How is that signposted?
7. **Multi-deliberation context.** When multiple are active (e.g.
   a REOPEN happens mid-S4), how does the user navigate between
   them?

---

## Inputs we'll need before brainstorming

- The locked master flow from `system-flow-stages.md`.
- The live system-flow diagram, so we know how a single
  deliberation surfaces in context.
- The vocabulary rules in `.claude/rules/terminology.md` —
  whatever we design must use Participant / Question / Plan / etc.
  consistently.

---

## Reminder for the next session

When picking this up, start by reading:

1. `docs-specs/system-flow-stages.md` — for the master flow
2. `docs-specs/asks-ux-overhaul.md` — for what's already shipped
3. `.claude/rules/terminology.md` — for the vocabulary contract
4. `.claude/rules/ui-design-system.md` — for the UI patterns

Then write a fresh brainstorm doc here (replacing this placeholder)
that walks the questions above and captures @rakesh's calls.
