"""Persistent terminal shell for Quorum.

`quorum` with no subcommand drops the user into a slash-command REPL
backed by prompt_toolkit. Public entry: :func:`run_shell`.
"""

from .shell import run_shell

__all__ = ["run_shell"]
