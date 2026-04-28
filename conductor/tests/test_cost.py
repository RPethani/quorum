"""Cost-summary tests."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.cost import compute_cost
from quorum_conductor.core.routing_defaults import RoutingDefaults
from quorum_conductor.events import (
    AgentCompleted,
    AgentFailed,
    EventLogger,
    ValidationFailed,
)


def _defaults() -> RoutingDefaults:
    return RoutingDefaults(
        fitness={},
        cost={"@a": 5, "@b": 1},
        usd_per_invocation={"@a": 0.10, "@b": 0.01},
    )


def test_compute_cost_empty_when_no_events(tmp_path: Path) -> None:
    summary = compute_cost(tmp_path / "events.jsonl", _defaults())
    assert summary.spent_usd == 0.0
    assert summary.invocations == 0
    assert summary.unknown_handles == []


def test_compute_cost_sums_completed_events(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        AgentCompleted(
            handle="@a",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            duration_s=0.1,
            return_code=0,
            attempt=1,
            stdout_chars=100,
        )
    )
    log.emit(
        AgentCompleted(
            handle="@b",
            role="critic",
            deliberation_id="0001",
            move_type="CRITIQUE",
            duration_s=0.1,
            return_code=0,
            attempt=1,
            stdout_chars=80,
        )
    )
    summary = compute_cost(log.path, _defaults())
    assert summary.invocations == 2
    assert summary.spent_usd == 0.11
    assert summary.by_handle == {"@a": 0.10, "@b": 0.01}
    assert summary.by_handle_invocations == {"@a": 1, "@b": 1}


def test_compute_cost_includes_failed_attempts(tmp_path: Path) -> None:
    """The user paid for failed model calls too — count them toward the ceiling."""
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        AgentFailed(
            handle="@a",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            duration_s=0.0,
            reason="subprocess_failed",
            error="exit 2",
            attempt=1,
            return_code=2,
        )
    )
    log.emit(
        ValidationFailed(
            handle="@a",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            errors=["bad summary"],
            attempt=1,
        )
    )
    summary = compute_cost(log.path, _defaults())
    assert summary.invocations == 2
    assert summary.spent_usd == 0.20


def test_compute_cost_records_unknown_handles(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        AgentCompleted(
            handle="@unrated",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            duration_s=0.1,
            return_code=0,
            attempt=1,
            stdout_chars=100,
        )
    )
    summary = compute_cost(log.path, _defaults())
    assert summary.spent_usd == 0.0
    assert summary.invocations == 1
    assert summary.unknown_handles == ["@unrated"]


def test_at_or_above_ceiling_threshold() -> None:
    from quorum_conductor.core.cost import CostSummary

    summary = CostSummary(
        spent_usd=10.0,
        invocations=10,
        by_handle={"@a": 10.0},
        by_handle_invocations={"@a": 10},
        unknown_handles=[],
    )
    assert summary.at_or_above_ceiling(10.0)
    assert summary.at_or_above_ceiling(5.0)
    assert not summary.at_or_above_ceiling(20.0)
    assert summary.fraction_of(20.0) == 0.5
