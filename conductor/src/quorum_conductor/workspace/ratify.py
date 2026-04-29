"""Auto-ratify the outcome manifest when the seed deliberation decides.

Per design-doc §1.7:

> Even for concrete users, the manifest is established via deliberation
> #0001, not as an off-protocol artifact. … For concrete users the
> deliberation is fast (propose, **ratify, lock**).

When a DECISION (or OVERRIDE) lands on a deliberation whose frontmatter
declares `ratifies: outcome-manifest.md`, this module:

1. Pulls the canonical manifest content from the deliberation — preferring
   the latest SYNTHESIS body, falling back to the latest PROPOSAL.
2. Writes that content into `outcome-manifest.md` with frontmatter
   `status: LOCKED`.
3. Emits a `manifest_ratified` audit event.

The user never has to flip statuses by hand or paste anything between
files.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from ..events import Event, EventLogger
from ..paths import WorkspacePaths

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_RATIFIES_RE = re.compile(r"^ratifies:\s*(\S+)\s*$", re.MULTILINE)
_MOVE_HEADER_BLOCK_RE = re.compile(
    r"^###\s*\[(?P<type>[A-Z_]+)\][^\n]*\n(?P<body>.*?)(?=^###\s*\[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def maybe_ratify_manifest(
    paths: WorkspacePaths, deliberation_path: Path
) -> bool:
    """If `deliberation_path` ratifies the manifest and its terminal
    move was a DECISION/OVERRIDE, write the agreed content into
    `outcome-manifest.md` and lock it. Returns True if anything was
    written.

    Idempotent: if the manifest is already LOCKED, do nothing.
    """
    if not deliberation_path.is_file():
        return False
    body = deliberation_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(body)
    if not fm_match:
        return False
    if not _RATIFIES_RE.search(fm_match.group(1)):
        return False
    target = _RATIFIES_RE.search(fm_match.group(1))
    assert target is not None  # we just matched
    if target.group(1).strip() != "outcome-manifest.md":
        # Some other artifact — out of scope here. Future versions will
        # generalise this to all `ratifies:` targets.
        return False

    # The terminal move must be a DECISION/OVERRIDE. We find the last
    # move header in the body.
    moves = list(_MOVE_HEADER_BLOCK_RE.finditer(body))
    if not moves:
        return False
    last = moves[-1]
    if last.group("type") not in {"DECISION", "OVERRIDE"}:
        return False

    # Pick the canonical manifest content — latest SYNTHESIS, else
    # latest PROPOSAL.
    canonical = _pick_canonical_body(moves)
    if canonical is None:
        return False

    if not paths.outcome_manifest.is_file():
        return False
    current = paths.outcome_manifest.read_text(encoding="utf-8")
    if "status: LOCKED" in current:
        return False  # already ratified, idempotent

    new_body = _render_manifest(canonical)
    paths.outcome_manifest.write_text(new_body, encoding="utf-8")
    _bump_state_manifest_status(paths, "LOCKED")

    EventLogger(paths.events_jsonl).emit(
        _ManifestRatified(
            deliberation_id=_extract_id(fm_match.group(1)) or "",
            decided_by=_extract_decision_author(last.group(0)),
        )
    )
    return True


def _bump_state_manifest_status(paths: WorkspacePaths, new_status: str) -> None:
    """Mirror manifest status into state.yaml so the UI's progress read
    stays consistent with the file. The two surfaces are otherwise
    independent (state.yaml is the conductor's lifecycle log; the
    manifest file is the artifact); this is the only crosslink."""
    from .state import load_state, save_state

    try:
        state = load_state(paths.state_yaml)
    except Exception:
        return
    state.manifest.status = new_status
    save_state(paths.state_yaml, state)


def _pick_canonical_body(moves: list[re.Match[str]]) -> str | None:
    """Return the body text of the latest SYNTHESIS, else PROPOSAL."""
    for preferred in ("SYNTHESIS", "PROPOSAL"):
        for m in reversed(moves):
            if m.group("type") == preferred:
                return m.group("body").strip()
    return None


def _render_manifest(content: str) -> str:
    """Wrap the agreed content with the canonical manifest frontmatter."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return (
        "---\n"
        "status: LOCKED\n"
        "protocol_version: 0.1\n"
        f"created: {today}\n"
        f"locked_at: {today}\n"
        "template_used: null\n"
        "---\n\n"
        "# Outcome Manifest\n\n"
        "<!--\n"
        "  Auto-ratified by the conductor when the seed deliberation\n"
        "  reached a DECISION. Edit via the Raw editor if you need to\n"
        "  amend; agents will see the new version on subsequent moves.\n"
        "-->\n\n"
        f"{content.strip()}\n"
    )


def _extract_id(frontmatter: str) -> str | None:
    m = re.search(r'^id:\s*"?(\S+?)"?\s*$', frontmatter, re.MULTILINE)
    return m.group(1) if m else None


def _extract_decision_author(move_block: str) -> str:
    m = re.match(r"###\s*\[[A-Z_]+\]\s*(@\S+)", move_block)
    return m.group(1) if m else "@human"


# ---------------------------------------------------------------------- #
# Audit event
# ---------------------------------------------------------------------- #


from dataclasses import dataclass, field  # noqa: E402

from ..events.log import EVENT_SCHEMA_VERSION, _now_iso  # noqa: E402


@dataclass(frozen=True)
class _ManifestRatified(Event):
    """Emitted when the conductor auto-locks outcome-manifest.md."""

    deliberation_id: str = ""
    decided_by: str = ""

    def __init__(
        self,
        *,
        deliberation_id: str,
        decided_by: str,
        ts: str | None = None,
    ) -> None:
        object.__setattr__(self, "type", "manifest_ratified")
        object.__setattr__(self, "ts", ts or _now_iso())
        object.__setattr__(self, "schema_version", EVENT_SCHEMA_VERSION)
        object.__setattr__(self, "deliberation_id", deliberation_id)
        object.__setattr__(self, "decided_by", decided_by)


_ = field  # keep import warm; some linters drop dataclasses' field if unused.

__all__ = ["maybe_ratify_manifest"]
