"""Auto-maintenance of `summarized-decisions.md`.

Per design-doc §1.8 "Layer 1 — Standing context bundle", the conductor
maintains a single concatenated file of every DECISION move's Summary
line. Every subsequent invocation reads it as part of the standing
bundle, so its quality compounds over the workspace's life.

This module is the only writer to `registers/summarized-decisions.md`.
On each successful append of a DECISION move, the invoker calls
`append_summary_line()` here.

The file is intentionally simple Markdown:

    # Summarized decisions

    - **DECISION@<author>#<id>** — <summary line>
    - **DECISION@<author>#<id>** — <summary line>
    ...

Idempotent: appending the same move-ref twice is a no-op (we scan
existing lines).
"""

from __future__ import annotations

import re
from pathlib import Path

from .move_format import MoveHeader

_HEADING = "# Summarized decisions"
_SUMMARY_LINE_RE = re.compile(
    r"^##\s+Summary\s+line\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NEXT_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def append_summary_line(
    summarized_path: Path,
    *,
    deliberation_id: str,
    header: MoveHeader,
    move_text: str,
) -> bool:
    """Append the move's Summary line to `summarized-decisions.md`.

    Only acts on DECISION-class moves with a non-empty Summary line.
    Returns True if a new line was appended, False otherwise (e.g.,
    move was already summarised, or no Summary line was found).
    """
    if header.move_type not in ("DECISION", "DEPUTY_DECISION", "OVERRIDE"):
        return False

    summary = _extract_summary_line(move_text)
    if summary is None or not summary.strip():
        return False

    # Reference convention from PROTOCOL.md §3:
    # <MOVE_TYPE>@<author>#<deliberation_id> with no leading @ on author.
    bare_author = header.author.lstrip("@")
    ref = f"{header.move_type}@{bare_author}#{deliberation_id}"
    summarized_path.parent.mkdir(parents=True, exist_ok=True)

    if summarized_path.is_file():
        existing = summarized_path.read_text(encoding="utf-8")
        if f"**{ref}**" in existing:
            return False  # already summarised
        body = existing.rstrip() + "\n"
    else:
        body = _HEADING + "\n\n"

    line = f"- **{ref}** — {summary.strip()}\n"
    summarized_path.write_text(body + line, encoding="utf-8")
    return True


def _extract_summary_line(move_text: str) -> str | None:
    """Pull the body of the `## Summary line` H2 section, if present.

    DECISION moves may not have a Summary line section (e.g. OVERRIDE
    isn't required to). Returns None if absent or empty after stripping
    template comments.
    """
    match = _SUMMARY_LINE_RE.search(move_text)
    if match is None:
        return None
    body_start = match.end()
    next_h2 = _NEXT_H2_RE.search(move_text, pos=body_start + 1)
    body_end = next_h2.start() if next_h2 else len(move_text)
    body = move_text[body_start:body_end]
    body = _HTML_COMMENT_RE.sub("", body).strip()
    return body or None
