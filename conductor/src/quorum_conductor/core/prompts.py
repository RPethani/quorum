"""Render the standing prompt for a single invocation.

The on-disk standing prompt at `prompts/agent-standing-prompt.md` is
sectioned by `## AUGMENTATION — <name>` (and one `## BASE — …`) so that
the conductor can extract a subset for a given (role, mode) pair.

Per the prompt's own composition rules:

  BASE
  → context-discipline   (always)
  → permission-discipline (always)
  → role-specific        (explainer | bootstrapper | none)
  → mode-specific        (autonomous | deputy-decider | none)
  → per-handle override  (last)

Anything not in that order is appended after in the order it appears in
the file. Unknown augmentation names are ignored — better to skip than
to crash if the prompt file gains a section we don't recognise yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .deliberation import DeliberationMeta
from .participants import Participant

# Match a section heading. Tolerant of "—", "-", or "—" as the dash.
# The captured `name` excludes any trailing parenthetical descriptor
# (e.g. "context-discipline (always applied)" -> "context-discipline")
# so callers can look up sections by their canonical short name.
_SECTION_RE = re.compile(
    r"^##\s+(?P<kind>BASE|AUGMENTATION)\s*[-—]\s*(?P<name>[^\n(]+?)\s*(?:\(.*)?$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class _Section:
    kind: str  # "BASE" | "AUGMENTATION"
    name: str  # normalised, e.g. "context-discipline"
    body: str  # everything between this heading and the next ## heading


def _split_sections(text: str) -> list[_Section]:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return []
    sections: list[_Section] = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Body excludes the trailing blank line(s) before the next heading.
        body = text[body_start:body_end].strip("\n")
        name = m.group("name").strip().lower().replace(" ", "-")
        sections.append(_Section(kind=m.group("kind"), name=name, body=body))
    return sections


def _format_section(section: _Section) -> str:
    suffix = "" if section.kind == "BASE" else f" — {section.name}"
    return f"## {section.kind}{suffix}\n\n{section.body.rstrip()}\n"


@dataclass(frozen=True)
class PromptInputs:
    """Everything `render_prompt` needs to produce a final prompt."""

    handle: Participant
    role: str
    deliberation: DeliberationMeta
    mode: str  # "interactive" | "autonomous"
    standing_prompt_path: Path
    overrides_dir: Path
    workspace_root: Path
    deputy_active: bool = False  # set by the loop when human-timeout fires
    move_type: str | None = None  # what we're asking the agent to produce


def render_prompt(inputs: PromptInputs) -> str:
    """Return the complete prompt to feed the CLI on stdin."""
    prompt = inputs.standing_prompt_path.read_text(encoding="utf-8")
    sections = _split_sections(prompt)
    by_name = {(s.kind, s.name): s for s in sections}

    selected: list[_Section] = []
    base = next((s for s in sections if s.kind == "BASE"), None)
    if base is not None:
        selected.append(base)

    # Always-applied augmentations.
    for always in ("context-discipline", "permission-discipline"):
        sec = by_name.get(("AUGMENTATION", always))
        if sec is not None:
            selected.append(sec)

    # Role-specific.
    role_aug = _role_to_augmentation(inputs.role)
    if role_aug is not None:
        sec = by_name.get(("AUGMENTATION", role_aug))
        if sec is not None:
            selected.append(sec)

    # Mode-specific.
    if inputs.mode == "autonomous":
        sec = by_name.get(("AUGMENTATION", "autonomous-mode"))
        if sec is not None:
            selected.append(sec)
    if inputs.deputy_active:
        sec = by_name.get(("AUGMENTATION", "deputy-decider"))
        if sec is not None:
            selected.append(sec)

    rendered = "\n".join(_format_section(s) for s in selected)

    # Per-handle override, if present.
    override = _read_override(inputs.overrides_dir, inputs.handle.handle)
    if override:
        rendered += f"\n## OVERRIDE — {inputs.handle.handle}\n\n{override.rstrip()}\n"

    rendered += _task_framing(inputs)
    rendered = _replace_placeholders(rendered, inputs)
    return rendered


def _role_to_augmentation(role: str) -> str | None:
    if role == "explainer":
        return "explainer"
    if role == "bootstrapper":
        return "bootstrapper"
    return None


def _read_override(overrides_dir: Path, handle: str) -> str | None:
    candidate = overrides_dir / f"{handle}.md"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return None


def _task_framing(inputs: PromptInputs) -> str:
    move_type_line = (
        f"You are being invoked as the {inputs.role.upper()} for deliberation "
        f"#{inputs.deliberation.id} ({inputs.deliberation.title}).\n"
    )
    if inputs.move_type:
        move_type_line += (
            f"Produce a {inputs.move_type} move per "
            f"`protocol/templates/{inputs.move_type.lower()}.md`. "
            "All required sections must be present.\n"
        )
    return (
        "\n## TASK\n\n"
        + move_type_line
        + f"\nWorkspace root: {inputs.workspace_root}\n"
        + f"Your handle: {inputs.handle.handle}\n"
    )


def _replace_placeholders(text: str, inputs: PromptInputs) -> str:
    """Substitute `<handle>` and `@<handle>` placeholders in the standing prompt body."""
    handle = inputs.handle.handle
    bare = handle.lstrip("@")
    return text.replace("@<handle>", handle).replace("<handle>", bare)
