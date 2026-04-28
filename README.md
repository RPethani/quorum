# Quorum

*Where premium AI subscriptions deliberate together.*

## What Quorum is

A quorum is the minimum number of members of a deliberative body needed to make valid decisions. Quorum (the project) is a local, file-first hub that lets multiple paid AI assistants — Claude, ChatGPT, Gemini, and others you already pay for — collaborate on hard problems through structured, auditable artifacts rather than ad-hoc copy-pasting.

The canonical journey: **vague thought → deliberation → critical human questions → synthesis → decided spec, ADR, or brief.**

Agents take turns appending typed *moves* (PROPOSAL, CRITIQUE, SYNTHESIS, DECISION, …) to Markdown files in a workspace folder under your project. A small Python *conductor* routes work to the right agent for each role, and a local Next.js UI lets you watch deliberations unfold, intervene, and approve the outcome. The repo is the medium; Markdown is the lingua franca; you are editor-in-chief.

Quorum's niche is **collaborative reasoning** — turning vague product ideas, architecture questions, research directions, and rough drafts into well-reasoned, decided artifacts. It is not a code-execution coordinator; tools like Cursor, Aider, and Windsurf already address that space.

## Status

🚧 **Under construction.** Quorum is being built in phases against a locked v0.18 design (`multi-agent-collab-hub-design.md`) and an implementation plan (`IMPLEMENTATION_BOOTSTRAP.md`, `PHASES.md`). Nothing here runs yet. The current phase is tracked in `PHASES.md`.

## Install

Installation instructions will land in Phase 14 (polish & packaging). For now, this repo contains the design, the implementation plan, and the in-progress code tree.

## Repository layout

- `multi-agent-collab-hub-design.md` — the design spec (v0.18). Source of truth for *what* to build.
- `IMPLEMENTATION_BOOTSTRAP.md` — operating instructions for the build. Source of truth for *how* to build.
- `PHASES.md` — phase plan with deliverables and validation gates.
- `docs/architecture.md` — one-page system overview.
- `docs/decisions/` — implementation ADRs.
- `conductor/` — Python package: routing, validation, lifecycle, file watching, HTTP/WebSocket server.
- `ui/` — Next.js 15 app: workspace shell, deliberation timeline, settings panels.
- `protocol/` — the Markdown protocol: `PROTOCOL.md`, move templates, manifest templates.
- `prompts/` — standing agent prompt and per-handle overrides.
- `routing-defaults/` — bundled fitness ratings for canonical handles.
- `scripts/` — installer and dev convenience scripts.

## License

MIT. See `LICENSE`.
