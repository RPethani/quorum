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


class AppendError(RuntimeError):
    """Raised when a move cannot be appended (e.g. no Contributions section)."""


def append_move(deliberation_path: Path, move_text: str) -> None:
    """Insert `move_text` at the end of the `## Contributions` section.

    Caller is expected to hold a deliberation lock for the duration.
    """
    if not deliberation_path.is_file():
        raise AppendError(f"{deliberation_path} does not exist")
    body = deliberation_path.read_text(encoding="utf-8")

    contrib_match = _CONTRIBUTIONS_RE.search(body)
    if contrib_match is None:
        raise AppendError(f"{deliberation_path}: no `## Contributions` heading")
    insert_start = contrib_match.end()

    next_h2 = _NEXT_H2_RE.search(body, pos=insert_start + 1)
    insert_end = next_h2.start() if next_h2 else len(body)

    section = body[insert_start:insert_end]
    new_section = section.rstrip("\n") + "\n\n" + move_text.strip("\n") + "\n\n"

    new_body = body[:insert_start] + new_section + body[insert_end:]
    deliberation_path.write_text(new_body, encoding="utf-8")


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
