"""Full structural validator for protocol moves.

The minimal validator (`core/move_format.validate_minimal`) checks that
the output has a canonical header line and a recognised move type. This
module layers on top: required-section presence (driven by the on-disk
template files at `protocol/templates/<move_type>.md`), plus a small
catalogue of anti-vacuousness rules per design-doc §5:

  * DECISION         — Summary line: ≥30 chars, ≤120 chars, plain English,
                        not in the reject-pattern list.
  * PROPOSAL         — Alternatives I considered: must have *something*
                        beyond a literal "none" or template comment.
  * EXPLANATION      — anti-confabulation:
                        * 'What I couldn't find in the workspace' must be
                          present and non-empty.
                        * 'Sources cited' must be present and non-empty.

Templates are the structural source of truth. We extract section names
from the templates at runtime (cached) so editing a template's
required-sections list automatically updates the validator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .move_format import (
    MoveHeader,
    is_known_move_type,
    validate_minimal,
)

# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class FullMoveValidation:
    """Strictly-richer counterpart to `MoveValidation`.

    `errors` is the fail list the agent / human will read; if non-empty
    the move is rejected. `warnings` are protocol-relevant nits we track
    but do not gate on.
    """

    ok: bool
    header: MoveHeader | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def reasons(self) -> str:
        return "; ".join(self.errors) if self.errors else "ok"


def validate_move(
    text: str,
    *,
    expected_move_type: str | None,
    templates_dir: Path,
    deliberation_ratifies: str | None = None,
) -> FullMoveValidation:
    """Run the full structural + anti-vacuousness validation.

    `templates_dir` should be the workspace's `protocol/templates/` (so
    edits to the workspace's own templates are honoured); falls back to
    the bundled templates if absent.

    `deliberation_ratifies` is the value of the source deliberation's
    `ratifies:` frontmatter field, if any. Used to enforce structural
    constraints that depend on the deliberation's role — currently
    just one: DROP is not permitted on the seed manifest deliberation
    (the one that ratifies `outcome-manifest.md`). Letting DROP land
    there leaves the manifest stuck in `DRAFTING` with no agent
    available to retry, and without the manifest there's no plan to
    work against — the workspace becomes meaningless.

    Per-artifact ratification deliberations (e.g., the deliberation
    that ratifies `recommendation.md`) are NOT protected by this
    rule — the user must be free to drop work on a specific artifact
    if they decide it's no longer relevant.

    See `docs-specs/system-flow-stages.md` open question #1.
    """
    minimal = validate_minimal(text, expected_move_type=expected_move_type)
    if not minimal.ok or minimal.header is None:
        # Header missing / unknown / mismatched — nothing further to check.
        return FullMoveValidation(
            ok=False,
            header=minimal.header,
            errors=list(minimal.errors),
        )

    header = minimal.header
    move_type = header.move_type

    errors: list[str] = []
    warnings: list[str] = []

    if not is_known_move_type(move_type):
        errors.append(f"unknown move type {move_type!r}")
        return FullMoveValidation(ok=False, header=header, errors=errors)

    template_sections = _required_sections_for(move_type, templates_dir)
    move_sections = _h2_sections(text)

    for section in template_sections:
        if section not in move_sections:
            errors.append(f"required section missing: {section!r}")

    # Anti-vacuousness rules.
    if move_type == "DECISION":
        errors.extend(_check_decision_summary(move_sections))
    if move_type == "PROPOSAL":
        errors.extend(_check_proposal_alternatives(move_sections))
    if move_type == "EXPLANATION":
        errors.extend(_check_explanation(move_sections))

    # Structural rule: DROP is forbidden on the seed manifest
    # deliberation. Per-artifact ratification deliberations remain
    # DROP-able — the user may abandon work on a specific artifact.
    if (
        move_type == "DROP"
        and deliberation_ratifies
        and deliberation_ratifies.strip().lower() == "outcome-manifest.md"
    ):
        errors.append(
            "DROP is not permitted on the seed deliberation (which "
            "ratifies the outcome manifest). Without a ratified "
            "manifest there is no plan to work against. Use DECISION "
            "to ratify or OVERRIDE to terminate, then archive the "
            "workspace if you want to abandon the project."
        )

    return FullMoveValidation(
        ok=not errors,
        header=header,
        errors=errors,
        warnings=warnings,
    )


def render_validation_feedback(validation: FullMoveValidation) -> str:
    """Render a short, agent-readable explanation of what failed.

    Used by the invoker on the one-retry path to tell the agent exactly
    what to fix.
    """
    lines: list[str] = ["Your previous response failed validation."]
    if validation.errors:
        lines.append("")
        lines.append("Errors:")
        for err in validation.errors:
            lines.append(f"  - {err}")
    lines.append("")
    lines.append(
        "Produce the move again. Every required section must be present "
        "(write 'none' if a section truly does not apply). Do not skip "
        "sections, do not combine sections, do not paraphrase the section "
        "headings."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# Section discovery
# ---------------------------------------------------------------------- #


_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
# Lines like "## Spawns ADR?" should match cleanly. We strip trailing
# punctuation only when comparing template -> move so "Spawns ADR?" in
# the template equals "Spawns ADR?" in the move.


def _h2_sections(text: str) -> dict[str, str]:
    """Return {section_title: body} for every `## Heading` block.

    Body excludes the heading line itself; trailing whitespace is trimmed.
    """
    matches = list(_H2_RE.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group("title").strip()
        body = text[body_start:body_end].strip("\n").rstrip()
        out[title] = body
    return out


@lru_cache(maxsize=64)
def _required_sections_for(move_type: str, templates_dir_str: str | None) -> tuple[str, ...]:
    """Return the ordered list of required H2 section titles for `move_type`.

    Looks up `<templates_dir>/<move_type_lower>.md` first, then falls
    back to a bundled copy. Result is cached because templates rarely
    change at runtime (and re-reading from disk on every move is a
    small but real cost).
    """
    candidates: list[Path] = []
    if templates_dir_str:
        candidates.append(Path(templates_dir_str) / f"{move_type.lower()}.md")
    bundled = _bundled_template(move_type)
    if bundled is not None:
        candidates.append(bundled)

    for candidate in candidates:
        if candidate.is_file():
            sections = _h2_sections(candidate.read_text(encoding="utf-8"))
            return tuple(sections.keys())
    return ()


def _required_sections_for_path(move_type: str, templates_dir: Path) -> tuple[str, ...]:
    """Wrapper that turns the Path into a string for cache compatibility."""
    return _required_sections_for(move_type, str(templates_dir) if templates_dir else None)


def _bundled_template(move_type: str) -> Path | None:
    """Find the canonical template shipped with the conductor's repo."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "protocol" / "templates" / f"{move_type.lower()}.md"
        if candidate.is_file():
            return candidate
    return None


# Public alias for consistency with the rest of `core/`.
required_sections_for = _required_sections_for_path


# ---------------------------------------------------------------------- #
# Anti-vacuousness helpers
# ---------------------------------------------------------------------- #


# Reject-pattern list for DECISION Summary lines (design-doc §5).
_VACUOUS_DECISION_SUMMARY_RE = re.compile(
    r"^\s*("
    r"approved\.?|"
    r"approve\.?|"
    r"decided\s*yes\.?|"
    r"decided\s*no\.?|"
    r"we'?ll\s+do\s+this\.?|"
    r"go\s+with\s+it\.?|"
    r"yes\.?|"
    r"no\.?"
    r")\s*$",
    re.IGNORECASE,
)


def _check_decision_summary(sections: dict[str, str]) -> list[str]:
    body = sections.get("Summary line")
    if body is None:
        return []  # missing-section error already raised upstream
    cleaned = _strip_template_comments(body).strip()
    if not cleaned:
        return ["DECISION 'Summary line' is empty"]
    if len(cleaned) < 30:
        return [
            f"DECISION 'Summary line' is too short ({len(cleaned)} chars; "
            "design-doc §5 requires ≥30 chars of substantive summary)"
        ]
    if len(cleaned) > 120:
        return [
            f"DECISION 'Summary line' is too long ({len(cleaned)} chars; "
            "design-doc §5 caps it at 120 chars)"
        ]
    if _VACUOUS_DECISION_SUMMARY_RE.match(cleaned):
        return [
            "DECISION 'Summary line' is vacuous "
            "(matches a reject pattern: 'approved' / 'decided yes' / etc.). "
            "Write a specific one-sentence summary of what was decided."
        ]
    return []


def _check_proposal_alternatives(sections: dict[str, str]) -> list[str]:
    body = sections.get("Alternatives I considered")
    if body is None:
        return []  # presence already checked
    cleaned = _strip_template_comments(body).strip()
    if not cleaned:
        return [
            "PROPOSAL 'Alternatives I considered' is empty. "
            "Even \"none — this is the obvious choice\" is acceptable, but "
            "must be explicit."
        ]
    return []


def _check_explanation(sections: dict[str, str]) -> list[str]:
    errors: list[str] = []
    sources = sections.get("Sources cited")
    if sources is None or not _strip_template_comments(sources).strip():
        errors.append(
            "EXPLANATION 'Sources cited' is empty. "
            "Every workspace-specific claim must cite a source."
        )
    gaps = sections.get("What I couldn't find in the workspace")
    if gaps is None or not _strip_template_comments(gaps).strip():
        errors.append(
            "EXPLANATION 'What I couldn't find in the workspace' is empty. "
            "Write 'nothing relevant was missing' if all clarifications were "
            "fully grounded; otherwise list the gaps explicitly."
        )
    return errors


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_template_comments(text: str) -> str:
    """Strip `<!-- guidance -->` comments left over from the template."""
    return _HTML_COMMENT_RE.sub("", text)
