"""`quorum doctor` — structural health check of registered handles.

Phase 4b scope: parse `registers/participants.md`, verify each `cli`
handle's command-line tool is on PATH, and report a coloured summary.
Real probing of model availability (sending a tiny test prompt) lands in
Phase 4d alongside invocation.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

from ..paths import WorkspacePaths

# A pragmatic regex-based parser for the participants.md table. The file
# is human-edited Markdown with a fixed pipe-table schema (design doc
# §3.5); a Markdown AST library would be overkill. We only need handle,
# command, and transport for doctor.
_TABLE_ROW_RE = re.compile(r"^\|\s*(?P<cells>.+?)\s*\|\s*$")


@dataclass
class HandleHealth:
    handle: str
    transport: str
    cli_command: str
    on_path: bool | None  # None for non-cli transports
    note: str = ""


def _strip_cell(cell: str) -> str:
    return cell.strip().strip("`")


def _parse_participants_table(markdown: str) -> list[dict[str, str]]:
    """Return one dict per data row of the participants table.

    Tolerant of leading frontmatter and surrounding prose. Returns [] if
    no data rows are present.
    """
    lines = markdown.splitlines()
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for raw in lines:
        m = _TABLE_ROW_RE.match(raw)
        if not m:
            continue
        cells = [_strip_cell(c) for c in m.group("cells").split("|")]
        if all(set(c) <= {"-", ":"} and c for c in cells):
            # Markdown table separator row.
            continue
        if headers is None:
            headers = [c.lower() for c in cells]
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def doctor_check(paths: WorkspacePaths) -> list[HandleHealth]:
    """Inspect each handle in participants.md and return a health record."""
    if not paths.participants.is_file():
        return []
    markdown = paths.participants.read_text(encoding="utf-8")
    rows = _parse_participants_table(markdown)

    out: list[HandleHealth] = []
    for row in rows:
        handle = row.get("handle", "").strip()
        if not handle:
            continue
        transport = row.get("transport", "").strip().lower() or "unknown"
        cli_command = row.get("cli command", "").strip()
        if transport == "cli":
            program = _first_token(cli_command)
            on_path = shutil.which(program) is not None if program else False
            note = (
                f"`{program}` not on PATH"
                if not on_path and program
                else ("no command configured" if not program else "")
            )
            out.append(
                HandleHealth(
                    handle=handle,
                    transport=transport,
                    cli_command=cli_command,
                    on_path=on_path,
                    note=note,
                )
            )
        else:
            # `manual`, `mcp` (v2), `ide` (v2) — nothing on-PATH to verify.
            out.append(
                HandleHealth(
                    handle=handle,
                    transport=transport,
                    cli_command=cli_command,
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
