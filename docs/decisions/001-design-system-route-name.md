# 001: Design-system showcase route is `/design-system`, not `/_design-system`

**Date:** 2026-04-28
**Phase:** 2
**Status:** active

## Context

`IMPLEMENTATION_BOOTSTRAP.md §2 (Phase 2)` and `§1 (repo layout)` specify the showcase route at `ui/app/_design-system/page.tsx`, framed as a "private, dev-only path." This conflates a naming convention with Next.js routing semantics: in the App Router, **a folder prefixed with `_` is excluded from routing entirely** ("private folder" — see Next.js docs: *Project Structure → Private folders*). The route at `/_design-system` therefore returns 404 and the showcase is unreachable.

Discovered during Phase 2 validation when the user opened `http://localhost:3000/_design-system` and saw 404.

## Decision

Rename the folder from `ui/app/_design-system/` to `ui/app/design-system/`. The route is `/design-system`. Do not gate the route in v1.

## Reasoning

- **The bootstrap's intent was a verification surface that exists during development.** A working route serves that intent; an unroutable folder does not.
- **The local UI runs only on the user's dev server** (the conductor and UI are local-only by design — see `docs/architecture.md`). There is no public production deployment from which the showcase needs to be hidden, so the "private" aspect of the bootstrap's instruction is moot.
- **No middleware gating in v1.** Adding env-var or middleware-based route gating to recreate the bootstrap's "dev-only" framing would add complexity for no benefit; the route is already only reachable on localhost.
- The bootstrap was correct in spirit; this is a Next.js technical detail it got wrong. Defer to the bootstrap's intent (a working showcase) over the literal path.

## Alternatives considered

- **Use a route group** (`(dev)/design-system/`): route groups in App Router don't gate the route — they're a folder-organization mechanism that doesn't appear in URLs. They wouldn't make the route dev-only either. Rejected: same problem, more indirection.
- **Add middleware that 404s the route in production builds**: would re-create the "private" framing but adds a code path with no real consumer (no production builds in v1). Rejected as YAGNI.
- **Edit `IMPLEMENTATION_BOOTSTRAP.md`**: the bootstrap is locked per §0 of itself; deviations are logged here instead. Rejected.
