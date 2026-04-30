# Cross-artifact coordination — placeholder

**Status:** queued. Surfaced during the Q3 (REOPEN multiplexing)
discussion in `system-flow-stages.md`. Picked up after the live
system-flow diagram and the deliberation UX overhaul ship.

**Owner:** Claude (will draft brainstorm), @rakesh (decides)

---

## Why this is on the list

@rakesh, on Q3 of the master-flow brainstorm:

> "Most of the times, the documents decided for outputs have to
> stay in sync. User would not brainstorm in one direction only.
> Things could change down the line which might demand the
> cascaded changes in upstream documents. If this is not true in
> current system, we risk producing disconnected output documents
> at the end of the brainstorming."

He's right. The current protocol's "one deliberation per artifact"
model assumes artifacts are independent, but real artifacts have
dependencies (ux-requirements depends on requirements;
recommendation depends on option-analysis depends on criteria).
When a downstream insight invalidates an upstream assumption,
today the *user* is the only mechanism that propagates the
change — by deciding to REOPEN. Nothing in the protocol records
the dependency, signals the conflict, or coordinates the
revision.

---

## What's actually in the code today

Audited 2026-04-30. Two facts that frame the problem:

1. **Only the manifest auto-writes from its deliberation.**
   `workspace/ratify.py:maybe_ratify_manifest` early-returns if
   the deliberation's `ratifies:` value is not `outcome-manifest.md`.
   Comment in the code: *"Future versions will generalise this to
   all ratifies: targets."* So `option-analysis.md`,
   `recommendation.md`, etc. **are not produced as real files on
   disk** by the conductor today. The artifact's content lives
   only inside its deliberation's canonical move body (latest
   SYNTHESIS, fallback to latest PROPOSAL).

2. **No protocol primitive for cross-deliberation revision.** The
   existing levers either stay within one deliberation
   (REVISION, STEER, INTERJECTION) or have to be invoked from
   outside the in-flight one (REOPEN). No move type lets
   deliberation B formally say "and please revise A."

What does propagate automatically: each agent invocation reads
the workspace state fresh, so if an upstream deliberation's
content changes, downstream agents' *next* invocations see the
new content. They just don't get told "by the way, an upstream
just changed — reconsider whether your current PROPOSAL still
stands."

---

## Questions the brainstorm has to answer

When this gets picked up, the design needs calls on:

1. **Should the conductor auto-produce artifact files from
   DECIDED deliberations?** Generalising `maybe_ratify_manifest`
   so each `ratifies:` deliberation, on terminal DECISION/OVERRIDE,
   writes the canonical move body to its target file. Pros:
   makes "the artifact" a real thing on disk; gives downstream
   agents (and humans) a clean reference. Cons: introduces a
   second source of truth (file vs. deliberation body) — risk of
   drift if a user hand-edits the file.

2. **What's the protocol primitive for "this DECISION implies
   upstream revision is needed"?** Options:
   - A new move type, e.g. `REVISES_UPSTREAM` that points at a
     specific other deliberation and triggers a REOPEN-with-
     context.
   - An annotation on DECISION (`triggers_revision_of: <delib_id>`)
     that gets picked up by the planner.
   - An Ask that surfaces to the operator: "the work in B
     implies A needs revision — REOPEN A?"
   - Nothing formal; just leave it to STEER / inbox tags.

3. **Should the system track artifact-version dependencies?**
   E.g. "B was decided against vN of A; A is now vN+1, surface a
   'reconsider B' Ask." Pros: prevents stale-assumption silent
   drift. Cons: significant state-machinery; needs a versioning
   system for artifact bodies.

4. **What's the user's discovery surface for "an upstream
   changed, this in-flight deliberation may have stale
   assumptions"?** Could be:
   - A banner on the deliberation in the UI.
   - An auto-generated CRITIQUE move emitted by the conductor
     when a dependency change is detected.
   - A new Ask shape: "upstream A was revised — should
     deliberation B incorporate the change before deciding?"

5. **Dependency declaration — explicit or inferred?** The
   manifest could carry per-artifact dependency declarations
   (e.g. `recommendation.md depends on: option-analysis.md`).
   The conductor uses these to compute "if A changes, what's
   downstream?" Or we infer dependencies from `relevant_context`
   references. Or we leave it unstated and rely on user/agent
   judgement.

6. **Backwards-compat with the current single-deliberation-per-
   artifact model.** Whatever we add must not require existing
   workspaces to migrate; it must layer on cleanly.

---

## What's NOT in scope

- The single-shot artifact production pipeline (turning a
  DECIDED deliberation into a file on disk) — that's part of
  question 1 above and could ship independently.
- The general "we need to auto-write artifact files" gap. If
  worth shipping ahead of the full coordination feature, do
  it as a separate small commit; don't wait on this brainstorm.

---

## Reading list when this is picked up

1. `docs-specs/system-flow-stages.md` — the master flow
2. `conductor/src/quorum_conductor/workspace/ratify.py` — the
   manifest-only ratification path that needs generalising
3. `conductor/src/quorum_conductor/workspace/auto_advance.py` —
   per-artifact deliberation opener
4. The protocol move-type catalog in `protocol/templates/*.md`
5. `.claude/rules/non-negotiables.md` for protocol invariants
   that any new move type has to respect
