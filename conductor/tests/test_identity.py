"""Tests for the human-handle detection helper."""

from __future__ import annotations

from unittest.mock import patch

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
        assert handle.startswith("@human-")
        slug = handle[len("@human-") :]
        assert len(slug) <= 24
