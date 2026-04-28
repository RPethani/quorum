"""`quorum doctor` — structural health check of registered handles.

Phase 4b scope: parse `registers/participants.md`, verify each `cli`
handle's command-line tool is on PATH, report a coloured summary. Real
probing of model availability lands in Phase 4d.

The participants table parser lives in `core/participants.py`; this
module is just the doctor-side rendering and PATH probe.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from ..core.participants import parse_participants
from ..paths import WorkspacePaths


@dataclass
class HandleHealth:
    handle: str
    transport: str
    cli_command: str
    on_path: bool | None  # None for non-cli transports
    note: str = ""


def doctor_check(paths: WorkspacePaths) -> list[HandleHealth]:
    """Inspect each handle in participants.md and return a health record."""
    out: list[HandleHealth] = []
    for p in parse_participants(paths.participants):
        if p.transport == "cli":
            program = _first_token(p.cli_command)
            on_path = shutil.which(program) is not None if program else False
            note = (
                f"`{program}` not on PATH"
                if not on_path and program
                else ("no command configured" if not program else "")
            )
            out.append(
                HandleHealth(
                    handle=p.handle,
                    transport=p.transport,
                    cli_command=p.cli_command,
                    on_path=on_path,
                    note=note,
                )
            )
        else:
            out.append(
                HandleHealth(
                    handle=p.handle,
                    transport=p.transport,
                    cli_command=p.cli_command,
                    on_path=None,
                    note="non-cli handle; no PATH check applies",
                )
            )
    return out


def render_doctor_report(records: list[HandleHealth]) -> str:
    if not records:
        return "No handles registered. Edit registers/participants.md to add one."

    lines: list[str] = []
    lines.append(f"{len(records)} handle(s) registered:")
    lines.append("")
    width = max(len(r.handle) for r in records)
    for r in records:
        if r.on_path is True:
            mark = "ok   "
        elif r.on_path is False:
            mark = "fail "
        else:
            mark = "n/a  "
        suffix = f" — {r.note}" if r.note else ""
        lines.append(f"  [{mark}] {r.handle.ljust(width)}  ({r.transport}){suffix}")
    return "\n".join(lines)


def _first_token(command: str) -> str:
    return command.strip().split()[0] if command.strip() else ""
