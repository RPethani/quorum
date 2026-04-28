# quorum-conductor

The Python conductor for Quorum: routing, validation, lifecycle, file watching, and (later) the HTTP/WebSocket server the UI consumes. This package is invoked through the `quorum` CLI installed by the project script entry.

## Quick start (development)

```bash
cd conductor
uv sync                # creates .venv, installs deps + dev-deps from pyproject.toml
uv run quorum --help   # exercise the CLI
uv run pytest          # run the test suite
uv run mypy            # type-check
uv run ruff check .    # lint
```

## What's implemented

This is the v1 build, growing through the sub-phases listed in `PHASES.md`:

- **4a – scaffolding** ✅ — package layout, CLI entry, `--help`, `--version`.
- **4b – workspace lifecycle** ✅ — `init`, `status`, `doctor`, `archive`, `unarchive`.
- 4c – routing engine
- 4d – invocation
- 4e – validator
- 4f – loop (`start`, `pause`, `step`, `run`, `resume`)
- 4g – events.jsonl
- 4h – bootstrapper (deliberation #0001)
- 4i – cost ceiling
- 4j – tests across modules

Sub-phase status lives in `PHASES.md` at the repo root.
