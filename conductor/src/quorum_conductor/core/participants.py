"""Parse `registers/participants.md`.

Per design-doc §3.5 the file is human-readable Markdown with a fixed
pipe-table schema, optionally preceded by YAML frontmatter. The format
is intentionally not "JSON-strict" — humans edit it directly. This
module gives the rest of the conductor a structured view.

Tolerated extensions:
- An optional `Inherits Fitness From` column (right-most). Used by
  routing when the handle name does not match a canonical entry in
  `routing-defaults.yaml`. See design-doc §3.5 "Fitness inheritance for
  non-canonical handles."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_TABLE_ROW_RE: Final = re.compile(r"^\|\s*(?P<cells>.+?)\s*\|\s*$")


@dataclass(frozen=True)
class Participant:
    """A single row of the participants registry."""

    handle: str
    display_name: str
    cli_command: str
    model: str
    transport: str
    quota_daily: int | None
    quota_per_deliberation: int | None
    permission_capability: str
    account_label: str
    health: str
    inherits_fitness_from: str | None = None


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def parse_participants(path: Path) -> list[Participant]:
    """Return one Participant per data row of the table.

    Returns [] if the file is missing or contains no data rows. Raises
    `ParticipantsParseError` only if the file is present but
    syntactically broken in a way we cannot recover from.
    """
    if not path.is_file():
        return []
    return _parse_markdown(path.read_text(encoding="utf-8"))


class ParticipantsParseError(RuntimeError):
    """Raised when the participants table is unrecoverable."""


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _strip_cell(cell: str) -> str:
    return cell.strip().strip("`")


def _parse_markdown(markdown: str) -> list[Participant]:
    headers: list[str] | None = None
    rows: list[Participant] = []
    for raw in markdown.splitlines():
        match = _TABLE_ROW_RE.match(raw)
        if not match:
            continue
        cells = [_strip_cell(c) for c in match.group("cells").split("|")]
        if all(set(c) <= {"-", ":"} and c for c in cells):
            # Markdown separator row.
            continue
        if headers is None:
            headers = [c.lower() for c in cells]
            continue
        if len(cells) != len(headers):
            # Tolerate widening the table over time: skip rows whose
            # column count diverges from the header rather than crashing.
            continue
        record = dict(zip(headers, cells, strict=True))
        rows.append(_record_to_participant(record))
    return rows


def _record_to_participant(record: dict[str, str]) -> Participant:
    handle = record.get("handle", "").strip()
    if not handle:
        raise ParticipantsParseError("Participant row is missing the Handle column.")
    quota = record.get("quota (daily/per-deliberation)") or record.get("quota") or ""
    quota_daily, quota_per_delib = _parse_quota(quota)
    return Participant(
        handle=handle,
        display_name=record.get("display name", "").strip(),
        cli_command=record.get("cli command", "").strip(),
        model=record.get("model", "").strip(),
        transport=record.get("transport", "").strip().lower(),
        quota_daily=quota_daily,
        quota_per_deliberation=quota_per_delib,
        permission_capability=record.get("permission capability", "").strip(),
        account_label=record.get("account label", "").strip(),
        health=record.get("health", "").strip().lower() or "unknown",
        inherits_fitness_from=_clean_optional(record.get("inherits fitness from")),
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"(none)", "none", "n/a", "-"}:
        return None
    return cleaned


def _parse_quota(quota: str) -> tuple[int | None, int | None]:
    """Parse a `daily/per-deliberation` cell.

    `unlimited`, blank, or `n/a` map to (None, None) — uncapped.
    Otherwise expect `<int>/<int>` and return both. Anything malformed
    is treated as uncapped to avoid the conductor refusing to route
    over a typo'd participants table.
    """
    cleaned = quota.strip().lower()
    if not cleaned or cleaned in {"unlimited", "n/a", "-"}:
        return (None, None)
    parts = cleaned.split("/")
    if len(parts) != 2:
        return (None, None)
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return (None, None)
