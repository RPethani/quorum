"""Parse `artifact:<filename>` fenced blocks out of an agent reply.

Per `docs-specs/canvas-redesign.md` S3, agents create or update
artifacts by emitting a fenced markdown code block whose language
tag starts with `artifact:`::

    Here's my take:

    ```artifact:requirements.md
    # Requirements
    - …
    ```

    Anything else?

The conductor calls `extract_artifacts()` on each agent reply
*before* the reply is appended to `canvas.md`. The function returns
both the cleaned reply (with each block replaced by a one-line
"📝 updated `<filename>`" indicator) and the list of artifact
contents to write to disk.

This module is pure — no file I/O. The caller owns disk side-effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Match a fenced block whose language tag is `artifact:<filename>`.
# Capture the filename and the body. Filename allows letters, digits,
# `_`, `-`, `.`, and `/` so agents can emit nested paths
# (e.g. `artifact:specs/api.md`). The body is non-greedy so multiple
# blocks in one reply parse independently.
_ARTIFACT_RE = re.compile(
    r"^```artifact:(?P<filename>[\w./\-]+)\s*\n"
    r"(?P<body>.*?)"
    r"^```\s*$",
    re.DOTALL | re.MULTILINE,
)


@dataclass(frozen=True)
class ArtifactEmit:
    """One artifact create/update parsed from an agent reply.

    `body` is the artifact's full intended content (the conductor
    overwrites the file wholesale per S3 — no patch semantics).
    """

    filename: str
    body: str


@dataclass(frozen=True)
class ParsedReply:
    """The result of `extract_artifacts()`.

    `cleaned` is what gets stored in `canvas.md` — every artifact
    block in the original reply is replaced in place by a single-line
    indicator like `` 📝 updated `requirements.md` ``. `artifacts`
    are the parsed emits, in the order they appeared in the reply.
    """

    cleaned: str
    artifacts: list[ArtifactEmit]


def extract_artifacts(reply: str) -> ParsedReply:
    """Strip `artifact:<filename>` fenced blocks from *reply*.

    Returns the cleaned reply and the parsed artifacts. If the reply
    contains no artifact blocks the reply is returned unchanged and
    the artifact list is empty.
    """
    emits: list[ArtifactEmit] = []

    def _replace(match: re.Match[str]) -> str:
        filename = match.group("filename")
        body = match.group("body")
        # Strip a single trailing newline if present so the body
        # round-trips exactly when written back to a fenced block.
        if body.endswith("\n"):
            body = body[:-1]
        emits.append(ArtifactEmit(filename=filename, body=body))
        return f"📝 updated `{filename}`"

    cleaned = _ARTIFACT_RE.sub(_replace, reply)
    return ParsedReply(cleaned=cleaned, artifacts=emits)
