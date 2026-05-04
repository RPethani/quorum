"""Tests for the combined .gitignore + .contextignore matcher."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.context.gitignore import (
    CONTEXTIGNORE_FILENAME,
    DEFAULT_PATTERNS,
    IgnoreMatcher,
)


def _matcher(repo: Path, workspace: Path | None = None) -> IgnoreMatcher:
    return IgnoreMatcher.for_repo(repo, workspace)


def test_default_patterns_skip_node_modules(tmp_path: Path) -> None:
    m = _matcher(tmp_path)
    assert m.should_skip("node_modules/foo.js")
    assert m.should_skip("nested/node_modules/foo.js")


def test_default_patterns_skip_dotgit(tmp_path: Path) -> None:
    m = _matcher(tmp_path)
    assert m.should_skip(".git/HEAD")
    assert m.should_skip(".git/refs/heads/main")


def test_default_patterns_skip_python_caches(tmp_path: Path) -> None:
    m = _matcher(tmp_path)
    assert m.should_skip("src/foo/__pycache__/bar.cpython-312.pyc")
    assert m.should_skip("foo.pyc")
    assert m.should_skip(".pytest_cache/v/cache/lastfailed")
    assert m.should_skip(".mypy_cache/3.12/foo.json")


def test_real_files_are_not_skipped(tmp_path: Path) -> None:
    m = _matcher(tmp_path)
    assert not m.should_skip("src/index.ts")
    assert not m.should_skip("README.md")
    assert not m.should_skip("docs/architecture.md")


def test_repo_gitignore_extends_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("*.log\nsecrets/\n", encoding="utf-8")
    m = _matcher(repo)
    assert m.should_skip("server.log")
    assert m.should_skip("secrets/aws.key")
    # Defaults still apply
    assert m.should_skip("node_modules/foo.js")


def test_workspace_contextignore_override(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    (workspace / "context").mkdir(parents=True)
    (workspace / "context" / CONTEXTIGNORE_FILENAME).write_text(
        "*.tmp\nfixtures/\n", encoding="utf-8"
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    m = _matcher(repo, workspace)
    assert m.should_skip("scratch.tmp")
    assert m.should_skip("fixtures/big.bin")
    # Repo gitignore patterns absent — only workspace override + defaults.
    assert not m.should_skip("src/index.ts")


def test_negation_in_repo_gitignore(tmp_path: Path) -> None:
    """`!pattern` un-ignores a previously ignored path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("*.log\n!keep.log\n", encoding="utf-8")
    m = _matcher(repo)
    assert m.should_skip("random.log")
    assert not m.should_skip("keep.log")


def test_default_pattern_set_includes_expected_categories() -> None:
    """Sanity check that the public default list covers VCS, JS, Python."""
    assert ".git/" in DEFAULT_PATTERNS
    assert "node_modules/" in DEFAULT_PATTERNS
    assert "__pycache__/" in DEFAULT_PATTERNS
    assert ".venv/" in DEFAULT_PATTERNS
