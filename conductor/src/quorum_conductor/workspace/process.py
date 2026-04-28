"""Daemon-style start/pause helpers.

`quorum start` spawns the conductor's loop as a detached child process
and writes its PID to `runtime/conductor.pid`. `quorum pause` reads the
pidfile, sends SIGTERM to the child, and unlinks the pidfile.

Daemonisation is intentionally minimal:
  * `subprocess.Popen` with `start_new_session=True` so the child
    survives the parent's exit;
  * stdout/stderr redirected to a log file under `runtime/`;
  * pidfile is the contract — a fresh `quorum start` while a previous
    one is still alive is rejected.

This is good enough for v1. Real systemd-style supervision is out of
scope; if a workspace's conductor dies the user re-runs `quorum start`.
"""

from __future__ import annotations

import contextlib
import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..paths import WorkspacePaths


class ProcessError(RuntimeError):
    """Raised when start/pause cannot honour the user's intent."""


def conductor_running(paths: WorkspacePaths) -> int | None:
    pid = _read_pid(paths.conductor_pid)
    if pid is None:
        return None
    return pid if _alive(pid) else None


def daemonize_run(paths: WorkspacePaths) -> int:
    """Spawn `python -m quorum_conductor run --path <root>` detached.

    Returns the child PID. Refuses if a conductor is already running
    for this workspace.
    """
    existing = conductor_running(paths)
    if existing is not None:
        raise ProcessError(
            f"Conductor is already running for {paths.root} (pid {existing}). "
            "Use `quorum pause` to stop it first."
        )

    paths.runtime.mkdir(parents=True, exist_ok=True)
    log_path = paths.runtime / "conductor.log"
    log = log_path.open("ab")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "quorum_conductor",
            "run",
            "--path",
            str(paths.root),
            "--detached",
        ],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        close_fds=True,
    )
    paths.conductor_pid.write_text(str(proc.pid), encoding="utf-8")
    # Detach the file handle from us; the child inherits its own copy.
    log.close()
    return proc.pid


def stop_conductor(paths: WorkspacePaths, *, timeout_s: float = 5.0) -> int | None:
    """Send SIGTERM to a running conductor; wait briefly for exit.

    Returns the PID we stopped, or None if nothing was running.
    """
    pid = conductor_running(paths)
    if pid is None:
        # Stale pidfile? Clean it up anyway.
        with contextlib.suppress(FileNotFoundError):
            paths.conductor_pid.unlink()
        return None

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        with contextlib.suppress(FileNotFoundError):
            paths.conductor_pid.unlink()
        return None

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        # Last-resort SIGKILL.
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)

    with contextlib.suppress(FileNotFoundError):
        paths.conductor_pid.unlink()
    return pid


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _read_pid(pidfile: Path) -> int | None:
    if not pidfile.is_file():
        return None
    try:
        return int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM  # owned by another user → still alive.
    return True
