"""Dispatch a user message → invoke `@mention`ed agents → write artifacts.

This is the orchestration layer that ties together the four
canvas primitives (`io.append_message`, `mentions.extract_mentions`,
`artifacts.extract_artifacts`, `artifact_writer.write_artifact`) plus
state-counter management. It does *not* know how to spawn a CLI — it
takes an `invoke` callable as a dependency, so tests can drive it
without subprocesses and the real wiring (to `transport/`) lands as
a thin adapter.

Flow per the spec (`docs-specs/canvas-redesign.md` D3, S2, S3):

  1. Allocate an ID and append the user's message to ``canvas.md``.
  2. Extract `@mention`s from the body. No mentions ⇒ stop.
  3. For each mention in document order, sequentially:
     a. Invoke the agent.
     b. On success, parse out artifact emits, write each to disk,
        append the cleaned reply to ``canvas.md``.
     c. On failure, append an ``@system`` error message so the
        operator sees what happened (D14).

Sequential invocation is the MVP choice — each agent sees the
running canvas (which now contains the prior agent's reply) and
can riff off it. Parallel "blind" invocation can come later as an
opt-in mode.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .artifact_writer import ArtifactWriteResult, write_artifact
from .artifacts import extract_artifacts
from .io import append_message
from .mentions import extract_mentions
from .message import Message
from .remediation import Remediation
from .state import next_message_id

SYSTEM_HANDLE = "@system"
"""Author handle used for failure / informational messages emitted
by the conductor itself (per D14)."""


@dataclass(frozen=True)
class InvocationRequest:
    """What the dispatcher hands to the `invoke` callable."""

    handle: str
    """The mentioned participant, e.g. ``@claude-opus``."""
    workspace: Path
    """Workspace root — the agent will be spawned here as cwd (S2)."""
    user_message_id: str
    """ID of the user message that triggered this invocation."""


@dataclass(frozen=True)
class InvocationResult:
    """Outcome of an `invoke` call.

    On success, ``reply`` is the agent's full stdout (with any
    `artifact:<filename>` blocks still inline — the dispatcher parses
    them out). On failure, ``error`` is a human-readable reason and
    ``reply`` is empty. ``remediation`` is set when the failure
    matches a known fixable error pattern (per
    `canvas.remediation.detect`); the dispatcher embeds it in the
    error message so the UI can render an inline action button.
    """

    reply: str = ""
    error: str | None = None
    remediation: Remediation | None = None


InvokeFn = Callable[[InvocationRequest], InvocationResult]
"""Pluggable invocation function. The real implementation talks to
`transport/`; tests can pass a lambda."""

NowFn = Callable[[], datetime]


@dataclass(frozen=True)
class AgentTurn:
    """One agent's contribution from a single dispatch."""

    handle: str
    message: Message | None
    """The reply we appended to canvas.md, if any."""
    artifacts: list[ArtifactWriteResult]
    """Artifacts written as a side-effect of this turn."""
    error: str | None = None
    """``None`` on success; a reason string on failure."""
    remediation: Remediation | None = None
    """Suggested fix for a failure, if any. Embedded in the error
    message body so the UI can render an inline action button."""


@dataclass(frozen=True)
class DispatchResult:
    """Aggregate outcome of a single user-message dispatch."""

    user_message: Message
    turns: list[AgentTurn]


def dispatch(
    workspace: Path,
    body: str,
    *,
    invoke: InvokeFn,
    author: str = "@rakesh",
    now: NowFn | None = None,
) -> DispatchResult:
    """Append the user message and dispatch to all `@mention`ed agents.

    Parameters
    ----------
    workspace:
        Workspace root. Must already be scaffolded.
    body:
        The user's raw markdown.
    invoke:
        Callable that runs an agent and returns its reply (or an
        error). Injected for testability.
    author:
        Handle to attribute the user message to. Defaults to the
        conventional ``@rakesh``; the real UI will pass the human's
        actual handle.
    now:
        Optional clock; defaults to ``datetime.now(UTC)``.
    """
    clock: NowFn = now or (lambda: datetime.now(UTC))

    # 1. User message in.
    user_msg = Message(
        id=next_message_id(workspace),
        author=author,
        timestamp=clock(),
        body=body,
    )
    canvas_path = workspace / "canvas.md"
    append_message(canvas_path, user_msg)

    # 2. Routing.
    mentions = extract_mentions(body)
    turns: list[AgentTurn] = []

    # 3. Sequential invocation.
    for handle in mentions:
        result = invoke(
            InvocationRequest(
                handle=handle,
                workspace=workspace,
                user_message_id=user_msg.id,
            )
        )
        if result.error is not None:
            body = f"⚠️ `{handle}` couldn't respond — {result.error}"
            if result.remediation is not None:
                body += "\n\n" + _format_remediation_marker(result.remediation)
            error_msg = Message(
                id=next_message_id(workspace),
                author=SYSTEM_HANDLE,
                timestamp=clock(),
                body=body,
            )
            append_message(canvas_path, error_msg)
            turns.append(
                AgentTurn(
                    handle=handle,
                    message=error_msg,
                    artifacts=[],
                    error=result.error,
                    remediation=result.remediation,
                )
            )
            continue

        parsed = extract_artifacts(result.reply)
        artifacts: list[ArtifactWriteResult] = []
        for emit in parsed.artifacts:
            artifacts.append(write_artifact(workspace, emit, now=clock()))

        agent_msg = Message(
            id=next_message_id(workspace),
            author=handle,
            timestamp=clock(),
            body=parsed.cleaned,
        )
        append_message(canvas_path, agent_msg)
        turns.append(AgentTurn(handle=handle, message=agent_msg, artifacts=artifacts))

    return DispatchResult(user_message=user_msg, turns=turns)


def _format_remediation_marker(rem: Remediation) -> str:
    """Encode a remediation as a single-line HTML comment in the
    error body. The UI parses this back out and renders an inline
    action button. Persisting it in canvas.md means the button
    survives a page refresh.
    """
    import json

    payload = json.dumps(
        {
            "id": rem.id,
            "title": rem.title,
            "description": rem.description,
            "handle": rem.handle,
        },
        separators=(",", ":"),
    )
    return f"<!-- remediation: {payload} -->"
