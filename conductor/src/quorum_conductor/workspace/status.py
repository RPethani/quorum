"""`quorum status` — render the current workspace state for the terminal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..paths import WorkspacePaths
from .state import WorkspaceStateModel, load_state


@dataclass
class StatusSummary:
    paths: WorkspacePaths
    state: WorkspaceStateModel
    deliberation_count: int
    artifact_count: int
    decision_count: int
    task_count: int
    inbox_pending_count: int
    conductor_running: bool
    conductor_pid: int | None
    ui_running: bool
    ui_pid: int | None
    stale_active_markers: list[Path]


def status_summary(paths: WorkspacePaths) -> StatusSummary:
    state = load_state(paths.state_yaml)
    deliberations = _count_files(paths.deliberations, "*.md")
    artifacts = _count_files(paths.artifacts, "*.md", exclude_dirs={"versions"})
    decisions = _count_files(paths.decisions, "*.md")
    tasks = _count_files(paths.tasks, "*.md")
    inbox_pending = _count_inbox_pending(paths.inbox)

    conductor_pid = _read_pid(paths.conductor_pid)
    ui_pid = _read_pid(paths.ui_pid)
    return StatusSummary(
        paths=paths,
        state=state,
        deliberation_count=deliberations,
        artifact_count=artifacts,
        decision_count=decisions,
        task_count=tasks,
        inbox_pending_count=inbox_pending,
        conductor_running=conductor_pid is not None and _pid_alive(conductor_pid),
        conductor_pid=conductor_pid,
        ui_running=ui_pid is not None and _pid_alive(ui_pid),
        ui_pid=ui_pid,
        stale_active_markers=_stale_active_markers(paths),
    )


def render_status(summary: StatusSummary) -> str:
    p, s = summary.paths, summary.state
    lines: list[str] = []
    lines.append(f"workspace : {p.root}")
    lines.append(f"id        : {s.workspace_id}")
    lines.append(f"mode      : {s.mode.value}")
    lines.append(f"state     : {s.state.value}")
    lines.append(f"updated   : {s.state_changed_at}")
    lines.append("")
    lines.append("counts")
    lines.append(f"  deliberations : {summary.deliberation_count}")
    lines.append(f"  artifacts     : {summary.artifact_count}")
    lines.append(f"  decisions     : {summary.decision_count}")
    lines.append(f"  tasks         : {summary.task_count}")
    lines.append(f"  inbox pending : {summary.inbox_pending_count}")
    lines.append("")
    lines.append("processes")
    cond = (
        f"running (pid {summary.conductor_pid})"
        if summary.conductor_running
        else (
            f"stale pidfile (pid {summary.conductor_pid} not alive)"
            if summary.conductor_pid is not None
            else "not running"
        )
    )
    ui = (
        f"running (pid {summary.ui_pid})"
        if summary.ui_running
        else (
            f"stale pidfile (pid {summary.ui_pid} not alive)"
            if summary.ui_pid is not None
            else "not running"
        )
    )
    lines.append(f"  conductor : {cond}")
    lines.append(f"  ui        : {ui}")

    if summary.stale_active_markers:
        lines.append("")
        lines.append(
            f"warning: {len(summary.stale_active_markers)} stale lifecycle markers in runtime/active/"
        )
        for marker in summary.stale_active_markers[:5]:
            lines.append(f"  {marker.name}")
        if len(summary.stale_active_markers) > 5:
            lines.append(f"  …and {len(summary.stale_active_markers) - 5} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _count_files(directory: Path, pattern: str, exclude_dirs: set[str] | None = None) -> int:
    if not directory.is_dir():
        return 0
    excluded = exclude_dirs or set()
    count = 0
    for path in directory.rglob(pattern):
        if any(part in excluded for part in path.relative_to(directory).parts[:-1]):
            continue
        if path.is_file():
            count += 1
    return count


def _count_inbox_pending(inbox: Path) -> int:
    if not inbox.is_dir():
        return 0
    pending = 0
    for path in inbox.glob("*.md"):
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            pending += 1
    return pending


def _read_pid(pidfile: Path) -> int | None:
    if not pidfile.is_file():
        return None
    try:
        return int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# Stale-marker threshold per design-doc §10: 15 minutes.
STALE_MARKER_SECONDS = 15 * 60


def _stale_active_markers(paths: WorkspacePaths) -> list[Path]:
    if not paths.runtime_active.is_dir():
        return []
    import time

    cutoff = time.time() - STALE_MARKER_SECONDS
    stale: list[Path] = []
    for marker in paths.runtime_active.iterdir():
        if not marker.is_file():
            continue
        try:
            mtime = marker.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            stale.append(marker)
    return stale
