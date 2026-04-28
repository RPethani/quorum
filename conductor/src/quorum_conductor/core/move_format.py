"""Header-line parsing and minimal structural validation for moves.

Per design-doc §5 the canonical header line is:

    ### [MOVE_TYPE] @author · ISO-8601-timestamp [→ targets <REF>, <REF>]

The full per-section validator (4e) layers on top of this. This module
covers only what 4d needs: recognise the header, extract MOVE_TYPE and
@author, confirm the move type is a known one, and confirm the file is
not entirely empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# The full canonical move vocabulary (PROTOCOL.md §2).
KNOWN_MOVE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "PROPOSAL",
        "CRITIQUE",
        "QUESTION",
        "ANSWER",
        "SYNTHESIS",
        "DECISION",
        "DEPUTY_DECISION",
        "REVISION",
        "ARTIFACT_REVISION",
        "ABSTAIN",
        "EXPLANATION",
        "INTERJECTION",
        "OVERRIDE",
        "REOPEN",
        "DROP",
        "STEER",
        "CLARIFY",
    }
)

_HEADER_RE: Final = re.compile(
    r"^###\s+\[(?P<move_type>[A-Z_]+)\]\s+(?P<author>@[A-Za-z0-9_\-]+)"
    r"\s+·\s+(?P<timestamp>\S+)"
    r"(?:\s+→\s+targets\s+(?P<targets>.+?))?"
    r"\s*$"
)


@dataclass(frozen=True)
class MoveHeader:
    move_type: str
    author: str
    timestamp: str
    targets: str | None  # raw text of the "→ targets …" suffix, if present


def parse_header(line: str) -> MoveHeader | None:
    """Return the parsed header if `line` matches the canonical format.

    Does NOT verify that the move type is recognised — call
    `is_known_move_type(header.move_type)` for that. This split is
    deliberate: header parsing is structural; the vocabulary is policy.
    """
    match = _HEADER_RE.match(line.rstrip("\r\n"))
    if match is None:
        return None
    return MoveHeader(
        move_type=match["move_type"],
        author=match["author"],
        timestamp=match["timestamp"],
        targets=match["targets"],
    )


def find_first_header(text: str) -> MoveHeader | None:
    """Scan `text` for the first canonical move header. Returns None if none found."""
    for raw in text.splitlines():
        header = parse_header(raw)
        if header is not None:
            return header
    return None


def is_known_move_type(move_type: str) -> bool:
    return move_type in KNOWN_MOVE_TYPES


@dataclass(frozen=True)
class MoveValidation:
    ok: bool
    header: MoveHeader | None
    errors: list[str]


def validate_minimal(text: str, *, expected_move_type: str | None = None) -> MoveValidation:
    """Phase-4d validation: header present, recognised type, body non-empty.

    Full per-section validation (Alternatives I considered, Summary line,
    EXPLANATION grounding, etc.) lands in Phase 4e and supersedes this.
    """
    errors: list[str] = []
    if not text.strip():
        return MoveValidation(ok=False, header=None, errors=["empty output"])

    header = find_first_header(text)
    if header is None:
        return MoveValidation(
            ok=False,
            header=None,
            errors=[
                "no canonical move header found "
                "(expected `### [MOVE_TYPE] @author · ISO-8601-timestamp`)",
            ],
        )

    if not is_known_move_type(header.move_type):
        errors.append(
            f"unknown move type {header.move_type!r}; "
            f"known: {', '.join(sorted(KNOWN_MOVE_TYPES))}"
        )

    if expected_move_type is not None and header.move_type != expected_move_type:
        errors.append(
            f"expected move type {expected_move_type!r}, got {header.move_type!r}"
        )

    return MoveValidation(ok=not errors, header=header, errors=errors)
