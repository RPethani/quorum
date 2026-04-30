"""End-to-end tests for the Ask generator.

These tests construct a tiny but realistic workspace (state.yaml,
participants.md, config.yaml, routing-defaults, one deliberation file)
and verify that `regenerate_asks` produces the right Ask shape for each
trigger.
"""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace.ask_generator import regenerate_asks
from quorum_conductor.workspace.asks import list_open_asks


def _bootstrap_workspace(tmp_path: Path, *, manifest_locked: bool = True) -> WorkspacePaths:
    paths = WorkspacePaths(root=tmp_path)
    for d in paths.all_directories():
        d.mkdir(parents=True, exist_ok=True)

    (tmp_path / "state.yaml").write_text(
        "schema_version: '0.1'\nworkspace_id: test\nmode: interactive\n"
        "state: ACTIVE\nstate_changed_at: '2026-04-30T00:00:00Z'\n"
        "last_activity_at: null\nlast_human_activity_at: null\n"
        "pending_deputy_count: 0\n"
        "manifest:\n  status: " + ("LOCKED" if manifest_locked else "DRAFTING") + "\n"
        "  total_artifacts: 0\n  artifacts_complete: 0\n"
        "  artifacts_in_production: 0\n  artifacts_pending: 0\n"
        "  quality_gates_clear: false\n  closing_ceremony_eligible: false\n"
        "  final_deliberation_id: null\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "schema_version: '0.1'\nactive_template: null\n", encoding="utf-8"
    )
    paths.participants.write_text(
        "# Participants\n\n"
        "| Handle | Display Name | CLI Command | Model | Transport | Quota (daily/per-deliberation) | Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| @rakesh | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n"
        "| @claude-opus | Claude (Opus) | claude | opus | cli | unlimited | ask | (none) | unknown |\n"
        "| @gemini-pro | Gemini | gemini | gemini-2.5-pro | cli | unlimited | ask | (none) | unknown |\n",
        encoding="utf-8",
    )
    paths.routing_defaults.write_text(
        "schema_version: '0.1'\n"
        "fitness:\n"
        "  '@claude-opus':\n"
        "    proposer: 3\n    critic: 2\n    synthesizer: 3\n    decider: 1\n"
        "  '@gemini-pro':\n"
        "    proposer: 2\n    critic: 3\n    synthesizer: 2\n    decider: 1\n"
        "cost:\n"
        "  '@claude-opus': 5\n"
        "  '@gemini-pro': 3\n",
        encoding="utf-8",
    )
    return paths


def _write_delib(
    paths: WorkspacePaths, *, name: str, body: str, status: str = "OPEN"
) -> Path:
    p = paths.deliberations / name
    p.write_text(body, encoding="utf-8")
    return p


def test_pick_one_when_two_proposals_exist(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_delib(
        paths,
        name="0002-criteria.md",
        body=(
            "---\n"
            'id: "0002"\n'
            "title: Set comparison criteria for v2 directions\n"
            "status: OPEN\n"
            "protocol_version: 0.1\n"
            "created: 2026-04-30\n"
            "parent: null\n"
            "children: []\n"
            "roles:\n"
            "  proposer: null\n"
            "  critics: []\n"
            "  synthesizer: null\n"
            '  decider: "@rakesh"\n'
            'tags: ["@claude-opus", "@gemini-pro"]\n'
            "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
            "final: false\n"
            "---\n\n"
            "## Question\n\nWhat criteria?\n\n"
            "## Open Questions\n\n## Decision\n\n## Contributions\n\n"
            "### [PROPOSAL] @claude-opus · 2026-04-30T01:00:00Z\n\n"
            "## Position\n\nFour equal-weighted criteria.\n\n"
            "### [CRITIQUE] @gemini-pro · 2026-04-30T02:00:00Z\n\n"
            "## Objection\n\nDisagree with weighting.\n\n"
            "### [SYNTHESIS] @claude-opus · 2026-04-30T03:00:00Z\n\n"
            "## Position\n\nReconcile via dominant-axis weighting.\n"
        ),
    )

    created = regenerate_asks(paths)
    assert len(created) == 1
    ask = created[0]
    assert ask.shape == "pick_one"
    assert ask.target_move_type == "DECISION"
    assert ask.source_deliberation == "0002"
    # Synthesis from claude-opus is a single (winning) option for that
    # author. No proposal from gemini-pro (it only critiqued), so we
    # have one option total.
    assert len(ask.options) == 1
    assert ask.options[0].value == "@claude-opus"
    assert "synthesis" in ask.options[0].label
    assert "Reconcile" in ask.options[0].summary


def test_idempotent_across_passes(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _write_delib(
        paths,
        name="0002-x.md",
        body=(
            "---\n"
            'id: "0002"\n'
            "title: x\nstatus: OPEN\n"
            "protocol_version: 0.1\ncreated: 2026-04-30\n"
            "parent: null\nchildren: []\n"
            "roles:\n  proposer: null\n  critics: []\n  synthesizer: null\n"
            '  decider: "@rakesh"\n'
            'tags: ["@claude-opus"]\n'
            "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
            "final: false\n---\n\n"
            "## Question\n\n?\n\n## Open Questions\n\n## Decision\n\n## Contributions\n\n"
            "### [PROPOSAL] @claude-opus · 2026-04-30T01:00:00Z\n\n## Position\n\nDo X.\n\n"
            "### [CRITIQUE] @gemini-pro · 2026-04-30T02:00:00Z\n\n## Objection\n\nNo.\n\n"
            "### [SYNTHESIS] @claude-opus · 2026-04-30T03:00:00Z\n\n## Position\n\nFinal.\n"
        ),
    )
    first = regenerate_asks(paths)
    second = regenerate_asks(paths)
    assert len(first) == 1
    assert len(second) == 0
    assert len(list_open_asks(paths)) == 1


def test_ask_closed_when_planner_no_longer_blocks_on_human(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    delib = _write_delib(
        paths,
        name="0002-y.md",
        body=(
            "---\n"
            'id: "0002"\n'
            "title: y\nstatus: OPEN\n"
            "protocol_version: 0.1\ncreated: 2026-04-30\n"
            "parent: null\nchildren: []\n"
            "roles:\n  proposer: null\n  critics: []\n  synthesizer: null\n"
            '  decider: "@rakesh"\n'
            'tags: ["@claude-opus"]\n'
            "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
            "final: false\n---\n\n"
            "## Question\n\n?\n\n## Open Questions\n\n## Decision\n\n## Contributions\n\n"
            "### [PROPOSAL] @claude-opus · 2026-04-30T01:00:00Z\n\n## Position\n\nDo X.\n\n"
            "### [CRITIQUE] @gemini-pro · 2026-04-30T02:00:00Z\n\n## Objection\n\nNo.\n\n"
            "### [SYNTHESIS] @claude-opus · 2026-04-30T03:00:00Z\n\n## Position\n\nFinal.\n"
        ),
    )
    regenerate_asks(paths)
    assert len(list_open_asks(paths)) == 1

    # Simulate: a DECISION arrives. Planner no longer routes to human.
    delib.write_text(
        delib.read_text(encoding="utf-8")
        + "\n### [DECISION] @rakesh · 2026-04-30T04:00:00Z\n\n## Decision\n\nDone.\n",
        encoding="utf-8",
    )
    # Flip status to DECIDED so the planner skips it as terminal.
    text = delib.read_text(encoding="utf-8").replace("status: OPEN", "status: DECIDED")
    delib.write_text(text, encoding="utf-8")

    regenerate_asks(paths)
    assert list_open_asks(paths) == []


def test_no_proposals_falls_back_to_write(tmp_path: Path) -> None:
    """If the planner says the human is the decider but no PROPOSAL/
    SYNTHESIS bodies exist yet, the user gets a write Ask rather than an
    empty pick_one. (This shouldn't happen via the normal planner path,
    but the generator should be defensive.)"""
    paths = _bootstrap_workspace(tmp_path)
    # Planner won't route to DECISION without a PROPOSAL+SYNTHESIS, so
    # we don't actually exercise this path through plan() — but the
    # internal builder is used directly elsewhere. Smoke-test the
    # builder via a manually constructed pending item:
    from quorum_conductor.workspace.ask_generator import _build_decision_ask

    ask = _build_decision_ask(paths, paths.deliberations / "missing.md", "0002", "Tname")
    assert ask is not None
    assert ask.shape == "write"
    assert ask.target_move_type == "DECISION"
