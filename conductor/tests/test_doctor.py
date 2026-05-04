"""Tests for the doctor's participants.md parser and PATH check."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.canvas.workspace import scaffold
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.transport.doctor import doctor_check


def _set_participants(paths_root: Path, body: str) -> None:
    (paths_root / "registers" / "participants.md").write_text(body, encoding="utf-8")


def test_doctor_returns_empty_when_no_handles(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    paths = WorkspacePaths(root=target)
    # Fresh canvas workspace has no participants — doctor returns empty.
    assert doctor_check(paths) == []


def test_doctor_marks_missing_cli_as_failed(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    paths = WorkspacePaths(root=target)
    _set_participants(
        paths.root,
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @bogus-cli | Bogus | quorum-test-nonexistent-binary --x | bogus | cli | 1/1 | none | (none) | unknown |
""",
    )
    records = doctor_check(paths)
    bogus = [r for r in records if r.handle == "@bogus-cli"]
    assert bogus and bogus[0].on_path is False
    assert "not on PATH" in bogus[0].note


def test_doctor_recognises_a_real_binary(tmp_path: Path) -> None:
    target = tmp_path / "ws"
    scaffold(target)
    paths = WorkspacePaths(root=target)
    _set_participants(
        paths.root,
        """\
# Participants

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @python | Python | python3 | n/a | cli | 1/1 | none | (none) | green |
""",
    )
    records = doctor_check(paths)
    py = [r for r in records if r.handle == "@python"]
    assert py and py[0].on_path is True
