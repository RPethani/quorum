"""Phase-6b tests: repo digestion + relevance-tiered handle resolution."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import yaml

from quorum_conductor.core.config import WorkspaceConfig
from quorum_conductor.core.digestion import (
    RepoSpec,
    digest_repo,
    resolve_digester,
)
from quorum_conductor.core.participants import Participant


def _participant(handle: str, *, command: str = "true", health: str = "green") -> Participant:
    return Participant(
        handle=handle,
        display_name=handle,
        cli_command=command,
        model="x",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health=health,
    )


def _fake_cli(tmp_path: Path, output: str, exit_code: int = 0) -> Path:
    script = tmp_path / "fake_digester.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.stdout.write({output!r})
            sys.exit({exit_code})
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


# ---------------------------------------------------------------------- #
# resolve_digester
# ---------------------------------------------------------------------- #


def test_resolve_digester_uses_canonical_default() -> None:
    participants = [_participant("@claude-opus"), _participant("@claude-sonnet")]
    config = WorkspaceConfig()
    chosen = resolve_digester("high", config, participants)
    assert chosen is not None
    assert chosen.handle == "@claude-opus"


def test_resolve_digester_uses_config_override() -> None:
    participants = [_participant("@claude-sonnet"), _participant("@codex-gpt5")]
    config = WorkspaceConfig(
        extras={"context": {"digester_defaults": {"high": "@codex-gpt5"}}}
    )
    chosen = resolve_digester("high", config, participants)
    assert chosen is not None
    assert chosen.handle == "@codex-gpt5"


def test_resolve_digester_falls_back_to_first_cli_handle() -> None:
    # No canonical defaults registered; falls back to the only cli handle.
    participants = [_participant("@only")]
    chosen = resolve_digester("high", WorkspaceConfig(), participants)
    assert chosen is not None
    assert chosen.handle == "@only"


def test_resolve_digester_skips_unhealthy() -> None:
    participants = [_participant("@claude-opus", health="red"), _participant("@claude-sonnet")]
    chosen = resolve_digester("high", WorkspaceConfig(), participants)
    assert chosen is not None
    # Opus is red so we fall back to Sonnet (canonical for medium) or
    # the first available cli handle. Either way Opus must NOT be
    # selected.
    assert chosen.handle != "@claude-opus"


def test_resolve_digester_returns_none_when_empty() -> None:
    chosen = resolve_digester("high", WorkspaceConfig(), [])
    assert chosen is None


# ---------------------------------------------------------------------- #
# digest_repo
# ---------------------------------------------------------------------- #


def test_digest_repo_writes_digest_and_meta(tmp_path: Path) -> None:
    repo_path = tmp_path / "fakerepo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("hello\n", encoding="utf-8")

    fake = _fake_cli(
        tmp_path,
        textwrap.dedent(
            """\
            ## Architecture overview

            One small repo with a README.

            ## File tree (annotated)

            - README.md — top-level readme

            ## Key entry points

            - README.md

            ## Important interfaces

            none

            ## Conventions and idioms

            - Markdown only.

            ## Places to be careful

            - none

            ## What this digest does NOT cover

            nothing material
            """
        ),
    )
    digester = _participant(
        "@digester", command=f"{sys.executable} {fake}"
    )
    target_dir = tmp_path / "out" / "fakerepo"
    spec = RepoSpec(name="fakerepo", path=repo_path, role="test", relevance="medium")

    result = digest_repo(spec, digester, target_dir, timeout_s=10.0)

    assert result.status == "ok", result.error
    assert (target_dir / "digest.md").is_file()
    assert "Architecture overview" in (target_dir / "digest.md").read_text()
    meta = yaml.safe_load((target_dir / "meta.yaml").read_text())
    assert meta["name"] == "fakerepo"
    assert meta["digester"] == "@digester"
    assert meta["relevance"] == "medium"
    assert meta["digest_chars"] > 0


def test_digest_repo_handles_nonzero_exit(tmp_path: Path) -> None:
    repo_path = tmp_path / "fakerepo"
    repo_path.mkdir()
    fake = _fake_cli(tmp_path, "irrelevant", exit_code=2)
    digester = _participant("@digester", command=f"{sys.executable} {fake}")
    target_dir = tmp_path / "out"
    spec = RepoSpec(name="fakerepo", path=repo_path, role="t", relevance="low")
    result = digest_repo(spec, digester, target_dir, timeout_s=10.0)
    assert result.status == "subprocess_failed"
    assert result.return_code == 2
    assert not (target_dir / "digest.md").exists()


def test_digest_repo_handles_missing_binary(tmp_path: Path) -> None:
    repo_path = tmp_path / "fakerepo"
    repo_path.mkdir()
    digester = _participant("@absent", command="quorum-test-bogus-binary")
    target_dir = tmp_path / "out"
    spec = RepoSpec(name="fakerepo", path=repo_path, role="t", relevance="low")
    result = digest_repo(spec, digester, target_dir, timeout_s=5.0)
    assert result.status == "subprocess_failed"
    assert result.error is not None
    assert "not on PATH" in result.error or "No such file" in result.error
