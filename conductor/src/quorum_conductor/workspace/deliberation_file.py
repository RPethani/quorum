"""Append moves to a deliberation file and propagate inbox notifications.

A deliberation file is Markdown with a YAML frontmatter and a fixed set
of headings (§7 of the design doc, template at
`protocol/templates/deliberation.md`). The append target is the section
under the `## Contributions` heading. New moves go at the end of that
section, separated by blank lines. The validator and lock live in
`core/move_format.py` and `transport/locks.py`; this module only owns
the in-file edit and the inbox-update side effect.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

_CONTRIBUTIONS_RE = re.compile(r"^##\s+Contributions\s*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_\-]+")
_STATUS_LINE_RE = re.compile(r"^(status:\s*)(\S+)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_RATIFIES_RE = re.compile(r"^ratifies:\s*(\S+)\s*$", re.MULTILINE)
_MOVE_HEADER_RE = re.compile(r"^###\s*\[([A-Z_]+)\]", re.MULTILINE)
# Move-types that conclude a deliberation. DECISION is the normal end;
# OVERRIDE is the human-issued unilateral end. ABANDONED via DROP is
# also conclusive but uses a different terminal status.
_DECIDED_MOVES = {"DECISION", "OVERRIDE"}
_DROPPED_MOVES = {"DROP"}


class AppendError(RuntimeError):
    """Raised when a move cannot be appended (e.g. no Contributions section)."""


def append_move(deliberation_path: Path, move_text: str) -> None:
    """Append `move_text` to the deliberation's Contributions section.

    The deliberation file's structure is fixed: `## Contributions` is
    the last H2 section, so appending a move always means appending to
    the end of the file. We don't try to find a "section end" because
    move bodies themselves use H2 headings (`## Decision`, `## Position`,
    etc.) that would confuse any naive boundary detection. Keeping
    Contributions last sidesteps that whole class of bug.

    Caller is expected to hold a deliberation lock for the duration.
    Also flips the frontmatter `status` when the appended move is
    terminal (DECISION/OVERRIDE → DECIDED; DROP → ABANDONED).
    """
    if not deliberation_path.is_file():
        raise AppendError(f"{deliberation_path} does not exist")
    body = deliberation_path.read_text(encoding="utf-8")

    if _CONTRIBUTIONS_RE.search(body) is None:
        raise AppendError(f"{deliberation_path}: no `## Contributions` heading")

    new_body = body.rstrip("\n") + "\n\n" + move_text.strip("\n") + "\n"
    new_body = _maybe_flip_status(new_body, move_text)
    deliberation_path.write_text(new_body, encoding="utf-8")


def _maybe_flip_status(body: str, appended_move: str) -> str:
    """Update frontmatter `status:` if the appended move is terminal."""
    move_type = _peek_move_type(appended_move)
    if move_type is None:
        return body
    if move_type in _DECIDED_MOVES:
        target_status = "DECIDED"
    elif move_type in _DROPPED_MOVES:
        target_status = "ABANDONED"
    else:
        return body

    fm_match = _FRONTMATTER_RE.match(body)
    if not fm_match:
        return body
    fm_block = fm_match.group(0)
    new_fm = _STATUS_LINE_RE.sub(
        lambda m: m.group(0)
        if m.group(2) == target_status
        else f"{m.group(1)}{target_status}",
        fm_block,
        count=1,
    )
    if new_fm == fm_block:
        return body
    return new_fm + body[fm_match.end() :]


def _peek_move_type(move_text: str) -> str | None:
    """Pull the move type from the first `### [TYPE] ...` header."""
    m = re.match(r"###\s*\[([A-Z_]+)\]", move_text.lstrip())
    return m.group(1) if m else None


def update_inboxes_from_move(
    move_text: str,
    *,
    inbox_dir: Path,
    deliberation_id: str,
    move_type: str,
    author: str,
) -> list[str]:
    """Append a one-line notification to each inbox the move tags.

    Tagged handles are extracted as any `@handle` mentions in the move
    body that are not the author's own handle. Order of returned handles
    is the order they first appear; duplicates are de-duped.
    """
    seen: set[str] = set()
    tagged: list[str] = []
    for match in _HANDLE_RE.finditer(move_text):
        handle = match.group(0)
        if handle == author:
            continue
        if handle in seen:
            continue
        seen.add(handle)
        tagged.append(handle)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for handle in tagged:
        path = inbox_dir / f"{handle}.md"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        line = (
            f"- pending: {move_type} in #{deliberation_id} by {author} ({timestamp})\n"
        )
        path.write_text(existing + line, encoding="utf-8")
    return tagged
