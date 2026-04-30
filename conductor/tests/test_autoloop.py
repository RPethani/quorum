"""Tests for `server/autoloop.py` — the background auto-runner."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from quorum_conductor.server.autoloop import AutoLoop
from quorum_conductor.workspace.state import (
    WorkspaceState,
    load_state,
    save_state,
)
from tests.test_ask_generator import _bootstrap_workspace


def _flip_state(paths, state: WorkspaceState) -> None:
    s = load_state(paths.state_yaml)
    s.state = state
    save_state(paths.state_yaml, s)


def test_autoloop_skips_when_paused(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.PAUSED)
    with patch("quorum_conductor.server.autoloop.run_items_sync") as runner:
        loop = AutoLoop(paths)
        try:
            time.sleep(0.05)  # let one tick fire
            # Force a manual tick to be deterministic.
            loop._tick_once()  # noqa: SLF001
            runner.assert_not_called()
        finally:
            loop.stop()


def test_autoloop_skips_when_open_ask_exists(tmp_path: Path) -> None:
    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.ACTIVE)
    from quorum_conductor.workspace.asks import create_ask

    create_ask(
        paths,
        question="?",
        why="",
        shape="write",
        source_deliberation="0099",
        source_move_id="m1",
        target_move_type="ANSWER",
    )
    with patch("quorum_conductor.server.autoloop.run_items_sync") as runner:
        loop = AutoLoop(paths)
        try:
            loop._tick_once()  # noqa: SLF001
            runner.assert_not_called()
        finally:
            loop.stop()


def test_autoloop_runs_when_active_no_asks(tmp_path: Path) -> None:
    """Active state + a deliberation needing a runnable item → the
    runner is invoked."""
    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.ACTIVE)

    # Drop an open deliberation that needs a PROPOSAL — the planner
    # will route to @claude-opus.
    delib = paths.deliberations / "0002-x.md"
    delib.write_text(
        "---\n"
        'id: "0002"\n'
        "title: x\n"
        "status: OPEN\n"
        "protocol_version: 0.1\ncreated: 2026-04-30\n"
        "parent: null\nchildren: []\n"
        'roles:\n  proposer: "@claude-opus"\n  critics: []\n  synthesizer: null\n'
        '  decider: "@rakesh"\n'
        'tags: ["@claude-opus"]\n'
        "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
        "final: false\n---\n\n"
        "## Question\n\n?\n\n## Open Questions\n\n## Decision\n\n## Contributions\n",
        encoding="utf-8",
    )

    with patch("quorum_conductor.server.autoloop.run_items_sync") as runner:
        runner.return_value = []
        loop = AutoLoop(paths)
        try:
            loop._tick_once()  # noqa: SLF001
            # The daemon thread may also have ticked. Just assert the
            # runner was invoked at least once — meaning the loop
            # found a runnable item and dispatched it.
            assert runner.call_count >= 1
        finally:
            loop.stop()


def test_autoloop_pauses_when_all_agents_failing(tmp_path: Path) -> None:
    """When *every* viable agent for a runnable item has crossed the
    failure threshold, the loop must pause the workspace rather than
    retry forever. Distinct from substitution: if any alternative is
    still available, we'd substitute instead of pausing."""
    from quorum_conductor.events.log import EVENT_SCHEMA_VERSION
    from quorum_conductor.server.autoloop import REPEAT_FAILURE_THRESHOLD

    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.ACTIVE)

    delib = paths.deliberations / "0002-x.md"
    delib.write_text(
        "---\n"
        'id: "0002"\n'
        "title: x\n"
        "status: OPEN\n"
        "protocol_version: 0.1\ncreated: 2026-04-30\n"
        "parent: null\nchildren: []\n"
        "roles:\n  proposer: null\n  critics: []\n  synthesizer: null\n"
        '  decider: "@rakesh"\n'
        'tags: ["@claude-opus", "@gemini-pro"]\n'
        "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
        "final: false\n---\n\n"
        "## Question\n\n?\n\n## Open Questions\n\n## Decision\n\n## Contributions\n",
        encoding="utf-8",
    )

    import json

    paths.events_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with paths.events_jsonl.open("a", encoding="utf-8") as fh:
        # Exhaust BOTH CLI handles. Substitution should find no
        # viable alternative, and the loop should pause.
        for handle in ("@claude-opus", "@gemini-pro"):
            for _ in range(REPEAT_FAILURE_THRESHOLD):
                fh.write(
                    json.dumps(
                        {
                            "type": "agent_failed",
                            "ts": "2026-04-30T00:00:00Z",
                            "schema_version": EVENT_SCHEMA_VERSION,
                            "handle": handle,
                            "role": "proposer",
                            "deliberation_id": "0002",
                            "move_type": "PROPOSAL",
                        }
                    )
                    + "\n"
                )

    with patch("quorum_conductor.server.autoloop.run_items_sync") as runner:
        loop = AutoLoop(paths)
        try:
            loop._tick_once()  # noqa: SLF001
            runner.assert_not_called()
        finally:
            loop.stop()

    assert load_state(paths.state_yaml).state is WorkspaceState.PAUSED


def test_autoloop_substitutes_handle_when_primary_fails(tmp_path: Path) -> None:
    """When the chosen handle has failed too many times, the loop must
    re-route to the next-best handle rather than pausing — pausing is
    only correct when *every* alternative is exhausted too."""
    from quorum_conductor.events.log import EVENT_SCHEMA_VERSION
    from quorum_conductor.server.autoloop import REPEAT_FAILURE_THRESHOLD

    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.ACTIVE)

    # No `proposer` pin — the planner picks via fitness defaults.
    # @claude-opus has fitness 3 for proposer; @gemini-pro has 2.
    # Mark @claude-opus as exhausted; expect @gemini to substitute.
    delib = paths.deliberations / "0002-x.md"
    delib.write_text(
        "---\n"
        'id: "0002"\n'
        "title: x\n"
        "status: OPEN\n"
        "protocol_version: 0.1\ncreated: 2026-04-30\n"
        "parent: null\nchildren: []\n"
        "roles:\n  proposer: null\n  critics: []\n  synthesizer: null\n"
        '  decider: "@rakesh"\n'
        'tags: ["@claude-opus", "@gemini-pro"]\n'
        "relevant_context:\n  repos: []\n  docs: []\n  urls: []\n  notes: all\n"
        "final: false\n---\n\n"
        "## Question\n\n?\n\n## Open Questions\n\n## Decision\n\n## Contributions\n",
        encoding="utf-8",
    )

    import json

    paths.events_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with paths.events_jsonl.open("a", encoding="utf-8") as fh:
        for _ in range(REPEAT_FAILURE_THRESHOLD):
            fh.write(
                json.dumps(
                    {
                        "type": "agent_failed",
                        "ts": "2026-04-30T00:00:00Z",
                        "schema_version": EVENT_SCHEMA_VERSION,
                        "handle": "@claude-opus",
                        "role": "proposer",
                        "deliberation_id": "0002",
                        "move_type": "PROPOSAL",
                        "reason": "subprocess_failed",
                    }
                )
                + "\n"
            )

    captured: list[str] = []

    def _capture(items, **_kw):  # type: ignore[no-untyped-def]
        captured.extend(it.handle.handle for it in items)
        return []

    with patch(
        "quorum_conductor.server.autoloop.run_items_sync", side_effect=_capture
    ):
        loop = AutoLoop(paths)
        try:
            loop._tick_once()  # noqa: SLF001
        finally:
            loop.stop()

    # Substitute must be a non-claude-opus CLI handle.
    assert captured, "expected the loop to invoke a substitute"
    assert "@claude-opus" not in captured
    # Workspace must still be ACTIVE — substitution succeeded.
    assert load_state(paths.state_yaml).state is WorkspaceState.ACTIVE


def test_autoloop_swallows_tick_exceptions(tmp_path: Path) -> None:
    """A failing tick must not crash the daemon thread.

    `_tick_once` itself does NOT swallow — that's the contract of
    `_run`. We verify the daemon stays alive even after `plan` raises
    by letting the daemon thread tick (it catches at the outer loop)
    rather than calling `_tick_once` directly.
    """
    paths = _bootstrap_workspace(tmp_path)
    _flip_state(paths, WorkspaceState.ACTIVE)
    with patch(
        "quorum_conductor.server.autoloop.plan",
        side_effect=RuntimeError("boom"),
    ):
        loop = AutoLoop(paths)
        try:
            time.sleep(0.05)  # let the daemon hit the failing tick
            assert loop._thread.is_alive()  # noqa: SLF001
        finally:
            loop.stop()
