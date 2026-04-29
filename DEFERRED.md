# Deferred work — single source of truth

This document is the canonical register of everything Quorum has
deliberately not built yet. It consolidates:

- ADRs in `docs/decisions/` (v1-build deferrals)
- The design doc's §19 "Deferred Optimizations Register" (long-term
  punts with revisit triggers)
- The design doc's §9.7 "Out of scope for v1" notes
- Anything else marked v2+/later/future in the spec

Each row carries: **what's missing**, **why we deferred it**, **the
trigger that should make us revisit**, and a **rough cost estimate**
when we do.

If you're considering work that's already on this list, link to the
row in the PR. If you find something deferred that isn't here, add it.

---

## Table of contents

1. [v1 deferrals (active ADRs)](#1-v1-deferrals-active-adrs)
2. [v2+ items called out by the design doc](#2-v2-items-called-out-by-the-design-doc)
3. [§19 Deferred Optimizations Register](#3-19-deferred-optimizations-register)
4. [Smaller "out of scope for v1" items](#4-smaller-out-of-scope-for-v1-items)
5. [Closed deferrals (shipped)](#5-closed-deferrals-shipped)

---

## 1. v1 deferrals (active ADRs)

These are pieces of v1 scope we deliberately punted to keep the v1
release tractable. Each is documented in its own ADR; this section
just summarises so the table is scannable.

| Item | ADR | Impact today | Trigger to revisit | Estimated cost |
|---|---|---|---|---|
| **Live permission broker (stdin/stdout proxy)** | [003](docs/decisions/003-permission-broker-deferral.md) | Allowlist enforcement happens via `--allowedTools` only; out-of-allowlist requests fail moves cleanly. The data plane (request store, approve/deny endpoints, UI dialog) is already shipped — only the live proxy is missing. | Users repeatedly need an agent to access a tool that isn't on the static allowlist mid-deliberation. | 1–2 weeks. Standalone Python prototype wrapping a single CLI first to validate the pipe pattern; then per-CLI prompt-detection rules. |
| **Empirical prompt iteration** | [004](docs/decisions/004-phase-12-prompt-iteration-deferral.md) | The standing prompt + augmentations are present and validated structurally, but not tuned against gaming behaviour observed in real workspaces. The anti-gaming augmentation shipped. | After 5+ real-world workspaces produce a corpus of agent moves we can analyse for vacuous Alternatives, generic gaps, stakes misclassification, etc. | 1 dedicated week, real CLI invocations, ~$50–150 in agent costs. |
| **Real-world cross-archetype testing** | [005](docs/decisions/005-phase-13-real-world-testing-deferral.md) | v1 has only been exercised end-to-end in a single brainstorming workspace. The other archetypes (architecture decision, research direction, coding plan, strategic decision) have manifest templates but haven't been driven through. | When the user has time + a real problem in each archetype to drive. | ~1 week of mostly waiting-on-agents, low cost since the system is now stable. |
| **URL refresh-policy automation** | [002 update](docs/decisions/002-phase6-deferrals.md) | URL fetch on add and manual refresh both work. The `refresh_policy` field (`never` / `manual` / `weekly` / `monthly`) is captured on add and persisted, but no daemon acts on `weekly`/`monthly`. | Users notice cached URLs going stale and don't realise they need a manual refresh. | 1–2 days. Cron-ish loop in the conductor that polls the manifest, checks `fetched_at` against policy, calls the existing refresh endpoint. |

## 2. v2+ items called out by the design doc

Larger pieces explicitly marked for a future major version.

### 2.1 MCP transport for participants

**Description.** A `mcp` transport in the Participants schema. The
conductor would expose `list_pending_for(@handle)`,
`read_deliberation(id)`, `append_move(...)` to MCP-compatible clients;
agents pull from the MCP server reading the same files.

**Why deferred.** Mostly redundant with `cli` transport when agents
are CLI-native. Matters most for IDE-bound or MCP-native clients.

**Trigger.** A user is on a primarily-MCP-native model that doesn't
have a CLI shipping form, OR a meaningful integration with Cursor /
Windsurf / Zed becomes a goal.

**Estimated cost.** Medium. Need an MCP server implementation
(`mcp-python-sdk` or hand-rolled), plus tests covering the same
move-validation contract as the CLI invoker.

### 2.2 IDE transport (Cursor, Windsurf, …)

**Description.** Agent-mode IDE clients that read/write Quorum files
directly via the filesystem. Reuses the protocol; the `ide` transport
just identifies that the client may be a human-in-the-loop.

**Why deferred.** No current integration target stable enough to
build against; the protocol shape needs more soak time.

**Trigger.** Same as MCP — a concrete IDE integration becomes a
goal. Likely co-arrives with MCP.

**Estimated cost.** Low after MCP lands. The IDE flavour is
basically a manual-with-tooling variant.

### 2.3 OCR for scanned PDFs

**Description.** Currently `core/context_extract.extract_doc` raises
`DocumentExtractError` for PDFs with no extractable text.

**Why deferred.** OCR adds heavy native dependencies (Tesseract or
similar) for a tiny fraction of typical input.

**Trigger.** A user repeatedly hits the "scanned PDF" error path.

**Estimated cost.** Medium. New dep, new failure modes (OCR quality,
language detection), platform-specific bundling (Tesseract on
macOS/Linux/Windows differs).

### 2.4 Authenticated URL fetch

**Description.** Currently `fetch_url` does an unauthenticated GET
via trafilatura. Internal wikis, paywalled content, Confluence, Notion,
Google Docs are all out of reach.

**Why deferred.** Auth is per-platform. Doing it well means
credential storage, refresh, scoped permissions — a project in
itself.

**Trigger.** Multiple users need to feed Confluence/Notion content
into workspaces and "save the page as a doc and add-doc it" wears
out as a workaround.

**Estimated cost.** High. Credential management, per-platform
adapters (Confluence REST, Notion API, Google Docs export), and a
UX for "this URL needs auth — connect your account."

### 2.5 Cross-workspace shared registers and context

**Description.** A user-level profile directory that workspaces
inherit `glossary.md`, `participants.md`, `routing-defaults.yaml`,
and registered context sources from. Tracked as DO-4 in §19.

**Why deferred.** Premature. Sync semantics (when does the shared
view of a repo digest evolve, and what happens to dependent
workspaces?) need real usage to design well.

**Trigger.** Users report friction re-adding the same context
across many workspaces, OR the "many parallel brainstorms in the
same org" use case becomes common.

**Estimated cost.** Medium. New `~/.quorum/` directory, override
semantics in `core/config` and `core/participants`, conflict
resolution UX.

## 3. §19 Deferred Optimizations Register

The design doc maintains a permanent register of optimisations we've
deliberately not built. The full text lives in §19 of
`multi-agent-collab-hub-design.md`; this section captures the
decision-relevant facts so a future reader doesn't have to re-derive
them.

### DO-1 — Warm-pool process management

**What.** Pre-started CLI processes idling, ready for instant
invocation. Removes the 2–4s cold-start per turn.

**Why deferred.** Most CLIs don't cleanly support
single-prompt-into-running-process. The design's existing latency
hiding (§9.6 progressive status messages) covers the perceptual cost.

**Triggers.** (a) Deliberations exceed 50 invocations consistently;
(b) `cold_start_ms` >20% of total wall clock from logs; (c) user
friction despite latency hiding; (d) multi-hour brainstorming becomes
the primary use case.

**Cost.** Substantial. Per-CLI implementation, new failure modes.

### DO-2 — Dynamic per-move routing (LLM-driven)

**What.** Replace static fitness tables with a small LLM that picks
the best handle per move dynamically. Design calls this the
"north-star" routing architecture.

**Why deferred.** Adds an LLM call per turn; static is 80% as good
with 0% of the failure surface. Need observation data to tune.

**Triggers.** (a) ~500 deliberations of log data; (b) high
`move_outcome: revised` rates correlated with specific
(role, handle) pairs; (c) >20 handles in routing-defaults; (d)
frequent workspace overrides indicating defaults are wrong.

**Cost.** Medium. The events.jsonl schema (§10.5) already records
`routing_decision` and `move_outcome` so the training data is
available the moment we want it.

### DO-3 — Automatic context-source staleness detection + quality scoring

**What.** Detect when a digest has materially diverged from current
source without re-digesting; score digest quality against a
deliberation's needs; surface "this digest looks thin" warnings.

**Why deferred.** v1 has manual freshness indicators
(`last_digested_at` on each source, `digest_age_at_use` on each
invocation via the `ContextLoaded` event). The signals needed for
automation are present in events.jsonl; we just don't yet know which
patterns predict trouble.

**Triggers.** (a) Users report decisions on stale digests; (b)
high `on_demand_file_read` correlates with poor moves; (c)
multi-month workspaces become common.

**Cost.** Medium. Needs offline analysis tooling for events.jsonl
plus a UX for surfacing "this digest is suspect."

### DO-4 — Cross-workspace shared registers and context

**See §2.5 above.** Same item; cross-listed because the design doc
puts it in §19 too.

### DO-5 — Agent-driven protocol evolution

**What.** Agents propose changes to PROTOCOL.md itself through normal
deliberation moves.

**Why deferred.** The protocol must stabilise before it can evolve
through its own mechanisms. Premature self-reference is confusing.

**Triggers.** PROTOCOL.md reaches v0.3+ (i.e. has been through real
revisions) AND users start wanting to extend it.

**Cost.** Low when triggered. Just a new move type and a CI step
that bumps `PROTOCOL.md` after a DECISION on a meta-deliberation.

### DO-6 — LLM-narrated resume briefing

**What.** Augment the structured resume briefing with an
LLM-generated narrative ("Your last session focused on pricing…").

**Why deferred.** Structured briefing covers 90% of the value
without an LLM call.

**Triggers.** (a) Users say the structured briefing isn't enough
after week-long pauses; (b) sessions span months; (c)
collaborator-onboarding-into-an-existing-workspace becomes a use
case.

**Cost.** Low. One small LLM call on resume; reuses existing prompt
plumbing.

### DO-7 — Adaptive stakes classification & deputy thresholds

**What.** Learn per-handle stakes-misclassification rates and
override rates on deputy decisions; adjust which handles can author
QUESTION moves, per-stakes wait timers, or per-user thresholds.

**Why deferred.** No data yet. The events.jsonl schema is designed
to make this a labeled-dataset problem when we have ~100 deputy
decisions.

**Triggers.** (a) Users report deputy decisions overridden too
often; (b) deputy decisions feel too conservative; (c) ~100 deputy
decisions of data accumulate.

**Cost.** Medium. Offline analysis + per-handle threshold persistence.

## 4. Smaller "out of scope for v1" items

Tighter cuts from the spec — easy to add when the use case lands.

| Item | Source | Notes |
|---|---|---|
| Move editing after submission | §9.7 | REVISIONs supersede; never edit. Probably permanent. |
| Drafts in compose-move form | §9.7 | Nice-to-have; not essential. |
| Rich-text formatting in compose-move | §9.7 | Plain Markdown only by design. Keep it that way. |
| Inline suggestions / autocomplete in compose-move | §9.7 | "Later" — likely v2 if a corpus of past moves is large enough to suggest from. |
| Per-day quota tracking on routing | `core/routing.py:_is_available` | Phase 4g punted this. `quota_daily` field on Participant exists; routing only checks `health == red` today. |
| Real per-call token accounting | `core/cost.py` | Flat-rate per invocation; the docstring acknowledges this. Needs per-CLI parsers for "tokens used" lines plus tiktoken/equivalent for fallback. |
| Context-load monitoring (token-budget enforcement) | design doc §10 | `ContextLoaded` event now carries `bundle_tokens_estimated`; nothing currently caps the bundle size. |

## 5. Closed deferrals (shipped)

For honesty: items that *were* on this list and are now shipped.

| Item | Originally deferred in | Closed in |
|---|---|---|
| Doc digestion (PDF/DOCX) | ADR-002 | `core/context_extract.py` + the digestion queue (kind=doc). |
| Web URL fetch + Markdown caching | ADR-002 | trafilatura via `core/context_extract.fetch_url`. Manual refresh works; only refresh-policy automation remains. |
| Async digestion job queue | ADR-002 | `core/digestion_queue.py` with daemon-thread workers and persistent state in `runtime/services/digestions.json`. |
| `digest_age_at_use` per-invocation logging | ADR-002 | `core/context_bundle.summarize_bundle` + `ContextLoaded` event from `transport/runner`. |
| Unavailability policy actually drives routing | audit gap | `core/routing.py` honours `strict` / `substitute` / `substitute_aggressively`. |
| No-progress stop detector (real version) | audit gap | "Two consecutive ticks with no MoveAppended" loop in `cli._cmd_run`. |
| Audit events: `digester_chosen`, `digest_started`, `digest_completed`, `permission_requested`, `permission_decided`, `context_loaded` | design-doc §10.5 | All emit-sites wired in this v1. |
| Raw YAML editor (Tier 3) | audit gap | `RawEditorDialog` in the workspace. |
| Settings tier indicators (frozen / live / live-with-effects) | audit gap | `TierBadge` in every settings panel. |

---

## How to use this document

- **Reading:** Start with §1 (active v1 deferrals — most likely to be relevant). §3 and §2 are where v2+ work lives.
- **Adding an entry:** When you defer something, add it here in the appropriate section with the same shape (impact / trigger / cost). Cross-link any ADR.
- **Closing an entry:** Move the row from §1–4 down to §5 with a one-line note about where it landed.
- **Cross-referencing:** PR descriptions for any feature work should link the entry here that they close.
