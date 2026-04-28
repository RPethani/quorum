"""Tests for the doctor's participants.md parser and PATH check."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.transport.doctor import doctor_check
from quorum_conductor.workspace import InitOptions, init_workspace


def _set_participants(paths_root: Path, body: str) -> None:
    (paths_root / "registers" / "participants.md").write_text(body, encoding="utf-8")


def test_doctor_returns_empty_when_no_handles(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    # Default participants.md only registers the human handle; the doctor
    # should report it but with on_path=None (manual transport).
    records = doctor_check(paths)
    assert any(r.handle == "@human-rohan" and r.on_path is None for r in records)


def test_doctor_marks_missing_cli_as_failed(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    _set_participants(
        paths.root,
        """\
---
schema_version: 0.1
---

# Participants Registry

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
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    # `python3` is virtually guaranteed to be on PATH in any environment
    # where these tests run, including CI.
    _set_participants(
        paths.root,
        """\
---
schema_version: 0.1
---

# Participants Registry

| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @python | Python | python3 | n/a | cli | 1/1 | none | (none) | green |
""",
    )
    records = doctor_check(paths)
    py = [r for r in records if r.handle == "@python"]
    assert py and py[0].on_path is True
