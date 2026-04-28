# Manual Protocol Exercise

This guide walks through running the Quorum protocol *by hand*, before the conductor exists. The point is to expose protocol problems early — vague templates, missing sections, gaming behavior, prompts that don't land — while the cost of fixing them is just a Markdown edit.

You play the conductor. You invoke each CLI agent yourself, paste its output into the deliberation file, route the next move to the next agent, and observe what works and what doesn't.

This corresponds to design-doc §14 build-order step 3 and Phase 3 of `IMPLEMENTATION_BOOTSTRAP.md`. Doing this exercise is **optional** — but the protocol is unproven until someone has. If you skip it now, do it before Phase 5 (vertical slice).

---

## 1. Why this exercise matters

The protocol is 20 move templates, a standing prompt, and a fitness matrix. None of those have been pressure-tested against real model output. The conductor (Phase 4) automates orchestration — it does **not** improve the protocol. If the standing prompt produces vacuous Alternatives sections, the conductor will produce them faster.

The exercise answers four questions:

1. **Do agents follow the move templates** when handed only `PROTOCOL.md`, the relevant template, and a deliberation file? Or do they paraphrase, drop sections, or hallucinate sections we didn't ask for?
2. **Are required sections produced honestly?** A PROPOSAL's `Alternatives I considered` is the canary. If agents fill it with weasel-language ("various approaches were considered") rather than real alternatives, the prompt and template need stronger grounding.
3. **Does SYNTHESIS preserve disagreement?** A SYNTHESIS that silently flattens a disagreement is worse than no synthesis.
4. **Is the DECISION's Summary line non-vacuous** when produced by a real model? If agents reach for "Approved the proposal," the validator's reject list (or the prompt) needs work.

Findings go into a feedback file you fill in as you go (§6). Phase 5 reads it.

---

## 2. What you need

- **Three CLI agents**, ideally three different model families. A reasonable trio:
  - `@claude-opus` — `claude --print --model opus` (Anthropic; strong proposer/synthesizer)
  - `@gemini-pro` — `gemini --model gemini-2.5-pro` (Google; sharp critic per design-doc §3.6)
  - `@codex-gpt5` — `codex exec --model gpt-5` (OpenAI; strong specifier)
- Substitutes are fine — anything CLI-headless that takes a prompt on stdin or as an argument and prints completion to stdout. If you only have two CLIs, use `@claude-sonnet` as the third.
- A scratch directory you can throw away when done.
- About 30–60 minutes. The exercise is not long; honest review of what came back is the time-consuming part.
- A few dollars of LLM budget. The exercise is one PROPOSAL + one CRITIQUE + one SYNTHESIS + one DECISION (the DECISION is yours, no model cost), so under $1 in practice.

---

## 3. Setup — scaffold a scratch workspace by hand

You'll mimic what `quorum init` (Phase 4) will eventually do. Pick a scratch path and create the minimum file tree:

```bash
export QUORUM_SCRATCH=~/quorum-scratch
mkdir -p "$QUORUM_SCRATCH"/{deliberations,inbox,registers,protocol/templates,prompts}
cd "$QUORUM_SCRATCH"
```

Copy the protocol layer from this repo:

```bash
# Adjust QUORUM_REPO to wherever you cloned this repo.
export QUORUM_REPO=~/Personal/quorum

cp "$QUORUM_REPO/protocol/PROTOCOL.md"           protocol/PROTOCOL.md
cp -R "$QUORUM_REPO/protocol/templates/."         protocol/templates/
cp "$QUORUM_REPO/prompts/agent-standing-prompt.md" prompts/agent-standing-prompt.md
cp "$QUORUM_REPO/routing-defaults/routing-defaults.yaml" registers/routing-defaults.yaml
```

Create a tiny `participants.md`:

```bash
cat > registers/participants.md <<'EOF'
---
schema_version: 0.1
last_updated: 2026-04-28
---

# Participants Registry

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @claude-opus  | Claude (Opus)  | claude --print --model opus       | claude-opus-4-7 | cli | 30/5  | fine_grained | (none) | green |
| @gemini-pro   | Gemini Pro     | gemini --model gemini-2.5-pro     | gemini-2.5-pro  | cli | 50/10 | fine_grained | (none) | green |
| @codex-gpt5   | Codex (GPT-5)  | codex exec --model gpt-5          | gpt-5           | cli | 50/10 | fine_grained | (none) | green |
| @human-rohan  | You            | (manual)                          | n/a             | manual | unlimited | n/a | (none) | n/a |
EOF
```

Pick a small problem and write `problem-statement.md`. The worked example in §7 uses one; if you want a different one, see §5.2 for what makes a good problem.

Create a deliberation file from the template:

```bash
cp protocol/templates/deliberation.md deliberations/0001-pick-a-question.md
# Edit it: set a real id (0001), title, status: OPEN, created date,
# fill in Question and Context. Leave Contributions empty for now.
```

Create empty inbox files for each handle:

```bash
for h in claude-opus gemini-pro codex-gpt5 human-rohan; do
  touch "inbox/@${h}.md"
done
```

You're set. Workspace is on-disk and isomorphic to what the conductor will eventually scaffold.

---

## 4. The exercise

Each round you do four things:

1. **Render the prompt** for the next agent (template below).
2. **Invoke the CLI** with that prompt.
3. **Hand-validate the output** against `protocol/templates/<move_type>.md`.
4. **Append the move** to the deliberation file's `## Contributions` section. Update inboxes.

Prompts can be passed via stdin. The render-and-invoke shape is the same each round — only the move type and the targeting changes.

### 4.1 Round 1 — PROPOSAL

Pick a proposer (e.g., `@claude-opus`). Render this prompt:

```text
You are @claude-opus in a Quorum workspace at $QUORUM_SCRATCH.

1. Read protocol/PROTOCOL.md.
2. Read registers/participants.md.
3. Read deliberations/0001-<slug>.md in full.

You are the PROPOSER for this deliberation. Produce a PROPOSAL move
following protocol/templates/proposal.md exactly. All required sections
must be present. Write "none" if a section does not apply.

When done, append the move to deliberations/0001-<slug>.md under the
Contributions heading. Tag @gemini-pro for critique with a one-line
justification. Update inbox/@gemini-pro.md.

Do not edit prior moves. Do not skip sections.
```

Invoke (Claude Code as example):

```bash
claude --print --model opus --add-dir "$QUORUM_SCRATCH" < /tmp/proposer-prompt.txt > /tmp/proposer-output.txt
```

(Other CLIs: `gemini --prompt-file …`, `codex exec --input-file …`. Check each tool's flags.)

Read `/tmp/proposer-output.txt`. If the agent edited the deliberation and inbox files itself (Claude Code can), great. Otherwise paste the move under `## Contributions` yourself, prefixed by the canonical header line:

```
### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z
```

Then validate against the template (§5.1).

### 4.2 Round 2 — CRITIQUE

Critic prompt (substitute the targeted PROPOSAL's reference):

```text
You are @gemini-pro in a Quorum workspace at $QUORUM_SCRATCH.

1. Read protocol/PROTOCOL.md.
2. Read registers/participants.md.
3. Read inbox/@gemini-pro.md and the referenced deliberation file in full.

You are the CRITIC for this deliberation. Produce a CRITIQUE move
targeting PROPOSAL@claude-opus#0001, following
protocol/templates/critique.md exactly. All required sections must be
present.

Append the move to the deliberation file under Contributions. Tag a
synthesizer with a one-line justification (e.g., @codex-gpt5 or
@claude-opus). Update that inbox.

Do not edit prior moves.
```

Invoke. Append. Validate.

### 4.3 Round 3 — SYNTHESIS

Synthesizer prompt:

```text
You are @codex-gpt5 in a Quorum workspace at $QUORUM_SCRATCH.

1. Read protocol/PROTOCOL.md.
2. Read registers/participants.md.
3. Read inbox/@codex-gpt5.md and the referenced deliberation file in full.

You are the SYNTHESIZER for this deliberation. Produce a SYNTHESIS move
reconciling PROPOSAL@claude-opus#0001 and CRITIQUE@gemini-pro#0001,
following protocol/templates/synthesis.md exactly. All required sections
must be present. Remaining disagreements MUST NOT be silently dropped;
preserve any disagreement that did not resolve.

Append the move under Contributions. Tag @human-rohan for DECISION.
Update inbox/@human-rohan.md.
```

Invoke. Append. Validate.

### 4.4 Round 4 — DECISION (you, by hand)

You are the decider. Read the SYNTHESIS. Decide. Write a `DECISION` move directly into the deliberation file using `protocol/templates/decision.md`. Pay particular attention to the **Summary line** rules (≤120 chars, ≥30 chars, plain English, specific not generic).

Update the deliberation's `## Decision` section with a pointer plus the Summary line. Update the deliberation status to `DECIDED` in the frontmatter.

You're done. Don't bother spawning ADRs/tasks unless you want to test the spawning flow too.

---

## 5. What to watch for

### 5.1 Per-move structural checks

After each model output, run through the template's required-sections list. Mark each section:

- **Present and substantive** — the section exists and has real content.
- **Present but vacuous** — the section exists but the content is filler ("none considered", "various approaches", "see above"). This is the failure mode we most need to detect.
- **Missing** — the section is absent. The validator (Phase 4e) will reject this; for now, note it and ask the agent to retry once.

Per-move pitfalls to flag:

| Move | Pitfall | What to look for |
|---|---|---|
| PROPOSAL | Vacuous Alternatives | "Various approaches were considered." vs. ≥2 named, weighed alternatives |
| PROPOSAL | Risks erased | "No major risks." on a non-trivial decision is suspect |
| CRITIQUE | Strong-objection inflation | A "strong objection" that's actually a nitpick |
| CRITIQUE | Missing Agreed points | Calibrated critics agree somewhere; pure-adversarial output is a prompt issue |
| SYNTHESIS | Disagreement laundering | Smooth narrative that silently dropped a real disagreement |
| SYNTHESIS | Alternatives weighed missing | Required by §5; agents skip it when not pushed |
| DECISION | Vacuous Summary line | "Approved the proposal." → reject. Aim for the kind of line a future agent could read in a list and understand the decision. |

### 5.2 What makes a good test problem

Pick something that:

- **Has at least two real alternatives** with non-trivial tradeoffs. Single-answer questions don't exercise CRITIQUE or SYNTHESIS.
- **Fits in one deliberation** — a paragraph of context, decidable in 3 moves. Don't pick something that genuinely needs cross-deliberation work.
- **Is decidable by you alone** — you'll be the decider, so the problem must not require domain knowledge you lack.
- **Is not real product work.** Real work tempts you to fight the agents instead of testing the protocol. Use a fictional or low-stakes scenario.

The worked example in §7 demonstrates a fitting problem.

### 5.3 Cross-cutting protocol checks

- **Header line format** — does the agent produce `### [MOVE_TYPE] @author · timestamp [→ targets …]` exactly? Variations break the parser.
- **Reference convention** — `<MOVE_TYPE>@<author>#<deliberation_id>`. Variants like `proposal-by-claude-opus-in-#0001` break parsing.
- **Inbox tagging** — does the agent actually update the next agent's inbox with a justification, or skip it?
- **Status transition** — did the deliberation status get updated in the frontmatter when SYNTHESIS appeared (→ SYNTHESIS), and again at DECISION (→ DECIDED)? Agents often forget; the conductor will own this in Phase 4.
- **No-edit discipline** — did any agent edit a prior move rather than appending a REVISION? Critical to catch.

### 5.4 Prompt-side checks

- **Did the agent read PROTOCOL.md and the template?** A response that ignores them suggests the prompt's instructions to read those files aren't strong enough.
- **Did the agent ask permission to edit files?** If yes, the standing prompt's "permission discipline" augmentation needs tightening.
- **Did the agent claim to have done something it didn't?** (E.g., "I've updated the inbox" when the inbox is empty.) Prompt-side problem worth recording.

---

## 6. What to record

Keep a notes file as you go. Suggested location: `$QUORUM_SCRATCH/findings.md`. Don't commit it back to this repo — instead, after you finish, distill it into a short summary that lands in `docs/vertical-slice-findings.md` at the start of Phase 5 (which exists for exactly this purpose).

A useful structure:

```markdown
# Manual Protocol Exercise — Findings

Run date: 2026-04-28
Trio: @claude-opus, @gemini-pro, @codex-gpt5
Test problem: <one line>

## What worked
- <one bullet per thing that landed cleanly>

## What didn't
- <one bullet per pitfall observed; cite the move and the section>

## Standing prompt issues
- <prompt augmentations that need work>

## Template issues
- <required-section ambiguities, missing examples, etc.>

## Validator implications
- <patterns the Phase-4e validator must catch>
```

Concretely, whenever you mark a section "present but vacuous" or "missing," add a bullet. Whenever an agent ignores the template, add a bullet. Whenever the protocol felt awkward, add a bullet.

---

## 7. Worked example

A fictional, low-stakes problem with the kind of output you should expect. Times and prose are illustrative, not literal.

### 7.1 Problem

`problem-statement.md`:

```markdown
# Problem Statement

We are deciding whether the v1 of our note-taking SaaS should offer a
free tier, or trial-only.

## What I'm trying to figure out
Whether v1 ships with a free tier alongside paid tiers, or trial-only
("14 days free, then pay") with no permanent free option.

## What I already know / believe
- We have ~$8k/month in compute headroom for free users.
- Conversion-rate-anchored arguments tend to dominate this debate, but
  free-tier brand effects also matter for a productivity tool.

## What I'm uncertain about
- Whether free users will materially reduce paid signups via reference
  effects ("anchoring on free").
- Whether trial-only will limit our top-of-funnel below sustainable.

## What "done" looks like
A DECIDED deliberation that says either "free tier in v1" or
"trial-only in v1," with the alternatives weighed and the leading
indicators we'd watch.

## Constraints / non-goals
Out of scope: pricing of paid tiers, annual discount policy.
```

### 7.2 Deliberation seed

`deliberations/0001-free-tier-vs-trial-only.md`:

```markdown
---
id: 0001
title: Free tier vs trial-only in v1
status: OPEN
protocol_version: 0.1
created: 2026-04-28
parent: null
children: []
roles:
  proposer: "@claude-opus"
  critics: ["@gemini-pro"]
  synthesizer: "@codex-gpt5"
  decider: "@human-rohan"
tags: [pricing, mvp, scope]
relevant_context: { repos: [], docs: [], urls: [], notes: all }
final: false
ratifies: null
---

## Question
Should v1 of the product offer a permanent free tier, or be trial-only
("14 days, then pay")?

## Context
See problem-statement.md. We have ~$8k/month in compute headroom for
free users. No prior deliberation on this question.

## Contributions

## Open Questions

## Decision
```

### 7.3 What good output looks like

A clean PROPOSAL from `@claude-opus` (excerpted):

```markdown
### [PROPOSAL] @claude-opus · 2026-04-28T14:32:18Z

## Position
Ship trial-only in v1, with an explicit revisit at month 6 once we have
real conversion-rate and acquisition-cost data.

## Reasoning
A permanent free tier is a structural commitment we can't reverse
without a costly comms event. Trial-only is reversible: we can add a
free tier later if signups stall. The reverse — removing a free tier —
turns existing free users into churn at exactly the moment we're
asking the market for trust.

## Assumptions
- We can run paid acquisition cheaply enough in months 1–6 to test
  trial-only without depending on a free-tier funnel.
- Our $8k/month compute headroom is real and durable, not a one-quarter
  burn-down.

## Risks I see
- Trial-only top-of-funnel may be smaller than projected; if month-3
  signups undershoot by >40% we should reconsider.
- Productivity-tool category has free-tier brand effects we may
  underweight.

## Alternatives I considered
- **Permanent free tier with strict feature limits.** Strong top-of-funnel,
  hard to remove later if conversion is poor. Set aside in favor of the
  reversibility argument.
- **Time-limited free tier (e.g., free for the first 1,000 users).**
  Hybrid; preserves brand effect but caps cost. Set aside as adding
  complexity without resolving the reversibility problem.

## Tagging
- @gemini-pro: critique — your adversarial framing usually finds the
  structural risks I miss, and the "reversibility" argument is exactly
  the kind of claim that benefits from a hard look.
```

A clean CRITIQUE from `@gemini-pro` would have a Strong objection that names something specific (e.g., "reversibility framing assumes existing free users are visible costs; the more dangerous case is invisible: prospects who tried a competitor instead because we had no free tier"), at least one Agreed point, and either a counter-proposal or "none — I object but do not have a better proposal yet."

A clean SYNTHESIS from `@codex-gpt5` consolidates, lists every alternative both moves surfaced (the three above plus the critique's potential addition), preserves any unresolved disagreement explicitly (e.g., "We disagree on whether the visible/invisible cost asymmetry outweighs reversibility"), and recommends.

A clean DECISION from `@human-rohan`:

```markdown
### [DECISION] @human-rohan · 2026-04-28T15:01:12Z → targets SYNTHESIS@codex-gpt5#0001

## Decision
Ship trial-only (14 days) in v1. Open a follow-up deliberation at month 6
to revisit on real conversion data. Track signups, trial→paid conversion,
and qualitative "tried us first?" survey data as the leading indicators.

## Summary line
v1 ships trial-only (14 days, then paid); free-tier decision revisited
at month 6 against signup volume and trial→paid conversion data.

## Rationale
The reversibility argument and the $8k/month compute commitment combined
outweigh the invisible-cost concern, given that the month-6 revisit
makes the choice non-permanent in practice.

## Path not taken
Permanent free tier; time-limited free-tier; deferring the call to
month 3.

## Spawns ADR? yes
## Spawns task? yes
```

Note the Summary line: 117 chars, specific (says trial duration, condition for revisit, the metrics that matter), reads usefully on its own.

### 7.4 Failure modes you should expect to see at least once

In practice, a real run produces some of:

- A PROPOSAL whose `Alternatives I considered` lists things without saying why each was set aside.
- A CRITIQUE that fails to fill `Agreed points` (writes "none" reflexively).
- A SYNTHESIS that smooths over the actual disagreement into a "balanced" recommendation.
- An agent that writes paragraphs after the move template, narrating its work.
- An agent that asks for permission to read or write files even though the standing prompt says it shouldn't need to.

These are the data. Write them down.

---

## 8. After the exercise

Distill `findings.md` into a short paragraph for each: prompt issues, template issues, validator implications. Keep that distilled summary; it becomes the seed for `docs/vertical-slice-findings.md` at the start of Phase 5.

Then throw away `$QUORUM_SCRATCH`. Nothing in it should be committed back here — it's a sandbox, not a contribution.
