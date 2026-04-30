"""Turn protocol moves that route to the human into user-facing Asks.

The conductor's planner already identifies "this deliberation is waiting
on a manual-transport handle." This module looks at each such pending
item and synthesises an Ask in the shape the user can answer:

  expected DECISION on a deliberation with PROPOSAL/SYNTHESIS bodies
    → pick_one Ask whose options summarise each candidate
  expected ANSWER on a deliberation with a tagged QUESTION move
    → write Ask whose default_value is empty
  manifest-ratification (deliberation #0001 ratifies outcome-manifest.md
    with PROPOSAL/SYNTHESIS in body)
    → confirm Ask ("Lock this in?")

The generator is idempotent: a stable `source_move_id` per (deliberation,
expected_move_type) means re-running the generator on every tick won't
duplicate Asks. If the protocol state changes such that an open Ask is
no longer relevant (e.g. another agent's CRITIQUE invalidated the
options), we close the Ask with `closed_reason`.

This module is the *only* place that's allowed to create Asks. The HTTP
endpoint just calls in here on append, and the loop runner does the same
after each tick.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.contributions import parse_contributions
from ..core.deliberation import load_deliberation
from ..core.loop import PendingItem, plan
from ..paths import WorkspacePaths
from .asks import (
    Ask,
    AskOption,
    close_ask,
    create_ask,
    find_open_ask_for_move,
    list_open_asks,
)

_MOVE_BLOCK_RE = re.compile(
    r"^###\s*\[(?P<type>[A-Z_]+)\]\s+(?P<author>@\S+)\s+·\s+(?P<ts>\S+)"
    r"[^\n]*\n(?P<body>.*?)(?=^###\s*\[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def regenerate_asks(paths: WorkspacePaths) -> list[Ask]:
    """Rebuild the open-Ask set to match the planner's current view.

    Steps:
      0. Auto-advance: if the manifest is LOCKED and the next artifact
         doesn't have a deliberation yet, open one.
      1. Run the planner once.
      2. For every manual-blocked item, ensure an open Ask exists.
      3. Close any open Ask whose triggering deliberation no longer
         appears in the planner's manual list (reason: "no longer
         needed").

    Returns the list of Asks created in this pass (i.e. new Asks only).
    """
    created: list[Ask] = []
    try:
        from .auto_advance import maybe_open_next_artifact_deliberation

        maybe_open_next_artifact_deliberation(paths)
    except Exception:
        pass

    try:
        result = plan(paths)
    except Exception:
        return created

    manual_items = list(result.manual())
    expected_keys: set[str] = set()
    for item in manual_items:
        key = _source_move_id(item.deliberation.id, item.move_type)
        expected_keys.add(key)
        if find_open_ask_for_move(paths, source_move_id=key) is not None:
            continue
        ask = _build_ask_for_item(paths, item)
        if ask is not None:
            created.append(ask)

    for ask in list_open_asks(paths):
        if ask.source_move_id not in expected_keys and ask.source_move_id.startswith(
            "delib::"
        ):
            close_ask(paths, ask.id, reason="no longer needed")

    return created


def _build_ask_for_item(
    paths: WorkspacePaths, item: PendingItem
) -> Ask | None:
    """Create the right Ask shape for a manual-blocked planner item."""
    delib_id = item.deliberation.id
    move_type = item.move_type
    title = item.deliberation.title
    delib_path = item.deliberation_path

    if move_type == "DECISION":
        return _build_decision_ask(paths, delib_path, delib_id, title)
    if move_type == "ANSWER":
        return _build_answer_ask(paths, delib_path, delib_id, title)
    return None


# ---------------------------------------------------------------------- #
# Shape: pick_one for DECISION
# ---------------------------------------------------------------------- #


def _build_decision_ask(
    paths: WorkspacePaths,
    delib_path: Path,
    delib_id: str,
    title: str,
) -> Ask | None:
    options = _options_from_proposals(delib_path)
    if not options:
        # No proposals yet — fall back to a write Ask so the user can
        # write the decision body themselves.
        return create_ask(
            paths,
            question=f"Decide: {title}",
            why=(
                "Agents haven't proposed concrete options yet, but you're "
                "named as decider. Write the decision in your own words."
            ),
            shape="write",
            source_deliberation=delib_id,
            source_move_id=_source_move_id(delib_id, "DECISION"),
            target_move_type="DECISION",
        )

    return create_ask(
        paths,
        question=f"Decide: {title}",
        why=_decision_why(options),
        shape="pick_one",
        source_deliberation=delib_id,
        source_move_id=_source_move_id(delib_id, "DECISION"),
        target_move_type="DECISION",
        options=options,
    )


def _decision_why(options: list[AskOption]) -> str:
    n = len(options)
    if n == 1:
        return "One agent proposed a direction. Approve, or write your own."
    if n == 2:
        return "Two agents disagree on the direction. Pick one or write your own."
    return f"{n} candidate directions on the table. Pick one or write your own."


def _options_from_proposals(delib_path: Path) -> list[AskOption]:
    """Extract pick_one options from the latest PROPOSAL/SYNTHESIS bodies.

    Strategy: walk every move in `## Contributions`. Group by author. For
    each author, keep their LATEST PROPOSAL or SYNTHESIS body (synthesis
    wins if both exist). One option per author. The label is the author
    handle (without `@`); the summary is the first non-empty line of the
    `## Position` (or first paragraph if no Position section); the
    `expand` field carries the full body so the UI can render it on
    request.
    """
    if not delib_path.is_file():
        return []
    body = delib_path.read_text(encoding="utf-8")
    by_author: dict[str, tuple[str, str]] = {}  # author -> (move_type, body)
    for m in _MOVE_BLOCK_RE.finditer(body):
        mt = m.group("type")
        if mt not in {"PROPOSAL", "SYNTHESIS"}:
            continue
        author = m.group("author")
        text = (m.group("body") or "").strip()
        if not text:
            continue
        prev = by_author.get(author)
        # Synthesis wins over proposal; later wins among same type.
        if prev is None:
            by_author[author] = (mt, text)
            continue
        prev_mt, _ = prev
        if prev_mt == "PROPOSAL" and mt == "SYNTHESIS":
            by_author[author] = (mt, text)
        elif prev_mt == mt:
            by_author[author] = (mt, text)

    options: list[AskOption] = []
    for author, (move_type, text) in by_author.items():
        label = author.lstrip("@")
        if move_type == "SYNTHESIS":
            label = f"{label} (synthesis)"
        summary = _extract_summary(text)
        options.append(
            AskOption(
                value=author,
                label=label,
                summary=summary,
                expand=text,
            )
        )
    options.sort(key=lambda o: o.value)
    return options


def _extract_summary(body: str) -> str:
    """Pull a one-line summary out of a move body.

    Preference order:
      1. First non-empty line of the `## Position` section.
      2. First non-empty paragraph of the body.
    """
    pos = _section_text(body, "Position")
    if pos:
        for line in pos.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return _truncate(stripped, 280)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return _truncate(stripped, 280)
    return ""


def _section_text(body: str, heading: str) -> str:
    """Return the body of a `## <heading>` subsection, or empty."""
    pat = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<content>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(body)
    return (m.group("content") or "").strip() if m else ""


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------------- #
# Shape: write for ANSWER
# ---------------------------------------------------------------------- #


def _build_answer_ask(
    paths: WorkspacePaths,
    delib_path: Path,
    delib_id: str,
    title: str,
) -> Ask | None:
    """Build a write Ask when the planner says the human should ANSWER.

    For now we synthesize the question from the latest QUESTION move's
    body (or the deliberation's `## Question` section as a fallback). A
    richer extractor that picks out the specific phrase being asked is
    future work.
    """
    question_text = _latest_question_body(delib_path) or _deliberation_question(
        delib_path
    )
    if not question_text:
        question_text = title
    why = "An agent asked you a question; reply in your own words."
    return create_ask(
        paths,
        question=question_text,
        why=why,
        shape="write",
        source_deliberation=delib_id,
        source_move_id=_source_move_id(delib_id, "ANSWER"),
        target_move_type="ANSWER",
    )


def _latest_question_body(delib_path: Path) -> str:
    if not delib_path.is_file():
        return ""
    body = delib_path.read_text(encoding="utf-8")
    last: str | None = None
    for m in _MOVE_BLOCK_RE.finditer(body):
        if m.group("type") == "QUESTION":
            last = (m.group("body") or "").strip()
    return _extract_summary(last or "") if last else ""


def _deliberation_question(delib_path: Path) -> str:
    if not delib_path.is_file():
        return ""
    body = delib_path.read_text(encoding="utf-8")
    after_fm = re.sub(r"\A---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL)
    section = _section_text(after_fm, "Question")
    return _extract_summary(section) if section else ""


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _source_move_id(deliberation_id: str, move_type: str) -> str:
    """Stable key for the (deliberation, expected-move) pair.

    Idempotent generation depends on this. Two generator passes on the
    same workspace state must produce the same key so the second pass
    sees the existing Ask and skips creating a duplicate.
    """
    return f"delib::{deliberation_id}::{move_type}"


# Re-exports for the runner:
__all__ = ["regenerate_asks"]


# Avoid ruff F401 for imports kept warm above.
_ = (parse_contributions, load_deliberation)
