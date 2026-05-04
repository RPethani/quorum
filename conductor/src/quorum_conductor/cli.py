"""`quorum` command-line entry.

Argparse-based, no external CLI dep. Canvas-only — the protocol-era
`init`/`plan`/`step`/`run`/`start`/`pause`/`resume`/`archive`/`context`
subcommands have been retired with the protocol surface.

Subcommand surface:

    quorum init <path> [--title=…] [--no-start]
        Scaffold a new canvas workspace and (by default) start the
        conductor server + UI in the background.

    quorum serve [--path=…] [--host=…] [--port=…]
        Foreground HTTP server.

    quorum status [--path=…]
        Print workspace title, message count, cost, services state.

    quorum doctor [--path=…]
        Health-check registered participant CLIs.

    quorum up | down | restart | logs
        Manage the detached server + UI processes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .canvas.workspace import scaffold as canvas_scaffold
from .context import (
    ContextOperationError,
    DigestError,
    add_doc,
    add_note,
    add_repo,
    digest_repo,
    load_manifest,
    make_digest_invoker,
    mark_stale_repos,
    refresh as context_refresh,
    remove as context_remove,
)
from .events import EventLogger  # noqa: F401 — kept exported via package
from .paths import WorkspaceNotFoundError, WorkspacePaths, require_workspace
from .server import DEFAULT_HOST, DEFAULT_PORT, serve_forever
from .transport.doctor import doctor_check, render_doctor_report
from .workspace import services as _services
from .workspace.process import ProcessError
from .workspace.services import (
    SERVICE_NAMES,
    ServiceError,
    ServiceName,
)

services_status = _services.all_status
service_start = _services.start
service_stop = _services.stop
service_restart = _services.restart
service_tail_log = _services.tail_log


def main(argv: list[str] | None = None) -> int:
    real_argv = sys.argv[1:] if argv is None else argv
    if not real_argv:
        # Bare `quorum` — print help. The interactive shell that used to
        # live here was protocol-shaped and has been retired.
        _build_parser().print_help()
        return 0

    parser = _build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    try:
        return int(handler(args) or 0)
    except (
        WorkspaceNotFoundError,
        ProcessError,
        ServiceError,
        ContextOperationError,
        DigestError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------- #
# Parser construction
# ---------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quorum",
        description="Quorum — local hub for multi-AI collaborative brainstorming.",
    )
    parser.add_argument("--version", action="version", version=f"quorum {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # init — scaffold a fresh canvas workspace.
    p_init = sub.add_parser(
        "init",
        help="Scaffold a new brainstorm workspace and start the server + UI.",
    )
    p_init.add_argument("path", nargs="?", default="quorum", help="Workspace folder.")
    p_init.add_argument(
        "--title",
        default=None,
        help='One-line title (default: "Untitled brainstorm").',
    )
    p_init.add_argument(
        "--no-start",
        action="store_true",
        help="Don't auto-start the server + UI after scaffolding.",
    )
    p_init.set_defaults(handler=_cmd_init)

    # serve — foreground HTTP server.
    p_serve = sub.add_parser(
        "serve",
        help="Run the conductor HTTP server in the foreground.",
    )
    _add_path(p_serve)
    p_serve.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST}).")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT}).")
    p_serve.set_defaults(handler=_cmd_serve)

    # status — quick read-only summary.
    p_status = sub.add_parser("status", help="Print workspace + services status.")
    _add_path(p_status)
    p_status.set_defaults(handler=_cmd_status)

    # doctor — health-check participant CLIs.
    p_doctor = sub.add_parser("doctor", help="Health-check registered participant CLIs.")
    _add_path(p_doctor)
    p_doctor.set_defaults(handler=_cmd_doctor)

    # up / down / restart / logs — detached service management.
    p_up = sub.add_parser(
        "up",
        help="Start the conductor server + UI in the background.",
    )
    _add_path(p_up)
    p_up.add_argument("--server-port", type=int, default=8500, help="HTTP API port (default 8500).")
    p_up.add_argument("--ui-port", type=int, default=3000, help="UI dev-server port (default 3000).")
    p_up.add_argument("--server-only", action="store_true", help="Start only the conductor server.")
    p_up.add_argument("--ui-only", action="store_true", help="Start only the UI.")
    p_up.set_defaults(handler=_cmd_up)

    p_down = sub.add_parser("down", help="Stop the background server / UI.")
    _add_path(p_down)
    p_down.add_argument(
        "service",
        nargs="?",
        choices=SERVICE_NAMES,
        default=None,
        help="Which service to stop (default: both).",
    )
    p_down.set_defaults(handler=_cmd_down)

    p_restart = sub.add_parser("restart", help="Restart the server / UI.")
    _add_path(p_restart)
    p_restart.add_argument(
        "service",
        nargs="?",
        choices=SERVICE_NAMES,
        default=None,
        help="Which service to restart (default: both).",
    )
    p_restart.set_defaults(handler=_cmd_restart)

    p_logs = sub.add_parser("logs", help="Tail the server / UI log file.")
    _add_path(p_logs)
    p_logs.add_argument(
        "service",
        nargs="?",
        choices=SERVICE_NAMES,
        default="server",
        help="Which log to tail (default: server).",
    )
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow new lines as they appear.")
    p_logs.add_argument("-n", "--lines", type=int, default=80, help="Show the last N lines (default 80).")
    p_logs.set_defaults(handler=_cmd_logs)

    # context — manage context-seeding entries (repos, docs, notes).
    p_ctx = sub.add_parser(
        "context",
        help="List / add / remove / refresh context entries (repos, docs, notes).",
    )
    ctx_sub = p_ctx.add_subparsers(dest="context_command", metavar="<subcommand>")

    p_ctx_list = ctx_sub.add_parser("list", help="List context entries.")
    _add_path(p_ctx_list)
    p_ctx_list.set_defaults(handler=_cmd_context_list)

    p_ctx_add = ctx_sub.add_parser(
        "add",
        help="Add a repo (directory) or doc (file) by path.",
    )
    _add_path(p_ctx_add)
    p_ctx_add.add_argument("source", help="Filesystem path to a directory (repo) or file (doc).")
    p_ctx_add.add_argument("--name", default=None, help="Display name (default: basename of source).")
    p_ctx_add.set_defaults(handler=_cmd_context_add)

    p_ctx_note = ctx_sub.add_parser(
        "add-note",
        help="Add a free-form note. Body read from --body or stdin.",
    )
    _add_path(p_ctx_note)
    p_ctx_note.add_argument("name", help="Short name for the note.")
    p_ctx_note.add_argument("--body", default=None, help="Note body (default: read from stdin).")
    p_ctx_note.set_defaults(handler=_cmd_context_add_note)

    p_ctx_rm = ctx_sub.add_parser("remove", help="Remove a context entry by id.")
    _add_path(p_ctx_rm)
    p_ctx_rm.add_argument("entry_id", help="Entry id, e.g. ctx-0003.")
    p_ctx_rm.set_defaults(handler=_cmd_context_remove)

    p_ctx_refresh = ctx_sub.add_parser(
        "refresh",
        help="Mark a repo entry as pending re-digestion.",
    )
    _add_path(p_ctx_refresh)
    p_ctx_refresh.add_argument("entry_id", help="Entry id, e.g. ctx-0001.")
    p_ctx_refresh.set_defaults(handler=_cmd_context_refresh)

    p_ctx_digest = ctx_sub.add_parser(
        "digest",
        help="Synchronously digest a repo entry using the configured digester.",
    )
    _add_path(p_ctx_digest)
    p_ctx_digest.add_argument("entry_id", help="Entry id, e.g. ctx-0001.")
    p_ctx_digest.add_argument(
        "--handle",
        default=None,
        help="Override the digester handle (default: state.yaml `digester_handle`).",
    )
    p_ctx_digest.set_defaults(handler=_cmd_context_digest)

    p_ctx_stale = ctx_sub.add_parser(
        "stale",
        help="Re-check repo HEADs and update the stale flag in the manifest.",
    )
    _add_path(p_ctx_stale)
    p_ctx_stale.set_defaults(handler=_cmd_context_stale)

    return parser


def _add_path(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )


def _resolve_workspace(args: argparse.Namespace) -> WorkspacePaths:
    start = Path(args.path).expanduser() if args.path else None
    return require_workspace(start)


# ---------------------------------------------------------------------- #
# Subcommand handlers
# ---------------------------------------------------------------------- #


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser()
    title = args.title or "Untitled brainstorm"
    canvas_scaffold(target, title=title)
    paths = WorkspacePaths(root=target.resolve())
    print(f"initialised workspace at {paths.root}")
    print(f"title  : {title}")

    if not args.no_start:
        print()
        print("starting services in the background…")
        try:
            server = service_start(paths, "server")
            ui = service_start(paths, "ui")
        except ServiceError as exc:
            print(f"warning: could not auto-start services — {exc}", file=sys.stderr)
        else:
            print(f"  server  ● running   http://127.0.0.1:{server.port}   pid={server.pid}")
            print(f"  ui      ● running   http://127.0.0.1:{ui.port}   pid={ui.pid}")
            print()
            print(f"open http://127.0.0.1:{ui.port} to start brainstorming.")
            print("`quorum status` to inspect, `quorum down` to stop.")
            return 0

    print()
    print("next steps:")
    print(f"  1. add at least one CLI participant to {paths.root}/registers/participants.md")
    print("     (or use the UI — http://localhost:3000 → '+ Add participant')")
    print("  2. run `quorum up` from the workspace folder")
    print("  3. open http://localhost:3000 in the browser")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)

    def _on_listen(addr: tuple[str, int]) -> None:
        print(f"listening on http://{addr[0]}:{addr[1]}")

    serve_forever(paths, host=args.host, port=args.port, on_listen=_on_listen)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from .canvas.state import StateError, load_state

    paths = _resolve_workspace(args)
    try:
        state = load_state(paths.root)
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"workspace : {paths.root}")
    print(f"title     : {state.title}")
    print(f"messages  : {state.message_counter}")
    print(
        f"cost      : ${state.cost.spent:.2f} / ${state.cost.cap:.2f} "
        f"({'enforced' if state.cost.enforce else 'soft'})"
    )
    print()
    print("services:")
    for s in services_status(paths):
        marker = "●" if s.state == "running" else "○"
        port = f"http://127.0.0.1:{s.port}" if s.port else "(not running)"
        print(f"  {s.name:<7} {marker} {s.state:<8} {port}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    report = doctor_check(paths)
    print(render_doctor_report(report))
    # Exit non-zero if any cli participant is unreachable.
    failed = [r for r in report if r.transport == "cli" and r.on_path is False]
    return 0 if not failed else 1


def _cmd_up(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    only_server = bool(args.server_only)
    only_ui = bool(args.ui_only)
    if only_server and only_ui:
        print("error: --server-only and --ui-only are mutually exclusive.", file=sys.stderr)
        return 1

    targets: list[ServiceName] = []
    if not only_ui:
        targets.append("server")
    if not only_server:
        targets.append("ui")

    for name in targets:
        try:
            s = service_start(paths, name, server_port=args.server_port, ui_port=args.ui_port)
        except ServiceError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        marker = "●" if s.state == "running" else "○"
        print(f"  {name:<7} {marker} {s.state:<8} http://127.0.0.1:{s.port}   pid={s.pid}")
    return 0


def _cmd_down(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    targets: list[ServiceName] = (
        list(SERVICE_NAMES) if args.service is None else [args.service]
    )
    for name in targets:
        prior = service_stop(paths, name)
        marker = "○"
        if prior is None:
            print(f"  {name:<7} {marker} already stopped")
        else:
            print(f"  {name:<7} {marker} stopped")
    return 0


def _cmd_restart(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    targets: list[ServiceName] = (
        list(SERVICE_NAMES) if args.service is None else [args.service]
    )
    for name in targets:
        s = service_restart(paths, name)
        marker = "●" if s.state == "running" else "○"
        print(f"  {name:<7} {marker} {s.state:<8} http://127.0.0.1:{s.port}   pid={s.pid}")
    return 0


def _cmd_context_list(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    manifest = load_manifest(paths.root)
    if not manifest.entries:
        print("(no context entries)")
        return 0
    for e in manifest.entries:
        head = f"{e.id}  {e.kind:<5}  {e.name}"
        if e.kind == "repo":
            status = e.digest_status or "—"
            stale = "  [stale]" if e.stale else ""
            print(f"{head}   ({e.source})  status={status}{stale}")
        elif e.kind == "doc":
            print(f"{head}   ({e.source})")
        else:
            print(head)
    return 0


def _cmd_context_add(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    src = Path(args.source).expanduser()
    if not src.exists():
        print(f"error: no such path: {src}", file=sys.stderr)
        return 1
    if src.is_dir():
        entry = add_repo(paths.root, src, name=args.name)
        kind = "repo"
    elif src.is_file():
        entry = add_doc(paths.root, src, name=args.name)
        kind = "doc"
    else:
        print(f"error: not a file or directory: {src}", file=sys.stderr)
        return 1
    print(f"added {kind} {entry.id}: {entry.name}")
    return 0


def _cmd_context_add_note(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    body = args.body if args.body is not None else sys.stdin.read()
    entry = add_note(paths.root, args.name, body)
    print(f"added note {entry.id}: {entry.name}")
    return 0


def _cmd_context_remove(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    entry = context_remove(paths.root, args.entry_id)
    print(f"removed {entry.kind} {entry.id}: {entry.name}")
    return 0


def _cmd_context_refresh(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    entry = context_refresh(paths.root, args.entry_id)
    print(f"marked {entry.id} as pending — digester will re-run it")
    return 0


def _cmd_context_digest(args: argparse.Namespace) -> int:
    from .canvas.state import load_state

    paths = _resolve_workspace(args)
    handle = (args.handle or load_state(paths.root).digester_handle).strip()
    if not handle:
        print(
            "error: no digester handle configured. Pass --handle=<participant> "
            "or set `digester_handle` in state.yaml.",
            file=sys.stderr,
        )
        return 1

    invoke = make_digest_invoker()
    print(f"digesting {args.entry_id} via {handle}…")
    entry = digest_repo(paths.root, args.entry_id, invoke=invoke, handle=handle)
    if entry.digest_status == "ready":
        print(f"  ready: {entry.digest_summary}")
        return 0
    print(f"  failed: {entry.digest_error}", file=sys.stderr)
    return 1


def _cmd_context_stale(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    manifest = mark_stale_repos(paths.root)
    repos = [e for e in manifest.entries if e.kind == "repo"]
    if not repos:
        print("(no repo entries)")
        return 0
    for e in repos:
        flag = "  [stale]" if e.stale else ""
        print(f"{e.id}  {e.name}{flag}")
    return 0


def _cmd_logs(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    text = service_tail_log(paths, args.service, n=args.lines)
    if text:
        print(text)
    if args.follow:
        # Simple poll-based follow — `services.tail_log` returns a snapshot;
        # we re-read every 250ms and emit any new bytes.
        import time

        from .workspace.services import _log_path

        path = _log_path(paths, args.service)
        offset = path.stat().st_size if path.is_file() else 0
        try:
            while True:
                time.sleep(0.25)
                if not path.is_file():
                    continue
                size = path.stat().st_size
                if size > offset:
                    with path.open("rb") as f:
                        f.seek(offset)
                        chunk = f.read(size - offset).decode("utf-8", errors="replace")
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    offset = size
        except KeyboardInterrupt:
            pass
    return 0
