"""End-to-end invoker tests using a fake CLI.

The fake CLI is a tiny Python script written into the test's tmp_path
that reads its prompt from stdin and prints a canned move to stdout.
The real Claude/Gemini/Codex CLIs are not available in test environments;
this fake exercises the same subprocess + capture + append + lock path.
"""

from __future__ import annotations

import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from quorum_conductor.core.deliberation import (
    load_deliberation,
)
from quorum_conductor.core.participants import Participant
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.transport.invoker import InvocationRequest, invoke
from quorum_conductor.workspace import InitOptions, init_workspace


def _make_fake_cli(tmp_path: Path, output: str, exit_code: int = 0) -> Path:
    """Write a fake CLI that prints `output` to stdout and exits `exit_code`."""
    script = tmp_path / "fake_cli.py"
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys
        sys.stdin.read()  # consume the prompt; ignore it
        sys.stdout.write({output!r})
        sys.exit({exit_code})
        """
    )
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def _seed_deliberation(paths: WorkspacePaths, *, deliberation_id: str = "0001") -> Path:
    path = paths.deliberations / f"{deliberation_id}-pricing.md"
    path.write_text(
        "---\n"
        f'id: "{deliberation_id}"\n'
        "title: Pricing tier structure\n"
        "status: OPEN\n"
        "protocol_version: 0.1\n"
        "roles:\n"
        '  proposer: "@claude-opus"\n'
        "  critics: []\n"
        "  synthesizer: null\n"
        '  decider: "@human-rohan"\n'
        "tags: []\n"
        "---\n\n"
        "## Question\n\nFree tier vs trial-only?\n\n"
        "## Contributions\n\n"
        "## Open Questions\n\n"
        "## Decision\n",
        encoding="utf-8",
    )
    return path


def _build_request(
    paths: WorkspacePaths, deliberation_path: Path, fake_cli: Path
) -> InvocationRequest:
    handle = Participant(
        handle="@fake-cli",
        display_name="Fake CLI",
        cli_command=f"{sys.executable} {fake_cli}",
        model="fake",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health="green",
    )
    meta = load_deliberation(deliberation_path)
    return InvocationRequest(
        handle=handle,
        role="proposer",
        move_type="PROPOSAL",
        deliberation=meta,
        deliberation_path=deliberation_path,
        mode="interactive",
        timeout_s=10.0,
    )


def test_invoke_appends_a_valid_move(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed_deliberation(paths)
    move_text = textwrap.dedent(
        """\
        ### [PROPOSAL] @fake-cli · 2026-04-28T14:32:18Z

        ## Position

        Ship trial-only in v1.

        ## Reasoning

        Reversibility wins.

        ## Assumptions

        none

        ## Risks I see

        none

        ## Alternatives I considered

        - Permanent free tier — set aside for reversibility reasons.

        ## Tagging

        - @gemini-pro: critique — your adversarial framing usually finds the structural risks.
        """
    )
    fake = _make_fake_cli(tmp_path, move_text)
    request = _build_request(paths, delib, fake)
    result = invoke(request, paths)

    assert result.status == "ok", result.error
    assert result.appended is True
    assert result.move_type == "PROPOSAL"
    assert result.handle == "@fake-cli"
    assert "@gemini-pro" in result.inboxes_notified
    body = delib.read_text(encoding="utf-8")
    assert "[PROPOSAL] @fake-cli" in body
    # Lifecycle marker and stream cleaned up on success.
    assert not list(paths.runtime_active.iterdir())
    assert not list(paths.runtime_streams.glob("*.stream"))
    # Inbox notification.
    inbox_body = (paths.inbox / "@gemini-pro.md").read_text(encoding="utf-8")
    assert "PROPOSAL in #0001" in inbox_body


def test_invoke_validation_failure_preserves_stream(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed_deliberation(paths)
    fake = _make_fake_cli(tmp_path, "no canonical header here, just prose\n")
    request = _build_request(paths, delib, fake)
    result = invoke(request, paths)

    assert result.status == "validation_failed"
    assert result.appended is False
    # Stream preserved under runtime/streams/failed/ for diagnosis.
    failed = list(paths.runtime_streams_failed.iterdir())
    assert failed, "expected the failed stream to be preserved"
    assert any("validation_failed" in p.name for p in failed)
    # Lifecycle marker remains so `quorum status` can show the failed invocation.
    assert list(paths.runtime_active.iterdir()), "expected the active marker to remain on failure"


def test_invoke_subprocess_nonzero_exit_is_failure(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed_deliberation(paths)
    fake = _make_fake_cli(tmp_path, "irrelevant", exit_code=2)
    request = _build_request(paths, delib, fake)
    result = invoke(request, paths)

    assert result.status == "subprocess_failed"
    assert result.return_code == 2
    assert result.appended is False


def test_invoke_command_not_on_path_returns_clean_failure(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed_deliberation(paths)
    handle = Participant(
        handle="@absent",
        display_name="Absent",
        cli_command="quorum-test-binary-that-does-not-exist",
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
        timeout_s=5.0,
    )
    result = invoke(request, paths)
    assert result.status == "subprocess_failed"
    assert result.error is not None
    assert "not on PATH" in result.error or "No such file" in result.error


@pytest.mark.skipif(shutil.which("python3") is None, reason="needs python3 on PATH")
def test_invoke_timeout(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    delib = _seed_deliberation(paths)
    sleeper = tmp_path / "sleeper.py"
    sleeper.write_text("import time, sys\nsys.stdin.read()\ntime.sleep(5)\n", encoding="utf-8")
    handle = Participant(
        handle="@sleeper",
        display_name="Sleeper",
        cli_command=f"{sys.executable} {sleeper}",
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
        timeout_s=0.5,
    )
    result = invoke(request, paths)
    assert result.status == "timeout"


def test_normalize_agent_response_strips_preamble_and_rewrites_header() -> None:
    """Sloppy agents emit preamble + a wrong author + a hallucinated
    timestamp. The normalizer must drop the preamble and rewrite the
    header with the conductor's known author + a real timestamp,
    leaving the body intact."""
    from quorum_conductor.transport.invoker import _normalize_agent_response

    sloppy = (
        "I will read the protocol and produce a critique.\n\n"
        "I will then think about it carefully.\n\n"
        "### [CRITIQUE] @runtime/active/gemini--0003--CRITIQUE.start · 2099-01-01T00:00:00Z\n\n"
        "## Strong objections\n\nThe matrix arithmetic is wrong.\n"
    )
    out = _normalize_agent_response(
        sloppy, expected_author="@gemini", expected_move_type="CRITIQUE"
    )
    assert out.startswith("### [CRITIQUE] @gemini · ")
    assert "I will read" not in out
    assert "## Strong objections" in out
    assert "matrix arithmetic" in out
    # Hallucinated timestamp should be replaced with something current.
    assert "2099-01-01" not in out


def test_normalize_passes_through_when_no_header() -> None:
    """If there's no canonical header at all, return the text unchanged
    so the validator can produce the canonical 'missing header' error."""
    from quorum_conductor.transport.invoker import _normalize_agent_response

    raw = "This is just prose with no protocol header anywhere."
    out = _normalize_agent_response(
        raw, expected_author="@x", expected_move_type="PROPOSAL"
    )
    assert out == raw
