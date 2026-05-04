"""Tests for `context.digester` — repo digestion + stale detection."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quorum_conductor.canvas.workspace import scaffold
from quorum_conductor.context.digester import (
    DigestError,
    DigestRequest,
    DigestResult,
    digest_repo,
    mark_stale_repos,
)
from quorum_conductor.context.manifest import load_manifest
from quorum_conductor.context.operations import add_doc, add_repo


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    scaffold(ws, now=datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC))
    return ws


def _git_init_with_commit(repo: Path) -> str:
    """Initialise a tiny git repo and return the commit's SHA. Skips
    the test if git isn't available — CI without git is a real case."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# t\n")
    try:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
            cwd=repo,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _commit(repo: Path, msg: str) -> str:
    (repo / "next.md").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", msg],
        cwd=repo,
        check=True,
    )
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


# ---------------------------------------------------------------------- #
# digest_repo — happy path
# ---------------------------------------------------------------------- #


def test_digest_repo_writes_digest_and_updates_entry(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    sha = _git_init_with_commit(repo)

    entry = add_repo(ws, repo)

    captured: list[DigestRequest] = []

    def fake_invoke(req: DigestRequest) -> DigestResult:
        captured.append(req)
        return DigestResult(body="A small Python project.\n\nMain entry: `main.py`.\n")

    result = digest_repo(
        ws,
        entry.id,
        invoke=fake_invoke,
        handle="@claude-opus",
        now=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
    )

    assert result.digest_status == "ready"
    assert result.digest_summary == "A small Python project."
    assert result.source_git_ref == sha
    assert result.stale is False

    digest_path = ws / "context" / "repos" / "v2-app" / "digest.md"
    assert digest_path.read_text(encoding="utf-8").startswith("A small Python project.")

    # Manifest persisted
    [persisted] = load_manifest(ws).entries
    assert persisted == result

    # Invoke saw the slug + source
    assert captured[0].slug == "v2-app"
    assert captured[0].source == repo.resolve()
    assert "v2-app" in captured[0].prompt


def test_digest_repo_marks_failure_when_invoke_errors(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    entry = add_repo(ws, repo)

    def fake_invoke(req: DigestRequest) -> DigestResult:
        return DigestResult(error="exit 1: not in a trusted directory")

    result = digest_repo(
        ws, entry.id, invoke=fake_invoke, handle="@claude-opus"
    )
    assert result.digest_status == "failed"
    assert "trusted directory" in result.digest_error
    # Failed digests don't write digest.md.
    assert not (ws / "context" / "repos" / "v2-app" / "digest.md").exists()


def test_digest_repo_treats_empty_body_as_failure(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    entry = add_repo(ws, repo)

    def fake_invoke(req: DigestRequest) -> DigestResult:
        return DigestResult(body="   \n\n")

    result = digest_repo(ws, entry.id, invoke=fake_invoke, handle="@claude-opus")
    assert result.digest_status == "failed"


def test_digest_repo_refuses_non_repo(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    src = tmp_path / "spec.md"
    src.write_text("body")
    e = add_doc(ws, src)
    with pytest.raises(DigestError):
        digest_repo(
            ws,
            e.id,
            invoke=lambda req: DigestResult(body="x"),
            handle="@claude-opus",
        )


def test_digest_repo_refuses_unknown_id(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    with pytest.raises(DigestError):
        digest_repo(
            ws,
            "ctx-9999",
            invoke=lambda req: DigestResult(body="x"),
            handle="@claude-opus",
        )


def test_digest_repo_refuses_empty_handle(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    e = add_repo(ws, repo)
    with pytest.raises(DigestError):
        digest_repo(ws, e.id, invoke=lambda req: DigestResult(body="x"), handle="   ")


def test_digest_repo_summary_skips_headings(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    e = add_repo(ws, repo)
    body = "# v2-app\n\n## Overview\n\nA distributed task runner.\n"
    res = digest_repo(
        ws,
        e.id,
        invoke=lambda req: DigestResult(body=body),
        handle="@claude-opus",
    )
    assert res.digest_summary == "A distributed task runner."


# ---------------------------------------------------------------------- #
# mark_stale_repos
# ---------------------------------------------------------------------- #


def test_mark_stale_repos_flips_when_head_changes(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    sha = _git_init_with_commit(repo)
    e = add_repo(ws, repo)
    digest_repo(
        ws,
        e.id,
        invoke=lambda req: DigestResult(body="summary"),
        handle="@claude-opus",
    )

    # Initially in sync
    [first] = load_manifest(ws).entries
    assert first.source_git_ref == sha
    assert first.stale is False
    after = mark_stale_repos(ws)
    assert after.entries[0].stale is False

    # Bump the source HEAD; should flip stale=True
    _commit(repo, "another commit")
    after = mark_stale_repos(ws)
    assert after.entries[0].stale is True


def test_mark_stale_repos_leaves_non_git_alone(tmp_path: Path) -> None:
    """Repos without source_git_ref (digest never ran or git absent)
    must not be marked stale just because we can't read HEAD."""
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    repo.mkdir()
    add_repo(ws, repo)
    after = mark_stale_repos(ws)
    assert after.entries[0].stale is False


def test_mark_stale_repos_clears_flag_when_back_in_sync(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    repo = tmp_path / "v2-app"
    sha = _git_init_with_commit(repo)
    e = add_repo(ws, repo)
    digest_repo(
        ws,
        e.id,
        invoke=lambda req: DigestResult(body="summary"),
        handle="@claude-opus",
    )
    new_sha = _commit(repo, "drift")
    mark_stale_repos(ws)
    [first] = load_manifest(ws).entries
    assert first.stale is True

    # Pretend a re-digest landed at the new SHA — the entry's
    # source_git_ref is the only thing mark_stale_repos consults.
    from dataclasses import replace as dc_replace

    from quorum_conductor.context.manifest import save_manifest

    m = load_manifest(ws)
    m = dc_replace(
        m, entries=[dc_replace(first, source_git_ref=new_sha, stale=True)]
    )
    save_manifest(ws, m)

    after = mark_stale_repos(ws)
    assert after.entries[0].stale is False
