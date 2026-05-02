---
description: Visual flow diagram drift defence — when the system's flow changes in code, the diagram and its schema must change too.
---

# Visual flow diagram — drift defence

The live system-flow diagram (`ui/components/flow/system-flow-diagram.tsx`)
is operator-clarity infrastructure. It's only useful if it accurately
reflects what the system is actually doing. When the system changes,
the diagram has to change with it — same commit, no exceptions.

This rule defines what counts as a flow change and what to update.

---

## What counts as a flow change

Any of the following:

1. **A new stage** in the master flow (the spine S1..S6).
2. **A change to an existing stage's enter/leave trigger** — e.g.
   adding a precondition for S2→S3, changing what writes the
   manifest LOCKED status, etc.
3. **A new sub-step** inside the per-deliberation move sequence
   (Propose → Critique → Synthesise → Decide), or a new terminal
   move (DECISION / OVERRIDE / DROP).
4. **A new orthogonal pause/block condition** — e.g. a new
   `WorkspacePhase` value in `next_actions.py` that the diagram
   should surface.
5. **A change to the workspace state machine** (`WorkspaceState`
   enum) or the manifest status machine.
6. **Renaming any of the above.**

If you're not sure whether your change qualifies, it probably does.
Ask before merging.

---

## What to update when a flow change happens

In the same commit:

1. **`docs-specs/system-flow-stages.md`** — the prose master spec.
   Update the relevant stage section, the open-questions list if
   one needs reopening, and the "Decisions locked so far" header
   if a previously-locked decision is being revisited.

2. **`docs-specs/flow.yaml`** — the machine-readable mirror. Keep
   it in sync with the prose. Both are source-of-truth from
   different angles.

3. **`ui/lib/flow/types.ts`** — the TypeScript types backing the
   diagram. Add/rename/remove enum values to match the new shape.

4. **`ui/lib/flow/derive.ts`** — the API → SystemFlowState
   derivation. Update `resolveStage`, `buildDetail`, and pause
   detection so the diagram lights up correctly for the new
   condition.

5. **`ui/components/flow/*.tsx`** — node renderers and the main
   `system-flow-diagram.tsx`. If you added a new sub-step or
   stage rendering shape, you need a new (or modified) custom
   node component.

6. **Tests** — when there are flow-derivation tests, add coverage
   for the new state. (No tests yet at first-draft time; this
   guidance applies once we add the `derive.test.ts`.)

---

## Anchor source files (read these before changing the master flow)

The master flow is implemented across:

- `conductor/src/quorum_conductor/workspace/state.py` —
  `WorkspaceState` enum + `ManifestProgress`
- `conductor/src/quorum_conductor/workspace/init.py` — initial
  workspace scaffold
- `conductor/src/quorum_conductor/workspace/bootstrapper.py` —
  seed deliberation creation
- `conductor/src/quorum_conductor/workspace/ratify.py` — manifest
  LOCKED transition
- `conductor/src/quorum_conductor/workspace/auto_advance.py` —
  per-artifact deliberation opening
- `conductor/src/quorum_conductor/workspace/archive.py` — ARCHIVED
  transition
- `conductor/src/quorum_conductor/server/autoloop.py` — tick
  policy and `agents_unreachable` pause
- `conductor/src/quorum_conductor/server/http_app.py` —
  `_handle_wizard_apply` / `_activate_if_ready`
- `conductor/src/quorum_conductor/core/loop.py` —
  `_TERMINAL_STATUSES`, planner
- `conductor/src/quorum_conductor/core/next_actions.py` —
  every `WorkspacePhase` value
- `conductor/src/quorum_conductor/core/move_format.py` — the
  protocol move types
- `conductor/src/quorum_conductor/core/validator.py` — the DROP
  on-seed rule

A change to any of these likely needs the diagram updated.

---

## Quick audit when in doubt

```
# Compare the master-flow doc against the current code state machines.
diff <(grep -E "^\s*[A-Z_]+ = \"" conductor/src/quorum_conductor/workspace/state.py) \
     <(grep -E "^\s*-\s*\b[A-Z_]+\b" docs-specs/flow.yaml | sort -u)
```

If you see new enum values in the code that aren't in `flow.yaml`,
or the other way around, that's drift.
