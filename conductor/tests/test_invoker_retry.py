"""Retry-on-validation-failure + events-emission tests for the invoker.

These complement test_invoker.py (4d). The fake CLI here is allowed to
emit different output on attempt 1 vs attempt 2 so we can exercise the
retry branch deterministically.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from quorum_conductor.core.deliberation import load_deliberation
from quorum_conductor.core.participants import Participant
from quorum_conductor.events import EventLogger, read_events
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.transport.invoker import InvocationRequest, invoke
from quorum_conductor.workspace import InitOptions, init_workspace

GOOD_PROPOSAL = textwrap.dedent(
    """\
    ### [PROPOSAL] @fake-cli · 2026-04-28T14:32:18Z

    ## Position

    Ship trial-only.

    ## Reasoning

    Reversibility wins.

    ## Assumptions

    none

    ## Risks I see

    none

    ## Alternatives I considered

    - Permanent free tier — set aside.

    ## Tagging

    - @gemini-pro: critique
    """
)

BAD_PROPOSAL_MISSING_TAGGING = textwrap.dedent(
    """\
    ### [PROPOSAL] @fake-cli · 2026-04-28T14:32:18Z

    ## Position

    Ship trial-only.

    ## Reasoning

    Reversibility wins.

    ## Assumptions

    none

    ## Risks I see

    none

    ## Alternatives I considered

    - Permanent free tier — set aside.
    """
)


def _make_two_attempt_cli(tmp_path: Path, first: str, second: str) -> Path:
    """Fake CLI that emits `first` on the first run and `second` on the second.

    Persists a counter file in tmp_path so the script is itself stateless.
    """
    counter = tmp_path / "_attempt_counter"
    script = tmp_path / "fake_cli.py"
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys
        from pathlib import Path
        counter = Path({str(counter)!r})
        n = int(counter.read_text()) if counter.is_file() else 0
        n += 1
        counter.write_text(str(n))
        sys.stdin.read()
        if n == 1:
            sys.stdout.write({first!r})
        else:
            sys.stdout.write({second!r})
        """
    )
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def _seed(paths: WorkspacePaths) -> Path:
    path = paths.deliberations / "0001-pricing.md"
    path.write_text(
        '---\n'
        'id: "0001"\n'
        'title: Pricing tier structure\n'
        'status: OPEN\n'
        'protocol_version: 0.1\n'
        'roles:\n'
        '  proposer: "@fake-cli"\n'
        '  critics: []\n'
        '  synthesizer: null\n'
        '  decider: "@human-rohan"\n'
        'tags: []\n'
        '---\n\n'
        '## Question\n\nFree tier vs trial-only?\n\n'
        '## Contributions\n\n'
        '## Open Questions\n\n'
        '## Decision\n',
        encoding="utf-8",
    )
    return path


def _build(paths: WorkspacePaths, deliberation: Path, fake_cli: Path) -> InvocationRequest:
    handle = Participant(
        handle="@fake-cli",
        display_name="Fake",
        cli_command=f"{sys.executable} {fake_cli}",
        model="fake",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health="green",
    )
    meta = load_deliberation(deliberation)
    return InvocationRequest(
        handle=handle,
        role="proposer",
        move_type="PROPOSAL",
        deliberation=meta,
        deliberation_path=deliberation,
        mode="interactive",
        timeout_s=10.0,
    )


def test_retry_recovers_after_first_validation_failure(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed(paths)
    fake = _make_two_attempt_cli(
        tmp_path,
        first=BAD_PROPOSAL_MISSING_TAGGING,
        second=GOOD_PROPOSAL,
    )
    request = _build(paths, delib, fake)
    events = EventLogger(paths.events_jsonl)
    result = invoke(request, paths, events=events)

    assert result.status == "ok", result.error
    assert result.attempts == 2
    assert result.appended is True
    body = delib.read_text(encoding="utf-8")
    assert "[PROPOSAL] @fake-cli" in body
    assert "## Tagging" in body

    types = [e["type"] for e in read_events(paths.events_jsonl)]
    # Sequence: agent_started → validation_failed → agent_started (retry)
    # → move_appended → agent_completed.
    assert types.count("agent_started") == 2
    assert types.count("validation_failed") == 1
    assert types.count("move_appended") == 1
    assert types.count("agent_completed") == 1
    assert types[-1] == "agent_completed"


def test_retry_exhausts_after_two_validation_failures(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed(paths)
    fake = _make_two_attempt_cli(
        tmp_path,
        first=BAD_PROPOSAL_MISSING_TAGGING,
        second=BAD_PROPOSAL_MISSING_TAGGING,
    )
    request = _build(paths, delib, fake)
    events = EventLogger(paths.events_jsonl)
    result = invoke(request, paths, events=events)

    assert result.status == "validation_failed"
    assert result.attempts == 2
    assert result.appended is False
    types = [e["type"] for e in read_events(paths.events_jsonl)]
    assert types.count("validation_failed") == 2
    # One terminal agent_failed event after the retries exhaust.
    assert types.count("agent_failed") == 1


def test_max_attempts_one_disables_retry(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed(paths)
    fake = _make_two_attempt_cli(
        tmp_path,
        first=BAD_PROPOSAL_MISSING_TAGGING,
        second=GOOD_PROPOSAL,
    )
    request = InvocationRequest(
        **{**_build(paths, delib, fake).__dict__, "max_attempts": 1},
    )
    events = EventLogger(paths.events_jsonl)
    result = invoke(request, paths, events=events)

    assert result.status == "validation_failed"
    assert result.attempts == 1
    types = [e["type"] for e in read_events(paths.events_jsonl)]
    assert types.count("agent_started") == 1
    assert types.count("validation_failed") == 1


def test_subprocess_failure_emits_agent_failed_no_retry(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed(paths)
    # Fake CLI that exits 2 (subprocess_failed). Retry should NOT fire.
    script = tmp_path / "fail_cli.py"
    script.write_text("import sys\nsys.stdin.read()\nsys.exit(2)\n", encoding="utf-8")
    script.chmod(0o755)
    handle = Participant(
        handle="@failing",
        display_name="Failing",
        cli_command=f"{sys.executable} {script}",
        model="x",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health="green",
    )
    meta = load_deliberation(delib)
    request = InvocationRequest(
        handle=handle,
        role="proposer",
        move_type="PROPOSAL",
        deliberation=meta,
        deliberation_path=delib,
        mode="interactive",
        timeout_s=10.0,
    )
    events = EventLogger(paths.events_jsonl)
    result = invoke(request, paths, events=events)
    assert result.status == "subprocess_failed"
    assert result.attempts == 1
    types = [e["type"] for e in read_events(paths.events_jsonl)]
    assert types.count("agent_started") == 1
    # Per-attempt failure event + terminal failure event = 2.
    assert types.count("agent_failed") == 2
