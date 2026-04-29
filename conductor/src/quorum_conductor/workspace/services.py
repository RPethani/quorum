"""Manage long-lived services (HTTP server + UI dev server) per workspace.

This is the building-block under `quorum up` / `quorum down` / `quorum
status` / `quorum logs`. The goal is the one-terminal experience: the
user runs a single command and both services are detached, surviving
the parent shell, with PIDs tracked under `runtime/services/`.

Lifecycle is intentionally minimal: pidfile-based, `kill -0` liveness
checks, SIGTERM-then-SIGKILL on stop, no auto-restart. The web UI is
rendered by Next.js's `next dev`; we record its process group so we
can tear down the watcher tree cleanly.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..paths import WorkspacePaths

ServiceName = Literal["server", "ui"]
SERVICE_NAMES: tuple[ServiceName, ...] = ("server", "ui")

DEFAULT_SERVER_PORT = 8500
DEFAULT_UI_PORT = 3000

_LOG_BYTES_TAIL = 4_000  # bytes to surface when crashed.


class ServiceError(RuntimeError):
    """Raised when a service operation cannot honour the user's intent."""


@dataclass(frozen=True)
class ServiceStatus:
    """Snapshot of one service. `state` is one of running/stopped/crashed."""

    name: ServiceName
    state: str
    pid: int | None
    pgid: int | None
    port: int | None
    log_path: Path
    started_at: str | None
    last_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["log_path"] = str(self.log_path)
        return d


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def status(paths: WorkspacePaths, name: ServiceName) -> ServiceStatus:
    """Inspect the recorded state for `name`. Stale pids are reconciled."""
    rec = _load_record(paths, name)
    log_path = _log_path(paths, name)
    if rec is None:
        return ServiceStatus(
            name=name,
            state="stopped",
            pid=None,
            pgid=None,
            port=None,
            log_path=log_path,
            started_at=None,
        )
    pid = _as_int(rec.get("pid"))
    started_at = _as_str(rec.get("started_at"))
    if pid is None or not _alive(pid):
        # Pidfile present, process gone → crashed (clean shutdown removes
        # the file, so the only way to be here is an unclean exit).
        tail = _tail_log(log_path)
        return ServiceStatus(
            name=name,
            state="crashed",
            pid=None,
            pgid=None,
            port=None,
            log_path=log_path,
            started_at=started_at,
            last_error=tail,
        )
    return ServiceStatus(
        name=name,
        state="running",
        pid=pid,
        pgid=_as_int(rec.get("pgid")),
        port=_as_int(rec.get("port")),
        log_path=log_path,
        started_at=started_at,
    )


def all_status(paths: WorkspacePaths) -> list[ServiceStatus]:
    return [status(paths, name) for name in SERVICE_NAMES]


def start(
    paths: WorkspacePaths,
    name: ServiceName,
    *,
    server_port: int = DEFAULT_SERVER_PORT,
    ui_port: int = DEFAULT_UI_PORT,
) -> ServiceStatus:
    """Start `name` if not already running. Idempotent on running services."""
    current = status(paths, name)
    if current.state == "running":
        return current
    if name == "server":
        return _start_server(paths, port=server_port)
    if name == "ui":
        # Tell the UI where the conductor is so the dev server's window
        # picks up the right backend, even if the user changed the port.
        return _start_ui(paths, ui_port=ui_port, server_port=server_port)
    raise ServiceError(f"unknown service: {name!r}")


def stop(paths: WorkspacePaths, name: ServiceName, *, timeout_s: float = 5.0) -> ServiceStatus | None:
    """Send SIGTERM (then SIGKILL) to `name`. Returns the prior status, or None."""
    rec = _load_record(paths, name)
    if rec is None:
        return None
    pid = _as_int(rec.get("pid"))
    pgid = _as_int(rec.get("pgid"))
    started_at = _as_str(rec.get("started_at"))
    port = _as_int(rec.get("port"))
    if pid is None:
        _clear_record(paths, name)
        return None
    if not _alive(pid):
        _clear_record(paths, name)
        return ServiceStatus(
            name=name,
            state="stopped",
            pid=None,
            pgid=None,
            port=None,
            log_path=_log_path(paths, name),
            started_at=started_at,
        )

    target = -pgid if pgid is not None and pgid > 0 else pid
    _send_signal(target, signal.SIGTERM)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        _send_signal(target, signal.SIGKILL)

    _clear_record(paths, name)
    return ServiceStatus(
        name=name,
        state="stopped",
        pid=pid,
        pgid=pgid,
        port=port,
        log_path=_log_path(paths, name),
        started_at=started_at,
    )


def restart(
    paths: WorkspacePaths,
    name: ServiceName,
    *,
    server_port: int = DEFAULT_SERVER_PORT,
    ui_port: int = DEFAULT_UI_PORT,
) -> ServiceStatus:
    stop(paths, name)
    return start(paths, name, server_port=server_port, ui_port=ui_port)


def tail_log(paths: WorkspacePaths, name: ServiceName, *, n: int = 80) -> str:
    """Return the last `n` lines of `name`'s log."""
    log_path = _log_path(paths, name)
    if not log_path.is_file():
        return ""
    with log_path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        f.seek(max(0, end - 64_000))
        text = f.read().decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-n:])


# ---------------------------------------------------------------------- #
# Service-specific launchers
# ---------------------------------------------------------------------- #


def _start_server(paths: WorkspacePaths, *, port: int) -> ServiceStatus:
    if not _port_is_free(port):
        raise ServiceError(
            f"port {port} is already in use — something else (maybe another "
            f"`quorum serve`) is bound there. Stop it first, or pass "
            f"`--server-port <other>` to use a different port."
        )
    actual_port = port
    log_path = _log_path(paths, "server")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "quorum_conductor",
                "serve",
                "--path",
                str(paths.root),
                "--host",
                "127.0.0.1",
                "--port",
                str(actual_port),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log.close()

    started = _now_iso()
    _save_record(
        paths,
        "server",
        {
            "pid": proc.pid,
            "pgid": _pgid(proc.pid),
            "port": actual_port,
            "started_at": started,
        },
    )
    # Brief readiness probe so we surface obvious failures (port collision,
    # import error) without making the user wait for the first request.
    if not _wait_http_ready(
        "127.0.0.1", actual_port, timeout_s=4.0, pid=proc.pid
    ) and not _alive(proc.pid):
        tail = _tail_log(log_path)
        raise ServiceError(
            f"conductor server exited immediately on port {actual_port}.\n"
            f"see {log_path}:\n{tail}"
        )
    return status(paths, "server")


def _start_ui(paths: WorkspacePaths, *, ui_port: int, server_port: int) -> ServiceStatus:
    ui_dir = _locate_ui_dir()
    if ui_dir is None:
        raise ServiceError(
            "Couldn't locate the UI directory. The web UI ships next to the "
            "conductor source — install Quorum from the repo with "
            "`scripts/install.sh` rather than a wheel."
        )
    pkg_mgr = _detect_pkg_manager(ui_dir)
    if pkg_mgr is None:
        raise ServiceError(
            "No JS package manager found (pnpm/bun/npm). Install one and "
            "re-run."
        )
    if not _port_is_free(ui_port):
        raise ServiceError(
            f"port {ui_port} is already in use — something else (maybe a "
            f"`pnpm dev` from another terminal) is bound there. Stop it "
            f"first, or pass `--ui-port <other>` to use a different port."
        )
    actual_port = ui_port
    log_path = _log_path(paths, "ui")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    env = os.environ.copy()
    env["PORT"] = str(actual_port)
    # The browser-side default is http://127.0.0.1:8500; if the user
    # picked another server port, expose it so the UI can prefer it.
    env["NEXT_PUBLIC_QUORUM_API"] = f"http://127.0.0.1:{server_port}"
    # If we're an x86_64 Python running under Rosetta on Apple Silicon
    # hardware, child node processes inherit x86_64 — and platform-
    # specific deps like lightningcss only ship the arm64 binary on
    # this machine. Force the spawn back to native arm64 so the right
    # native module is loaded.
    cmd: list[str] = [pkg_mgr, "run", "dev"]
    if _running_under_rosetta_on_arm64():
        cmd = ["arch", "-arm64", *cmd]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ui_dir),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
            env=env,
        )
    finally:
        log.close()

    started = _now_iso()
    _save_record(
        paths,
        "ui",
        {
            "pid": proc.pid,
            "pgid": _pgid(proc.pid),
            "port": actual_port,
            "started_at": started,
        },
    )
    # Next.js takes a beat to compile; don't wait — surface status from
    # the next `quorum status` call instead. We only fail fast if the
    # process died outright.
    time.sleep(0.4)
    if not _alive(proc.pid):
        tail = _tail_log(log_path)
        raise ServiceError(
            f"UI dev server exited immediately.\nsee {log_path}:\n{tail}"
        )
    return status(paths, "ui")


# ---------------------------------------------------------------------- #
# Filesystem layout
# ---------------------------------------------------------------------- #


def _services_dir(paths: WorkspacePaths) -> Path:
    return paths.runtime / "services"


def _record_path(paths: WorkspacePaths, name: ServiceName) -> Path:
    return _services_dir(paths) / f"{name}.json"


def _log_path(paths: WorkspacePaths, name: ServiceName) -> Path:
    return _services_dir(paths) / f"{name}.log"


def log_path_for(paths: WorkspacePaths, name: ServiceName) -> Path:
    """Public accessor for the on-disk log path of `name`."""
    return _log_path(paths, name)


def _save_record(paths: WorkspacePaths, name: ServiceName, rec: dict[str, object]) -> None:
    _services_dir(paths).mkdir(parents=True, exist_ok=True)
    _record_path(paths, name).write_text(json.dumps(rec), encoding="utf-8")


def _load_record(paths: WorkspacePaths, name: ServiceName) -> dict[str, object] | None:
    p = _record_path(paths, name)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _clear_record(paths: WorkspacePaths, name: ServiceName) -> None:
    with contextlib.suppress(FileNotFoundError):
        _record_path(paths, name).unlink()


# ---------------------------------------------------------------------- #
# Process helpers
# ---------------------------------------------------------------------- #


def _as_int(v: object) -> int | None:
    if isinstance(v, int):
        return v if v != 0 else None
    if isinstance(v, str) and v.strip().isdigit():
        n = int(v.strip())
        return n if n != 0 else None
    return None


def _as_str(v: object) -> str | None:
    return v if isinstance(v, str) and v else None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _pgid(pid: int) -> int | None:
    try:
        return os.getpgid(pid)
    except OSError:
        return None


def _send_signal(target: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(target, sig)


def _port_is_free(port: int) -> bool:
    """True iff `port` accepts a fresh bind on both IPv4 and IPv6.

    Probes both `127.0.0.1` and `::` so we don't miss listeners on the
    other stack (Next.js, for instance, listens on `::` by default
    which also covers IPv4 connections).
    """
    for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::")):
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            continue
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((addr, port))
        except OSError:
            return False
        finally:
            s.close()
    # Connect-probe as a final guard: if either stack accepts a TCP
    # handshake on this port, somebody's already there.
    for addr in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((addr, port), timeout=0.1):
                return False
        except OSError:
            pass
    return True


def _wait_http_ready(host: str, port: int, *, timeout_s: float, pid: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _alive(pid):
            return False
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tail_log(log_path: Path, *, max_bytes: int = _LOG_BYTES_TAIL) -> str:
    if not log_path.is_file():
        return ""
    with log_path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        f.seek(max(0, end - max_bytes))
        return f.read().decode("utf-8", errors="replace").strip()


def _running_under_rosetta_on_arm64() -> bool:
    """True if this Python is x86_64 but the host is Apple Silicon.

    Rosetta-translated children inherit the x86_64 arch, which breaks
    native modules (e.g. lightningcss) that only ship arm64 binaries
    on this machine. Detected via `sysctl.proc_translated`, which the
    macOS kernel sets to "1" when the calling process is translated.
    """
    if sys.platform != "darwin":
        return False
    if platform.machine() != "x86_64":
        return False
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "sysctl.proc_translated"],
            text=True,
            timeout=1.0,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return out == "1"


def _detect_pkg_manager(ui_dir: Path) -> str | None:
    if (ui_dir / "pnpm-lock.yaml").is_file() and shutil.which("pnpm"):
        return "pnpm"
    if (ui_dir / "bun.lockb").is_file() and shutil.which("bun"):
        return "bun"
    if shutil.which("pnpm"):
        return "pnpm"
    if shutil.which("bun"):
        return "bun"
    if shutil.which("npm"):
        return "npm"
    return None


def _locate_ui_dir() -> Path | None:
    """Find the repo's `ui/` directory.

    We rely on the editable install layout: this module lives at
    `<repo>/conductor/src/quorum_conductor/workspace/services.py`, so
    walking four parents up lands us at `<repo>/conductor/`. The UI
    sits at `<repo>/ui/`.
    """
    here = Path(__file__).resolve()
    # services.py → workspace/ → quorum_conductor/ → src/ → conductor/
    conductor_dir = here.parent.parent.parent.parent
    candidate = conductor_dir.parent / "ui"
    if (candidate / "package.json").is_file():
        return candidate
    return None


__all__ = [
    "DEFAULT_SERVER_PORT",
    "DEFAULT_UI_PORT",
    "SERVICE_NAMES",
    "ServiceError",
    "ServiceName",
    "ServiceStatus",
    "all_status",
    "restart",
    "start",
    "status",
    "stop",
    "tail_log",
]
