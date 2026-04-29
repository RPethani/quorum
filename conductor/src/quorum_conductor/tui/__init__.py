"""Interactive REPL — `quorum` with no args drops you into the shell.

The TUI is the operator console: start/stop/status/step/logs/permissions
in one terminal, with slash-command autocomplete and a persistent
header showing service state. The web UI remains the place you read
deliberations and make human moves.
"""

from .shell import run_shell

__all__ = ["run_shell"]
