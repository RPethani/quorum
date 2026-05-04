"""Real ``InvokeFn`` implementation that spawns participant CLIs.

Per `docs-specs/canvas-redesign.md` S2, the canvas dispatcher
exploits the fact that modern coding CLIs (Claude Code, Gemini
CLI, etc.) read files in their cwd. Our invocation is therefore
small:

1. Look up the participant row in ``registers/participants.md`` to
   find the ``cli_command``.
2. Spawn that command **with cwd = workspace root**.
3. Pipe a tiny system-prompt + instruction string into stdin.
4. Return the captured stdout as the agent's reply.

No protocol-era validation, no retries, no normalisation, no
move-type machinery. The dispatcher converts whatever stdout we
return into a regular message and parses out artifact emits.
"""

from __future__ import annotations

import shlex
import subprocess

from quorum_conductor.core.participants import parse_participants

from . import remediation
from .dispatcher import InvocationRequest, InvocationResult, InvokeFn

# Generous default timeout. Brainstorm replies over multi-page
# context can take a minute or two; we stop short of unbounded so
# a hung CLI doesn't park the dispatcher forever.
DEFAULT_TIMEOUT_S = 600.0

# System prompt rendered once per invocation. The placeholders are
# filled by `.format()`. Keep this short — the user pays for every
# character of system context every turn.
DEFAULT_SYSTEM_PROMPT = """\
You are participating as {handle} in a multi-AI brainstorming workspace.

This is a CONTINUING conversation — not a fresh task. The full
history is in `canvas.md` at the workspace root, with each turn
delimited by `<!-- msg:msg-NNNN -->` markers. Live artifacts are
in `artifacts/*.md`.

Your job is to respond to the **most recent user message** —
typically the last `## @rakesh …` block in `canvas.md`. Treat the
prior turns as context, not as something to re-summarise.

Hard rules:

  - **Do NOT re-introduce yourself or restate your prior position.**
    No "I'm in now", no "I have read canvas.md", no recapping what
    you said two turns ago. Just answer the new message.
  - **Build forward.** If the user asks a follow-up ("elaborate",
    "say more", "what about X?"), add new content; don't paraphrase
    your last reply.
  - **If the user asks you to write to or update an artifact, you
    MUST emit a fenced code block** whose language tag is
    `artifact:<filename>`. The conductor overwrites the file with
    the block's body. A reply that says "I'll update the file" but
    contains no `artifact:` block updates nothing.

Artifact emit format:

    ```artifact:requirements.md
    # Requirements
    - …
    ```

When updating an existing artifact, emit the **full new file**
inside the block — the conductor doesn't apply patches.

Keep replies focused. Bite-sized turns over walls of text.
"""


def make_invoker(
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> InvokeFn:
    """Build the real ``InvokeFn`` the canvas dispatcher uses.

    Parameters
    ----------
    timeout_s:
        Subprocess timeout. Defaults to 10 minutes.
    system_prompt:
        Template rendered with ``{handle}`` and prepended to the
        prompt. Override for tests or to change the contract.
    """

    def _invoke(req: InvocationRequest) -> InvocationResult:
        participants_path = req.workspace / "registers" / "participants.md"
        try:
            participants = parse_participants(participants_path)
        except Exception as e:
            return InvocationResult(error=f"participants registry unreadable: {e}")

        match = next((p for p in participants if p.handle == req.handle), None)
        if match is None:
            return InvocationResult(error=f"{req.handle} is not in the participants registry")
        if not match.cli_command.strip():
            return InvocationResult(error=f"{req.handle} has no cli_command configured")

        prompt = _render_prompt(req.handle, system_prompt)

        try:
            result = subprocess.run(
                shlex.split(match.cli_command),
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(req.workspace),
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return InvocationResult(error=f"timed out after {timeout_s:.0f}s")
        except FileNotFoundError:
            return InvocationResult(
                error=(
                    f"CLI binary not found for {req.handle} — "
                    f"check `cli_command` in registers/participants.md"
                )
            )
        except Exception as e:
            return InvocationResult(error=f"spawn failed: {e}")

        if result.returncode != 0:
            stderr_text = result.stderr or ""
            stderr_excerpt = stderr_text.strip() or "(no stderr output)"
            rem = remediation.detect(req.handle, stderr_text)
            return InvocationResult(
                error=f"exit {result.returncode}: {stderr_excerpt[:200]}",
                remediation=rem,
            )

        return InvocationResult(reply=result.stdout)

    return _invoke


def _render_prompt(handle: str, template: str) -> str:
    return (
        template.format(handle=handle)
        + "\n\nRespond to the latest user message in canvas.md. "
        + "Do not begin with 'I'm in now', 'I have read canvas.md', or any "
        + "self-introduction — those are fillers and the user is reading every "
        + "word. Start with substance."
    )
