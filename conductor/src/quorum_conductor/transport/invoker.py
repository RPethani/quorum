"""Invoke a single CLI agent and append the result to a deliberation.

The full per-invocation contract is in design-doc §10. Phase 4d
implements the structural skeleton:

  1. render the prompt for (handle, role, deliberation, mode)
  2. touch a lifecycle marker in /runtime/active/
  3. spawn the CLI subprocess; pipe the prompt on stdin; capture stdout
  4. write the captured stream to /runtime/streams/<...>.stream
  5. acquire the per-deliberation lock
  6. minimal structural validation (header line + known move type)
  7. append the move to the deliberation file
  8. propagate `@handle` mentions to inboxes
  9. release the lock
 10. on success: remove the active marker and stream buffer
     on failure: leave the active marker, move the stream into
                 /runtime/streams/failed/ for diagnosis

Phase 4e adds full per-section validation and a one-retry path. Phase
4g lights up `events.jsonl`. Phase 4f wraps this in the parallel async
loop. Until then this is a clean synchronous API the loop can call.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..core.deliberation import DeliberationMeta
from ..core.move_format import MoveValidation, validate_minimal
from ..core.participants import Participant
from ..core.prompts import PromptInputs, render_prompt
from ..paths import WorkspacePaths
from ..workspace.deliberation_file import (
    AppendError,
    append_move,
    update_inboxes_from_move,
)
from .locks import deliberation_lock

DEFAULT_TIMEOUT_S: float = 600.0


@dataclass(frozen=True)
class InvocationRequest:
    handle: Participant
    role: str
    move_type: str
    deliberation: DeliberationMeta
    deliberation_path: Path
    mode: str  # "interactive" | "autonomous"
    deputy_active: bool = False
    timeout_s: float = DEFAULT_TIMEOUT_S


@dataclass(frozen=True)
class InvocationResult:
    status: Literal["ok", "validation_failed", "subprocess_failed", "timeout"]
    handle: str
    role: str
    move_type: str
    deliberation_id: str
    duration_s: float
    stdout: str
    stderr: str
    return_code: int | None
    validation: MoveValidation | None
    appended: bool
    inboxes_notified: list[str]
    error: str | None


def invoke(
    request: InvocationRequest,
    paths: WorkspacePaths,
) -> InvocationResult:
    """Run one full invocation. Returns a structured result; never raises
    for ordinary failure modes (subprocess, validation, timeout) — only
    for unexpected programmer errors."""

    started = datetime.now(UTC)
    marker = _marker_path(paths, request)
    stream = _stream_path(paths, request)
    _touch(marker)

    try:
        prompt = render_prompt(
            PromptInputs(
                handle=request.handle,
                role=request.role,
                deliberation=request.deliberation,
                mode=request.mode,
                standing_prompt_path=paths.agent_standing_prompt,
                overrides_dir=paths.prompts_overrides,
                workspace_root=paths.root,
                deputy_active=request.deputy_active,
                move_type=request.move_type,
            )
        )

        try:
            proc = _spawn(request.handle.cli_command, prompt, request.timeout_s)
        except subprocess.TimeoutExpired as exc:
            _move_stream_to_failed(stream, paths, "timeout")
            return _failure(
                request,
                started,
                status="timeout",
                stdout=exc.stdout.decode("utf-8", "replace") if exc.stdout else "",
                stderr=exc.stderr.decode("utf-8", "replace") if exc.stderr else "",
                error=f"subprocess timed out after {request.timeout_s}s",
            )
        except FileNotFoundError as exc:
            return _failure(
                request,
                started,
                status="subprocess_failed",
                stdout="",
                stderr="",
                error=f"command not on PATH: {exc.filename}",
            )

        stream.parent.mkdir(parents=True, exist_ok=True)
        stream.write_text(proc.stdout, encoding="utf-8")

        if proc.returncode != 0:
            _move_stream_to_failed(stream, paths, "nonzero_exit")
            return _failure(
                request,
                started,
                status="subprocess_failed",
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                error=f"agent exited with code {proc.returncode}",
            )

        validation = validate_minimal(proc.stdout, expected_move_type=request.move_type)
        if not validation.ok or validation.header is None:
            _move_stream_to_failed(stream, paths, "validation_failed")
            return _failure(
                request,
                started,
                status="validation_failed",
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                validation=validation,
                error="; ".join(validation.errors) or "validation failed",
            )

        try:
            with deliberation_lock(request.deliberation_path):
                append_move(request.deliberation_path, proc.stdout)
                tagged = update_inboxes_from_move(
                    proc.stdout,
                    inbox_dir=paths.inbox,
                    deliberation_id=request.deliberation.id,
                    move_type=validation.header.move_type,
                    author=validation.header.author,
                )
        except AppendError as exc:
            _move_stream_to_failed(stream, paths, "append_failed")
            return _failure(
                request,
                started,
                status="validation_failed",
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                validation=validation,
                error=str(exc),
            )

        # Success: clean up artefacts.
        _remove_quietly(marker)
        _remove_quietly(stream)
        return InvocationResult(
            status="ok",
            handle=request.handle.handle,
            role=request.role,
            move_type=validation.header.move_type,
            deliberation_id=request.deliberation.id,
            duration_s=(datetime.now(UTC) - started).total_seconds(),
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=proc.returncode,
            validation=validation,
            appended=True,
            inboxes_notified=tagged,
            error=None,
        )

    finally:
        # The marker is removed on success above; on failure it stays so
        # the user can see the failed invocation in `quorum status`. The
        # stale-marker reaper (Phase 4f) cleans up after 15 minutes.
        pass


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _spawn(cli_command: str, prompt: str, timeout_s: float) -> subprocess.CompletedProcess[str]:
    cmd = shlex.split(cli_command)
    return subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def _marker_path(paths: WorkspacePaths, request: InvocationRequest) -> Path:
    handle = request.handle.handle.lstrip("@")
    name = f"{handle}--{request.deliberation.id}--{request.move_type}.start"
    return paths.runtime_active / name


def _stream_path(paths: WorkspacePaths, request: InvocationRequest) -> Path:
    handle = request.handle.handle.lstrip("@")
    name = f"{handle}--{request.deliberation.id}--{request.move_type}.stream"
    return paths.runtime_streams / name


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _remove_quietly(path: Path) -> None:
    import contextlib

    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def _move_stream_to_failed(stream: Path, paths: WorkspacePaths, reason: str) -> None:
    if not stream.is_file():
        return
    paths.runtime_streams_failed.mkdir(parents=True, exist_ok=True)
    target = paths.runtime_streams_failed / f"{stream.stem}.{reason}{stream.suffix}"
    stream.replace(target)


def _failure(
    request: InvocationRequest,
    started: datetime,
    *,
    status: Literal["validation_failed", "subprocess_failed", "timeout"],
    stdout: str,
    stderr: str,
    error: str,
    return_code: int | None = None,
    validation: MoveValidation | None = None,
) -> InvocationResult:
    return InvocationResult(
        status=status,
        handle=request.handle.handle,
        role=request.role,
        move_type=request.move_type,
        deliberation_id=request.deliberation.id,
        duration_s=(datetime.now(UTC) - started).total_seconds(),
        stdout=stdout,
        stderr=stderr,
        return_code=return_code,
        validation=validation,
        appended=False,
        inboxes_notified=[],
        error=error,
    )
