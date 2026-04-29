# 002: Phase 6 deferrals — async digestion, web URL fetch, document digestion

**Date:** 2026-04-29
**Phase:** 6
**Status:** active

## Context

Design-doc §1.8 specifies a context surface that includes:

1. **Repos** — agent-digested at setup, digest reused.
2. **Documents** — small (<5K tokens) used raw, large digested via PDF/Markdown/Word extraction.
3. **Web URLs** — fetched once, converted to Markdown via Readability + trafilatura, refresh-policy driven.
4. **Notes** — always raw, in standing bundle.

Plus:

- A **background job queue** for digestion so `add-repo` returns immediately.
- **Freshness tracking** with `digest_age_at_use` logged per invocation.

Phase 6 was completed in three sub-checkpoints (6a, 6b, 6d) but several pieces were deferred. This ADR records what was deferred and why, so Phase 9 (settings panels) and any subsequent UX work can pick them up cleanly.

## Decision

Phase 6 ships:

- **Repos**: full add / digest / store / Layer-2 inclusion. Digestion is **synchronous** (blocks the CLI until complete) and **only via cli-transport handles**.
- **Documents**: `add-doc` copies the file into `context/docs/raw/` and registers it in the manifest. **Document digestion is not implemented**: large docs are inserted raw into Layer 2 if declared. PDF / Word extraction (`pdfplumber`, `python-docx`) is deferred — adding those deps now would balloon the conductor's footprint for one untested code path.
- **Notes**: full add via `add-note --text` or `--file`. Layer-1 inclusion already works (Phase 6a).
- **Web URLs**: not implemented at all. The `add-url` command does not exist. Layer-2 url collection in `assemble_deliberation_bundle` reads from `context/web/cached/<name>.md` if a file is there — i.e., the user can manually drop a Markdown file with that name and it'll be picked up. No fetch / Readability / trafilatura.

Freshness tracking partial: each `meta.yaml` records `last_digested_at`, but `digest_age_at_use` is not yet logged on each invocation. The standing prompt's permission-discipline section mentions cached-URL fetch dates but no automated staleness annotation is injected.

## Reasoning

The Phase 6 validation gate per `PHASES.md` is *"user adds a repo via CLI command; digestion runs; bundle assembly is verified by inspecting an invocation's context via events.jsonl."* The scope above satisfies that gate fully. Synchronous digestion is fine for v1: a real Sonnet digest of a medium repo takes 60–180s, well within "I just ran a CLI command" patience.

Web URLs are conceptually clean but require:

- `trafilatura` or `readability-lxml` for HTML→Markdown,
- `requests`/`httpx` for fetch (with retry, timeout, redirect policy),
- a refresh-policy scheduler (cron-like; "weekly", "monthly"),
- auth handling (out of scope per design-doc),
- and a fetch-failure UX that's better than "the URL is just gone."

Each item is a small chore; together they're a meaningful chunk that belongs in Phase 9 (settings panels) when the user-visible UX surface is real.

Document digestion (PDF/Word) requires file-format extraction libs whose quality varies by document. v1 sidesteps this by accepting the user pre-converting external docs to Markdown and using `add-doc` for those. The current shape works for the common case (a Markdown spec) and degrades gracefully for binaries (the user gets a clear error when trying to add a `.pdf`).

Async digestion is a useful UX win but irrelevant to correctness. Adding a queue + worker thread + status polling adds enough complexity that I'd rather build it once with the full UI in Phase 7/8 than duplicate the work.

## Alternatives considered

- **Skip Phase 6 entirely until the UI exists** (Phase 7+): rejected. The conductor needs Layer-1 standing-bundle assembly and `summarized-decisions.md` maintenance to produce coherent moves on real workspaces, and those don't depend on UI.
- **Add `requests` + `trafilatura`** for web URLs now: rejected. Three new deps, untested error-mode surface, and the design-doc explicitly notes auth-required URLs are out of scope for v1 anyway. The user can manually save a page and use `add-doc`.
- **Add `pdfplumber` + `python-docx`** for document digestion: rejected for the same dep-bloat reason. The current Markdown-first add-doc is the 80% case.
- **Async digestion via threading.Thread + status file**: rejected. Synchronous digestion is correct for a CLI command; async only matters when there's a UI watching, which is Phase 7+.

## Consequences

- A user who adds a `.pdf` via `add-doc` will see it land in `context/docs/raw/<file>.pdf`, but Layer-2 inclusion will read the bytes as utf-8 with `errors="replace"` and the agent will see a stream of replacement characters. **Acceptable**: the user got a copy-once shortcut, not a magic ingestion. Phase 9 will add real digestion.
- A user wanting a web URL must manually save the rendered page to Markdown and `add-doc` it. **Acceptable** for v1.
- A user running 5 repo digestions in sequence pays for the wall time serially; for typical setups this is 5–15 minutes. **Acceptable**; async lands when the UI shows progress.
- The standing prompt currently doesn't auto-annotate digest age. Phase 12 (prompt iteration) will tune this when we observe whether agents' staleness handling is good enough already given just `last_digested_at` in the bundle's meta.

If any of these become a real workflow blocker in Phases 7–13, surface and we'll revisit.
