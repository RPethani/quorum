"""Canonical workspace paths.

Centralises the design-doc §7 folder layout so every module references the
same names. A `WorkspacePaths` is constructed once per CLI invocation from
the user's chosen workspace root (the directory containing `state.yaml`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    """File-system layout of a Quorum workspace.

    The workspace root is the directory that holds `state.yaml`. By
    convention the user runs `quorum init` *inside* a project, producing a
    `./quorum/` subfolder which becomes the root.
    """

    root: Path

    # --- top-level files ---
    @property
    def state_yaml(self) -> Path:
        return self.root / "state.yaml"

    @property
    def config_yaml(self) -> Path:
        return self.root / "config.yaml"

    @property
    def problem_statement(self) -> Path:
        return self.root / "problem-statement.md"

    @property
    def outcome_manifest(self) -> Path:
        return self.root / "outcome-manifest.md"

    @property
    def gitignore(self) -> Path:
        return self.root / ".gitignore"

    # --- directories ---
    @property
    def deliberations(self) -> Path:
        return self.root / "deliberations"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def artifact_versions(self) -> Path:
        return self.artifacts / "versions"

    @property
    def decisions(self) -> Path:
        return self.root / "decisions"

    @property
    def tasks(self) -> Path:
        return self.root / "tasks"

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def registers(self) -> Path:
        return self.root / "registers"

    @property
    def participants(self) -> Path:
        return self.registers / "participants.md"

    @property
    def routing_defaults(self) -> Path:
        return self.registers / "routing-defaults.yaml"

    @property
    def open_questions(self) -> Path:
        return self.registers / "open-questions.md"

    @property
    def glossary(self) -> Path:
        return self.registers / "glossary.md"

    @property
    def context(self) -> Path:
        return self.root / "context"

    @property
    def context_repos(self) -> Path:
        return self.context / "repos"

    @property
    def context_docs(self) -> Path:
        return self.context / "docs"

    @property
    def context_web(self) -> Path:
        return self.context / "web"

    @property
    def context_notes(self) -> Path:
        return self.context / "notes"

    @property
    def runtime(self) -> Path:
        return self.root / "runtime"

    @property
    def runtime_active(self) -> Path:
        return self.runtime / "active"

    @property
    def runtime_streams(self) -> Path:
        return self.runtime / "streams"

    @property
    def runtime_streams_failed(self) -> Path:
        return self.runtime_streams / "failed"

    @property
    def events_dir(self) -> Path:
        return self.runtime / "events"

    @property
    def events_jsonl(self) -> Path:
        return self.events_dir / "events.jsonl"

    @property
    def conductor_pid(self) -> Path:
        return self.runtime / "conductor.pid"

    @property
    def ui_pid(self) -> Path:
        return self.runtime / "ui.pid"

    # --- ergonomics ---
    def all_directories(self) -> list[Path]:
        """Every directory `init` should ensure exists. Order is irrelevant."""
        return [
            self.deliberations,
            self.artifacts,
            self.artifact_versions,
            self.decisions,
            self.tasks,
            self.inbox,
            self.registers,
            self.context,
            self.context_repos,
            self.context_docs,
            self.context_notes,
            self.context_web,
            self.runtime,
            self.runtime_active,
            self.runtime_streams,
            self.runtime_streams_failed,
            self.events_dir,
        ]


def find_workspace(start: Path | None = None) -> WorkspacePaths | None:
    """Walk up from `start` (default: cwd) looking for a `state.yaml`.

    Returns the workspace root if found, else None. Mirrors how `git`
    locates its repo root from any subdirectory.
    """
    cwd = (start or Path.cwd()).resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "state.yaml").is_file():
            return WorkspacePaths(root=candidate)
    return None


def require_workspace(start: Path | None = None) -> WorkspacePaths:
    """Like `find_workspace`, but raise a clear error if none is found."""
    ws = find_workspace(start)
    if ws is None:
        raise WorkspaceNotFoundError(
            "Couldn't find a Quorum workspace from "
            f"{(start or Path.cwd()).resolve()}. "
            "Run `quorum init` first, or cd into an existing workspace."
        )
    return ws


class WorkspaceNotFoundError(RuntimeError):
    """Raised when a command requires a workspace and none can be located."""
