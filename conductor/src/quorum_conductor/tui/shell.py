"""Slash-command REPL for Quorum.

Runs when the user types `quorum` with no subcommand. Wraps the
existing one-shot CLI handlers so power-users stay in one terminal:

    quorum>
    /help        list commands
    /status      workspace + services
    /up          start server + UI
    /down        stop services
    /restart     restart services
    /logs <svc>  tail a log
    /doctor      health-check participants
    /open        open the UI in your browser
    /init <path> scaffold a new workspace (when not already in one)
    /cd <path>   switch the active workspace within this session
    /clear       clear the screen
    /exit /quit  leave

Design notes:

  * On entry, if we're already inside a workspace, services are
    auto-started in the background — the URL is printed in the
    welcome banner so the user has nothing else to do.
  * If we're outside any workspace, the prompt nudges toward
    `/init` or `/cd`. Most other commands refuse politely until a
    workspace is set.
  * Each slash command synthesises an argparse Namespace and calls
    the same handler the one-shot CLI uses, so behaviour is in
    lock-step with `quorum <verb>`.
"""

from __future__ import annotations

import argparse
import shlex
import sys
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from .. import cli as cli_mod
from ..paths import WorkspaceNotFoundError, WorkspacePaths, find_workspace
from ..workspace import services as _services
from ..workspace.process import ProcessError
from ..workspace.services import ServiceError

# (description, requires_workspace)
SLASH_COMMANDS: dict[str, tuple[str, bool]] = {
    "/help": ("Show this help.", False),
    "/status": ("Workspace title, message count, cost, services state.", True),
    "/up": ("Start the conductor server + UI in the background.", True),
    "/down": ("Stop services. Args: [server|ui]", True),
    "/restart": ("Restart services. Args: [server|ui]", True),
    "/logs": ("Tail a log. Args: [server|ui] [-f] [-n N]", True),
    "/doctor": ("Health-check registered participants.", True),
    "/open": ("Open the UI in your default browser.", True),
    "/init": ("Scaffold a new workspace. Args: <path>", False),
    "/cd": ("Switch the active workspace. Args: <path>", False),
    "/exit": ("Leave the shell.", False),
}


@dataclass
class _ShellState:
    paths: WorkspacePaths | None = None
    history: InMemoryHistory = field(default_factory=InMemoryHistory)


def run_shell(initial_path: str | None = None) -> int:
    """Entry point. Returns the process exit code."""
    state = _ShellState(paths=_resolve_initial_workspace(initial_path))
    _print_banner(state)

    if state.paths is not None:
        _try_autostart(state)

    completer = _SlashCompleter()
    session: PromptSession[str] = PromptSession(
        history=state.history,
        completer=completer,
        complete_while_typing=True,
        bottom_toolbar=lambda: _toolbar(state),
        style=Style.from_dict(
            {
                "bottom-toolbar": "bg:#1f2937 #e5e7eb",
                "prompt": "ansicyan bold",
            }
        ),
    )

    while True:
        try:
            line = session.prompt(HTML("<prompt>quorum&gt;</prompt> "))
        except KeyboardInterrupt:
            continue  # ^C at empty prompt = stay
        except EOFError:
            print()
            return 0

        line = line.strip()
        if not line:
            continue
        if not line.startswith("/"):
            print("commands start with `/`. Try `/help`.")
            continue

        if not _dispatch(line, state):
            return 0  # /exit, /quit


# ---------------------------------------------------------------------- #
# Dispatch
# ---------------------------------------------------------------------- #


def _dispatch(line: str, state: _ShellState) -> bool:
    """Run one slash command. Returns False if the user asked to exit."""
    try:
        parts = shlex.split(line)
    except ValueError as e:
        print(f"parse error: {e}")
        return True

    cmd = parts[0]
    args = parts[1:]

    handler = _HANDLERS.get(cmd)
    if handler is None:
        print(f"unknown command: {cmd}. Try /help.")
        return True

    spec = SLASH_COMMANDS.get(cmd)
    if spec and spec[1] and state.paths is None:
        print(f"{cmd} needs a workspace. Use `/cd <path>` or `/init <path>` first.")
        return True

    try:
        return handler(state, args)
    except (
        WorkspaceNotFoundError,
        ProcessError,
        ServiceError,
    ) as exc:
        print(f"error: {exc}")
        return True


# ---------------------------------------------------------------------- #
# Handlers
# ---------------------------------------------------------------------- #


def _h_help(_state: _ShellState, _args: list[str]) -> bool:
    print()
    print("commands:")
    for name, (desc, _) in SLASH_COMMANDS.items():
        print(f"  {name:<10}  {desc}")
    print()
    return True


def _h_status(state: _ShellState, _args: list[str]) -> bool:
    return _run_cli_handler(cli_mod._cmd_status, state, {})


def _h_up(state: _ShellState, args: list[str]) -> bool:
    parsed = _parse(args, [
        ("--server-port", int, 8500),
        ("--ui-port", int, 3000),
        ("--server-only", "flag", False),
        ("--ui-only", "flag", False),
    ])
    return _run_cli_handler(cli_mod._cmd_up, state, parsed)


def _h_down(state: _ShellState, args: list[str]) -> bool:
    service = args[0] if args else None
    return _run_cli_handler(cli_mod._cmd_down, state, {"service": service})


def _h_restart(state: _ShellState, args: list[str]) -> bool:
    service = args[0] if args else None
    return _run_cli_handler(cli_mod._cmd_restart, state, {"service": service})


def _h_logs(state: _ShellState, args: list[str]) -> bool:
    parsed = _parse(args, [
        ("service", "positional", "server"),
        ("-f", "flag", False, "follow"),
        ("--follow", "flag", False, "follow"),
        ("-n", int, 80, "lines"),
        ("--lines", int, 80, "lines"),
    ])
    return _run_cli_handler(cli_mod._cmd_logs, state, parsed)


def _h_doctor(state: _ShellState, _args: list[str]) -> bool:
    return _run_cli_handler(cli_mod._cmd_doctor, state, {})


def _h_open(state: _ShellState, _args: list[str]) -> bool:
    if state.paths is None:
        print("no active workspace.")
        return True
    ui = next((s for s in _services.all_status(state.paths) if s.name == "ui"), None)
    if ui is None or ui.state != "running" or not ui.port:
        print("UI isn't running. Try `/up` first.")
        return True
    url = f"http://127.0.0.1:{ui.port}"
    print(f"opening {url}")
    webbrowser.open(url)
    return True


def _h_init(state: _ShellState, args: list[str]) -> bool:
    if not args:
        print("usage: /init <path> [--title …]")
        return True
    parsed = _parse(args, [
        ("path", "positional", None),
        ("--title", str, None),
        ("--no-start", "flag", False),
    ])
    rc = _run_cli_handler(cli_mod._cmd_init, state, parsed)
    # If init succeeded, switch the shell to the new workspace.
    if rc and parsed.get("path"):
        target = Path(parsed["path"]).expanduser().resolve()
        ws = find_workspace(target)
        if ws is not None:
            state.paths = ws
            print(f"active workspace: {ws.root}")
    return rc


def _h_cd(state: _ShellState, args: list[str]) -> bool:
    if not args:
        print("usage: /cd <path>")
        return True
    target = Path(args[0]).expanduser().resolve()
    ws = find_workspace(target)
    if ws is None:
        print(f"no workspace at {target}. Use `/init <path>` to create one.")
        return True
    state.paths = ws
    print(f"active workspace: {ws.root}")
    _try_autostart(state)
    return True


def _h_exit(_state: _ShellState, _args: list[str]) -> bool:
    return False


_HANDLERS: dict[str, Callable[[_ShellState, list[str]], bool]] = {
    "/help": _h_help,
    "/status": _h_status,
    "/up": _h_up,
    "/down": _h_down,
    "/restart": _h_restart,
    "/logs": _h_logs,
    "/doctor": _h_doctor,
    "/open": _h_open,
    "/init": _h_init,
    "/cd": _h_cd,
    "/exit": _h_exit,
}


# ---------------------------------------------------------------------- #
# Glue: run a one-shot CLI handler with a synthesised Namespace
# ---------------------------------------------------------------------- #


def _run_cli_handler(
    handler: Callable[[argparse.Namespace], int | None],
    state: _ShellState,
    extra: dict[str, Any],
) -> bool:
    """Wrap a one-shot CLI handler so it sees the shell's active
    workspace via `--path`, plus whatever extra args the slash
    command parsed."""
    payload: dict[str, Any] = {"path": str(state.paths.root) if state.paths else None}
    payload.update(extra)
    try:
        handler(argparse.Namespace(**payload))
    except SystemExit as exc:
        # argparse inside handlers sometimes calls sys.exit; keep the
        # shell alive.
        if exc.code not in (0, None):
            print(f"command exited with status {exc.code}")
    return True


# ---------------------------------------------------------------------- #
# Tiny arg parser — too small for argparse, big enough to be useful.
# ---------------------------------------------------------------------- #


def _parse(
    args: list[str],
    spec: list[tuple[Any, ...]],
) -> dict[str, Any]:
    """Walk `args` against `spec`. Spec entries:

      ("name", "positional", default)              — first free arg
      ("--flag", "flag", default[, alias])         — boolean
      ("--opt", type, default[, alias])            — typed value
    """
    out: dict[str, Any] = {}
    aliases: dict[str, str] = {}
    types: dict[str, Any] = {}
    flags: set[str] = set()
    positionals: list[tuple[str, Any]] = []

    for entry in spec:
        name = entry[0]
        kind = entry[1]
        default = entry[2]
        alias = entry[3] if len(entry) > 3 else None
        target = alias or name.lstrip("-").replace("-", "_")
        out.setdefault(target, default)
        if kind == "positional":
            positionals.append((target, default))
        elif kind == "flag":
            flags.add(name)
            aliases[name] = target
        else:
            types[name] = kind
            aliases[name] = target

    i = 0
    pos_idx = 0
    while i < len(args):
        tok = args[i]
        if tok in flags:
            out[aliases[tok]] = True
            i += 1
        elif tok in types:
            if i + 1 >= len(args):
                print(f"missing value for {tok}")
                return out
            out[aliases[tok]] = types[tok](args[i + 1])
            i += 2
        elif tok.startswith("-"):
            print(f"unknown flag: {tok}")
            i += 1
        else:
            if pos_idx < len(positionals):
                out[positionals[pos_idx][0]] = tok
                pos_idx += 1
            i += 1
    return out


# ---------------------------------------------------------------------- #
# Welcome banner / toolbar / completer
# ---------------------------------------------------------------------- #


def _print_banner(state: _ShellState) -> None:
    print()
    print("Quorum — local hub for multi-AI brainstorming")
    if state.paths is not None:
        print(f"workspace: {state.paths.root}")
    else:
        print("no workspace here. Use `/init <path>` or `/cd <path>` to get started.")
    print("type `/help` for commands, `/exit` to leave.")
    print()


def _toolbar(state: _ShellState) -> HTML:
    if state.paths is None:
        return HTML("<b>no workspace</b> — /init or /cd")
    rows = _services.all_status(state.paths)
    server = next((s for s in rows if s.name == "server"), None)
    ui = next((s for s in rows if s.name == "ui"), None)

    def fmt(s: Any) -> str:
        if s is None:
            return "?"
        marker = "●" if s.state == "running" else "○"
        port = f":{s.port}" if s.port else ""
        return f"{marker} {s.name}{port}"

    return HTML(
        f"<b>{state.paths.root.name}</b>  {fmt(server)}  {fmt(ui)}  "
        f"(/help · /exit)"
    )


def _try_autostart(state: _ShellState) -> None:
    """Best-effort: start any service that isn't already running.
    Failures don't kill the shell — we just print and continue."""
    if state.paths is None:
        return
    for s in _services.all_status(state.paths):
        if s.state == "running":
            continue
        try:
            started = _services.start(state.paths, s.name)
        except ServiceError as exc:
            print(f"  {s.name:<7} ○ couldn't start — {exc}")
            continue
        marker = "●" if started.state == "running" else "○"
        print(
            f"  {started.name:<7} {marker} {started.state:<8} "
            f"http://127.0.0.1:{started.port}"
        )


def _resolve_initial_workspace(initial_path: str | None) -> WorkspacePaths | None:
    """Find a workspace from an explicit path, or by walking up from
    cwd. Returns None if neither yields one — the shell handles the
    no-workspace case."""
    start: Path | None = Path(initial_path).expanduser() if initial_path else None
    return find_workspace(start)


class _SlashCompleter(Completer):
    """Autocomplete the slash command at the start of the line."""

    def get_completions(self, document: Document, _complete_event: Any):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        # Only complete the first token.
        if " " in text:
            return
        for cmd in SLASH_COMMANDS:
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))
