---
protocol_version: 0.1
status: draft
last_updated: 2026-04-28
---

# Quorum Protocol — v0.1

This document is the operating spec for every participant in a Quorum workspace. Read it once on each invocation. It is short by design: agents are stateless across invocations, so the protocol must fit comfortably in working memory.

The protocol is *structured but not strict*: required sections must be present, but the prose inside them is free. A small validator enforces structure; the human (and the deliberation itself) enforces semantic quality.

---

## 1. The frame

A **workspace** is a folder, typically `<your-project>/quorum/`, in which a body of agents and one human deliberate towards decided artifacts (specs, ADRs, briefs).

A **deliberation** is a single Markdown file under `/deliberations/`. It owns one question and is the unit of work.

A **move** is a typed contribution appended to a deliberation. Moves are append-only — a prior move is never edited. Supersession is explicit (`REVISION`, `ARTIFACT_REVISION`).

A **role** (proposer, critic, synthesizer, specifier, reviewer, domain expert, decider, bootstrapper, explainer) is assigned per-deliberation, not globally. Routing maps roles to handles; agents do not pick their own roles.

The **outcome manifest** (`outcome-manifest.md`) declares what the workspace must produce to be "done." The first deliberation always produces this manifest. The workspace transitions to `COMPLETED` only when the manifest's checks and quality gates clear and the decider issues a closing DECISION.

The **file system is the source of truth**. There is no database. Every state is a file you can read.

---

## 2. The move vocabulary

### Core moves (any participant)

| Move | Purpose |
|---|---|
| `PROPOSAL` | A position being put forward |
| `CRITIQUE` | Structured objections targeting a specific prior move |
| `QUESTION` | An open question requiring an answer |
| `ANSWER` | A response to a question |
| `SYNTHESIS` | Reconciliation over competing proposals/critiques |
| `DECISION` | A ruling, issued only by the designated decider |
| `DEPUTY_DECISION` | Provisional decision made by an agent on the human's behalf when the human-timeout policy fires. Always reversible; never used for `irreversible` stakes. |
| `REVISION` | An updated version of a prior move; supersedes, never edits |
| `ARTIFACT_REVISION` | An updated version of a previously-completed manifest artifact |
| `ABSTAIN` | Explicit "I have nothing to add" — closes a routing request cleanly |

### Auxiliary

| Move | Purpose | Issuer |
|---|---|---|
| `EXPLANATION` | Response to a `CLARIFY`, grounded in workspace content with required citations. Visually subordinate; does not change deliberation state. | An agent assigned the `explainer` role |

### Human-initiated moves (the proactive voice)

| Move | Purpose | Issuer |
|---|---|---|
| `INTERJECTION` | Inject new information mid-stream | Human only |
| `OVERRIDE` | End a deliberation with a unilateral decision | Decider only |
| `REOPEN` | Re-open a previously DECIDED deliberation | Decider only |
| `DROP` | Abandon a deliberation without resolving (→ ABANDONED) | Decider only |
| `STEER` | Non-binding advisory guidance to agents on a deliberation | Human only (v1) |
| `CLARIFY` | Request explanation about a move, artifact, or text span | Human only (v1) |

Why `ABSTAIN` exists: without it, "no response" is ambiguous between pending, abstained, and agent-failed. The state machine cannot close.

Why `DEPUTY_DECISION` is structurally distinct from `DECISION`: when automation answers on the human's behalf, the audit trail must be honest about what happened.

Why `CLARIFY`/`EXPLANATION` are distinct from `QUESTION`/`ANSWER`: a `QUESTION` progresses decision work; a `CLARIFY` requests understanding. They route to different agents (deciders vs explainers) under different prompts (decision-making posture vs teacher posture). Conflating them pollutes the audit trail.

---

## 3. Move block format

Posture: **structured, not strict.** Required sections must be present (write "none" if a section doesn't apply). Prose within sections is free.

### Header line

```
### [MOVE_TYPE] @author · ISO-8601-timestamp [→ targets <REF>, <REF>]
```

### Reference convention

```
<MOVE_TYPE>@<author>#<deliberation_id>
```

Example: `PROPOSAL@claude-opus#0014`. This convention makes targets parseable across deliberations without LLM parsing.

### Required sections (selected highlights)

The full per-move-type section list lives in `protocol/templates/<move_type>.md`. The headline rules:

- **PROPOSAL** must have an explicit `Alternatives I considered` section. "None, this was the obvious choice" is acceptable; silent omission is not. The point is to ground future EXPLANATIONs in real data so the audit trail does not need to confabulate.
- **SYNTHESIS** must have a `Remaining disagreements` section — disagreement is never silently dropped — and a consolidated `Alternatives weighed` list.
- **QUESTION** must declare `Stakes`: one of `trivial | tactical | strategic | irreversible`. This drives the human-timeout policy. Misclassification is a protocol violation flagged in human review.
- **DECISION** must have a `Summary line`: ≤120 characters, plain English, one sentence. The validator rejects vacuous lines (`approved`, `decided yes`, `we'll do this`, anything <30 chars). This is the single most-read sentence the workspace produces — every later invocation reads it via `summarized-decisions.md`.
- **EXPLANATION** must cite a specific source (move ref, file path, or line range) for every claim about *this workspace*, must visually distinguish general knowledge from workspace-specific claims, and must include a `What I couldn't find in the workspace` section. The validator rejects EXPLANATIONs whose workspace claims lack citations.

### Soft enforcement

A linter flags missing sections after each invocation. Bad moves are not rejected outright — the agent gets one retry. After that, the move is flagged for human review.

---

## 4. Status state machine

```
DRAFT → OPEN → IN_REVIEW → SYNTHESIS → DECIDED → ARCHIVED
                  ↓                       ↑   ↓
              BLOCKED_ON_HUMAN      OVERRIDE  REOPEN (back to IN_REVIEW)
                  ├─ → BLOCKED_ON_UNAVAILABLE
                  ├─ → BLOCKED_ON_ROUTING
                  ├─ → BLOCKED_ON_PERMISSION
                  └─ → DECIDED_PROVISIONALLY  (DEPUTY_DECISION pending ratification)

              BLOCKED_ON_EXTERNAL

Any active state ─DROP→ ABANDONED
```

Human-initiated transitions:

- `OVERRIDE`: any active state → DECIDED
- `REOPEN`: DECIDED → IN_REVIEW (prior DECISION preserved as superseded)
- `DROP`: any active state → ABANDONED

Each transition is itself a logged event.

---

## 5. The agent loop (what to do on invocation)

When the conductor invokes you:

1. Read `protocol/PROTOCOL.md` (this file).
2. Read `registers/participants.md` to learn who else is in the workspace and their strengths.
3. Read `inbox/@<your-handle>.md` to find your pending work.
4. For each pending item:
   - Read the referenced deliberation file in full.
   - Produce the requested move type, following the template in `protocol/templates/<move_type>.md`.
   - Append it to the deliberation file. **Never edit prior moves.**
   - Update the inbox of any agent you tag, with a one-line justification for tagging them specifically.
   - Mark the inbox item as handled.
5. When all your inbox items are handled, exit cleanly.

If you encounter a question only a human can answer (requirement ambiguity, business constraint, scope decision), issue a `QUESTION` tagged at the human, set the deliberation status to `BLOCKED_ON_HUMAN`, and stop. **Do not guess.**

Never edit other agents' contributions. Never skip required template sections — write "none" if a section doesn't apply.

---

## 6. Context discipline

The workspace's context surface lives in `/context/`:

- `/context/repos/*/digest.md` — agent-produced digests of each registered codebase.
- `/context/docs/digested/` — digests of uploaded files (PDFs, Markdown, Word).
- `/context/web/cached/` — point-in-time captures of registered URLs.
- `/context/notes/` — user-authored Markdown; treat as authoritative for this workspace.

**Trust digests for high-level understanding.** Read source files only when you need specific details a digest does not provide. Consistent over-reading suggests a digest gap; the events log captures which files you read so the workspace can fix the gap. For cached URLs, note their fetch dates if your move depends on current state.

---

## 7. Permission discipline

Most of your work — proposing, critiquing, synthesizing, deciding, explaining — is reading the workspace's context surface and producing structured Markdown moves. **This needs no shell access.**

For anything outside the allowlist, your CLI will prompt; that prompt is brokered to the user via the conductor and may take time. Do not request shell access casually. When you do, request the most narrowly-scoped operation possible.

---

## 8. The outcome manifest

The first deliberation in any workspace creates `outcome-manifest.md`, declaring what artifacts must be produced and the quality gates that must clear before the workspace is `COMPLETED`. Every subsequent deliberation, decision, and artifact is in service of the manifest.

DECISION moves may carry an optional `contributes_to:` frontmatter field naming the manifest artifact section the decision feeds. This drives synthesis-aggregated artifact production.

When all artifacts pass their completion checks and all quality gates clear, the conductor opens a final meta-deliberation (`final: true`) for a closing summary. The decider issues a DECISION on it; the workspace transitions to `COMPLETED`.

---

## 9. Folder map (for reference)

```
/quorum
  problem-statement.md     # seed input written by the user
  outcome-manifest.md      # what "done" looks like
  config.yaml              # routing overrides, caps, policies
  state.yaml               # workspace runtime state
  /deliberations           # one Markdown file per deliberation
  /artifacts               # the manifest's required outputs
    /versions              # superseded artifact versions
  /decisions               # ADRs (auto-spawned by DECISION moves)
  /tasks                   # tasks (auto-spawned by DECISION moves)
  /inbox                   # routing notifications, one file per handle
  /registers               # open-questions, glossary, participants, routing-defaults
  /protocol                # this spec + templates + manifest-templates
  /prompts                 # standing prompt + per-handle overrides
  /context                 # repos / docs / web / notes
  /runtime                 # ephemeral, gitignored
```

---

## 10. What this protocol is not

- It is not a chat protocol. The artifact is the unit of work, not the message.
- It is not a code-execution coordinator. Quorum is for collaborative reasoning; tools like Cursor and Aider own the execution space.
- It is not a model API wrapper. Quorum invokes existing user-installed CLIs and never makes API calls of its own.
- It is not a database. Every state is a file you can read with a text editor.

---

## 11. Versioning

This protocol is itself a versioned artifact. Material changes go through deliberation in the workspace where the change is being made, are logged as ADRs under `/decisions/`, and bump `protocol_version`. Workspaces that forked or initialized at an older version continue to operate against that version unless explicitly upgraded.
