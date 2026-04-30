"""Invoke a single CLI agent and append the result to a deliberation.

The full per-invocation contract is in design-doc §10. This module
implements:

  1. render the prompt for (handle, role, deliberation, mode)
  2. emit `agent_started`
  3. touch a lifecycle marker in /runtime/active/
  4. spawn the CLI subprocess; pipe the prompt on stdin; capture stdout
  5. write the captured stream to /runtime/streams/<...>.stream
  6. acquire the per-deliberation lock
  7. full structural + anti-vacuousness validation (4e)
     - on failure: emit `validation_failed`, retry once with feedback
  8. append the move to the deliberation file
  9. propagate `@handle` mentions to inboxes
 10. release the lock
 11. on success: emit `move_appended` + `agent_completed`; remove
                 the active marker and stream buffer
     on failure: emit `agent_failed`; leave the active marker; move the
                 stream into /runtime/streams/failed/ for diagnosis
"""

from __future__ import annotations

import contextlib
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..core.decisions_summary import append_summary_line
from ..core.deliberation import DeliberationMeta
from ..core.move_format import MoveValidation, strip_optional_code_fence
from ..core.participants import Participant
from ..core.prompts import PromptInputs, render_prompt
from ..core.validator import (
    FullMoveValidation,
    render_validation_feedback,
    validate_move,
)
from ..events import (
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    EventLogger,
    MoveAppended,
    ValidationFailed,
)
from ..paths import WorkspacePaths
from ..workspace.deliberation_file import (
    AppendError,
    append_move,
    update_inboxes_from_move,
)
from .locks import deliberation_lock

DEFAULT_TIMEOUT_S: float = 600.0
DEFAULT_MAX_ATTEMPTS: int = 2  # 1 original + 1 retry on validation failure


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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


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
    validation: FullMoveValidation | MoveValidation | None
    appended: bool
    inboxes_notified: list[str]
    error: str | None
    attempts: int


def invoke(
    request: InvocationRequest,
    paths: WorkspacePaths,
    *,
    events: EventLogger | None = None,
) -> InvocationResult:
    """Run one full invocation. Retries once on validation failure.

    Returns a structured `InvocationResult`; never raises for ordinary
    failure modes (subprocess, validation, timeout) — only for unexpected
    programmer errors.
    """
    logger = events or EventLogger(paths.events_jsonl)
    started = datetime.now(UTC)
    marker = _marker_path(paths, request)
    stream = _stream_path(paths, request)
    _touch(marker)

    last_result: InvocationResult | None = None
    feedback: str | None = None

    for attempt in range(1, request.max_attempts + 1):
        logger.emit(
            AgentStarted(
                handle=request.handle.handle,
                role=request.role,
                deliberation_id=request.deliberation.id,
                move_type=request.move_type,
                attempt=attempt,
            )
        )
        attempt_started = datetime.now(UTC)
        outcome = _run_attempt(
            request=request,
            paths=paths,
            stream_path=stream,
            attempt=attempt,
            feedback=feedback,
        )

        duration_s = (datetime.now(UTC) - attempt_started).total_seconds()

        if outcome.status == "ok":
            assert outcome.validation is not None and outcome.validation.header is not None
            logger.emit(
                MoveAppended(
                    handle=outcome.validation.header.author,
                    role=request.role,
                    deliberation_id=request.deliberation.id,
                    move_type=outcome.validation.header.move_type,
                    inboxes_notified=list(outcome.inboxes_notified),
                )
            )
            logger.emit(
                AgentCompleted(
                    handle=request.handle.handle,
                    role=request.role,
                    deliberation_id=request.deliberation.id,
                    move_type=outcome.validation.header.move_type,
                    duration_s=duration_s,
                    return_code=outcome.return_code or 0,
                    attempt=attempt,
                    stdout_chars=len(outcome.stdout),
                )
            )
            _remove_quietly(marker)
            _remove_quietly(stream)
            total = (datetime.now(UTC) - started).total_seconds()
            return InvocationResult(
                status="ok",
                handle=request.handle.handle,
                role=request.role,
                move_type=outcome.validation.header.move_type,
                deliberation_id=request.deliberation.id,
                duration_s=total,
                stdout=outcome.stdout,
                stderr=outcome.stderr,
                return_code=outcome.return_code,
                validation=outcome.validation,
                appended=True,
                inboxes_notified=outcome.inboxes_notified,
                error=None,
                attempts=attempt,
            )

        # Failed attempt — emit the appropriate event and decide whether to retry.
        if outcome.status == "validation_failed":
            assert outcome.validation is not None
            logger.emit(
                ValidationFailed(
                    handle=request.handle.handle,
                    role=request.role,
                    deliberation_id=request.deliberation.id,
                    move_type=request.move_type,
                    errors=list(outcome.validation.errors),
                    attempt=attempt,
                )
            )
        else:
            logger.emit(
                AgentFailed(
                    handle=request.handle.handle,
                    role=request.role,
                    deliberation_id=request.deliberation.id,
                    move_type=request.move_type,
                    duration_s=duration_s,
                    reason=outcome.status,
                    error=outcome.error or "",
                    attempt=attempt,
                    return_code=outcome.return_code,
                )
            )

        last_result = outcome

        # Only validation failures trigger a retry; subprocess/timeout errors
        # are not the agent's fault to recover from in the same loop.
        if outcome.status != "validation_failed" or attempt >= request.max_attempts:
            break

        feedback = render_validation_feedback(outcome.validation)  # type: ignore[arg-type]

    # Emit the terminal `agent_failed` event so consumers see one failure
    # event per request, not just per attempt. The per-attempt events are
    # additive context.
    assert last_result is not None
    total_duration = (datetime.now(UTC) - started).total_seconds()
    if last_result.status != "ok":
        logger.emit(
            AgentFailed(
                handle=request.handle.handle,
                role=request.role,
                deliberation_id=request.deliberation.id,
                move_type=request.move_type,
                duration_s=total_duration,
                reason=last_result.status,
                error=last_result.error or "",
                attempt=last_result.attempts,
                return_code=last_result.return_code,
            )
        )

    return InvocationResult(
        status=last_result.status,
        handle=last_result.handle,
        role=last_result.role,
        move_type=last_result.move_type,
        deliberation_id=last_result.deliberation_id,
        duration_s=total_duration,
        stdout=last_result.stdout,
        stderr=last_result.stderr,
        return_code=last_result.return_code,
        validation=last_result.validation,
        appended=last_result.appended,
        inboxes_notified=last_result.inboxes_notified,
        error=last_result.error,
        attempts=last_result.attempts,
    )


# ---------------------------------------------------------------------- #
# Single attempt
# ---------------------------------------------------------------------- #


def _run_attempt(
    *,
    request: InvocationRequest,
    paths: WorkspacePaths,
    stream_path: Path,
    attempt: int,
    feedback: str | None,
) -> InvocationResult:
    started = datetime.now(UTC)
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
            paths=paths,
        )
    )
    if feedback:
        prompt = prompt + "\n\n## RETRY FEEDBACK\n\n" + feedback + "\n"

    try:
        proc = _spawn(
            request.handle.cli_command,
            prompt,
            request.timeout_s,
            cwd=str(paths.root),
        )
    except subprocess.TimeoutExpired as exc:
        _move_stream_to_failed(stream_path, paths, "timeout")
        return _failure(
            request,
            started,
            attempt=attempt,
            status="timeout",
            stdout=exc.stdout.decode("utf-8", "replace") if exc.stdout else "",
            stderr=exc.stderr.decode("utf-8", "replace") if exc.stderr else "",
            error=f"subprocess timed out after {request.timeout_s}s",
        )
    except FileNotFoundError as exc:
        return _failure(
            request,
            started,
            attempt=attempt,
            status="subprocess_failed",
            stdout="",
            stderr="",
            error=f"command not on PATH: {exc.filename}",
        )

    stream_path.parent.mkdir(parents=True, exist_ok=True)
    stream_path.write_text(proc.stdout, encoding="utf-8")

    if proc.returncode != 0:
        _move_stream_to_failed(stream_path, paths, "nonzero_exit")
        return _failure(
            request,
            started,
            attempt=attempt,
            status="subprocess_failed",
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=proc.returncode,
            error=f"agent exited with code {proc.returncode}",
        )

    # Normalize the agent's response before validation. Less-obedient
    # models (Gemini in particular) tend to (a) emit a sentence or two
    # of "I will read X then Y" preamble before the canonical header,
    # (b) hallucinate an author handle from artifacts on disk, and
    # (c) hallucinate a timestamp. The conductor authoritatively knows
    # which agent it invoked and when, so we strip preamble and rewrite
    # the header with the known values instead of failing every move
    # over a few stray prose lines. Strictness on body sections is
    # preserved by `validate_move` below.
    normalized = _normalize_agent_response(
        proc.stdout,
        expected_author=request.handle.handle,
        expected_move_type=request.move_type,
    )
    validation = validate_move(
        normalized,
        expected_move_type=request.move_type,
        templates_dir=paths.protocol_templates,
        deliberation_ratifies=str(request.deliberation.extras.get("ratifies", "") or "")
        or None,
    )
    if not validation.ok or validation.header is None:
        _move_stream_to_failed(stream_path, paths, "validation_failed")
        return _failure(
            request,
            started,
            attempt=attempt,
            status="validation_failed",
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=proc.returncode,
            validation=validation,
            error=validation.reasons() if validation.errors else "validation failed",
        )

    try:
        with deliberation_lock(request.deliberation_path):
            append_move(request.deliberation_path, normalized)
            tagged = update_inboxes_from_move(
                normalized,
                inbox_dir=paths.inbox,
                deliberation_id=request.deliberation.id,
                move_type=validation.header.move_type,
                author=validation.header.author,
            )
            # Standing-bundle maintenance (design-doc §1.8 Layer 1):
            # every DECISION's Summary line gets appended to
            # registers/summarized-decisions.md so subsequent
            # invocations see the full decision history at a glance.
            append_summary_line(
                paths.summarized_decisions,
                deliberation_id=request.deliberation.id,
                header=validation.header,
                move_text=normalized,
            )
            # Auto-ratify the outcome manifest if this DECISION lands
            # on a deliberation that ratifies it (design-doc §1.7).
            from ..workspace.ratify import maybe_ratify_manifest

            maybe_ratify_manifest(paths, request.deliberation_path)
    except AppendError as exc:
        _move_stream_to_failed(stream_path, paths, "append_failed")
        return _failure(
            request,
            started,
            attempt=attempt,
            status="validation_failed",
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=proc.returncode,
            validation=validation,
            error=str(exc),
        )

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
        attempts=attempt,
    )


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


_HEADER_LINE_RE = re.compile(
    r"^###\s+\[([A-Z_]+)\]\s+(@\S+)\s+·\s+(\S+)([^\n]*)$",
    re.MULTILINE,
)


def _normalize_agent_response(
    text: str,
    *,
    expected_author: str,
    expected_move_type: str,
) -> str:
    """Strip preamble and authoritatively rewrite the header.

    Less-obedient agents emit prose before the canonical header and
    hallucinate the author handle / timestamp. The conductor knows both
    values authoritatively (it picked the agent and the dispatch time),
    so we rewrite them rather than failing the move over header
    metadata. Body content is preserved verbatim so anti-vacuousness
    checks still apply.

    If no canonical header is found in the response at all, we return
    the original text unchanged so the validator can produce a clear
    "missing header" error.
    """
    cleaned = strip_optional_code_fence(text).lstrip()
    match = _HEADER_LINE_RE.search(cleaned)
    if match is None:
        return text  # let validator emit its standard error
    move_type, _author, _ts, header_tail = match.groups()
    if move_type != expected_move_type:
        # Wrong move type — the validator's "expected X got Y" error is
        # the right thing to surface; don't paper over it.
        return cleaned[match.start() :]
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_header = f"### [{move_type}] {expected_author} · {timestamp}{header_tail}"
    body_after_header = cleaned[match.end() :]
    return new_header + body_after_header


def _spawn(
    cli_command: str,
    prompt: str,
    timeout_s: float,
    *,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = shlex.split(cli_command)
    return subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
        cwd=cwd,
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
    attempt: int,
    status: Literal["validation_failed", "subprocess_failed", "timeout"],
    stdout: str,
    stderr: str,
    error: str,
    return_code: int | None = None,
    validation: FullMoveValidation | MoveValidation | None = None,
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
        attempts=attempt,
    )
