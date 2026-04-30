"""End-to-end tests for the Ask answerer."""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.workspace.ask_answerer import AnswerError, answer_ask
from quorum_conductor.workspace.ask_generator import regenerate_asks
from quorum_conductor.workspace.asks import get_ask, list_open_asks
from tests.test_ask_generator import _bootstrap_workspace, _write_delib


_DELIB_TPL = """---
id: "0002"
title: Set comparison criteria
status: OPEN
protocol_version: 0.1
created: 2026-04-30
parent: null
children: []
roles:
  proposer: null
  critics: []
  synthesizer: null
  decider: "@rakesh"
tags: ["@claude-opus", "@gemini-pro"]
relevant_context:
  repos: []
  docs: []
  urls: []
  notes: all
final: false
---

## Question

What criteria?

## Open Questions

## Decision

## Contributions

### [PROPOSAL] @claude-opus · 2026-04-30T01:00:00Z

## Position

Four equal-weighted criteria.

### [CRITIQUE] @gemini-pro · 2026-04-30T02:00:00Z

## Objection

Disagree.

### [SYNTHESIS] @claude-opus · 2026-04-30T03:00:00Z

## Position

Reconcile via dominant-axis weighting.
"""


def _seed_with_pending_decision(tmp_path: Path):
    paths = _bootstrap_workspace(tmp_path)
    delib = _write_delib(paths, name="0002-criteria.md", body=_DELIB_TPL)
    regenerate_asks(paths)
    open_asks = list_open_asks(paths)
    assert len(open_asks) == 1
    return paths, delib, open_asks[0]


def test_pick_one_writes_decision_and_flips_status(tmp_path: Path) -> None:
    paths, delib, ask = _seed_with_pending_decision(tmp_path)
    answered = answer_ask(
        paths,
        ask.id,
        answer={"value": "@claude-opus", "note": "I trust the synthesis."},
        author="@rakesh",
    )
    assert answered.status == "answered"

    body = delib.read_text(encoding="utf-8")
    assert "[DECISION] @rakesh" in body
    assert "Picked:" in body and "claude-opus" in body
    assert "I trust the synthesis." in body
    # status flipped on terminal move
    assert "status: DECIDED" in body


def test_idempotent_double_submit(tmp_path: Path) -> None:
    paths, delib, ask = _seed_with_pending_decision(tmp_path)
    answer_ask(
        paths,
        ask.id,
        answer={"value": "@claude-opus"},
        author="@rakesh",
    )
    body_after_first = delib.read_text(encoding="utf-8")
    answer_ask(
        paths,
        ask.id,
        answer={"value": "@claude-opus"},
        author="@rakesh",
    )
    body_after_second = delib.read_text(encoding="utf-8")
    assert body_after_first == body_after_second


def test_custom_escape_writes_freeform_decision(tmp_path: Path) -> None:
    paths, delib, ask = _seed_with_pending_decision(tmp_path)
    answer_ask(
        paths,
        ask.id,
        answer={
            "value": "__custom__",
            "text": "None of the above. Use a totally different approach.",
        },
        author="@rakesh",
    )
    body = delib.read_text(encoding="utf-8")
    assert "[DECISION] @rakesh" in body
    assert "totally different approach" in body
    # Custom escape must NOT name a "Picked: **@…" winner.
    assert "Picked:" not in body.split("[DECISION]")[1]


def test_invalid_answer_raises(tmp_path: Path) -> None:
    paths, delib, ask = _seed_with_pending_decision(tmp_path)
    with pytest.raises(AnswerError):
        answer_ask(
            paths,
            ask.id,
            answer={"value": "@nobody"},
            author="@rakesh",
        )
    # Ask is still open.
    again = get_ask(paths, ask.id)
    assert again is not None and again.status == "open"
