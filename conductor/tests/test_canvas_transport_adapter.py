"""Tests for `canvas.transport_adapter.make_invoker`.

We avoid spawning real model CLIs by configuring the participant's
``cli_command`` to a tiny `python -c "..."` one-liner. This works
on every dev machine without binary fixtures.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from quorum_conductor.canvas.dispatcher import InvocationRequest
from quorum_conductor.canvas.transport_adapter import make_invoker
from quorum_conductor.canvas.workspace import scaffold


def _python_command(snippet: str) -> str:
    """Wrap a Python snippet as a CLI command string."""
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(snippet)}"


def _add_participant(workspace: Path, handle: str, cli_command: str) -> None:
    """Append a participant row to `registers/participants.md`.

    Uses the same nine-column shape the `core.participants` parser
    expects: Handle | Display Name | CLI Command | Model | Transport |
    Quota | Permission Capability | Account Label | Health.
    """
    p = workspace / "registers" / "participants.md"
    row = (
        f"| {handle} | {handle.lstrip('@').title()} | {cli_command} "
        "| model | cli | unlimited | n/a | (none) | green |\n"
    )
    p.write_text(p.read_text(encoding="utf-8") + row, encoding="utf-8")


def _request(workspace: Path, handle: str = "@claude-test") -> InvocationRequest:
    return InvocationRequest(
        handle=handle, workspace=workspace, user_message_id="msg-0001"
    )


def test_unknown_handle_returns_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    invoke = make_invoker()
    out = invoke(_request(ws, "@nobody"))
    assert out.reply == ""
    assert out.error is not None
    assert "@nobody" in out.error


def test_empty_cli_command_returns_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(ws, "@blank", "")
    invoke = make_invoker()
    out = invoke(_request(ws, "@blank"))
    assert out.error is not None
    assert "no cli_command" in out.error


def test_successful_invocation_returns_stdout(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(
        ws, "@claude-test", _python_command("print('hello from the test agent')")
    )
    invoke = make_invoker()
    out = invoke(_request(ws))
    assert out.error is None
    assert "hello from the test agent" in out.reply


def test_non_zero_exit_surfaces_as_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(
        ws,
        "@claude-test",
        _python_command(
            "import sys; sys.stderr.write('boom\\n'); sys.exit(2)"
        ),
    )
    invoke = make_invoker()
    out = invoke(_request(ws))
    assert out.reply == ""
    assert out.error is not None
    assert "exit 2" in out.error
    assert "boom" in out.error


def test_missing_binary_returns_friendly_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(ws, "@ghost", "/no/such/binary --do-things")
    invoke = make_invoker()
    out = invoke(_request(ws, "@ghost"))
    assert out.error is not None
    assert "not found" in out.error.lower()


def test_timeout_returns_timeout_error(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(
        ws,
        "@slowpoke",
        _python_command("import time; time.sleep(60)"),
    )
    invoke = make_invoker(timeout_s=0.2)
    out = invoke(_request(ws, "@slowpoke"))
    assert out.error is not None
    assert "timed out" in out.error.lower()


def test_invoker_runs_in_workspace_cwd(tmp_path: Path) -> None:
    """Per S2, the agent process must see the workspace as cwd so it can read canvas.md."""
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(
        ws,
        "@cwd-test",
        _python_command("import os; print(os.getcwd())"),
    )
    invoke = make_invoker()
    out = invoke(_request(ws, "@cwd-test"))
    assert out.error is None
    # On macOS tmp_path can be reported as /private/var/... — accept either.
    reported = out.reply.strip()
    assert str(ws) in reported or str(ws.resolve()) in reported


def test_system_prompt_is_piped_to_stdin(tmp_path: Path) -> None:
    """The agent should receive the rendered system prompt via stdin
    so it knows the cwd conventions and the artifact-emit format."""
    ws = tmp_path / "ws"
    scaffold(ws)
    _add_participant(
        ws,
        "@echo-test",
        _python_command("import sys; sys.stdout.write(sys.stdin.read())"),
    )
    invoke = make_invoker()
    out = invoke(_request(ws, "@echo-test"))
    assert out.error is None
    # The default prompt mentions canvas.md and artifact:filename.md.
    assert "canvas.md" in out.reply
    assert "artifact:" in out.reply
    assert "@echo-test" in out.reply
