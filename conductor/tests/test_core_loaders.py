"""Tests for the four input loaders the routing engine depends on:
participants.md, routing-defaults.yaml, config.yaml, deliberation
frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quorum_conductor.core import (
    Participant,
    load_deliberation,
    load_routing_defaults,
    load_workspace_config,
    parse_participants,
)
from quorum_conductor.core.deliberation import DeliberationParseError
from quorum_conductor.core.routing_defaults import RoutingDefaultsError

# ---------------------------------------------------------------------- #
# participants.md
# ---------------------------------------------------------------------- #


def test_participants_parses_canonical_table(tmp_path: Path) -> None:
    body = """\
---
schema_version: 0.1
---

# Participants Registry

| Handle | Display Name | CLI Command | Model | Transport | Quota (daily/per-deliberation) | Permission Capability | Account Label | Health |
|---|---|---|---|---|---|---|---|---|
| @claude-opus | Claude (Opus) | claude --print --model opus | claude-opus-4-7 | cli | 30/5 | fine_grained | (none) | green |
| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |
"""
    path = tmp_path / "participants.md"
    path.write_text(body, encoding="utf-8")
    rows = parse_participants(path)
    assert {r.handle for r in rows} == {"@claude-opus", "@human-rohan"}
    opus = next(r for r in rows if r.handle == "@claude-opus")
    assert opus.transport == "cli"
    assert opus.quota_daily == 30
    assert opus.quota_per_deliberation == 5
    assert opus.health == "green"
    human = next(r for r in rows if r.handle == "@human-rohan")
    assert human.transport == "manual"
    assert human.quota_daily is None  # unlimited


def test_participants_supports_inherits_fitness_from(tmp_path: Path) -> None:
    body = """\
| Handle | Display Name | CLI Command | Model | Transport | Quota | Permission Capability | Account Label | Health | Inherits Fitness From |
|---|---|---|---|---|---|---|---|---|---|
| @claude-work-opus | Claude (Work) | claude-work --print --model opus | claude-opus-4-7 | cli | 30/5 | fine_grained | Work | green | @claude-opus |
"""
    path = tmp_path / "participants.md"
    path.write_text(body, encoding="utf-8")
    rows = parse_participants(path)
    assert rows[0].inherits_fitness_from == "@claude-opus"


def test_participants_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert parse_participants(tmp_path / "missing.md") == []


# ---------------------------------------------------------------------- #
# routing-defaults.yaml
# ---------------------------------------------------------------------- #


def test_routing_defaults_round_trip(tmp_path: Path) -> None:
    yaml_body = """\
schema_version: 0.1
fitness:
  "@claude-opus":
    proposer: 3
    critic: 2
cost:
  "@claude-opus": 5
"""
    path = tmp_path / "routing-defaults.yaml"
    path.write_text(yaml_body, encoding="utf-8")
    defaults = load_routing_defaults(path)
    assert defaults.fitness_for("@claude-opus", "proposer") == 3
    assert defaults.cost_for("@claude-opus") == 5
    # Inheritance fallback works.
    assert (
        defaults.fitness_for("@claude-work-opus", "proposer", inherits_from="@claude-opus")
        == 3
    )


def test_routing_defaults_missing_returns_empty(tmp_path: Path) -> None:
    defaults = load_routing_defaults(tmp_path / "missing.yaml")
    assert defaults.fitness == {}
    assert defaults.cost == {}


def test_routing_defaults_rejects_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("- a list at the top level\n", encoding="utf-8")
    with pytest.raises(RoutingDefaultsError):
        load_routing_defaults(path)


# ---------------------------------------------------------------------- #
# config.yaml
# ---------------------------------------------------------------------- #


def test_config_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = load_workspace_config(tmp_path / "config.yaml")
    assert cfg.cost_ceiling_usd == 50.0
    assert cfg.cost_enforce is True
    assert cfg.routing_overrides == {}
    assert cfg.unavailability_policy == "substitute"


def test_config_reads_routing_overrides(tmp_path: Path) -> None:
    body = """\
schema_version: 0.1
routing:
  overrides:
    synthesizer: "@claude-opus"
cost:
  ceiling_usd: 25.0
  enforce: false
caps:
  per_deliberation_invocations: 50
unavailability_policy: strict
"""
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    cfg = load_workspace_config(path)
    assert cfg.routing_overrides == {"synthesizer": "@claude-opus"}
    assert cfg.cost_ceiling_usd == 25.0
    assert cfg.cost_enforce is False
    assert cfg.per_deliberation_invocations == 50
    assert cfg.unavailability_policy == "strict"


# ---------------------------------------------------------------------- #
# deliberation frontmatter
# ---------------------------------------------------------------------- #


def test_deliberation_frontmatter_parses_roles(tmp_path: Path) -> None:
    body = """\
---
id: "0014"
title: Pricing tier structure
status: IN_REVIEW
protocol_version: 0.1
roles:
  proposer: "@claude-opus"
  critics: ["@gemini-pro"]
  synthesizer: "@codex-gpt5"
  decider: "@human-rohan"
tags: [pricing, mvp]
final: false
---

## Question

Should v1 ship with a free tier?
"""
    path = tmp_path / "0014-pricing.md"
    path.write_text(body, encoding="utf-8")
    meta = load_deliberation(path)
    assert meta.id == "0014"
    assert meta.status == "IN_REVIEW"
    assert meta.roles.proposer == "@claude-opus"
    assert meta.roles.critics == ["@gemini-pro"]
    assert meta.roles.for_role("critic") == "@gemini-pro"
    assert meta.roles.for_role("decider") == "@human-rohan"
    assert meta.tags == ["pricing", "mvp"]


def test_deliberation_without_frontmatter_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.md"
    path.write_text("# No frontmatter here\n", encoding="utf-8")
    with pytest.raises(DeliberationParseError):
        load_deliberation(path)


def test_participant_dataclass_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    p = Participant(
        handle="@x",
        display_name="x",
        cli_command="x",
        model="m",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health="green",
    )
    with pytest.raises(FrozenInstanceError):
        p.handle = "@y"  # type: ignore[misc]
