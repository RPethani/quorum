"""Tests for `canvas.remediation`."""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.canvas.remediation import RemediationError, apply, detect
from quorum_conductor.canvas.workspace import scaffold


def _fixture_participants(workspace: Path, body: str) -> None:
    (workspace / "registers" / "participants.md").write_text(body, encoding="utf-8")


GEMINI_STDERR = (
    "Gemini CLI is not running in a trusted directory. "
    "To proceed, either use `--skip-trust`, set the "
    "`GEMINI_CLI_TRUST_WORKSPACE=true` environment variable, "
    "or trust this directory in interactive mode."
)


def test_detect_gemini_trust_returns_remediation():
    rem = detect("@gemini", GEMINI_STDERR)
    assert rem is not None
    assert rem.id == "gemini-trust"
    assert rem.handle == "@gemini"
    assert "Trust this workspace" in rem.title


def test_detect_returns_none_when_handle_not_gemini():
    assert detect("@claude-opus", GEMINI_STDERR) is None


def test_detect_returns_none_when_unrelated_error():
    assert detect("@gemini", "some other error message") is None


def test_apply_gemini_trust_appends_flag(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _fixture_participants(
        ws,
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @gemini | Gemini | gemini --print | gemini-2.5 | cli | unlimited | ask | (none) | green |
""",
    )
    msg = apply("gemini-trust", ws, "@gemini")
    assert "--skip-trust" in msg
    body = (ws / "registers" / "participants.md").read_text(encoding="utf-8")
    assert "gemini --print --skip-trust" in body


def test_apply_gemini_trust_idempotent(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _fixture_participants(
        ws,
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @gemini | Gemini | gemini --skip-trust --print | gemini-2.5 | cli | unlimited | ask | (none) | green |
""",
    )
    # Already present — apply should refuse, not double-add.
    with pytest.raises(RemediationError):
        apply("gemini-trust", ws, "@gemini")


def test_apply_gemini_trust_handle_without_at_prefix(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    _fixture_participants(
        ws,
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @gemini | Gemini | gemini --print | gemini-2.5 | cli | unlimited | ask | (none) | green |
""",
    )
    apply("gemini-trust", ws, "gemini")  # missing leading @
    body = (ws / "registers" / "participants.md").read_text(encoding="utf-8")
    assert "--skip-trust" in body


def test_apply_unknown_remediation_raises(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    with pytest.raises(RemediationError):
        apply("does-not-exist", ws, "@gemini")


# ---------------------------------------------------------------------- #
# Codex missing-binary rule
# ---------------------------------------------------------------------- #


CODEX_STDERR = (
    "file:///usr/local/lib/node_modules/@openai/codex/bin/codex.js:100\n"
    "    throw new Error(\n          ^\n\n"
    "Error: Missing optional dependency @openai/codex-darwin-x64. "
    "Reinstall Codex: npm install -g @openai/codex\n"
)


def test_detect_codex_missing_binary():
    rem = detect("@codex", CODEX_STDERR)
    assert rem is not None
    assert rem.id == "codex-missing-binary"
    assert rem.handle == "@codex"


def test_detect_codex_missing_binary_handle_variants():
    # `codex` substring matching covers e.g. `@codex-gpt5`.
    rem = detect("@codex-gpt5", CODEX_STDERR)
    assert rem is not None
    assert rem.id == "codex-missing-binary"


def test_detect_codex_missing_binary_skips_other_handles():
    assert detect("@claude-opus", CODEX_STDERR) is None


def test_detect_codex_unrelated_error_no_match():
    assert detect("@codex", "some other failure mode") is None


def test_detect_codex_trust():
    err = (
        "Reading prompt from stdin...\n"
        "Not inside a trusted directory and --skip-git-repo-check was not specified."
    )
    rem = detect("@codex", err)
    assert rem is not None
    assert rem.id == "codex-trust"


def test_apply_codex_trust_appends_flag(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    scaffold(ws)
    (ws / "registers" / "participants.md").write_text(
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @codex | OpenAI Codex | codex exec | gpt-5 | cli | unlimited | ask | (none) | unknown |
""",
        encoding="utf-8",
    )
    apply("codex-trust", ws, "@codex")
    body = (ws / "registers" / "participants.md").read_text(encoding="utf-8")
    assert "codex exec --skip-git-repo-check" in body


def test_codex_apply_eacces_error_explains_sudo(monkeypatch, tmp_path: Path) -> None:
    """When `npm install -g` fails with EACCES, the apply step should
    surface the manual `sudo` instruction rather than the raw error."""
    import subprocess

    from quorum_conductor.canvas import remediation as rmod

    class _Result:
        def __init__(self) -> None:
            self.returncode = 1
            self.stderr = (
                "npm error code EACCES\n"
                "npm error syscall rename\n"
                "npm error path /usr/local/lib/node_modules/@openai/codex\n"
            )
            self.stdout = ""

    def _fake_run(*_a: object, **_kw: object) -> _Result:
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    ws = tmp_path / "ws"
    scaffold(ws)
    with pytest.raises(rmod.RemediationError) as excinfo:
        rmod.apply("codex-missing-binary", ws, "@codex")
    msg = str(excinfo.value)
    assert "sudo npm install -g @openai/codex" in msg
    assert "user-writable prefix" in msg


