"""Phase-resolution tests for `core/next_actions.compute_phase`.

These guard the structural invariant that banners can't contradict
each other: every workspace state resolves to exactly one phase, and
each phase's action list is coherent on its own.

Tests construct a `_Signals` directly rather than seeding files —
the integration of file-state → signals is exercised by the broader
e2e tests.
"""

from __future__ import annotations

from quorum_conductor.core.next_actions import (
    WorkspacePhase,
    _actions_for,
    _resolve_phase,
    _Signals,
)


def _signals(**overrides: object) -> _Signals:
    """All-clear baseline; tests override one or two fields per case."""
    base: dict[str, object] = {
        "statement_empty": False,
        "deliberation_count": 1,
        "state_value": "ACTIVE",
        "cli_count": 1,
        "healthy_count": 1,
        "unhealthy": [],
        "pending_digests": 0,
        "pending_urls": 0,
        "pending_permissions": 0,
        "human_blocker_ids": [],
        "has_context": True,
    }
    base.update(overrides)
    return _Signals(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------- #
# Phase precedence
# ---------------------------------------------------------------------- #


def test_phase_needs_setup_wins_over_everything() -> None:
    s = _signals(
        statement_empty=True,
        deliberation_count=0,
        cli_count=0,  # also flagged
        human_blocker_ids=["0001"],
    )
    assert _resolve_phase(s) is WorkspacePhase.NEEDS_SETUP


def test_phase_needs_agent_when_setup_done_but_no_cli() -> None:
    s = _signals(cli_count=0, healthy_count=0)
    assert _resolve_phase(s) is WorkspacePhase.NEEDS_AGENT


def test_phase_agents_unreachable_when_cli_present_but_unhealthy() -> None:
    s = _signals(cli_count=1, healthy_count=0, unhealthy=["@claude"])
    assert _resolve_phase(s) is WorkspacePhase.AGENTS_UNREACHABLE


def test_phase_needs_digestion_blocks_human_action() -> None:
    """A pending digest is more urgent than a pending human move."""
    s = _signals(
        pending_digests=2,
        human_blocker_ids=["0001"],
    )
    assert _resolve_phase(s) is WorkspacePhase.NEEDS_DIGESTION


def test_phase_awaiting_permission_above_human() -> None:
    s = _signals(
        pending_permissions=1,
        human_blocker_ids=["0001"],
    )
    assert _resolve_phase(s) is WorkspacePhase.AWAITING_PERMISSION


def test_phase_awaiting_human_when_inbox_has_pending() -> None:
    s = _signals(human_blocker_ids=["0001"])
    assert _resolve_phase(s) is WorkspacePhase.AWAITING_HUMAN


def test_phase_ready_to_run_when_initialized_with_delibs() -> None:
    s = _signals(state_value="INITIALIZED")
    assert _resolve_phase(s) is WorkspacePhase.READY_TO_RUN


def test_phase_running_when_active_and_idle() -> None:
    s = _signals(state_value="ACTIVE")
    assert _resolve_phase(s) is WorkspacePhase.RUNNING


def test_phase_idle_terminal() -> None:
    s = _signals(state_value="DECIDED", deliberation_count=0)
    assert _resolve_phase(s) is WorkspacePhase.IDLE


# ---------------------------------------------------------------------- #
# Coherence: blockers and suggestions don't cohabit a phase
# ---------------------------------------------------------------------- #


def test_awaiting_human_emits_no_start_loop_suggestion() -> None:
    """The bug that motivated the refactor — start-loop must NOT appear
    while a human move is pending. answer-inbox is the only output."""
    s = _signals(
        state_value="INITIALIZED",
        human_blocker_ids=["0001"],
    )
    actions = _actions_for(_resolve_phase(s), s)
    ids = [a.id for a in actions]
    assert ids == ["answer-inbox"]
    assert all(a.severity == "blocking" for a in actions)


def test_needs_digestion_emits_only_digestion_blocker() -> None:
    s = _signals(state_value="INITIALIZED", pending_digests=1)
    actions = _actions_for(_resolve_phase(s), s)
    assert [a.id for a in actions] == ["digest-context"]


def test_ready_to_run_emits_start_loop_only_when_no_blockers() -> None:
    s = _signals(state_value="INITIALIZED")
    actions = _actions_for(_resolve_phase(s), s)
    assert any(a.id == "start-loop" and a.severity == "suggested" for a in actions)


def test_blocking_phases_never_emit_suggestions() -> None:
    """Sanity: every blocking-phase action list is severity=blocking only."""
    blocking_phases = (
        WorkspacePhase.NEEDS_SETUP,
        WorkspacePhase.NEEDS_AGENT,
        WorkspacePhase.AGENTS_UNREACHABLE,
        WorkspacePhase.NEEDS_DIGESTION,
        WorkspacePhase.AWAITING_PERMISSION,
        WorkspacePhase.AWAITING_HUMAN,
    )
    for phase in blocking_phases:
        actions = _actions_for(phase, _signals())
        assert actions, f"phase {phase} returned no actions"
        for a in actions:
            assert a.severity == "blocking", f"{phase} emitted non-blocking {a.id}"


def test_idle_with_context_emits_nothing() -> None:
    s = _signals(state_value="DECIDED", deliberation_count=0, has_context=True)
    actions = _actions_for(_resolve_phase(s), s)
    assert actions == []


def test_idle_without_context_emits_only_add_context_suggestion() -> None:
    s = _signals(state_value="DECIDED", deliberation_count=0, has_context=False)
    actions = _actions_for(_resolve_phase(s), s)
    assert [a.id for a in actions] == ["add-context"]
    assert all(a.severity == "suggested" for a in actions)


def test_ready_to_run_without_context_emits_both_suggestions() -> None:
    s = _signals(state_value="INITIALIZED", has_context=False)
    actions = _actions_for(_resolve_phase(s), s)
    assert [a.id for a in actions] == ["start-loop", "add-context"]
    assert all(a.severity == "suggested" for a in actions)
