"""Tests for the human-handle detection helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from quorum_conductor.workspace import InitOptions, init_workspace
from quorum_conductor.workspace.identity import default_human_handle


def test_quorum_human_handle_env_wins() -> None:
    with patch.dict("os.environ", {"QUORUM_HUMAN_HANDLE": "@human-explicit"}, clear=False):
        assert default_human_handle() == "@human-explicit"


def test_quorum_human_handle_env_adds_at_prefix() -> None:
    with patch.dict("os.environ", {"QUORUM_HUMAN_HANDLE": "human-noprefix"}, clear=False):
        assert default_human_handle() == "@human-noprefix"


def test_user_env_var_slugified() -> None:
    with patch.dict(
        "os.environ",
        {"QUORUM_HUMAN_HANDLE": "", "USER": "Jane Doe"},
        clear=False,
    ):
        assert default_human_handle() == "@human-jane-doe"


def test_user_env_var_truncated_at_24_chars() -> None:
    with patch.dict(
        "os.environ",
        {
            "QUORUM_HUMAN_HANDLE": "",
            "USER": "this-is-a-very-long-username-that-should-truncate",
        },
        clear=False,
    ):
        handle = default_human_handle()
        # @human- + slug; slug capped at 24 chars
        assert handle.startswith("@human-")
        slug = handle[len("@human-") :]
        assert len(slug) <= 24


def test_init_uses_detected_handle_when_unset(tmp_path: Path) -> None:
    with patch.dict(
        "os.environ",
        {"QUORUM_HUMAN_HANDLE": "@human-fixture"},
        clear=False,
    ):
        paths = init_workspace(InitOptions(target=tmp_path / "ws"))
    body = paths.participants.read_text(encoding="utf-8")
    assert "@human-fixture" in body
    assert (paths.inbox / "@human-fixture.md").is_file()


def test_init_explicit_human_handle_overrides_detection(tmp_path: Path) -> None:
    paths = init_workspace(
        InitOptions(target=tmp_path / "ws", human_handle="@human-explicit"),
    )
    body = paths.participants.read_text(encoding="utf-8")
    assert "@human-explicit" in body
    assert (paths.inbox / "@human-explicit.md").is_file()


def test_bootstrapper_pins_human_decider(tmp_path: Path) -> None:
    from quorum_conductor.workspace import bootstrap_seed_deliberation

    paths = init_workspace(
        InitOptions(target=tmp_path / "ws", human_handle="@human-jane"),
    )
    seed = bootstrap_seed_deliberation(paths)
    body = seed.read_text(encoding="utf-8")
    assert 'decider: "@human-jane"' in body
