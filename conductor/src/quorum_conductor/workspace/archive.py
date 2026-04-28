"""`quorum archive` / `quorum unarchive`.

Archive: workspace state -> ARCHIVED, runtime/ deleted, marker recorded
in state.yaml. Unarchive reverses to INITIALIZED. We do *not* chmod the
filesystem read-only; the marker is sufficient and avoids permission
trouble on shared trees. The conductor refuses to run on ARCHIVED
workspaces (enforced in start/run/step in later sub-phases).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime

from ..paths import WorkspacePaths
from .state import WorkspaceState, load_state, save_state


class ArchiveError(RuntimeError):
    """Raised when archive/unarchive cannot proceed."""


def archive_workspace(paths: WorkspacePaths, *, archived_by: str = "@human", reason: str = "completed") -> None:
    state = load_state(paths.state_yaml)
    if state.state == WorkspaceState.ARCHIVED:
        raise ArchiveError("Workspace is already archived.")

    # Tear down ephemeral runtime. The dir itself is recreated on unarchive
    # by `init`-style scaffolding, so deletion here is safe and intentional.
    if paths.runtime.is_dir():
        shutil.rmtree(paths.runtime)

    state.state = WorkspaceState.ARCHIVED
    state.state_changed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.extras["archive"] = {
        "archived_at": state.state_changed_at,
        "archived_by": archived_by,
        "reason": reason,
    }
    save_state(paths.state_yaml, state)


def unarchive_workspace(paths: WorkspacePaths) -> None:
    state = load_state(paths.state_yaml)
    if state.state != WorkspaceState.ARCHIVED:
        raise ArchiveError("Workspace is not archived.")

    state.state = WorkspaceState.INITIALIZED
    state.state_changed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.extras.pop("archive", None)
    save_state(paths.state_yaml, state)

    # Restore the runtime directory tree so subsequent commands have
    # somewhere to write markers. We recreate just the skeleton; events
    # archive will rebuild from scratch.
    for d in (
        paths.runtime,
        paths.runtime_active,
        paths.runtime_streams,
        paths.runtime_streams_failed,
        paths.events_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)
