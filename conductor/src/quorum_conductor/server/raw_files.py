"""Whitelist of files that the /api/raw read/write endpoints expose.

Per design-doc §9.8 Tier 3 the user can edit a small set of "raw" YAML
and Markdown files directly. We refuse anything not on this list — the
editor is an escape hatch, not a free-form file browser.
"""

from __future__ import annotations

from pathlib import Path

from ..paths import WorkspacePaths


def whitelist(paths: WorkspacePaths) -> dict[str, Path]:
    return {
        "config.yaml": paths.config_yaml,
        "state.yaml": paths.state_yaml,
        "problem-statement.md": paths.problem_statement,
        "outcome-manifest.md": paths.outcome_manifest,
        "registers/participants.md": paths.participants,
        "registers/routing-defaults.yaml": paths.routing_defaults,
        "registers/glossary.md": paths.glossary,
        "registers/open-questions.md": paths.open_questions,
        "registers/summarized-decisions.md": paths.summarized_decisions,
        "context/index.md": paths.context_index,
        "context/context-manifest.yaml": paths.context_manifest,
    }
