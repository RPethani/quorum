"""Read a deliberation file's YAML frontmatter.

The deliberation file is Markdown with a leading YAML frontmatter block
fenced by `---`. Everything below the second fence is prose — we don't
parse it here. The frontmatter alone is enough to drive routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---\s*(?:\n|$)", re.DOTALL)


@dataclass(frozen=True)
class DeliberationRoles:
    proposer: str | None = None
    critics: list[str] = field(default_factory=list)
    synthesizer: str | None = None
    decider: str | None = None
    extras: dict[str, str] = field(default_factory=dict)

    def for_role(self, role: str) -> str | None:
        """Return the explicitly-pinned handle for `role`, if any.

        `role == "critic"` returns the first declared critic — the
        routing engine still picks one critic at a time.
        """
        match role:
            case "proposer":
                return self.proposer
            case "critic":
                return self.critics[0] if self.critics else None
            case "synthesizer":
                return self.synthesizer
            case "decider":
                return self.decider
            case _:
                return self.extras.get(role)


@dataclass(frozen=True)
class DeliberationMeta:
    id: str
    title: str
    status: str
    roles: DeliberationRoles
    tags: list[str]
    final: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def load_deliberation(path: Path) -> DeliberationMeta:
    """Parse a deliberation file's frontmatter into a DeliberationMeta."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise DeliberationParseError(f"{path}: no YAML frontmatter found.")
    raw = yaml.safe_load(match.group("body")) or {}
    if not isinstance(raw, dict):
        raise DeliberationParseError(f"{path}: frontmatter is not a YAML mapping.")
    return _meta_from_raw(raw)


def _meta_from_raw(raw: dict[str, Any]) -> DeliberationMeta:
    roles_raw = raw.get("roles") or {}
    if not isinstance(roles_raw, dict):
        raise DeliberationParseError("frontmatter `roles` must be a mapping.")
    critics_raw = roles_raw.get("critics") or []
    if isinstance(critics_raw, str):
        critics = [critics_raw]
    elif isinstance(critics_raw, list):
        critics = [str(c) for c in critics_raw]
    else:
        critics = []

    known_role_keys = {"proposer", "critics", "synthesizer", "decider"}
    role_extras: dict[str, str] = {}
    for key, value in roles_raw.items():
        if key in known_role_keys or value is None:
            continue
        role_extras[str(key)] = str(value)

    roles = DeliberationRoles(
        proposer=_clean_handle(roles_raw.get("proposer")),
        critics=[c for c in (_clean_handle(c) for c in critics) if c],
        synthesizer=_clean_handle(roles_raw.get("synthesizer")),
        decider=_clean_handle(roles_raw.get("decider")),
        extras=role_extras,
    )
    tags_raw = raw.get("tags") or []
    tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []

    known_top: set[str] = {"id", "title", "status", "roles", "tags", "final"}
    extras = {k: v for k, v in raw.items() if k not in known_top}

    return DeliberationMeta(
        id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        status=str(raw.get("status", "DRAFT")),
        roles=roles,
        tags=tags,
        final=bool(raw.get("final", False)),
        extras=extras,
    )


def _clean_handle(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


class DeliberationParseError(RuntimeError):
    """Raised when a deliberation file cannot be parsed."""
