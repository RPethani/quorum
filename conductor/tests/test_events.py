"""events.jsonl logger and reader tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from quorum_conductor.events import (
    EVENT_SCHEMA_VERSION,
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    EventLogger,
    MoveAppended,
    RoutingDecisionEvent,
    ValidationFailed,
    read_events,
)


def test_emit_writes_one_jsonl_line(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events" / "events.jsonl")
    log.emit(
        AgentStarted(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
        )
    )
    body = log.path.read_text(encoding="utf-8").splitlines()
    assert len(body) == 1
    obj = json.loads(body[0])
    assert obj["type"] == "agent_started"
    assert obj["handle"] == "@claude-opus"
    assert obj["role"] == "proposer"
    assert obj["deliberation_id"] == "0001"
    assert obj["move_type"] == "PROPOSAL"
    assert obj["attempt"] == 1
    assert obj["schema_version"] == EVENT_SCHEMA_VERSION
    assert "ts" in obj


def test_emit_appends_new_lines(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        AgentStarted(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
        )
    )
    log.emit(
        AgentCompleted(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            duration_s=0.5,
            return_code=0,
            attempt=1,
            stdout_chars=512,
        )
    )
    events = list(read_events(log.path))
    assert [e["type"] for e in events] == ["agent_started", "agent_completed"]


def test_routing_decision_event_serialises_alternatives(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        RoutingDecisionEvent(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            layer="defaults",
            fitness=3,
            cost=5,
            alternatives=[
                {
                    "handle": "@gemini-pro",
                    "fitness": 2,
                    "cost": 3,
                    "rejected_because": "lower_fitness",
                }
            ],
            note="",
        )
    )
    obj = next(iter(read_events(log.path)))
    assert obj["type"] == "routing_decision"
    assert obj["alternatives"][0]["handle"] == "@gemini-pro"
    assert obj["alternatives"][0]["rejected_because"] == "lower_fitness"


def test_validation_failed_carries_error_list(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        ValidationFailed(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            errors=["required section missing: 'Tagging'"],
        )
    )
    obj = next(iter(read_events(log.path)))
    assert obj["type"] == "validation_failed"
    assert obj["errors"] == ["required section missing: 'Tagging'"]


def test_agent_failed_carries_reason_and_error(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        AgentFailed(
            handle="@x",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            duration_s=0.0,
            reason="subprocess_failed",
            error="exit code 2",
            attempt=1,
            return_code=2,
        )
    )
    obj = next(iter(read_events(log.path)))
    assert obj["reason"] == "subprocess_failed"
    assert obj["error"] == "exit code 2"
    assert obj["return_code"] == 2


def test_move_appended_carries_inboxes(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")
    log.emit(
        MoveAppended(
            handle="@claude-opus",
            role="proposer",
            deliberation_id="0001",
            move_type="PROPOSAL",
            inboxes_notified=["@gemini-pro", "@human-rohan"],
        )
    )
    obj = next(iter(read_events(log.path)))
    assert obj["inboxes_notified"] == ["@gemini-pro", "@human-rohan"]


def test_emit_is_thread_safe(tmp_path: Path) -> None:
    log = EventLogger(tmp_path / "events.jsonl")

    def emit_many() -> None:
        for _ in range(50):
            log.emit(
                AgentStarted(
                    handle="@x",
                    role="proposer",
                    deliberation_id="0001",
                    move_type="PROPOSAL",
                )
            )

    threads = [threading.Thread(target=emit_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events = list(read_events(log.path))
    assert len(events) == 200
    # Every line must have been a complete JSON object.
    assert all(e["type"] == "agent_started" for e in events)


def test_read_events_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"type":"agent_started","ts":"2026-04-28T00:00:00Z","schema_version":"0.1"}\n'
        "\n"
        "not json\n"
        '{"type":"agent_completed","ts":"2026-04-28T00:00:01Z","schema_version":"0.1"}\n',
        encoding="utf-8",
    )
    events = list(read_events(path))
    assert [e["type"] for e in events] == ["agent_started", "agent_completed"]
