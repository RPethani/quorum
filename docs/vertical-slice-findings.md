# Vertical-slice findings — v0.1

**Run date:** 2026-04-29
**Trio:** `@claude-sonnet` (sonnet-4.6) only — single-handle slice to keep cost minimal
**Test problem:** SaaS onboarding — blank-canvas vs 3-step guided flow
**Cost:** $0.05 against a $1 ceiling (one Sonnet PROPOSAL on the manifest deliberation, 224s wall, return code 0)

This document captures what the Phase-5 vertical slice exposed about the protocol, the standing prompt, the validator, and the conductor. Phase 6 should not begin until the **P1** items here are addressed.

---

## What worked

- **Conductor end-to-end pipeline**: routing (Layer-3 fitness defaults) → CLI invocation → minimal validation → append-with-lock → inbox notification → events.jsonl. Every step on the happy path of `transport/invoker.invoke()` exercised cleanly. The exit-code-0 + `appended: yes` on the first try is a strong signal that the orchestration substrate is solid.
- **`--add-dir .` worked**: the agent successfully read `protocol/PROTOCOL.md`, the move template, and `problem-statement.md` from the workspace cwd. Setting subprocess `cwd=paths.root` (added during 5b setup) was the right move.
- **Cost tracking**: $0.05 / $1.00 (5%) after one Sonnet invocation. The flat-rate USD-per-invocation estimate is in the right ballpark.
- **Move format compliance**: the model produced a structurally-perfect PROPOSAL — canonical header line, every required section in the right order (`Position` / `Reasoning` / `Assumptions` / `Risks I see` / `Alternatives I considered` / `Tagging`), with substantive (not vacuous) content in each. No prompt rewrite is needed for the move-block format itself.
- **Inbox notification**: `@human-rohan` got the right `pending: PROPOSAL in #0001 by @claude-sonnet` line. The tag-extraction logic works against real model output.
- **Events log**: `routing_decision → agent_started → move_appended → agent_completed` recorded in events.jsonl with correct attempt number, duration, and stdout-character count.

The protocol's structural intent is right. The bugs below are integration glitches between the agent runtime, the standing prompt, and the validator — fixable without touching the move vocabulary itself.

---

## What broke

### P1 — Standing prompt tells the agent to do file I/O the conductor handles

**Symptom.** Sonnet emitted prose at the top of its response: *"Write permissions are being blocked in this session. Here is the complete PROPOSAL move I've composed — the user can apply it manually or grant write access."* It then included the canonical move *inside a fenced code block*, plus instructional prose about how to apply it and meta-edits to two inbox files.

**Root cause.** The standing prompt (`prompts/agent-standing-prompt.md`) tells the agent:

> - Append the move to the deliberation file. **Never edit prior moves.**
> - If you tag another agent, update their inbox and include a one-line justification…

But the conductor's invoker is the writer (it captures stdout and appends). The agent doesn't have Write/Edit tools available unless we pass `--allowedTools Write,Edit`, and even if it did, two writers would race the file lock. The standing-prompt language collides with the actual orchestration model.

**Fix.** Rewrite the standing prompt's "what to do on each invocation" section so the agent:

1. Outputs **only** the canonical move (header line + sections + prose), starting at the very first character of stdout.
2. Does **not** attempt file writes; the conductor handles all persistence.
3. Does **not** wrap the move in a code fence.
4. Does **not** include instructional prose, follow-up suggestions, or "also needed" sections.

A draft replacement clause: *"Your response must consist of one and only one move: a canonical block starting with `### [MOVE_TYPE] @author · timestamp` and containing every required section per `protocol/templates/<move_type>.md`. Output nothing before the header, nothing after the move's last section, and no fenced code blocks around it. The conductor reads stdout and appends the move; you never write to disk."*

**Affected:** `prompts/agent-standing-prompt.md`. Probably also the per-handle override docs once those exist.

---

### P1 — Validator is too lenient: prose preamble made it through

**Symptom.** The deliberation file now contains, under `## Contributions`:

```text
Write permissions are being blocked in this session. Here is the complete PROPOSAL move I've composed — the user can apply it manually or grant write access.

---

## PROPOSAL move to append to `deliberations/0001-outcome-manifest.md`

Insert after the `## Contributions` heading (before `## Open Questions`):

```markdown
### [PROPOSAL] @claude-sonnet · 2026-04-29T00:00:00Z

## Position

…
```

The validator accepted this because `find_first_header()` (in `core/move_format.py`) scans **every** line for a canonical header — it doesn't care that there are 5+ lines of prose and a code-fence opener before it.

**Fix.** Two complementary changes in `core/move_format.py` and `core/validator.py`:

1. **Strip code-fence wrappers** on the way in: if the agent's stdout (after leading whitespace) begins with ```` ```markdown ```` or similar, strip the fence and the trailing ` ``` `. Many models reflexively wrap structured output.
2. **Require the move to be at-or-near the start of the response.** Allow only whitespace and an optional fence before the header. If anything else precedes it, validation fails. The retry feedback should explicitly say *"do not include any text before the canonical header."*

Once those land, this exact failure mode trips the retry path; the second attempt will likely produce a clean response.

**Affected:** `conductor/src/quorum_conductor/core/move_format.py`, `core/validator.py`, plus tests.

---

### P2 — Planner doesn't recognise the bootstrapper role

**Symptom.** Deliberation #0001 has `roles: { bootstrapper: null, proposer: null, … }` in frontmatter (set by `workspace/bootstrapper._seed_body()`). But `core/loop.plan_for_delib._next_action()` always asks for `proposer` first when no PROPOSAL exists. So the seed deliberation gets routed as `proposer/PROPOSAL`, not `bootstrapper/PROPOSAL`. Result: **the bootstrapper-specific standing-prompt augmentation is never applied** ("you are creating the workspace's first deliberation, which is always about the outcome manifest…").

In this slice, Sonnet inferred from the file contents that this was a manifest-bootstrapping context and behaved appropriately, but that's accidental compensation. A weaker model might not.

**Fix.** Add a step to the planner's state machine:

```
if a PROPOSAL is missing AND the deliberation declares a bootstrapper role
   OR the frontmatter contains `ratifies: outcome-manifest.md`:
    return ("bootstrapper", "PROPOSAL", "open_needs_manifest_proposal")
else if a PROPOSAL is missing:
    return ("proposer", "PROPOSAL", "open_needs_proposal")
```

Plus a corresponding `routing-defaults.yaml` lookup for the `bootstrapper` role (already present in the file).

**Affected:** `core/loop.py:_next_action()`, `core/deliberation.py` (expose the bootstrapper role / `ratifies` field clearly), tests.

---

### P2 — `manifest-templates/` not copied to the workspace

**Symptom.** Sonnet noted: *"`protocol/manifest-templates/` is empty (no files found), so I am working from the protocol spec and problem statement alone."* The agent is correct — `scaffold_workspace()` copies `protocol/PROTOCOL.md` and `protocol/templates/*` from the repo, but **not** `protocol/manifest-templates/*`.

That's a v0.1 design judgement I made ("manifest templates are repo-shipped starting points, not editable workspace artifacts"). The slice shows it's the wrong default: the bootstrapper agent expects to read them from the workspace.

**Fix.** Either:

- (a) copy `manifest-templates/*` into the workspace at init alongside the move templates, or
- (b) in the bootstrapper standing-prompt augmentation, point the agent at the *bundled* location explicitly (`<repo>/protocol/manifest-templates/`).

(a) is simpler and consistent with how move templates already work. Pick (a).

**Affected:** `workspace/scaffolding.py` (copy block), `paths.py` (add `manifest_templates` path), the bootstrapper augmentation in `prompts/agent-standing-prompt.md`.

---

## P3 observations (file for later — not gates)

- **224s wall-time per invocation.** Claude Code's startup (system prompt assembly, tool registration, plugin sync, CLAUDE.md auto-discovery) eats 90%+ of the wall time before generation. For Phase 12's prompt-iteration this matters; consider `claude --bare` for tighter iteration loops, accepting the loss of CLAUDE.md context.
- **Recursive Claude Code invocation.** We invoked Claude Code from inside a Claude Code session. It worked, but real users running `quorum start` from a terminal won't pay this overhead. Worth noting in user docs.
- **Agent volunteered "also needed" follow-up instructions** ("Also needed: inbox/@human-rohan.md should…"). Likely a downstream symptom of the P1 prompt issue — once the prompt forbids meta-instruction, this should disappear.
- **The substantive PROPOSAL content is excellent.** Once the prompt + validator are tightened, the move's *content* needs no further prompt engineering for the manifest case. We may discover different stories with CRITIQUE / SYNTHESIS / DECISION; those will surface in subsequent slices.

---

## Action items, ordered by gate impact

1. **[P1] Standing prompt rewrite** — output-only-the-move; no I/O; no code fences; no preamble. ✅
2. **[P1] Validator: strip fences + require move at start.** ✅
3. **[P2] Planner detects bootstrapper deliberation** and schedules `bootstrapper/PROPOSAL`. ✅
4. **[P2] Scaffold copies `manifest-templates/`** into the workspace at init. ✅
5. **Re-run the slice** with the fixes. ✅

Phase 6 (context surface) is unblocked.

---

## Re-run after fixes (gate validation)

Run date: 2026-04-29
Workspace: `/tmp/quorum-slice-2/demo` (same problem statement)
Trio: `@claude-sonnet` only
Result: **gate passes** — clean canonical PROPOSAL appended; cumulative cost $0.10 / $1.00 across two invocations.

### What changed mechanically

- Plan now reads `[defaults] #0001 bootstrapper/PROPOSAL → @claude-sonnet` (was `proposer/PROPOSAL`). The seed deliberation routes under the bootstrapper role, so the standing prompt's bootstrapper augmentation fires.
- `protocol/manifest-templates/` is populated in the workspace at init (5 archetypes). The agent referenced `protocol/manifest-templates/saas-product.md` by name in its Reasoning section.

### Validator + retry behavior

`attempts: 2` — the first attempt emitted a preamble before the canonical header. Validator rejected it with the message *"response must start with the canonical move header — no preamble, no \"here is the move\" prose, no fenced code blocks."* The retry feedback was fed back into the prompt, the second attempt produced a clean response, and validation passed. Retry path is working as designed.

This is also a good first data point on the retry feature itself: real-model feedback works, and 64s on the retry vs 116s wall-time total includes the 51s of the failed first attempt — implying retry is roughly the same cost as a fresh attempt. Worth keeping in mind for cost accounting.

### Quality of the produced move

Sonnet's PROPOSAL on the second attempt is materially *better* than the first:

- Two-artifact manifest (decision + supporting analysis), not three.
- Reasons explicitly about not adopting `saas-product.md` because pricing / tech-stack / ux-requirements are out of scope per `problem-statement.md`.
- Names a `Single agent workspace` risk: with only `@claude-sonnet` and `@human-rohan` registered, there's no critic or synthesizer; the deliberation will rely on the human for adversarial pressure. Honest and useful.
- Tagging is concrete — addressed at `@human-rohan` for the required DECISION, with stakes-classification (`strategic`) called out.

The move's structural compliance is perfect: every required PROPOSAL section is present and substantive. The validator's per-section + anti-vacuousness checks all pass.

### Remaining P3 observations (unblockers, not gates)

- Wall time: 116s for two attempts (51s + 64s). Faster than the first run because the agent's response was shorter on the retry; tool-loading still dominates startup. `claude --bare` would help.
- The agent's Reasoning section explicitly cites `protocol/manifest-templates/saas-product.md` — confirming that the agent does read the templates. The `--add-dir .` + cwd=workspace setup is correct.
- Single-agent workspaces work for the manifest deliberation but the move quality would improve with at least one other handle (different model or different account) for CRITIQUE. We knew this; the slice confirms it.

### Gate decision

Phase 5 is **closed**. Phase 6 (context surface) may begin.
