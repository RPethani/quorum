# System retrospective / observability — placeholder

**Status:** queued. Surfaced during Q5 of the master-flow
brainstorm. Picked up after the live system-flow diagram, the
deliberation UX overhaul, and the cross-artifact coordination
work ship. This is fourth in the queue at minimum — it's a
"how do we make Quorum itself better" feature, not a
"how do we make the current project better" feature.

**Owner:** Claude (will draft brainstorm), @rakesh (decides)

---

## Why this is on the list

@rakesh, on Q5 of the master-flow brainstorm:

> "Retrospective should be internal function of the system for
> whole system. This is something we can build something
> independently in future to monitor the system from every angle
> throughout the life cycle and see what goes right/wrong and
> what can be improved."

The closing deliberation (S5) was originally going to bundle
project recap + process retrospective into one `summary.md`.
We split them: `summary.md` is the project's outward-facing
deliverable (Q5 resolution); retrospective lives elsewhere as a
system-wide observability concern.

The intent is for Quorum itself to be observable — across all
projects, what works, what fails, where users get stuck, where
agents go off the rails, where the protocol's edges get worn.

---

## What "system retrospective" might mean

Open scope. The brainstorm needs to figure out which of these
the user actually wants:

1. **Per-workspace retrospective** that's distinct from
   `summary.md`. Same data sources but oriented inward (process,
   not result). Lives in the workspace alongside the audit trail.
2. **Cross-workspace observability** — a meta-view across every
   workspace the user has ever run, surfacing patterns:
   - Which agents fail validation most often?
   - Which deliberations spent the most time blocked on humans?
   - Which manifest templates produce the most ABANDONED
     artifacts?
   - Where does the protocol force users into manual recovery
     (e.g. `NEEDS_MANIFEST_RATIFICATION` stuck states)?
3. **Per-component health** — observability into the conductor's
   internals as the system runs:
   - Autoloop tick latency, dispatch hit rate
   - Per-handle invocation success/failure breakdown
   - Cost trends over time
   - Validation failure rate by move type
4. **A continuous "Quorum-on-Quorum" workspace** — eat our own
   dog food: a permanent workspace whose problem statement is
   "improve Quorum based on what's happened in other workspaces,"
   manifest artifacts are improvement proposals, etc. The
   recursion is heavy but interesting.

---

## Likely shape (placeholder thinking)

- A read-only dashboard surface, not part of any single project
- Aggregates data from all workspaces' `events.jsonl` + `state.yaml`
- Identifies anti-patterns: stuck states that recurred,
  participants that consistently underperformed, manifest
  templates that produced incoherent outputs
- Surfaces specific suggestions ("you've hit
  `agents_unreachable` 4 times in the last week — consider
  registering a fallback participant")
- May feed back into the `.claude/rules/` directory: as we
  observe drift between docs and code, propose rule updates

---

## Why we're queueing it not building it

Retrospective is meaningful only when there's data to
retrospect on. Right now the user is mid-flight on their first
real workspace. Building observability infrastructure before the
system is settled is premature — we'd be observing a moving
target.

Build the live system-flow diagram first (the user-facing real-
time view). Build the deliberation UX overhaul next (so the user
isn't fighting the system). Build cross-artifact coordination
(so artifacts actually stay in sync). THEN start observing how
all of that goes, and let observations drive retrospective
design.

---

## Reading list when this gets picked up

1. `docs-specs/system-flow-stages.md` — for what we're observing
2. `docs-specs/visual-flow-diagram.md` — the live single-workspace
   view; retrospective is the cross-time / cross-workspace
   complement
3. `conductor/src/quorum_conductor/events/log.py` — the data
   plane retrospective will read
4. `.claude/skills/debug-loop/` — the diagnostic checklist;
   retrospective formalises and aggregates what debug-loop does
   ad-hoc
