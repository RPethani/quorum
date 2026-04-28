"""Phase 4h — open the workspace's first deliberation.

The bootstrapper exists so a fresh workspace's first auto-loop tick has
something to work on. It produces the seed deliberation #0001 (the
outcome manifest, per design-doc §1.7) if and only if:

  1. `outcome-manifest.md` is still in `DRAFTING` (i.e., not yet locked
     by a real DECISION), and
  2. no deliberation file already exists.

The seed is a *plain* deliberation file with the bootstrapper role
declared in frontmatter. The loop's planner (4f) will then schedule
the bootstrapper for a PROPOSAL, the standing prompt's `bootstrapper`
augmentation will tell that agent to draft the manifest, and downstream
moves carry the deliberation through to a human-issued DECISION.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..paths import WorkspacePaths

SEED_DELIBERATION_ID = "0001"


def needs_bootstrap(paths: WorkspacePaths) -> bool:
    """True if we should open the seed deliberation."""
    if not paths.deliberations.is_dir():
        return False
    existing = list(paths.deliberations.glob("*.md"))
    if existing:
        return False
    if not paths.outcome_manifest.is_file():
        return True
    body = paths.outcome_manifest.read_text(encoding="utf-8")
    # If the manifest is already LOCKED or READY, the workspace was
    # bootstrapped previously and is mid-flight; do not seed.
    return "status: LOCKED" not in body and "status: READY" not in body


def bootstrap_seed_deliberation(paths: WorkspacePaths) -> Path:
    """Create deliberation #0001 if missing. Returns the path either way."""
    target = paths.deliberations / f"{SEED_DELIBERATION_ID}-outcome-manifest.md"
    if target.exists():
        return target
    paths.deliberations.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    target.write_text(_seed_body(today), encoding="utf-8")
    return target


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _seed_body(today: str) -> str:
    return (
        "---\n"
        f'id: "{SEED_DELIBERATION_ID}"\n'
        "title: Outcome manifest — what 'done' looks like\n"
        "status: OPEN\n"
        "protocol_version: 0.1\n"
        f"created: {today}\n"
        "parent: null\n"
        "children: []\n"
        "roles:\n"
        "  proposer: null   # bootstrapper role; routing fills this in\n"
        "  critics: []\n"
        "  synthesizer: null\n"
        "  decider: \"@human-rohan\"\n"
        "  bootstrapper: null\n"
        "tags: [bootstrap, manifest]\n"
        "relevant_context:\n"
        "  repos: []\n"
        "  docs: []\n"
        "  urls: []\n"
        "  notes: all\n"
        "final: false\n"
        "ratifies: outcome-manifest.md\n"
        "---\n\n"
        "## Question\n\n"
        "What artifacts must this workspace produce, with what completion checks "
        "and quality gates, before it can be considered done?\n\n"
        "## Context\n\n"
        "This is the seed deliberation (design-doc §1.7). The proposer is "
        "invoked under the `bootstrapper` augmentation: they read "
        "`problem-statement.md` and any relevant manifest template under "
        "`protocol/manifest-templates/`, then propose a complete manifest "
        "for human review.\n\n"
        "## Contributions\n\n"
        "## Open Questions\n\n"
        "## Decision\n"
    )
