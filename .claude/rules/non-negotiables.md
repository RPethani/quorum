---
description: Project-wide invariants that must never be broken. Read before any change.
---

# Non-negotiables

These rules have been broken before, hurt, and got us into the design
we have now. Treat them as load-bearing.

## Auto-loop policy

The conductor's autoloop must:

1. Tick continuously while `state == ACTIVE`.
2. Sleep when there's an open Ask — humans block; agents wait.
3. Sleep when no runnable item is available — quiet, not paused.
4. **Substitute, then pause.** If a participant fails repeatedly,
   re-route to the next-best participant for that role. Only pause
   when *every* viable participant is exhausted. Pausing on first
   failure is forbidden — that was the early bug.
5. Treat `timeout` as 3-strikes immediately. Treat `subprocess_failed`
   / `validation_failed` as one strike each.

If you change this, update `conductor/tests/test_autoloop.py` in the
same commit and call out the policy change explicitly.

## Protocol invariants

- `## Contributions` is the **last H2** in a deliberation file. Move
  bodies use H2 sub-headings (`## Position`, `## Decision`, `## Reasoning`)
  which would otherwise truncate parser output. Don't reorder.
- Handle tokens (`@claude`, `@gemini`, `@rakesh`, ...) **must be
  quoted** in YAML flow sequences. `@` is reserved in YAML and
  `tags: [@x, @y]` is invalid. Use `tags: ["@x", "@y"]`.
- The seed deliberation `#0001` carries `ratifies: outcome-manifest.md`
  in frontmatter. When it reaches DECISION/OVERRIDE, the conductor
  auto-locks the manifest and auto-opens the next artifact's
  ratification deliberation. Don't bypass this.

## Server lifecycle

- Always run from source: `uv run python -m quorum_conductor serve …`.
  The `~/.local/bin/quorum` binary is a uv-installed *snapshot* of
  the source from some earlier point — it will not pick up your
  changes. Several debugging hours have been lost to this.
- HTTP server hosts the autoloop in-process. There is no separate
  `quorum start` daemon in normal operation. The autoloop is wired in
  `server/http_app.py:create_server()`.

## Workflow rules

- **Don't commit unless asked.** The user reviews changes before
  commits. When you finish a unit of work, summarise what's in the
  working tree. Commit only on explicit "commit this" or "let's
  commit".
- **Run the full test suite before declaring done.**
  `cd conductor && uv run pytest -q`
  `cd ui && npx --yes tsc --noEmit && npx --yes @biomejs/biome check .`
  Failure means don't ship.
- **Don't add deps casually.** Bundle adders for UI deps need user
  approval. Same for new Python deps. Most things can be done with
  what's already there.
- **Verify, don't assume.** Curl the live API, read the actual file,
  run the actual test. Do not write "the implementation should…"
- **No restart without need.** Server restarts cost time; only when
  Python code changed. UI changes are hot-reloaded.

## When in doubt, look at neighbours

- Adding a UI component? Look at `components/workspace/` and copy
  the patterns. Don't invent.
- Adding a Python module? Look at neighbours in `core/` or
  `workspace/`. The codebase has a strong house style.
- Adding a token class? Don't. Use what `app/globals.css` defines.
