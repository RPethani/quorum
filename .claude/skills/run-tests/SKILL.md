---
description: Run the full project test + lint suite for Python (pytest + mypy + ruff) and TypeScript (tsc + biome). User-only — invoke via `/run-tests`. Claude must not auto-run tests.
disable-model-invocation: true
---

# Run tests

Quorum has two test/lint domains: the Python conductor and the
Next.js UI. Both must pass before declaring a change done.

## Python (conductor)

```bash
cd /Users/rakeshpethani/Personal/quorum/conductor

# Full test suite (~15s):
uv run pytest -q

# One file, stop on first failure:
uv run pytest tests/<file>.py -x -q

# Type-check the modules you changed:
uv run mypy --strict src/quorum_conductor/<module>.py

# Lint:
uv run ruff check src tests
```

Expected: `217+ passed in <20s`. Anything failing means don't ship.

## TypeScript (UI)

```bash
cd /Users/rakeshpethani/Personal/quorum/ui

# Type check (must come back silent):
npx --yes tsc --noEmit

# Lint + format check:
npx --yes @biomejs/biome check .

# Auto-fix safe issues:
npx --yes @biomejs/biome check --write app components lib
```

Expected: `Checked N files. No fixes applied.` on the check command.

## Sequencing

If you've changed Python only → just the Python suite.
If you've changed TS only → just the TS suite.
If you've changed both → run Python first (faster signal), then TS.

## When tests fail

1. Read the failure output, don't summarise it.
2. Fix the smallest thing that makes the test pass without changing
   the test's intent.
3. If the test seems wrong, **flag it to the user** — don't silently
   rewrite it.
4. Re-run the same target until green, then run the full suite once
   more to catch regressions.

## When biome complains about something you didn't touch

The `biome check --write` command applies safe auto-fixes. If it
modifies a file you didn't open, that's still your responsibility to
review before declaring done — read the diff.
