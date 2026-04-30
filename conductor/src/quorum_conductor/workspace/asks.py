"""The Ask abstraction — the only thing the user interacts with after setup.

An Ask is generated whenever the protocol routes to the human. It wraps a
plain-English question and one of four answer shapes (`confirm`, `pick_one`,
`pick_any`, `write`). When the user submits an answer, the Ask is converted
back into a protocol move (DECISION / ANSWER / OVERRIDE) and appended to the
source deliberation via the existing `append_move` path.

See `docs-specs/asks-ux-overhaul.md` for the design and rationale.

Storage: one JSON file per Ask under `asks/`, with a small
`asks/index.json` for cheap listing. We use file-per-record (not a single
SQLite db) to stay consistent with the rest of the workspace, which is
file-shaped on purpose so users can read it with `cat`.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..paths import WorkspacePaths

AskShape = Literal["confirm", "pick_one", "pick_any", "write"]
AskStatus = Literal["open", "answered", "closed"]

SCHEMA_VERSION = 1


class AskError(RuntimeError):
    """Raised on Ask validation or storage problems."""


@dataclass(frozen=True)
class AskOption:
    """One choice in a `pick_one` or `pick_any` Ask."""

    value: str
    label: str
    summary: str = ""
    expand: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("summary"):
            d.pop("summary")
        if not d.get("expand"):
            d.pop("expand")
        return d


@dataclass(frozen=True)
class Ask:
    """A user-facing question. See module docstring."""

    id: str
    created_at: str
    question: str
    why: str
    shape: AskShape
    source_deliberation: str
    source_move_id: str
    target_move_type: str
    options: list[AskOption] = field(default_factory=list)
    min_select: int | None = None
    max_select: int | None = None
    default_value: str | None = None
    status: AskStatus = "open"
    answered_at: str | None = None
    answer: dict[str, Any] | None = None
    closed_reason: str | None = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "status": self.status,
            "question": self.question,
            "why": self.why,
            "shape": self.shape,
            "source_deliberation": self.source_deliberation,
            "source_move_id": self.source_move_id,
            "target_move_type": self.target_move_type,
        }
        if self.options:
            d["options"] = [o.to_dict() for o in self.options]
        for key in ("min_select", "max_select", "default_value"):
            v = getattr(self, key)
            if v is not None:
                d[key] = v
        if self.answered_at:
            d["answered_at"] = self.answered_at
        if self.answer is not None:
            d["answer"] = self.answer
        if self.closed_reason:
            d["closed_reason"] = self.closed_reason
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Ask:
        opts_raw = raw.get("options") or []
        options = [
            AskOption(
                value=str(o["value"]),
                label=str(o.get("label", o["value"])),
                summary=str(o.get("summary", "")),
                expand=str(o.get("expand", "")),
            )
            for o in opts_raw
        ]
        return cls(
            id=str(raw["id"]),
            created_at=str(raw["created_at"]),
            question=str(raw["question"]),
            why=str(raw.get("why", "")),
            shape=_validate_shape(raw["shape"]),
            source_deliberation=str(raw["source_deliberation"]),
            source_move_id=str(raw["source_move_id"]),
            target_move_type=str(raw["target_move_type"]),
            options=options,
            min_select=_as_int_or_none(raw.get("min_select")),
            max_select=_as_int_or_none(raw.get("max_select")),
            default_value=raw.get("default_value"),
            status=_validate_status(raw.get("status", "open")),
            answered_at=raw.get("answered_at"),
            answer=raw.get("answer"),
            closed_reason=raw.get("closed_reason"),
            schema_version=int(raw.get("schema_version", SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------- #
# Storage
# ---------------------------------------------------------------------- #


def _ensure_dir(paths: WorkspacePaths) -> None:
    paths.asks.mkdir(parents=True, exist_ok=True)


def _ask_path(paths: WorkspacePaths, ask_id: str) -> Path:
    return paths.asks / f"{ask_id}.json"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_asks(paths: WorkspacePaths) -> list[Ask]:
    """Return all Asks in the workspace, newest first."""
    if not paths.asks.is_dir():
        return []
    out: list[Ask] = []
    for path in paths.asks.glob("ask-*.json"):
        try:
            out.append(load_ask(path))
        except Exception:
            continue
    out.sort(key=lambda a: a.created_at, reverse=True)
    return out


def list_open_asks(paths: WorkspacePaths) -> list[Ask]:
    return [a for a in list_asks(paths) if a.status == "open"]


def get_ask(paths: WorkspacePaths, ask_id: str) -> Ask | None:
    path = _ask_path(paths, ask_id)
    if not path.is_file():
        return None
    return load_ask(path)


def load_ask(path: Path) -> Ask:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ask.from_dict(raw)


def save_ask(paths: WorkspacePaths, ask: Ask) -> Path:
    _ensure_dir(paths)
    path = _ask_path(paths, ask.id)
    body = json.dumps(ask.to_dict(), indent=2, sort_keys=False) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def next_ask_id(paths: WorkspacePaths) -> str:
    """Return the next free `ask-NNNN` id."""
    _ensure_dir(paths)
    used = 0
    pat = re.compile(r"ask-(\d+)\.json$")
    for p in paths.asks.glob("ask-*.json"):
        m = pat.search(p.name)
        if m:
            used = max(used, int(m.group(1)))
    return f"ask-{used + 1:04d}"


def find_open_ask_for_move(
    paths: WorkspacePaths, *, source_move_id: str
) -> Ask | None:
    """Return the open Ask that points at `source_move_id`, if any.

    Used by the generator to avoid creating duplicate Asks for the same
    pending move on every loop tick.
    """
    for ask in list_open_asks(paths):
        if ask.source_move_id == source_move_id:
            return ask
    return None


# ---------------------------------------------------------------------- #
# Lifecycle
# ---------------------------------------------------------------------- #


def create_ask(
    paths: WorkspacePaths,
    *,
    question: str,
    why: str,
    shape: AskShape,
    source_deliberation: str,
    source_move_id: str,
    target_move_type: str,
    options: list[AskOption] | None = None,
    min_select: int | None = None,
    max_select: int | None = None,
    default_value: str | None = None,
) -> Ask:
    """Create and persist a new open Ask."""
    if shape in {"pick_one", "pick_any"} and not options:
        raise AskError(f"shape={shape} requires options")
    if shape == "pick_one" and options is not None and min_select not in (None, 1):
        raise AskError("pick_one cannot set min_select")
    ask = Ask(
        id=next_ask_id(paths),
        created_at=_now_iso(),
        question=question.strip(),
        why=why.strip(),
        shape=shape,
        source_deliberation=source_deliberation,
        source_move_id=source_move_id,
        target_move_type=target_move_type.upper(),
        options=list(options or []),
        min_select=min_select,
        max_select=max_select,
        default_value=default_value,
        status="open",
    )
    save_ask(paths, ask)
    return ask


def mark_answered(
    paths: WorkspacePaths,
    ask_id: str,
    *,
    answer: dict[str, Any],
) -> Ask:
    """Mark an open Ask as answered with the given payload. Idempotent —
    a second call returns the existing answered record unchanged."""
    existing = get_ask(paths, ask_id)
    if existing is None:
        raise AskError(f"ask {ask_id} not found")
    if existing.status == "answered":
        return existing
    if existing.status == "closed":
        raise AskError(f"ask {ask_id} is closed; cannot answer")
    updated = Ask(
        id=existing.id,
        created_at=existing.created_at,
        question=existing.question,
        why=existing.why,
        shape=existing.shape,
        source_deliberation=existing.source_deliberation,
        source_move_id=existing.source_move_id,
        target_move_type=existing.target_move_type,
        options=existing.options,
        min_select=existing.min_select,
        max_select=existing.max_select,
        default_value=existing.default_value,
        status="answered",
        answered_at=_now_iso(),
        answer=dict(answer),
    )
    save_ask(paths, updated)
    return updated


def close_ask(
    paths: WorkspacePaths, ask_id: str, *, reason: str
) -> Ask | None:
    """Mark an Ask as closed (no longer needed)."""
    existing = get_ask(paths, ask_id)
    if existing is None or existing.status != "open":
        return existing
    updated = Ask(
        id=existing.id,
        created_at=existing.created_at,
        question=existing.question,
        why=existing.why,
        shape=existing.shape,
        source_deliberation=existing.source_deliberation,
        source_move_id=existing.source_move_id,
        target_move_type=existing.target_move_type,
        options=existing.options,
        min_select=existing.min_select,
        max_select=existing.max_select,
        default_value=existing.default_value,
        status="closed",
        closed_reason=reason,
    )
    save_ask(paths, updated)
    return updated


# ---------------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------------- #


def validate_answer(ask: Ask, answer: dict[str, Any]) -> None:
    """Raise AskError if `answer` doesn't match the Ask's shape contract.

    Answer payload by shape:
      confirm  -> {"value": "yes" | "no" | "more_info", "note"?: str}
      pick_one -> {"value": <option.value>, "note"?: str}
                  or {"value": "__custom__", "text": <str>} for the
                  "None of the above" escape hatch
      pick_any -> {"values": [<option.value>, ...], "note"?: str}
      write    -> {"text": <str>}
    """
    if ask.status != "open":
        raise AskError(f"ask {ask.id} is not open (status={ask.status})")

    if ask.shape == "confirm":
        v = answer.get("value")
        if v not in {"yes", "no", "more_info"}:
            raise AskError("confirm answer must be yes|no|more_info")
        return

    if ask.shape == "pick_one":
        v = answer.get("value")
        if v == "__custom__":
            text = answer.get("text", "")
            if not isinstance(text, str) or not text.strip():
                raise AskError("custom pick_one requires non-empty text")
            return
        valid = {o.value for o in ask.options}
        if v not in valid:
            raise AskError(f"pick_one value {v!r} not in options {sorted(valid)}")
        return

    if ask.shape == "pick_any":
        vs = answer.get("values")
        if not isinstance(vs, list) or not all(isinstance(x, str) for x in vs):
            raise AskError("pick_any answer requires values: list[str]")
        valid = {o.value for o in ask.options}
        bad = [x for x in vs if x not in valid]
        if bad:
            raise AskError(f"pick_any values {bad!r} not in options")
        if ask.min_select is not None and len(vs) < ask.min_select:
            raise AskError(f"pick_any requires at least {ask.min_select} selections")
        if ask.max_select is not None and len(vs) > ask.max_select:
            raise AskError(f"pick_any allows at most {ask.max_select} selections")
        if len(set(vs)) != len(vs):
            raise AskError("pick_any values must be unique")
        return

    if ask.shape == "write":
        text = answer.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise AskError("write answer requires non-empty text")
        return

    raise AskError(f"unknown shape {ask.shape!r}")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _validate_shape(value: Any) -> AskShape:
    if value == "confirm":
        return "confirm"
    if value == "pick_one":
        return "pick_one"
    if value == "pick_any":
        return "pick_any"
    if value == "write":
        return "write"
    raise AskError(f"invalid shape: {value!r}")


def _validate_status(value: Any) -> AskStatus:
    if value == "open":
        return "open"
    if value == "answered":
        return "answered"
    if value == "closed":
        return "closed"
    raise AskError(f"invalid status: {value!r}")


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "Ask",
    "AskError",
    "AskOption",
    "AskShape",
    "AskStatus",
    "SCHEMA_VERSION",
    "close_ask",
    "create_ask",
    "find_open_ask_for_move",
    "get_ask",
    "list_asks",
    "list_open_asks",
    "load_ask",
    "mark_answered",
    "next_ask_id",
    "save_ask",
    "validate_answer",
]
