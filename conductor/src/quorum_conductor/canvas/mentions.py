"""`@mention` extraction for dispatch routing.

Per `docs-specs/canvas-redesign.md` D3, the canvas dispatcher routes
on `@mention`s. This module is a single pure function that parses
a message body and returns the mentioned handles in document order,
deduplicated.

Code blocks and inline code spans are stripped before scanning so
that quoting a handle in code (e.g. `` `@claude-opus is the lead` ``
or inside a fenced ``artifact:`` block) doesn't accidentally trigger
a dispatch.
"""

from __future__ import annotations

import re

# Match @handle where the handle is word characters with optional
# embedded hyphens or dots. Anchored at the @, which must be preceded
# by start-of-line, whitespace, or punctuation — so emails like
# `foo@bar.com` don't match. The handle must *end* on a word char so
# trailing sentence punctuation (`@claude.`) doesn't get sucked in.
_MENTION_RE = re.compile(
    r"(?:^|(?<=[\s.,;:!?\(\[<]))@(\w(?:[\w.-]*\w)?)"
)
_FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_RE = re.compile(r"`[^`\n]+`")


def extract_mentions(body: str) -> list[str]:
    """Return mentioned handles (with leading ``@``) in document order.

    Duplicates are removed while preserving first-occurrence order.
    Code blocks (fenced or inline) are stripped before scanning to
    avoid false dispatches on quoted handles.
    """
    stripped = _FENCED_RE.sub("", body)
    stripped = _INLINE_RE.sub("", stripped)

    seen: set[str] = set()
    out: list[str] = []
    for m in _MENTION_RE.finditer(stripped):
        handle = "@" + m.group(1)
        if handle not in seen:
            seen.add(handle)
            out.append(handle)
    return out
