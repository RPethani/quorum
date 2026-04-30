"""Convert a user's Ask answer into the corresponding protocol move.

An Ask is the user-facing surface; the protocol underneath still owns the
audit trail. When the user submits an answer:

  1. We validate the answer against the Ask shape.
  2. We render a protocol move (DECISION / ANSWER / OVERRIDE) from a
     fixed template.
  3. We append it to the source deliberation via the existing
     `append_move` path — so frontmatter status flips, ratification runs,
     inbox notifications fire, all unchanged.
  4. We mark the Ask `answered`.

The shape-specific rendering lives in `_render_*` helpers below. New
shapes / move-types extend that table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..paths import WorkspacePaths
from .asks import Ask, AskError, get_ask, mark_answered, validate_answer
from .deliberation_file import append_move, update_inboxes_from_move
from .ratify import maybe_ratify_manifest


class AnswerError(RuntimeError):
    """Raised when an answer cannot be converted into a protocol move."""


def answer_ask(
    paths: WorkspacePaths,
    ask_id: str,
    *,
    answer: dict[str, Any],
    author: str,
) -> Ask:
    """Apply `answer` to the Ask, write the corresponding move, mark answered.

    Idempotent: if the Ask is already answered, returns the existing
    record without writing another move. Raises AnswerError on shape /
    state mismatches.
    """
    ask = get_ask(paths, ask_id)
    if ask is None:
        raise AnswerError(f"ask {ask_id} not found")
    if ask.status == "answered":
        return ask
    if ask.status == "closed":
        raise AnswerError(f"ask {ask_id} is closed; cannot answer")

    try:
        validate_answer(ask, answer)
    except AskError as exc:
        raise AnswerError(str(exc)) from exc

    delib_path = _find_deliberation_file(paths, ask.source_deliberation)
    if delib_path is None:
        raise AnswerError(
            f"deliberation file for {ask.source_deliberation} not found"
        )

    move_text = _render_move(ask=ask, answer=answer, author=author)
    append_move(delib_path, move_text)
    update_inboxes_from_move(
        move_text,
        inbox_dir=paths.inbox,
        deliberation_id=ask.source_deliberation,
        move_type=ask.target_move_type,
        author=author,
    )
    maybe_ratify_manifest(paths, delib_path)

    return mark_answered(paths, ask.id, answer=answer)


# ---------------------------------------------------------------------- #
# Move rendering
# ---------------------------------------------------------------------- #


def _render_move(*, ask: Ask, answer: dict[str, Any], author: str) -> str:
    """Render the protocol move text from a validated answer."""
    move_type = ask.target_move_type.upper()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"### [{move_type}] {author} · {timestamp}"

    body = _render_body(ask=ask, answer=answer)
    return f"{header}\n\n{body}\n"


def _render_body(*, ask: Ask, answer: dict[str, Any]) -> str:
    if ask.shape == "confirm":
        return _render_confirm(ask=ask, answer=answer)
    if ask.shape == "pick_one":
        return _render_pick_one(ask=ask, answer=answer)
    if ask.shape == "pick_any":
        return _render_pick_any(ask=ask, answer=answer)
    if ask.shape == "write":
        return _render_write(ask=ask, answer=answer)
    raise AnswerError(f"unknown shape: {ask.shape}")


def _render_confirm(*, ask: Ask, answer: dict[str, Any]) -> str:
    value = answer["value"]
    note = (answer.get("note") or "").strip()
    decision_word = {"yes": "Approved", "no": "Declined", "more_info": "Need more info"}[
        value
    ]
    parts = [f"## {ask.target_move_type.title()}", "", decision_word + "."]
    if ask.question:
        parts.extend(["", f"_Question:_ {ask.question}"])
    if note:
        parts.extend(["", "## Reasoning", "", note])
    return "\n".join(parts)


def _render_pick_one(*, ask: Ask, answer: dict[str, Any]) -> str:
    value = answer["value"]
    note = (answer.get("note") or "").strip()
    if value == "__custom__":
        text = (answer.get("text") or "").strip()
        parts = [f"## {ask.target_move_type.title()}", "", text]
        if ask.question:
            parts.extend(["", f"_In response to:_ {ask.question}"])
        return "\n".join(parts)

    chosen = next((o for o in ask.options if o.value == value), None)
    if chosen is None:
        raise AnswerError(f"option {value!r} not in Ask {ask.id}")

    parts = [f"## {ask.target_move_type.title()}", ""]
    parts.append(f"Picked: **{chosen.label}** (proposed by {chosen.value}).")
    if chosen.summary:
        parts.extend(["", chosen.summary])
    if note:
        parts.extend(["", "## Reasoning", "", note])
    return "\n".join(parts)


def _render_pick_any(*, ask: Ask, answer: dict[str, Any]) -> str:
    values = answer["values"]
    note = (answer.get("note") or "").strip()
    chosen = [o for o in ask.options if o.value in values]
    parts = [f"## {ask.target_move_type.title()}", ""]
    parts.append("Selected:")
    for o in chosen:
        suffix = f" — {o.summary}" if o.summary else ""
        parts.append(f"- **{o.label}** ({o.value}){suffix}")
    if note:
        parts.extend(["", "## Reasoning", "", note])
    return "\n".join(parts)


def _render_write(*, ask: Ask, answer: dict[str, Any]) -> str:
    text = (answer.get("text") or "").strip()
    parts = [f"## {ask.target_move_type.title()}", "", text]
    if ask.question:
        parts.extend(["", f"_In response to:_ {ask.question}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _find_deliberation_file(
    paths: WorkspacePaths, deliberation_id: str
) -> Path | None:
    if not paths.deliberations.is_dir():
        return None
    target_prefix = f"{deliberation_id}-"
    for p in paths.deliberations.glob(f"{target_prefix}*.md"):
        return p
    # Last-ditch: glob by id-only.
    for p in paths.deliberations.glob(f"{deliberation_id}*.md"):
        return p
    return None


__all__ = ["answer_ask", "AnswerError"]
