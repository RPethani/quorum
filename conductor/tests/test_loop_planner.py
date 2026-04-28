"""Planner tests: deliberation flow → next (role, move_type)."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core import plan
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace import InitOptions, init_workspace


def _participants(paths: WorkspacePaths) -> None:
    paths.participants.write_text(
        "---\n"
        "schema_version: 0.1\n"
        "---\n\n"
        "# Participants Registry\n\n"
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| @fake-cli | Fake | python3 -V | x | cli | 30/5 | fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )


def _delib(paths: WorkspacePaths, *, contributions: str = "") -> Path:
    p = paths.deliberations / "0001-test.md"
    p.write_text(
        "---\n"
        'id: "0001"\n'
        "title: t\n"
        "status: OPEN\n"
        "protocol_version: 0.1\n"
        "roles:\n"
        '  proposer: "@fake-cli"\n'
        "  critics: []\n"
        "  synthesizer: null\n"
        '  decider: "@human-rohan"\n'
        "tags: []\n"
        "---\n\n"
        "## Question\n\nq\n\n"
        f"## Contributions\n{contributions}\n"
        "## Open Questions\n\n"
        "## Decision\n",
        encoding="utf-8",
    )
    return p


def test_plan_open_with_no_proposal(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _participants(paths)
    _delib(paths)
    result = plan(paths)
    assert len(result.items) == 1
    item = result.items[0]
    assert (item.role, item.move_type) == ("proposer", "PROPOSAL")
    assert item.handle.handle == "@fake-cli"
    assert item.is_manual is False


def test_plan_after_proposal_schedules_critique(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _participants(paths)
    _delib(
        paths,
        contributions="\n### [PROPOSAL] @fake-cli · 2026-04-28T14:00:00Z\n\nbody\n",
    )
    result = plan(paths)
    assert len(result.items) == 1
    assert result.items[0].move_type == "CRITIQUE"


def test_plan_after_critique_schedules_synthesis(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _participants(paths)
    _delib(
        paths,
        contributions=(
            "\n### [PROPOSAL] @fake-cli · 2026-04-28T14:00:00Z\n\nbody\n\n"
            "### [CRITIQUE] @fake-cli · 2026-04-28T14:30:00Z\n\nobj\n"
        ),
    )
    result = plan(paths)
    assert len(result.items) == 1
    assert result.items[0].move_type == "SYNTHESIS"


def test_plan_after_synthesis_routes_decision_to_human(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _participants(paths)
    _delib(
        paths,
        contributions=(
            "\n### [PROPOSAL] @fake-cli · 2026-04-28T14:00:00Z\n\nbody\n\n"
            "### [CRITIQUE] @fake-cli · 2026-04-28T14:30:00Z\n\nobj\n\n"
            "### [SYNTHESIS] @fake-cli · 2026-04-28T15:00:00Z\n\nrec\n"
        ),
    )
    result = plan(paths)
    assert len(result.items) == 1
    assert result.items[0].move_type == "DECISION"
    # The decider is @human-rohan (manual); the planner surfaces it but the
    # runnable list excludes manual items.
    assert result.items[0].is_manual is True
    assert result.runnable() == ()


def test_plan_terminal_status_skipped(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _participants(paths)
    p = _delib(paths)
    body = p.read_text(encoding="utf-8").replace("status: OPEN", "status: DECIDED")
    p.write_text(body, encoding="utf-8")
    result = plan(paths)
    assert result.items == ()
    assert len(result.skipped_terminal) == 1


def test_plan_blocked_when_no_handle_available(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    # Empty participants table — no proposer can be routed.
    paths.participants.write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota "
        "| Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n",
        encoding="utf-8",
    )
    _delib(paths)
    result = plan(paths)
    assert result.items == ()
    assert len(result.blocked) == 1
    assert result.blocked[0].role == "proposer"
