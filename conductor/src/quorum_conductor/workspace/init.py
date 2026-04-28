"""`quorum init` — scaffold a workspace and write its initial state.yaml."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from ..paths import WorkspacePaths
from .scaffolding import ScaffoldingError, scaffold_workspace
from .state import WorkspaceMode, WorkspaceState, WorkspaceStateModel, save_state


@dataclass
class InitOptions:
    target: Path  # the workspace root (typically <project>/quorum)
    mode: WorkspaceMode = WorkspaceMode.INTERACTIVE


def init_workspace(opts: InitOptions) -> WorkspacePaths:
    """Scaffold a fresh workspace at `opts.target`.

    Returns the resolved `WorkspacePaths`. Raises `ScaffoldingError` if
    the target already contains a workspace.
    """
    paths = WorkspacePaths(root=opts.target.resolve())
    scaffold_workspace(paths)

    state = WorkspaceStateModel(
        workspace_id=secrets.token_hex(8),
        mode=opts.mode,
        state=WorkspaceState.INITIALIZED,
    )
    save_state(paths.state_yaml, state)
    return paths


__all__ = ["InitOptions", "ScaffoldingError", "init_workspace"]
