"""`quorum` command-line entry.

Argparse-based. No external CLI dep — keeps the conductor's footprint
small and the `--help` output stable. Subcommands route to thin wrappers
in `workspace/` and `transport/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .paths import WorkspaceNotFoundError, WorkspacePaths, require_workspace
from .transport.doctor import doctor_check, render_doctor_report
from .workspace import (
    InitOptions,
    WorkspaceMode,
    archive_workspace,
    init_workspace,
    status_summary,
    unarchive_workspace,
)
from .workspace.archive import ArchiveError
from .workspace.scaffolding import ScaffoldingError
from .workspace.state import StateFileError
from .workspace.status import render_status


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    try:
        return int(handler(args) or 0)
    except (
        ScaffoldingError,
        ArchiveError,
        StateFileError,
        WorkspaceNotFoundError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------- #
# Parser construction
# ---------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quorum",
        description="Quorum — local hub for multi-agent collaborative reasoning.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"quorum {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # init
    p_init = sub.add_parser(
        "init",
        help="Scaffold a new workspace in ./quorum/ (or the given path).",
    )
    p_init.add_argument(
        "path",
        nargs="?",
        default="quorum",
        help="Workspace root to create (default: ./quorum).",
    )
    p_init.add_argument(
        "--autonomous",
        action="store_true",
        help="Initialise the workspace in autonomous mode (no human participant).",
    )
    p_init.set_defaults(handler=_cmd_init)

    # status
    p_status = sub.add_parser("status", help="Print workspace status.")
    p_status.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )
    p_status.set_defaults(handler=_cmd_status)

    # doctor
    p_doctor = sub.add_parser(
        "doctor",
        help="Health-check registered handles (CLI tools on PATH, etc.).",
    )
    p_doctor.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )
    p_doctor.set_defaults(handler=_cmd_doctor)

    # archive
    p_archive = sub.add_parser(
        "archive",
        help="Archive the current workspace (state -> ARCHIVED, runtime/ deleted).",
    )
    p_archive.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )
    p_archive.add_argument(
        "--reason",
        default="completed",
        help="Archive reason (free text). Default: 'completed'.",
    )
    p_archive.set_defaults(handler=_cmd_archive)

    # unarchive
    p_unarchive = sub.add_parser(
        "unarchive",
        help="Reverse an archive (state -> INITIALIZED, runtime/ recreated).",
    )
    p_unarchive.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )
    p_unarchive.set_defaults(handler=_cmd_unarchive)

    return parser


# ---------------------------------------------------------------------- #
# Subcommand handlers
# ---------------------------------------------------------------------- #


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser()
    mode = WorkspaceMode.AUTONOMOUS if args.autonomous else WorkspaceMode.INTERACTIVE
    paths = init_workspace(InitOptions(target=target, mode=mode))
    print(f"initialised workspace at {paths.root}")
    print(f"mode: {mode.value}")
    print()
    print("next steps:")
    print(f"  1. edit {_rel(paths.problem_statement)} with your problem statement")
    print(f"  2. add at least one cli handle to {_rel(paths.participants)}")
    print("  3. run `quorum doctor` to verify your handles")
    print("  4. run `quorum status` to confirm INITIALIZED state")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    summary = status_summary(paths)
    print(render_status(summary))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    records = doctor_check(paths)
    print(render_doctor_report(records))
    any_failed = any(r.on_path is False for r in records)
    return 1 if any_failed else 0


def _cmd_archive(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    archive_workspace(paths, reason=args.reason)
    print(f"archived workspace at {paths.root}")
    return 0


def _cmd_unarchive(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    unarchive_workspace(paths)
    print(f"unarchived workspace at {paths.root}")
    return 0


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _resolve_workspace(args: argparse.Namespace) -> WorkspacePaths:
    explicit = getattr(args, "path", None)
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / "state.yaml").is_file():
            raise WorkspaceNotFoundError(
                f"No workspace at {root} (no state.yaml). Use `quorum init {explicit}` to create one."
            )
        return WorkspacePaths(root=root)
    return require_workspace()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
