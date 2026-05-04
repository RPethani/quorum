"""The Message dataclass — one parsed turn from canvas.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Message:
    """One message in the conversation canvas.

    The canonical on-disk shape is the HTML-fenced block in
    `canvas.md` (see `docs-specs/canvas-redesign.md` S1). This is the
    parsed in-memory form. Bodies are raw markdown verbatim — any
    `artifact:<filename>` fenced blocks inside are the artifact
    parser's concern, not ours.
    """

    id: str
    """Stable identifier (e.g. ``msg-0042``). Used by retry endpoints."""

    author: str
    """Quorum handle including the leading ``@`` (e.g. ``@rakesh``)."""

    timestamp: datetime
    """UTC timestamp; emitted as ISO 8601 with the ``Z`` suffix."""

    body: str
    """Raw markdown body of the message; never the HTML fence wrappers."""
