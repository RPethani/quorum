"""Prompt-rendering tests against the bundled standing prompt."""

from __future__ import annotations

from pathlib import Path

from quorum_conductor.core.deliberation import DeliberationMeta, DeliberationRoles
from quorum_conductor.core.participants import Participant
from quorum_conductor.core.prompts import PromptInputs, render_prompt
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.workspace import InitOptions, init_workspace


def _make_inputs(
    *, mode: str = "interactive", role: str = "proposer", deputy_active: bool = False
) -> tuple[PromptInputs, Path]:
    # An init'd workspace gives us the standing prompt copied in.
    paths = init_workspace(InitOptions(target=Path("/tmp/__not_used__/quorum")))
    # Re-init to a tmp dir each call would be cleaner; we use the test
    # caller's tmp_path via the wrapping fixture in actual tests.
    return _build_inputs(paths, mode=mode, role=role, deputy_active=deputy_active), paths.root


def _build_inputs(
    paths: WorkspacePaths, *, mode: str, role: str, deputy_active: bool
) -> PromptInputs:
    handle = Participant(
        handle="@claude-opus",
        display_name="Claude (Opus)",
        cli_command="claude --print --model opus",
        model="claude-opus-4-7",
        transport="cli",
        quota_daily=30,
        quota_per_deliberation=5,
        permission_capability="fine_grained",
        account_label="",
        health="green",
    )
    delib = DeliberationMeta(
        id="0001",
        title="Pricing tier structure",
        status="OPEN",
        roles=DeliberationRoles(),
        tags=[],
    )
    return PromptInputs(
        handle=handle,
        role=role,
        deliberation=delib,
        mode=mode,
        standing_prompt_path=paths.agent_standing_prompt,
        overrides_dir=paths.prompts_overrides,
        workspace_root=paths.root,
        deputy_active=deputy_active,
        move_type="PROPOSAL",
    )


def _init_workspace(tmp_path: Path) -> WorkspacePaths:
    return init_workspace(InitOptions(target=tmp_path / "quorum"))


def test_render_prompt_includes_base_and_always_augmentations(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="interactive", role="proposer", deputy_active=False)
    out = render_prompt(inputs)
    assert "## BASE" in out
    assert "context-discipline" in out.lower()
    assert "permission-discipline" in out.lower()
    assert "## TASK" in out
    # Role-specific augmentations should NOT be applied for `proposer`.
    assert "AUGMENTATION — explainer" not in out
    assert "AUGMENTATION — bootstrapper" not in out


def test_render_prompt_applies_explainer_augmentation(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="interactive", role="explainer", deputy_active=False)
    out = render_prompt(inputs)
    assert "explainer" in out.lower()
    assert "anti-confabulation" in out.lower() or "grounding requirements" in out.lower()


def test_render_prompt_applies_bootstrapper_augmentation(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="interactive", role="bootstrapper", deputy_active=False)
    out = render_prompt(inputs)
    assert "outcome manifest" in out.lower()


def test_render_prompt_applies_autonomous_mode(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="autonomous", role="proposer", deputy_active=False)
    out = render_prompt(inputs)
    assert "autonomous" in out.lower()
    assert "do not ask a human" in out.lower()


def test_render_prompt_applies_deputy_when_active(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="interactive", role="decider", deputy_active=True)
    out = render_prompt(inputs)
    assert "provisional" in out.lower()
    assert "deputy" in out.lower()


def test_render_prompt_applies_per_handle_override(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    paths.prompts_overrides.mkdir(parents=True, exist_ok=True)
    (paths.prompts_overrides / "@claude-opus.md").write_text(
        "Default posture: be especially blunt about risks.", encoding="utf-8"
    )
    inputs = _build_inputs(paths, mode="interactive", role="proposer", deputy_active=False)
    out = render_prompt(inputs)
    assert "OVERRIDE — @claude-opus" in out
    assert "blunt about risks" in out


def test_render_prompt_substitutes_handle_placeholders(tmp_path: Path) -> None:
    paths = _init_workspace(tmp_path)
    inputs = _build_inputs(paths, mode="interactive", role="proposer", deputy_active=False)
    out = render_prompt(inputs)
    # The standing prompt contains `@<handle>` placeholders that must be
    # substituted with the actual handle.
    assert "@<handle>" not in out
    assert "@claude-opus" in out
