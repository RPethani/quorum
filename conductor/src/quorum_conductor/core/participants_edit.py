"""Programmatic edits to `registers/participants.md`.

The file is hand-edited Markdown by default (design-doc §3.5). For
the UI's "Add agent" affordance we still write the same table format
so the file stays diff-friendly and round-trips through
`parse_participants` cleanly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .participants import parse_participants

_TABLE_ROW_RE = re.compile(r"^\|.*\|\s*$")


class ParticipantsEditError(RuntimeError):
    """Raised when an append cannot be honoured (duplicate handle, no table, …)."""


@dataclass(frozen=True)
class NewParticipant:
    """Minimal payload for adding a row.

    `handle` should start with `@`; we normalise it if not. Everything
    else has reasonable defaults so the UI form stays small.
    """

    handle: str
    display_name: str = ""
    cli_command: str = ""
    model: str = ""
    transport: str = "cli"
    quota_daily: int | None = None
    quota_per_deliberation: int | None = None
    permission_capability: str = "ask"
    account_label: str = ""
    health: str = "unknown"

    def normalised_handle(self) -> str:
        h = self.handle.strip()
        return h if h.startswith("@") else f"@{h}"


def append_participant(path: Path, new: NewParticipant) -> None:
    """Append `new` to the participants table at `path`.

    Refuses if a participant with the same handle already exists.
    Raises if the file has no recognisable table to append to.
    """
    handle = new.normalised_handle()
    if not handle or handle == "@":
        raise ParticipantsEditError("Handle is required.")

    if path.is_file():
        existing = parse_participants(path)
        if any(p.handle.lower() == handle.lower() for p in existing):
            raise ParticipantsEditError(f"Handle {handle!r} already exists in participants.md.")

    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not _has_table(text):
        raise ParticipantsEditError(
            "participants.md does not contain a Markdown table; can't append."
        )

    row = _format_row(handle, new)
    updated = _append_to_last_table(text, row)
    path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _has_table(text: str) -> bool:
    return any(_TABLE_ROW_RE.match(line) for line in text.splitlines())


def _format_row(handle: str, p: NewParticipant) -> str:
    quota = (
        f"{p.quota_daily}/{p.quota_per_deliberation}"
        if p.quota_daily is not None and p.quota_per_deliberation is not None
        else "unlimited"
    )
    cells = [
        handle,
        p.display_name or handle.lstrip("@"),
        p.cli_command or "(set me)",
        p.model or "n/a",
        p.transport or "cli",
        quota,
        p.permission_capability or "ask",
        p.account_label or "(none)",
        p.health or "unknown",
    ]
    return "| " + " | ".join(cells) + " |"


def _append_to_last_table(text: str, row: str) -> str:
    """Append `row` to whatever table block trails `text`.

    We find the index of the last `|`-prefixed line and insert `row`
    immediately after it, preserving whatever follows (e.g. trailing
    HTML comments or other prose). If the file ends with the table,
    we just concatenate.
    """
    lines = text.splitlines(keepends=False)
    last_table_idx = -1
    for i, line in enumerate(lines):
        if _TABLE_ROW_RE.match(line):
            last_table_idx = i
    if last_table_idx < 0:
        # _has_table caller already guards against this, but defend.
        raise ParticipantsEditError("No table row found.")
    new_lines = [*lines[: last_table_idx + 1], row, *lines[last_table_idx + 1 :]]
    out = "\n".join(new_lines)
    if not out.endswith("\n"):
        out += "\n"
    return out


__all__ = [
    "NewParticipant",
    "ParticipantsEditError",
    "append_participant",
]
