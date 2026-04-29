# 003: Permission broker — live stdin/stdout pipe proxying deferred

**Date:** 2026-04-29
**Phase:** 11
**Status:** active

## Context

Design-doc §10.6 describes a permission broker that:

1. proxies the agent CLI's stdin/stdout,
2. detects "may I run this shell command?" prompts in the CLI's output,
3. routes the prompt to the user via the UI's permission-request cards,
4. injects the user's decision back into the CLI's stdin so the agent can proceed.

This is the part of the broker that turns "the agent asked for permission and got an answer" into a real workflow primitive. It requires a per-CLI prompt-detection layer (each CLI has its own prompt format), pty-style stdin/stdout management, and back-pressure handling for pre-CLI buffer states.

Phase 11 in `PHASES.md` is "the full broker." I shipped the data plane and UI but not the live proxy.

## Decision

Phase 11 ships:

- `core/permissions.py` — full request/decision data plane (PermissionRequest, status enum, stakes enum, file-system layout under `runtime/permissions/{,decided}/<id>.yaml`, list/get/approve/deny/auto_approve operations).
- HTTP endpoints — `GET /api/permissions`, `POST /api/permissions`, `POST /api/permissions/<id>/{approve,deny}`.
- UI — `/permissions` page that polls every 5s, lists pending + decided requests, and approves/denies inline.

What's deferred:

- **Live stdin/stdout proxying.** No mechanism in the conductor's `transport/invoker._spawn` to detect that a child process is waiting for permission, intercept that prompt, write a permission-request file, and feed the user's decision back to the child once it's made.
- **Per-CLI prompt detection.** Each CLI (Claude Code, Gemini, Codex) has its own way of asking for permission; production-grade detection needs per-CLI handlers.
- **`broker.enabled` config plumbing.** Config schema mentions it; no code reads it yet because there's no consumer.

The v1 baseline defense remains the `--allowedTools` flag passed to whichever CLIs support it; out-of-allowlist requests fail the move cleanly via the existing invocation path.

## Reasoning

The data plane and UI surface are the part that other phases will integrate with: the loop, the audit trail, the UX patterns. They benefit from being settled now even if no requester yet uses them. The live proxy is a discrete, well-bounded chunk of work — pty management, regex prompt detection, back-pressure — that's easier to land cleanly when prioritised on its own than when squeezed in alongside everything else Phase 11 aimed to ship.

The bootstrap doc's Phase-11 instructions actually anticipate this: *"Build standalone first (per design doc): a small Python prototype that wraps a single CLI and validates the pipe pattern works, before integrating into the conductor."* Treating that prototype as a Phase-11.5 or Phase-13 follow-up matches the design's own staging.

The validation gate per `PHASES.md` says "User enables broker in Settings, triggers an out-of-allowlist request, approves it, sees the agent proceed." That requires the live proxy. We're not closing that gate with this commit — it stays open until the proxy lands.

## Alternatives considered

- **Ship a partial proxy (Claude-Code-only, no pty management)**: rejected. The design needs to handle multiple CLIs; building one CLI's prompt detection without a generalised abstraction would force a rewrite when the second CLI lands. Better to do it once with the abstraction in place.
- **Expand the data plane to model a "live request waiting on agent stdin"**: rejected. Without a way to surface that to the agent, the model would be a fiction.
- **Drop the data plane entirely until the proxy is ready**: rejected. The UI surface is useful for tests, manual approvals (someone could write a permission request via `POST /api/permissions` and approve it through the UI), and as the schema other phases code against.

## Consequences

- The Phase-11 validation gate stays open: the gate cannot pass without the live proxy. Phase 12+ can proceed (they don't depend on it), but a follow-up checkpoint will close 11 fully when the proxy lands.
- A permission request created via `POST /api/permissions` and approved via the UI does *not* unblock any agent in v1; the conductor never reads the decided file. Useful only for testing the data plane.
- `broker.enabled: true` in `config.yaml` has no effect in v1; Phase-11.5 follow-up makes it meaningful.
