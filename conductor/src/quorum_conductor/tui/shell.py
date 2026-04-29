"""Interactive shell for Quorum.

Runs when the user types `quorum` with no subcommand. Provides a
slash-command REPL that wraps the existing CLI so every operation a
power-user would shell into stays in one terminal:

    quorum>
    /help                 → list commands
    /status               → workspace + service status
    /plan                 → what the loop would do next
    /step                 → run the next pending invocation
    /up   /down /restart  → manage the server + UI services
    /logs server -f       → tail a log (Ctrl-C to stop following)
    /open                 → open the UI in the browser
    /quit                 → exit

Implementation notes:
  * `prompt_toolkit.PromptSession` provides the input line, history,
    and slash-command autocomplete.
  * Each command output is printed inline above the next prompt;
    we don't try to be a full TUI with separate panes — that lives
    behind a future Textual upgrade.
  * The header (service status + workspace path) is recomputed on
    every prompt as the bottom-toolbar so it always reflects truth.
"""

from __future__ import annotations

import io
import shlex
import sys
import webbrowser
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from ..paths import WorkspacePaths, find_workspace
from ..workspace import services as _services

# Keep the surface tight — every entry maps to a CLI subcommand.
# (description, argv_template). `argv_template` may be None, meaning
# the rest of the command line is forwarded verbatim.
SLASH_COMMANDS: dict[str, str] = {
    "/help": "Show this help.",
    "/status": "Workspace + service status.",
    "/plan": "Show what the loop would invoke next.",
    "/step": "Run the next pending invocation.",
    "/run": "Foreground loop until idle. Args: [--max-ticks N]",
    "/up": "Start the conductor server + UI in the background.",
    "/down": "Stop the server / UI. Args: [server|ui]",
    "/restart": "Restart the server / UI. Args: [server|ui]",
    "/logs": "Tail a log. Args: [server|ui] [-f] [-n N]",
    "/doctor": "Health-check registered handles.",
    "/pause": "Stop the daemonised conductor loop.",
    "/start": "Start the daemonised conductor loop.",
    "/archive": "Archive the workspace. Args: [--reason …]",
    "/unarchive": "Unarchive the workspace.",
    "/context": "Manage context. Args: add-repo <path> | add-doc <file> | add-note <name> --text … | list",
    "/open": "Open the UI in your default browser.",
    "/next": "Show next-best actions for the current state.",
    "/init": "Scaffold a new workspace here. Args: [path]",
    "/cd": "Change the active workspace. Args: <path>",
    "/clear": "Clear the screen.",
    "/quit": "Exit the shell.",
    "/exit": "Alias for /quit.",
}


def run_shell(initial_path: str | None = None) -> int:
    """Entry point. Returns the process exit code."""
    paths = _resolve_initial_workspace(initial_path)
    state = _ShellState(paths=paths)

    _print_banner(state)

    # Auto-start services if we already have a workspace and they're
    # not running. Surfaces the URLs immediately so the user can open
    # the web UI without a separate command.
    if state.paths is not None:
        _try_autostart(state)

    completer = _SlashCompleter(state)
    session: PromptSession[str] = PromptSession(
        history=InMemoryHistory(),
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
            # Treat Ctrl-C at an empty prompt as "still here".
            continue
        except EOFError:
            print()  # newline after ^D
            return _on_exit(state)

        line = line.strip()
        if not line:
            continue
        if not line.startswith("/"):
            print(
                "tip: commands start with `/`. Try `/help`. "
                "(use the web UI for free-form moves on a deliberation)"
            )
            continue

        try:
            should_exit = _dispatch(state, line)
        except KeyboardInterrupt:
            print()
            print("(interrupted)")
            continue
        except SystemExit as exc:
            # argparse calls sys.exit on --help / errors; trap it.
            print(f"(command exited {exc.code})")
            continue
        except Exception as exc:
            print(f"error: {exc}")
            continue

        if should_exit:
            return _on_exit(state)


# ---------------------------------------------------------------------- #
# State + dispatch
# ---------------------------------------------------------------------- #


class _ShellState:
    """Mutable holder for the shell's session-scope state."""

    def __init__(self, paths: WorkspacePaths | None) -> None:
        self.paths = paths


def _dispatch(state: _ShellState, line: str) -> bool:
    """Run one slash command. Returns True if the shell should exit."""
    parts = shlex.split(line)
    cmd, *rest = parts
    cmd = cmd.lower()

    if cmd in {"/quit", "/exit"}:
        return True
    if cmd == "/help":
        _print_help()
        return False
    if cmd == "/clear":
        # ANSI clear-screen + cursor home.
        print("\033[2J\033[H", end="")
        return False
    if cmd == "/cd":
        if not rest:
            print("usage: /cd <workspace-path>")
            return False
        new_paths = _resolve_initial_workspace(rest[0])
        if new_paths is None:
            print(f"no workspace at {rest[0]} (no state.yaml).")
            return False
        state.paths = new_paths
        print(f"workspace → {new_paths.root}")
        return False
    if cmd == "/init":
        path = rest[0] if rest else "quorum"
        _run_cli(["init", path])
        # If init succeeded, switch the shell to the new workspace.
        candidate = Path(path).expanduser().resolve()
        if (candidate / "state.yaml").is_file():
            state.paths = WorkspacePaths(root=candidate)
        return False
    if cmd == "/open":
        return _do_open(state)

    # Workspace-required commands from here on.
    if state.paths is None:
        print(
            "no workspace. Run `/init [path]`, or start the shell from "
            "inside one (`cd <workspace>; quorum`)."
        )
        return False

    mapping: dict[str, Callable[[_ShellState, list[str]], None]] = {
        "/status": lambda s, r: _run_cli_with_path(s, ["status", *r]),
        "/plan": lambda s, r: _run_cli_with_path(s, ["plan", *r]),
        "/step": lambda s, r: _run_cli_with_path(s, ["step", *r]),
        "/run": lambda s, r: _run_cli_with_path(s, ["run", *r]),
        "/up": lambda s, r: _run_cli_with_path(s, ["up", *r]),
        "/down": lambda s, r: _run_cli_with_path(s, ["down", *r]),
        "/restart": lambda s, r: _run_cli_with_path(s, ["restart", *r]),
        "/logs": lambda s, r: _run_cli_with_path(s, ["logs", *r]),
        "/doctor": lambda s, r: _run_cli_with_path(s, ["doctor", *r]),
        "/pause": lambda s, r: _run_cli_with_path(s, ["pause", *r]),
        "/start": lambda s, r: _run_cli_with_path(s, ["start", *r]),
        "/archive": lambda s, r: _run_cli_with_path(s, ["archive", *r]),
        "/unarchive": lambda s, r: _run_cli_with_path(s, ["unarchive", *r]),
        "/context": lambda s, r: _run_cli_with_path(s, ["context", *r]),
        "/next": _do_next_actions,
    }
    fn = mapping.get(cmd)
    if fn is None:
        print(f"unknown command: {cmd} (try /help)")
        return False
    fn(state, rest)
    return False


def _run_cli_with_path(state: _ShellState, argv: list[str]) -> None:
    if state.paths is None:
        print("no workspace.")
        return
    full = [argv[0], "--path", str(state.paths.root), *argv[1:]]
    _run_cli(full)


def _run_cli(argv: list[str]) -> None:
    """Call the conductor CLI in-process."""
    # Imported lazily to avoid a circular at module import time.
    from ..cli import main as cli_main

    rc = cli_main(argv)
    if rc not in (0, None):
        print(f"(exit {rc})")


# ---------------------------------------------------------------------- #
# Toolbar + banner
# ---------------------------------------------------------------------- #


def _toolbar(state: _ShellState) -> Any:
    if state.paths is None:
        return HTML("<style fg='#9ca3af'>no workspace — try /init or /cd</style>")
    server = _services.status(state.paths, "server")
    ui = _services.status(state.paths, "ui")
    parts = [
        f"<b>{_shorten(state.paths.root)}</b>",
        _service_pill("server", server),
        _service_pill("ui", ui),
    ]
    return HTML("  ".join(parts))


def _service_pill(label: str, st: _services.ServiceStatus) -> str:
    if st.state == "running":
        return f"<style fg='#34d399'>● {label} {st.port}</style>"
    if st.state == "crashed":
        return f"<style fg='#f87171'>✗ {label} crashed</style>"
    return f"<style fg='#9ca3af'>○ {label} stopped</style>"


def _shorten(p: Path) -> str:
    try:
        rel = p.relative_to(Path.home())
        return f"~/{rel}"
    except ValueError:
        return str(p)


def _print_banner(state: _ShellState) -> None:
    print()
    print("  quorum  •  multi-agent collaboration hub")
    print("  type /help for commands, /quit to exit")
    if state.paths is not None:
        print(f"  workspace: {state.paths.root}")
    else:
        print("  no workspace — /init [path] to scaffold one, or /cd <path>")
    print()


def _print_help() -> None:
    print()
    print("  available commands:")
    width = max(len(c) for c in SLASH_COMMANDS) + 2
    for cmd, blurb in SLASH_COMMANDS.items():
        print(f"    {cmd.ljust(width)} {blurb}")
    print()
    print("  forwarded args work — e.g. `/logs ui -f`, `/restart server`.")
    print()


# ---------------------------------------------------------------------- #
# Init flow
# ---------------------------------------------------------------------- #


def _resolve_initial_workspace(initial_path: str | None) -> WorkspacePaths | None:
    if initial_path is not None:
        candidate = Path(initial_path).expanduser().resolve()
        if (candidate / "state.yaml").is_file():
            return WorkspacePaths(root=candidate)
        return None
    return find_workspace()


def _try_autostart(state: _ShellState) -> None:
    if state.paths is None:
        return
    server = _services.status(state.paths, "server")
    ui = _services.status(state.paths, "ui")
    if server.state == "running" and ui.state == "running":
        print(f"  ● server  http://127.0.0.1:{server.port}")
        print(f"  ● ui      http://127.0.0.1:{ui.port}")
        print()
        return
    print("  starting server + ui in the background…")
    # Run quietly; the toolbar will reflect the new state.
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            _run_cli(["up", "--path", str(state.paths.root)])
    except Exception as exc:
        print(f"  (auto-start failed: {exc})")
        return
    # Re-read fresh status now that things are up.
    server = _services.status(state.paths, "server")
    ui = _services.status(state.paths, "ui")
    if server.state == "running":
        print(f"  ● server  http://127.0.0.1:{server.port}")
    if ui.state == "running":
        print(f"  ● ui      http://127.0.0.1:{ui.port}")
    print()


def _do_next_actions(state: _ShellState, _rest: list[str]) -> None:
    """Show the same next-best-action list the UI's panel surfaces."""
    if state.paths is None:
        print("no workspace.")
        return
    from ..core.next_actions import compute_next_actions

    actions = compute_next_actions(state.paths)
    print()
    for i, a in enumerate(actions):
        marker = "★" if a.primary else " "
        print(f"  {marker} {a.title}")
        print(f"      {a.description}")
        if a.payload and a.kind == "cli":
            print(f"      run: {a.payload}")
        elif a.payload and a.kind == "dialog":
            print(f"      open: {a.payload} dialog in the web UI")
        if i < len(actions) - 1:
            print()
    print()


def _do_open(state: _ShellState) -> bool:
    if state.paths is None:
        print("no workspace.")
        return False
    ui = _services.status(state.paths, "ui")
    if ui.state != "running" or not ui.port:
        print("UI is not running. Try /up first.")
        return False
    url = f"http://127.0.0.1:{ui.port}"
    print(f"opening {url} …")
    webbrowser.open(url)
    return False


def _on_exit(state: _ShellState) -> int:
    """Ask whether to leave services running. Default: leave them."""
    if state.paths is None:
        return 0
    server = _services.status(state.paths, "server")
    ui = _services.status(state.paths, "ui")
    if server.state != "running" and ui.state != "running":
        return 0
    print("services are still running:")
    if server.state == "running":
        print(f"  ● server  http://127.0.0.1:{server.port}")
    if ui.state == "running":
        print(f"  ● ui      http://127.0.0.1:{ui.port}")
    try:
        answer = input("stop them on exit? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer == "y":
        from ..cli import main as cli_main

        cli_main(["down", "--path", str(state.paths.root)])
    else:
        print("services left running. `quorum down` from anywhere to stop them.")
    return 0


# ---------------------------------------------------------------------- #
# Completion
# ---------------------------------------------------------------------- #


class _SlashCompleter(Completer):
    """Completes the leading slash command. Args are not completed in v1."""

    def __init__(self, state: _ShellState) -> None:
        self._state = state

    def get_completions(self, document: Document, complete_event: Any) -> Any:
        text = document.text_before_cursor
        # Only complete the first token (the slash command itself).
        if " " in text:
            return
        prefix = text.lower()
        for cmd, blurb in SLASH_COMMANDS.items():
            if cmd.startswith(prefix):
                yield Completion(
                    cmd,
                    start_position=-len(prefix),
                    display_meta=blurb,
                )


# ---------------------------------------------------------------------- #
# Module-level entry for `python -m quorum_conductor.tui`
# ---------------------------------------------------------------------- #


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_shell())
