"""Phase-6b/d tests: `quorum context add-{repo,note,doc} list` end-to-end."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import yaml

from quorum_conductor.cli import main


def _write_fake_digester(path: Path, body: str) -> Path:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.stdout.write({body!r})
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _participants_with_fake_digester(workspace: Path, fake: Path) -> None:
    (workspace / "registers" / "participants.md").write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        f"| @claude-sonnet | Sonnet | {sys.executable} {fake} | x | cli | 30/5 | "
        "fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )


def test_add_repo_runs_digest_and_writes_files(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    assert main(["init", str(workspace)]) == 0
    capsys.readouterr()
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "README.md").write_text("hi\n", encoding="utf-8")

    fake = _write_fake_digester(
        tmp_path / "fake.py",
        "## Architecture overview\n\nA repo.\n\n## File tree (annotated)\n\nnone\n",
    )
    _participants_with_fake_digester(workspace, fake)

    rc = main([
        "context",
        "add-repo",
        str(repo),
        "--name", "myrepo",
        "--role", "the test repo",
        "--relevance", "medium",
        "--path", str(workspace),
    ])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "registered repo 'myrepo'" in out
    assert "digesting via @claude-sonnet" in out
    assert "status   : ok" in out

    digest = workspace / "context" / "repos" / "myrepo" / "digest.md"
    assert digest.is_file()
    assert "Architecture overview" in digest.read_text(encoding="utf-8")

    meta = yaml.safe_load(
        (workspace / "context" / "repos" / "myrepo" / "meta.yaml").read_text()
    )
    assert meta["name"] == "myrepo"
    assert meta["digester"] == "@claude-sonnet"

    cm = yaml.safe_load((workspace / "context" / "context-manifest.yaml").read_text())
    assert any(r["name"] == "myrepo" for r in cm["repos"])


def test_add_repo_no_digest_skips_invocation(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    assert main(["init", str(workspace)]) == 0
    capsys.readouterr()
    repo = tmp_path / "repo2"
    repo.mkdir()

    rc = main([
        "context", "add-repo", str(repo),
        "--name", "repo2", "--no-digest",
        "--path", str(workspace),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "digestion skipped" in out
    assert not (workspace / "context" / "repos" / "repo2" / "digest.md").exists()


def test_add_note_with_text(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    assert main(["init", str(workspace)]) == 0
    capsys.readouterr()
    rc = main([
        "context", "add-note", "convention",
        "--text", "We never propose modal dialogs.",
        "--path", str(workspace),
    ])
    assert rc == 0, capsys.readouterr().out
    note = workspace / "context" / "notes" / "convention.md"
    assert note.is_file()
    assert "modal dialogs" in note.read_text()


def test_add_doc_copies_into_workspace(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    assert main(["init", str(workspace)]) == 0
    capsys.readouterr()
    src = tmp_path / "spec.md"
    src.write_text("# Spec\n\nbody.\n", encoding="utf-8")

    rc = main([
        "context", "add-doc", str(src), "--name", "spec",
        "--path", str(workspace),
    ])
    assert rc == 0, capsys.readouterr().out
    target = workspace / "context" / "docs" / "raw" / "spec.md"
    assert target.is_file()
    assert "body." in target.read_text()


def test_context_list_shows_added_sources(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    main(["init", str(workspace)])
    main([
        "context", "add-note", "n1",
        "--text", "x", "--path", str(workspace),
    ])
    capsys.readouterr()
    rc = main(["context", "list", "--path", str(workspace)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "notes (1)" in out
    assert "n1" in out
