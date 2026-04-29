"""`quorum` command-line entry.

Argparse-based. No external CLI dep — keeps the conductor's footprint
small and the `--help` output stable. Subcommands route to thin wrappers
in `workspace/`, `transport/`, `core/`.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from . import __version__
from .core import (
    NoHandleAvailableError,
    PendingItem,
    PlanResult,
    compute_cost,
    load_routing_defaults,
    load_workspace_config,
    parse_participants,
    plan,
)
from .events import EventLogger, RoutingDecisionEvent
from .paths import WorkspaceNotFoundError, WorkspacePaths, require_workspace
from .server import DEFAULT_HOST, DEFAULT_PORT, serve_forever
from .transport.doctor import doctor_check, render_doctor_report
from .transport.runner import run_items_sync
from .workspace import (
    InitOptions,
    WorkspaceMode,
    WorkspaceState,
    archive_workspace,
    bootstrap_seed_deliberation,
    init_workspace,
    load_state,
    needs_bootstrap,
    save_state,
    status_summary,
    unarchive_workspace,
)
from .workspace.archive import ArchiveError
from .workspace.process import ProcessError, conductor_running, daemonize_run, stop_conductor
from .workspace.scaffolding import ScaffoldingError
from .workspace.state import StateFileError
from .workspace.status import render_status

# Default loop tick when running foreground.
_LOOP_IDLE_SLEEP_S: float = 1.0
_LOOP_MAX_TICKS_DEFAULT: int = 0  # 0 == unlimited


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
        NoHandleAvailableError,
        ProcessError,
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
    parser.add_argument("--version", action="version", version=f"quorum {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # init
    p_init = sub.add_parser("init", help="Scaffold a new workspace in ./quorum/.")
    p_init.add_argument("path", nargs="?", default="quorum", help="Workspace root.")
    p_init.add_argument(
        "--autonomous",
        action="store_true",
        help="Initialise the workspace in autonomous mode (no human participant).",
    )
    p_init.add_argument(
        "--human",
        default=None,
        help=(
            "Your handle for the workspace (e.g. @human-jane). "
            "Default: detected from $USER / git config / $QUORUM_HUMAN_HANDLE."
        ),
    )
    p_init.set_defaults(handler=_cmd_init)

    # status
    p_status = sub.add_parser("status", help="Print workspace status.")
    _add_path(p_status)
    p_status.set_defaults(handler=_cmd_status)

    # doctor
    p_doctor = sub.add_parser("doctor", help="Health-check registered handles.")
    _add_path(p_doctor)
    p_doctor.set_defaults(handler=_cmd_doctor)

    # archive / unarchive
    p_archive = sub.add_parser("archive", help="Archive the current workspace.")
    _add_path(p_archive)
    p_archive.add_argument("--reason", default="completed", help="Archive reason.")
    p_archive.set_defaults(handler=_cmd_archive)

    p_unarchive = sub.add_parser("unarchive", help="Reverse an archive.")
    _add_path(p_unarchive)
    p_unarchive.set_defaults(handler=_cmd_unarchive)

    # plan (read-only inspection of what the loop would do next)
    p_plan = sub.add_parser("plan", help="Show what the loop would invoke next.")
    _add_path(p_plan)
    p_plan.set_defaults(handler=_cmd_plan)

    # step — runs the next pending item once, foreground.
    p_step = sub.add_parser(
        "step",
        help="Run the next pending invocation (single-step debug mode).",
    )
    _add_path(p_step)
    p_step.set_defaults(handler=_cmd_step)

    # run — foreground loop.
    p_run = sub.add_parser("run", help="Foreground loop: run items until idle or blocked.")
    _add_path(p_run)
    p_run.add_argument(
        "--max-ticks",
        type=int,
        default=_LOOP_MAX_TICKS_DEFAULT,
        help="Stop after N idle ticks (0 = run until SIGTERM/Ctrl-C).",
    )
    p_run.add_argument(
        "--detached",
        action="store_true",
        help=argparse.SUPPRESS,  # set by `quorum start`'s daemonize child.
    )
    p_run.set_defaults(handler=_cmd_run)

    # start — daemonized run.
    p_start = sub.add_parser(
        "start",
        help="Start the conductor daemonised (writes runtime/conductor.pid).",
    )
    _add_path(p_start)
    p_start.set_defaults(handler=_cmd_start)

    # resume — alias for start (semantic for PAUSED workspaces).
    p_resume = sub.add_parser(
        "resume",
        help="Alias for `start`; intended for PAUSED workspaces.",
    )
    _add_path(p_resume)
    p_resume.set_defaults(handler=_cmd_start)

    # pause — stop the daemonised conductor.
    p_pause = sub.add_parser("pause", help="Stop the daemonised conductor.")
    _add_path(p_pause)
    p_pause.set_defaults(handler=_cmd_pause)

    # serve — local HTTP for the UI.
    p_serve = sub.add_parser(
        "serve",
        help="Start the local HTTP API the UI consumes (foreground).",
    )
    _add_path(p_serve)
    p_serve.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind host (default: {DEFAULT_HOST}).",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port (default: {DEFAULT_PORT}).",
    )
    p_serve.set_defaults(handler=_cmd_serve)

    # context — add repos, docs, notes (Phase 6).
    p_context = sub.add_parser(
        "context",
        help="Manage workspace context: repos, documents, notes.",
    )
    p_context_sub = p_context.add_subparsers(
        dest="context_command", metavar="<subcommand>"
    )

    p_ctx_repo = p_context_sub.add_parser(
        "add-repo",
        help="Register a local repo and (optionally) digest it now.",
    )
    p_ctx_repo.add_argument("repo_path", help="Path to the repo on disk.")
    p_ctx_repo.add_argument(
        "--name",
        default=None,
        help="Workspace-local short name (default: repo directory name).",
    )
    p_ctx_repo.add_argument(
        "--role",
        default="",
        help='One-line role descriptor (e.g. "user-facing web app; React, TS").',
    )
    p_ctx_repo.add_argument(
        "--relevance",
        choices=("high", "medium", "low"),
        default="medium",
        help="Drives digester selection. high=Opus / medium=Sonnet / low=Haiku.",
    )
    p_ctx_repo.add_argument(
        "--no-digest",
        action="store_true",
        help="Skip digestion now; just register the metadata.",
    )
    _add_path(p_ctx_repo)
    p_ctx_repo.set_defaults(handler=_cmd_context_add_repo)

    p_ctx_note = p_context_sub.add_parser(
        "add-note",
        help="Add a Markdown note to the standing bundle (always included).",
    )
    p_ctx_note.add_argument(
        "name", help="Short slug (becomes context/notes/<name>.md)."
    )
    p_ctx_note.add_argument(
        "--text",
        default=None,
        help="Note body as a string. If omitted, --file is required.",
    )
    p_ctx_note.add_argument(
        "--file",
        default=None,
        help="Path to a Markdown file to copy in.",
    )
    _add_path(p_ctx_note)
    p_ctx_note.set_defaults(handler=_cmd_context_add_note)

    p_ctx_doc = p_context_sub.add_parser(
        "add-doc",
        help="Register a document in /context/docs/raw/ (Phase-6d simple form).",
    )
    p_ctx_doc.add_argument("doc_path", help="Path to a Markdown / text doc.")
    p_ctx_doc.add_argument(
        "--name",
        default=None,
        help="Workspace-local short name (default: file stem).",
    )
    _add_path(p_ctx_doc)
    p_ctx_doc.set_defaults(handler=_cmd_context_add_doc)

    p_ctx_list = p_context_sub.add_parser(
        "list",
        help="List registered context sources (repos / docs / notes).",
    )
    _add_path(p_ctx_list)
    p_ctx_list.set_defaults(handler=_cmd_context_list)

    return parser


def _add_path(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--path",
        default=None,
        help="Workspace root (default: search upward from cwd).",
    )


# ---------------------------------------------------------------------- #
# Subcommand handlers
# ---------------------------------------------------------------------- #


def _cmd_init(args: argparse.Namespace) -> int:
    from .workspace.identity import default_human_handle

    target = Path(args.path).expanduser()
    mode = WorkspaceMode.AUTONOMOUS if args.autonomous else WorkspaceMode.INTERACTIVE
    human_handle = args.human or default_human_handle()
    paths = init_workspace(
        InitOptions(target=target, mode=mode, human_handle=human_handle)
    )
    print(f"initialised workspace at {paths.root}")
    print(f"mode    : {mode.value}")
    print(f"you     : {human_handle}")
    print()
    print("next steps:")
    print(f"  1. edit {_rel(paths.problem_statement)} with your problem statement")
    print(f"  2. add at least one cli handle to {_rel(paths.participants)}")
    print("  3. run `quorum doctor` to verify your handles")
    print("  4. run `quorum start` to begin the conductor")
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


def _cmd_plan(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    _ensure_seed(paths)
    result = plan(paths)
    _print_plan(result)
    return 0


def _cmd_step(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    _ensure_seed(paths)
    state = load_state(paths.state_yaml)
    config = load_workspace_config(paths.config_yaml)
    defaults = load_routing_defaults(paths.routing_defaults)
    if config.cost_enforce:
        pre_cost = compute_cost(paths.events_jsonl, defaults)
        if pre_cost.at_or_above_ceiling(config.cost_ceiling_usd):
            print(
                f"cost ceiling reached: ${pre_cost.spent_usd:.2f} >= "
                f"${config.cost_ceiling_usd:.2f}. Edit config.yaml's "
                "cost.ceiling_usd or set cost.enforce: false to override."
            )
            return 2
    result = plan(paths)
    runnable = result.runnable()
    if not runnable:
        print("nothing to do.")
        _print_plan(result, header=False)
        return 0
    item = runnable[0]
    print(f"step → {item.routing.handle} as {item.role} ({item.move_type}) on #{item.deliberation.id}")
    events = EventLogger(paths.events_jsonl)
    events.emit(
        RoutingDecisionEvent(
            handle=item.routing.handle,
            role=item.routing.role,
            deliberation_id=item.routing.deliberation_id,
            layer=item.routing.layer.value,
            fitness=item.routing.fitness,
            cost=item.routing.cost,
            alternatives=[
                {
                    "handle": a.handle,
                    "fitness": a.fitness,
                    "cost": a.cost,
                    "rejected_because": a.rejected_because,
                }
                for a in item.routing.alternatives
            ],
            note=item.routing.note,
        )
    )
    results = run_items_sync(
        [item], paths=paths, events=events, mode=state.mode.value, max_concurrent=1
    )
    res = results[0]
    print(f"status   : {res.status}")
    print(f"duration : {res.duration_s:.1f}s  attempts: {res.attempts}")
    if res.appended:
        print(f"appended : yes — {res.move_type} by {res.handle}")
        if res.inboxes_notified:
            print(f"notified : {', '.join(res.inboxes_notified)}")
    else:
        print("appended : no")
        if res.error:
            print(f"error    : {res.error}")
    return 0 if res.status == "ok" else 2


def _cmd_run(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    _ensure_seed(paths)
    _transition_to(paths, WorkspaceState.ACTIVE)
    if not getattr(args, "detached", False):
        print(f"conductor running on {paths.root} (Ctrl-C to stop)")

    stop = _install_stop_handlers()
    state = load_state(paths.state_yaml)
    events = EventLogger(paths.events_jsonl)
    config = load_workspace_config(paths.config_yaml)
    defaults = load_routing_defaults(paths.routing_defaults)
    idle_ticks = 0
    # Skip-list of (deliberation_id, role, move_type) tuples that already
    # failed during this run so a single bad agent does not loop forever.
    # The loop's no-progress stop condition (design-doc §10) is the
    # higher-quality answer; this is the v1 minimum.
    failed_keys: set[tuple[str, str, str]] = set()

    while not stop["flag"]:
        if config.cost_enforce:
            spend = compute_cost(paths.events_jsonl, defaults)
            if spend.at_or_above_ceiling(config.cost_ceiling_usd):
                if not getattr(args, "detached", False):
                    print(
                        f"cost ceiling reached: ${spend.spent_usd:.2f} >= "
                        f"${config.cost_ceiling_usd:.2f}. Pausing."
                    )
                break

        result = plan(paths)
        runnable = tuple(
            i
            for i in result.runnable()
            if (i.deliberation.id, i.role, i.move_type) not in failed_keys
        )
        if not runnable:
            if result.manual() or result.blocked or failed_keys:
                # Either humans owe us a move, routing is blocked, or
                # we've already exhausted retries on every runnable role.
                break
            idle_ticks += 1
            if args.max_ticks and idle_ticks >= args.max_ticks:
                break
            time.sleep(_LOOP_IDLE_SLEEP_S)
            continue
        idle_ticks = 0
        for item in runnable:
            events.emit(
                RoutingDecisionEvent(
                    handle=item.routing.handle,
                    role=item.routing.role,
                    deliberation_id=item.routing.deliberation_id,
                    layer=item.routing.layer.value,
                    fitness=item.routing.fitness,
                    cost=item.routing.cost,
                    alternatives=[
                        {
                            "handle": a.handle,
                            "fitness": a.fitness,
                            "cost": a.cost,
                            "rejected_because": a.rejected_because,
                        }
                        for a in item.routing.alternatives
                    ],
                    note=item.routing.note,
                )
            )
        invocation_results = run_items_sync(
            runnable, paths=paths, events=events, mode=state.mode.value
        )
        for item, ir in zip(runnable, invocation_results, strict=True):
            if ir.status != "ok":
                failed_keys.add((item.deliberation.id, item.role, item.move_type))

    _transition_to(paths, WorkspaceState.PAUSED)
    if getattr(args, "detached", False):
        # Clean our own pidfile so `quorum status` doesn't show a stale
        # one after a clean exit. `quorum pause` also handles this; this
        # branch covers the loop-exited-on-its-own case.
        import contextlib

        with contextlib.suppress(FileNotFoundError):
            paths.conductor_pid.unlink()
    else:
        print("conductor paused.")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    _ensure_seed(paths)
    pid = daemonize_run(paths)
    print(f"conductor started (pid {pid}). logs: {paths.runtime / 'conductor.log'}")
    return 0


def _cmd_pause(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    pid = stop_conductor(paths)
    if pid is None:
        print("no running conductor.")
        return 0
    print(f"conductor (pid {pid}) stopped.")
    _transition_to(paths, WorkspaceState.PAUSED)
    return 0


def _cmd_context_add_repo(args: argparse.Namespace) -> int:
    from .core.context_bundle import load_context_manifest, save_context_manifest
    from .core.digestion import RepoSpec, digest_repo, resolve_digester

    paths = _resolve_workspace(args)
    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.is_dir():
        print(f"error: {repo_path} is not a directory.", file=sys.stderr)
        return 1
    name = args.name or repo_path.name

    paths.context_repos.mkdir(parents=True, exist_ok=True)
    target_dir = paths.context_repos / name

    manifest = load_context_manifest(paths)
    repos = manifest.setdefault("repos", [])
    existing = next((r for r in repos if r.get("name") == name), None)
    record = {
        "name": name,
        "path": str(repo_path),
        "role": args.role,
        "relevance": args.relevance,
        "added_at": _now_iso(),
    }
    if existing is not None:
        existing.update(record)
    else:
        repos.append(record)
    save_context_manifest(paths, manifest)
    print(f"registered repo {name!r} at {repo_path} (relevance={args.relevance})")

    if args.no_digest:
        print("digestion skipped (--no-digest).")
        target_dir.mkdir(parents=True, exist_ok=True)
        return 0

    config = load_workspace_config(paths.config_yaml)
    participants = parse_participants(paths.participants)
    digester = resolve_digester(args.relevance, config, participants)
    if digester is None:
        print(
            "warning: no `cli`-transport handle is registered. "
            "Edit registers/participants.md to add one, then "
            f"`quorum context add-repo {repo_path} --name {name}` again "
            "(or use --no-digest to defer).",
            file=sys.stderr,
        )
        return 1

    print(f"digesting via {digester.handle} → {target_dir / 'digest.md'}")
    spec = RepoSpec(
        name=name, path=repo_path, role=args.role, relevance=args.relevance
    )
    result = digest_repo(spec, digester, target_dir)
    print(f"status   : {result.status}")
    print(f"duration : {result.duration_s:.1f}s")
    if result.status == "ok":
        print(f"digest   : {result.digest_path}")
        return 0
    print(f"error    : {result.error}")
    return 2


def _cmd_context_add_note(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    if args.text is None and args.file is None:
        print("error: provide --text or --file.", file=sys.stderr)
        return 1
    paths.context_notes.mkdir(parents=True, exist_ok=True)
    target = paths.context_notes / f"{args.name}.md"
    if args.file:
        src = Path(args.file).expanduser().resolve()
        if not src.is_file():
            print(f"error: {src} is not a file.", file=sys.stderr)
            return 1
        target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        body = args.text
        if not body.endswith("\n"):
            body += "\n"
        target.write_text(body, encoding="utf-8")

    from .core.context_bundle import load_context_manifest, save_context_manifest

    manifest = load_context_manifest(paths)
    notes = manifest.setdefault("notes", [])
    if not any(n.get("name") == args.name for n in notes):
        notes.append({"name": args.name, "added_at": _now_iso()})
        save_context_manifest(paths, manifest)
    print(f"added note {target}")
    return 0


def _cmd_context_add_doc(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)
    src = Path(args.doc_path).expanduser().resolve()
    if not src.is_file():
        print(f"error: {src} is not a file.", file=sys.stderr)
        return 1
    name = args.name or src.stem
    raw_dir = paths.context_docs / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / src.name
    target.write_bytes(src.read_bytes())

    from .core.context_bundle import load_context_manifest, save_context_manifest

    manifest = load_context_manifest(paths)
    docs = manifest.setdefault("docs", [])
    record = {
        "name": name,
        "filename": src.name,
        "size_bytes": src.stat().st_size,
        "added_at": _now_iso(),
    }
    if not any(d.get("name") == name for d in docs):
        docs.append(record)
    save_context_manifest(paths, manifest)
    print(f"added doc {name!r} → {target}")
    return 0


def _cmd_context_list(args: argparse.Namespace) -> int:
    from .core.context_bundle import load_context_manifest

    paths = _resolve_workspace(args)
    manifest = load_context_manifest(paths)
    print(f"context sources for {paths.root}")
    for label, key in (("repos", "repos"), ("docs", "docs"), ("urls", "urls"), ("notes", "notes")):
        items = manifest.get(key) or []
        print(f"  {label} ({len(items)}):")
        for item in items:
            name = item.get("name", "?")
            extras: list[str] = []
            if "relevance" in item:
                extras.append(f"relevance={item['relevance']}")
            if "path" in item:
                extras.append(f"path={item['path']}")
            print(f"    - {name}" + (" — " + ", ".join(extras) if extras else ""))
    return 0


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_serve(args: argparse.Namespace) -> int:
    paths = _resolve_workspace(args)

    def _on_listen(addr: tuple[str, int]) -> None:
        host, port = addr
        print(f"quorum http on http://{host}:{port}  (workspace: {paths.root})")
        print("Ctrl-C to stop.")

    try:
        serve_forever(paths, host=args.host, port=args.port, on_listen=_on_listen)
    except KeyboardInterrupt:
        print()
        print("server stopped.")
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
                f"No workspace at {root} (no state.yaml). Use `quorum init {explicit}`."
            )
        return WorkspacePaths(root=root)
    return require_workspace()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _ensure_seed(paths: WorkspacePaths) -> None:
    """If the workspace has no deliberations yet, open #0001 (the manifest)."""
    if needs_bootstrap(paths):
        path = bootstrap_seed_deliberation(paths)
        print(f"opened seed deliberation at {_rel(path)}")


def _transition_to(paths: WorkspacePaths, state: WorkspaceState) -> None:
    model = load_state(paths.state_yaml)
    if model.state == state:
        return
    if model.state == WorkspaceState.ARCHIVED:
        return  # archived workspaces don't run.
    model.state = state
    from datetime import UTC, datetime

    model.state_changed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(paths.state_yaml, model)


def _install_stop_handlers() -> dict[str, bool]:
    flag: dict[str, bool] = {"flag": False}

    def _handle(_signo: int, _frame: object) -> None:
        flag["flag"] = True

    import contextlib

    for sig in (signal.SIGINT, signal.SIGTERM):
        # Setting handlers fails inside non-main threads or on platforms
        # without signal support; both are acceptable here.
        with contextlib.suppress(ValueError, OSError):
            signal.signal(sig, _handle)
    return flag


def _print_plan(result: PlanResult, *, header: bool = True) -> None:
    if header:
        print(f"plan: {len(result.items)} item(s) ready, {len(result.blocked)} blocked")
    if not result.items and not result.blocked:
        print("  (nothing pending — every deliberation is done or blocked on humans)")
        return
    for item in result.items:
        _print_item(item)
    for blocked in result.blocked:
        print(
            f"  [blocked] #{blocked.deliberation.id} {blocked.role}/{blocked.move_type} "
            f"— {blocked.reason}"
        )


def _print_item(item: PendingItem) -> None:
    suffix = "  (manual)" if item.is_manual else ""
    print(
        f"  [{item.routing.layer.value:14}] #{item.deliberation.id} "
        f"{item.role}/{item.move_type:10} → {item.routing.handle}{suffix}"
    )
    _ = conductor_running  # silence ruff F401 if status helpers diverge later.
