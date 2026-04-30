---
description: Vocabulary rules — use these words in these places. Applies project-wide because terminology drift bites every layer.
---

# Terminology — use these words, in these places

The protocol has its own vocabulary. The user surface has its own.
Code that mixes them gets rejected on review. This file is the map.

---

## User-facing (Simple mode, copy, tooltips, error messages)

| Use | Don't use |
|---|---|
| Participant | Agent, model, bot |
| Question, Ask card | Move, deliberation move, prompt |
| Plan | Outcome manifest, manifest |
| Workspace | Project, repo, workspace_id |
| You | Human, user, manual handle |
| Working / Quiet / Your turn | ACTIVE / IDLE / BLOCKED_ON_HUMAN |
| Spend | Cost, USD spent |
| Add a participant | Add an agent, register an agent |

The Simple-mode UI must read like English to a non-technical reader.
If you find yourself writing "deliberation #0003 is in IN_REVIEW state
awaiting CRITIQUE from @gemini-pro", you are leaking the protocol.
The right phrasing is "Gemini is reviewing the option analysis".

---

## Advanced mode + audit trail + Raw editor

The protocol vocabulary is welcome here — these surfaces *are* for
power users who want to read what actually happened.

- Deliberation, move, PROPOSAL, CRITIQUE, SYNTHESIS, DECISION,
  OVERRIDE, DROP, QUESTION, ANSWER, INTERJECTION, REOPEN, STEER,
  CLARIFY, EXPLANATION, REVISION
- Frontmatter, role, transport, fitness, layer, route, alternative
- Inbox, marker, stream, validation
- Bootstrapper, ratifies, decided

These appear unchanged in `deliberations/*.md`, the events log, and
the Raw editor. The Activity feed in Simple mode rewrites them; the
Activity feed in Advanced mode shows them verbatim.

---

## Internal code (Python + TypeScript)

| Layer | Vocabulary |
|---|---|
| `conductor/core/` | Protocol vocabulary directly. `Deliberation`, `Move`, `Header`, `RoutingDecision`. |
| `conductor/transport/` | "Invocation" semantics. `InvocationRequest`, `invoke`, `_spawn`. The word "agent" is OK here because it really means "the CLI subprocess we spawn". |
| `conductor/workspace/` | File-system semantics. `WorkspacePaths`, `state.yaml`, `outcome-manifest.md`. |
| `conductor/server/` | HTTP / autoloop. `AutoLoop`, `_tick_once`. |
| `ui/components/` | User-facing language. **No** protocol words in default props/labels. The single exception is the Activity feed in Advanced mode. |

In TypeScript the type is `ParticipantRow`, the fetch is
`getParticipants()`. There is no `Agent` type and we do not introduce
one. Lucide icon names are not user-facing — `Bot` icon is fine in
code, but its tooltip says "participant".

---

## Protocol move types — exact spelling

`PROPOSAL`, `CRITIQUE`, `SYNTHESIS`, `DECISION`, `OVERRIDE`, `DROP`,
`QUESTION`, `ANSWER`, `INTERJECTION`, `REOPEN`, `STEER`, `CLARIFY`,
`EXPLANATION`, `REVISION`.

Always uppercase, always in `[brackets]` in the canonical header
(`### [DECISION] @rakesh · 2026-04-30T...`). Never "Decision" or
"decision_move" or anything else.

---

## Status values

### Workspace state (`state.yaml`)
`INITIALIZED`, `ACTIVE`, `PAUSED`, `ARCHIVED` — uppercase, exact.

### Deliberation status (frontmatter)
`OPEN`, `IN_REVIEW`, `BLOCKED_ON_HUMAN`, `BLOCKED_ON_ROUTING`,
`DECIDED`, `ABANDONED`, `ARCHIVED` — uppercase, exact.

### Manifest status (frontmatter)
`DRAFTING`, `READY`, `LOCKED` — uppercase, exact.

### Ask status (`asks/<id>.json`)
`open`, `answered`, `closed` — lowercase, exact.

The case difference between Ask status and the others is intentional:
asks are JSON-shaped data records, not protocol moves. Don't
"normalise" one to match the other.

---

## Tone

User-facing copy is plain, calm, and short. No marketing voice. No
exclamation marks. No emoji unless the user has requested them. If
something fails, say what failed in one sentence, and what to do
about it in the next.

> ✅ "Gemini isn't reachable. Open Settings → Participants to fix the
> CLI command, or skip it for now."
>
> ❌ "Oops! 😅 Looks like @gemini hit a snag — let's try again!"
