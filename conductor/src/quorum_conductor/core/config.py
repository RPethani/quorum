"""Read `config.yaml` — the workspace-level config.

Schema source: design-doc §10 plus the template written by `quorum init`.
The fields populated here are exactly those the routing engine reads;
others (cost ceiling, caps, human-timeout policy) round-trip through
`extras` so an older conductor cannot silently drop fields written by a
newer one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class WorkspaceConfig:
    schema_version: str = "0.1"
    routing_overrides: dict[str, str] = field(default_factory=dict)
    cost_ceiling_usd: float = 50.0
    cost_enforce: bool = True
    per_deliberation_invocations: int = 20
    no_progress_steps: int = 6
    unavailability_policy: str = "substitute"  # `substitute` | `strict`
    extras: dict[str, Any] = field(default_factory=dict)


def load_workspace_config(path: Path) -> WorkspaceConfig:
    if not path.is_file():
        return WorkspaceConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise WorkspaceConfigError(f"{path} is not a YAML mapping.")

    routing = (raw.get("routing") or {}).get("overrides") or {}
    if not isinstance(routing, dict):
        raise WorkspaceConfigError(f"{path}: routing.overrides must be a mapping.")

    cost = raw.get("cost") or {}
    caps = raw.get("caps") or {}

    known: set[str] = {
        "schema_version",
        "routing",
        "cost",
        "caps",
        "unavailability_policy",
    }
    extras = {k: v for k, v in raw.items() if k not in known}

    return WorkspaceConfig(
        schema_version=str(raw.get("schema_version", "0.1")),
        routing_overrides={str(k): str(v) for k, v in routing.items()},
        cost_ceiling_usd=float(cost.get("ceiling_usd", 50.0)),
        cost_enforce=bool(cost.get("enforce", True)),
        per_deliberation_invocations=int(caps.get("per_deliberation_invocations", 20)),
        no_progress_steps=int(caps.get("no_progress_steps", 6)),
        unavailability_policy=str(raw.get("unavailability_policy", "substitute")),
        extras=extras,
    )


class WorkspaceConfigError(RuntimeError):
    """Raised when config.yaml is malformed."""
