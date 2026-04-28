"""Parse the `## Contributions` section of a deliberation file.

Returns the ordered list of moves present (by header) so the loop's
planner (4f) can decide what's next. We deliberately do not re-parse
move *bodies* here — `core/move_format.parse_header` is enough.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .move_format import MoveHeader, parse_header

_CONTRIB_HEADING = "## Contributions"
_NEXT_H2_PREFIX = "## "


@dataclass(frozen=True)
class ContributionsView:
    moves: tuple[MoveHeader, ...]

    def by_type(self, move_type: str) -> tuple[MoveHeader, ...]:
        return tuple(m for m in self.moves if m.move_type == move_type)

    def by_author(self, author: str) -> tuple[MoveHeader, ...]:
        return tuple(m for m in self.moves if m.author == author)

    def has(self, move_type: str) -> bool:
        return any(m.move_type == move_type for m in self.moves)


def parse_contributions(deliberation_path: Path) -> ContributionsView:
    """Read the deliberation file and return the moves under Contributions."""
    text = deliberation_path.read_text(encoding="utf-8")
    section = _extract_section(text)
    moves: list[MoveHeader] = []
    for line in section.splitlines():
        header = parse_header(line)
        if header is not None:
            moves.append(header)
    return ContributionsView(moves=tuple(moves))


def _extract_section(text: str) -> str:
    idx = text.find(_CONTRIB_HEADING)
    if idx == -1:
        return ""
    body_start = idx + len(_CONTRIB_HEADING)
    # Find the next H2 after Contributions; everything between is the
    # section body. Split on lines so a `## ` inside a fenced code block
    # would only matter at column zero.
    rest = text[body_start:]
    end = len(rest)
    cursor = 0
    while cursor < len(rest):
        line_end = rest.find("\n", cursor)
        line_end = len(rest) if line_end == -1 else line_end
        line = rest[cursor:line_end]
        if line.startswith(_NEXT_H2_PREFIX):
            end = cursor
            break
        cursor = line_end + 1
    return rest[:end]
