"""Read and append-write `canvas.md`.

The canvas is a single markdown file containing the workspace's
chronological conversation. Each message is fenced by HTML comments
so the file remains valid, human-readable markdown while the parser
stays robust to arbitrary content in message bodies (headings,
fenced blocks, even embedded HTML comments other than the fences).

File shape::

    <!-- msg:msg-0001 -->
    ## @rakesh · 2026-05-03T10:00:00Z

    Body here. Anything goes — including:

    ## A heading inside the body
    ```artifact:requirements.md
    # ...
    ```
    <!-- /msg -->

    <!-- msg:msg-0002 -->
    ## @claude-opus · 2026-05-03T10:00:15Z

    Reply.
    <!-- /msg -->

The single hard constraint on bodies: they must not contain the
literal string ``<!-- /msg -->``. No agent emits that string in
normal operation; if one ever does, we'll escape during write.

Message IDs are caller-assigned (typically ``msg-{n:04d}`` from a
counter held in `state.yaml`) so retries can address a specific
turn deterministically.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .message import Message

# Each message block: <!-- msg:ID -->\n## @author · ISO8601\n\nBODY\n<!-- /msg -->
_BLOCK_RE = re.compile(
    r"<!--\s*msg:(?P<id>[\w-]+)\s*-->\s*\n"
    r"##\s+(?P<author>@[\w.-]+)\s+·\s+(?P<ts>\S+)\s*\n"
    r"(?P<body>.*?)"
    r"<!--\s*/msg\s*-->",
    re.DOTALL,
)


def parse_canvas(path: Path) -> list[Message]:
    """Read ``canvas.md`` and return all messages in file order.

    Returns an empty list if the file is missing or empty.
    Malformed blocks are silently skipped (agents shouldn't produce
    them; the conductor is the only writer).
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return _parse_text(text)


def append_message(path: Path, msg: Message) -> None:
    """Append ``msg`` to ``canvas.md``.

    Creates the file if it doesn't exist, separates new blocks from
    prior content with a blank line for readability. This is the
    only sanctioned way to add a message — never edit in place,
    never rewrite the whole file.
    """
    chunk = _format_message(msg)
    if path.exists() and path.read_text(encoding="utf-8").strip():
        with path.open("a", encoding="utf-8") as f:
            f.write("\n\n" + chunk + "\n")
    else:
        path.write_text(chunk + "\n", encoding="utf-8")


# ---------------------------------------------------------------------- #
# Internals
# ---------------------------------------------------------------------- #


def _parse_text(text: str) -> list[Message]:
    out: list[Message] = []
    for m in _BLOCK_RE.finditer(text):
        out.append(
            Message(
                id=m.group("id"),
                author=m.group("author"),
                timestamp=_parse_timestamp(m.group("ts")),
                body=m.group("body").strip("\n"),
            )
        )
    return out


def _parse_timestamp(s: str) -> datetime:
    """Accept ``...Z`` and ``...+00:00`` ISO 8601 forms."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _format_message(msg: Message) -> str:
    return (
        f"<!-- msg:{msg.id} -->\n"
        f"## {msg.author} · {_format_timestamp(msg.timestamp)}\n"
        "\n"
        f"{msg.body}\n"
        "<!-- /msg -->"
    )


def _format_timestamp(ts: datetime) -> str:
    """Emit ``YYYY-MM-DDTHH:MM:SSZ`` — Quorum's canonical UTC form."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    iso = ts.astimezone(UTC).isoformat()
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso
