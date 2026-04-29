"""In-process digestion queue.

The CLI's `quorum context add-repo` runs digestion synchronously,
which is fine for a terminal but unworkable behind an HTTP request
that has to return in milliseconds. The UI's Digestion dialog needs
to:

  * see the current status of every registered repo (digested / not
    digested / in progress / failed),
  * trigger a digest in the background and watch it complete,
  * route per-repo to a different agent if the user wants to override
    the relevance-default digester.

This module is the small daemon that backs all of that. Status lives
in memory (one dict per workspace, keyed by repo name) and is also
mirrored to `runtime/services/digestions.json` so a server restart
recovers the audit trail.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..paths import WorkspacePaths
from .config import load_workspace_config
from .digestion import RepoSpec, digest_repo
from .participants import Participant, parse_participants

DigestionStatus = Literal["idle", "queued", "running", "ok", "failed"]


@dataclass
class RepoDigestionState:
    """One row of the digestion tracker."""

    name: str
    relevance: str
    proposed_digester: str | None
    chosen_digester: str | None = None
    status: DigestionStatus = "idle"
    started_at: str | None = None
    completed_at: str | None = None
    duration_s: float | None = None
    error: str | None = None
    digest_exists: bool = False
    last_digested_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class _StoreShape:
    """JSON shape persisted under runtime/services/digestions.json."""

    repos: dict[str, RepoDigestionState] = field(default_factory=dict)


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


_LOCK = threading.Lock()
_STATE_BY_WORKSPACE: dict[Path, _StoreShape] = {}


def list_states(paths: WorkspacePaths) -> list[RepoDigestionState]:
    """Return one state row per registered repo, materialising defaults."""
    store = _ensure_store(paths)
    out: list[RepoDigestionState] = []
    config_extras = _safe_config_extras(paths)
    participants = _safe_participants(paths)
    digester_defaults = _digester_defaults(config_extras)
    repos = _registered_repos(paths)
    for repo in repos:
        name = str(repo.get("name", "")).strip()
        relevance = str(repo.get("relevance", "medium")).strip() or "medium"
        if not name:
            continue
        with _LOCK:
            state = store.repos.get(name)
            if state is None:
                state = RepoDigestionState(
                    name=name,
                    relevance=relevance,
                    proposed_digester=_propose_digester(
                        relevance, digester_defaults, participants
                    ),
                )
                store.repos[name] = state
            else:
                # Refresh proposed digester in case participants changed.
                state.relevance = relevance
                state.proposed_digester = _propose_digester(
                    relevance, digester_defaults, participants
                )
        # Reflect on-disk truth: digest.md presence + meta.yaml date.
        digest_path = paths.context_repos / name / "digest.md"
        meta_path = paths.context_repos / name / "meta.yaml"
        state.digest_exists = digest_path.is_file()
        state.last_digested_at = _read_meta_timestamp(meta_path)
        if (
            state.digest_exists
            and state.status not in {"running", "queued", "failed"}
        ):
            state.status = "ok"
        out.append(state)
    _persist(paths, store)
    return out


def queue_digest(
    paths: WorkspacePaths, name: str, *, digester_handle: str | None = None
) -> RepoDigestionState:
    """Queue a digestion run for `name`. Spawns a background thread.

    If `digester_handle` is None, picks the proposed default. Returns
    the tracker row so callers can poll. Idempotent — re-queueing while
    already running is a no-op.
    """
    store = _ensure_store(paths)
    repos = _registered_repos(paths)
    repo = next((r for r in repos if str(r.get("name")) == name), None)
    if repo is None:
        raise ValueError(f"no repo registered with name {name!r}")
    relevance = str(repo.get("relevance", "medium")).strip() or "medium"

    participants = _safe_participants(paths)
    by_handle: dict[str, Participant] = {p.handle: p for p in participants}
    chosen: str | None
    if digester_handle and digester_handle in by_handle:
        chosen = digester_handle
    else:
        config_extras = _safe_config_extras(paths)
        chosen = _propose_digester(relevance, _digester_defaults(config_extras), participants)
    if chosen is None:
        raise ValueError(
            "No usable cli-transport agent. Add an agent first, then retry."
        )

    with _LOCK:
        state = store.repos.get(name) or RepoDigestionState(
            name=name,
            relevance=relevance,
            proposed_digester=chosen,
        )
        if state.status in {"queued", "running"}:
            return state
        state.relevance = relevance
        state.chosen_digester = chosen
        state.status = "queued"
        state.started_at = None
        state.completed_at = None
        state.duration_s = None
        state.error = None
        store.repos[name] = state
    _persist(paths, store)

    # TODO: emit digester_chosen event for audit trail (design-doc §1.8).
    # Pending a generic Event subclass; the chosen handle is recorded in
    # runtime/services/digestions.json regardless.

    threading.Thread(
        target=_run_digestion,
        args=(paths, name, chosen, by_handle.get(chosen)),
        daemon=True,
    ).start()
    return state


# ---------------------------------------------------------------------- #
# Background worker
# ---------------------------------------------------------------------- #


def _run_digestion(
    paths: WorkspacePaths,
    name: str,
    digester_handle: str,
    digester: Participant | None,
) -> None:
    store = _ensure_store(paths)
    repos = _registered_repos(paths)
    repo = next((r for r in repos if str(r.get("name")) == name), None)
    if repo is None or digester is None:
        with _LOCK:
            state = store.repos.get(name)
            if state is not None:
                state.status = "failed"
                state.error = "repo or digester not found"
        _persist(paths, store)
        return

    repo_path_str = str(repo.get("path", "")).strip()
    role = str(repo.get("role", "")).strip()
    relevance = str(repo.get("relevance", "medium")).strip() or "medium"
    if relevance not in {"high", "medium", "low"}:
        relevance = "medium"
    spec_relevance: Literal["high", "medium", "low"] = relevance  # type: ignore[assignment]
    spec = RepoSpec(
        name=name,
        path=Path(repo_path_str).expanduser().resolve(),
        role=role,
        relevance=spec_relevance,
    )
    target = paths.context_repos / name
    target.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        state = store.repos.setdefault(
            name,
            RepoDigestionState(name=name, relevance=relevance, proposed_digester=digester_handle),
        )
        state.status = "running"
        state.started_at = _now_iso()
        state.chosen_digester = digester_handle
    _persist(paths, store)

    try:
        result = digest_repo(spec, digester, target)
    except Exception as exc:
        with _LOCK:
            state.status = "failed"
            state.completed_at = _now_iso()
            state.error = f"{type(exc).__name__}: {exc}"
        _persist(paths, store)
        return

    with _LOCK:
        state.status = "ok" if result.status == "ok" else "failed"
        state.completed_at = _now_iso()
        state.duration_s = result.duration_s
        state.error = result.error
    _persist(paths, store)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _registered_repos(paths: WorkspacePaths) -> list[dict[str, object]]:
    from .context_bundle import load_context_manifest

    manifest = load_context_manifest(paths)
    repos = manifest.get("repos") or []
    return [r for r in repos if isinstance(r, dict)]


def _safe_config_extras(paths: WorkspacePaths) -> dict[str, object]:
    try:
        cfg = load_workspace_config(paths.config_yaml)
    except Exception:
        return {}
    return cfg.extras or {}


def _safe_participants(paths: WorkspacePaths) -> list[Participant]:
    try:
        return list(parse_participants(paths.participants))
    except Exception:
        return []


def _digester_defaults(extras: dict[str, object]) -> dict[str, str]:
    ctx = extras.get("context") if isinstance(extras, dict) else None
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get("digester_defaults")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _propose_digester(
    relevance: str,
    digester_defaults: dict[str, str],
    participants: list[Participant],
) -> str | None:
    """Pick the proposed digester handle for a given relevance level.

    Honour user override first; otherwise canonical relevance default;
    otherwise first registered cli-transport participant.
    """
    override = digester_defaults.get(relevance)
    if override:
        return override
    canonical = {
        "high": "@claude-opus",
        "medium": "@claude-sonnet",
        "low": "@claude-haiku",
    }.get(relevance)
    if canonical:
        for p in participants:
            if p.handle == canonical and p.transport == "cli":
                return canonical
    for p in participants:
        if p.transport == "cli":
            return p.handle
    return None


def _ensure_store(paths: WorkspacePaths) -> _StoreShape:
    with _LOCK:
        store = _STATE_BY_WORKSPACE.get(paths.root)
        if store is None:
            store = _load(paths)
            _STATE_BY_WORKSPACE[paths.root] = store
        return store


def _store_path(paths: WorkspacePaths) -> Path:
    return paths.runtime / "services" / "digestions.json"


def _load(paths: WorkspacePaths) -> _StoreShape:
    p = _store_path(paths)
    if not p.is_file():
        return _StoreShape()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _StoreShape()
    repos: dict[str, RepoDigestionState] = {}
    for k, v in (raw.get("repos") or {}).items():
        try:
            repos[str(k)] = RepoDigestionState(**v)
        except TypeError:
            continue
    return _StoreShape(repos=repos)


def _persist(paths: WorkspacePaths, store: _StoreShape) -> None:
    target = _store_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"repos": {k: v.to_dict() for k, v in store.repos.items()}}
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_meta_timestamp(meta_path: Path) -> str | None:
    if not meta_path.is_file():
        return None
    try:
        import yaml as _yaml

        data = _yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        v = data.get("last_digested_at") if isinstance(data, dict) else None
        return str(v) if v else None
    except Exception:
        return None


__all__ = [
    "RepoDigestionState",
    "list_states",
    "queue_digest",
]
