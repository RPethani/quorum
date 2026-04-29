"""Tests for the layered routing engine (design-doc §3.6)."""

from __future__ import annotations

import pytest

from quorum_conductor.core import (
    DeliberationMeta,
    DeliberationRoles,
    NoHandleAvailableError,
    Participant,
    RoutingDefaults,
    RoutingLayer,
    WorkspaceConfig,
    route,
)


def _participant(handle: str, *, health: str = "green", inherits: str | None = None) -> Participant:
    return Participant(
        handle=handle,
        display_name=handle,
        cli_command=f"{handle.lstrip('@')} --x",
        model="model",
        transport="cli",
        quota_daily=None,
        quota_per_deliberation=None,
        permission_capability="fine_grained",
        account_label="",
        health=health,
        inherits_fitness_from=inherits,
    )


def _delib(roles: DeliberationRoles | None = None) -> DeliberationMeta:
    return DeliberationMeta(
        id="0001",
        title="test",
        status="OPEN",
        roles=roles or DeliberationRoles(),
        tags=[],
    )


# ---------------------------------------------------------------------- #
# Layer 3 — fitness-based defaults (the normal path)
# ---------------------------------------------------------------------- #


def test_layer3_picks_highest_fitness() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"proposer": 3},
            "@gemini-pro": {"proposer": 2},
        },
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [_participant("@claude-opus"), _participant("@gemini-pro")]
    decision = route(
        role="proposer",
        deliberation=_delib(),
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@claude-opus"
    assert decision.layer is RoutingLayer.DEFAULTS
    assert decision.fitness == 3
    assert decision.cost == 5
    assert any(a.handle == "@gemini-pro" for a in decision.alternatives)


def test_layer3_breaks_ties_by_lowest_cost() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"critic": 3},
            "@gemini-pro": {"critic": 3},
        },
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [_participant("@claude-opus"), _participant("@gemini-pro")]
    decision = route(
        role="critic",
        deliberation=_delib(),
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@gemini-pro"
    assert decision.cost == 3


def test_layer3_skips_unhealthy_handles() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"proposer": 3},
            "@gemini-pro": {"proposer": 2},
        },
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [
        _participant("@claude-opus", health="red"),
        _participant("@gemini-pro"),
    ]
    decision = route(
        role="proposer",
        deliberation=_delib(),
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@gemini-pro"
    assert any(a.rejected_because == "unhealthy" for a in decision.alternatives)


# ---------------------------------------------------------------------- #
# Layer 1 — per-deliberation override
# ---------------------------------------------------------------------- #


def test_layer1_pin_in_frontmatter_wins() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"synthesizer": 3},
            "@gemini-pro": {"synthesizer": 2},
        },
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [_participant("@claude-opus"), _participant("@gemini-pro")]
    delib = _delib(DeliberationRoles(synthesizer="@gemini-pro"))
    decision = route(
        role="synthesizer",
        deliberation=delib,
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@gemini-pro"
    assert decision.layer is RoutingLayer.PER_DELIBERATION


def test_layer1_pin_falls_through_when_handle_missing() -> None:
    """A pin to a handle absent from the registry must not crash."""
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"proposer": 3}},
        cost={"@claude-opus": 5},
    )
    participants = [_participant("@claude-opus")]
    delib = _delib(DeliberationRoles(proposer="@absent-handle"))
    decision = route(
        role="proposer",
        deliberation=delib,
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@claude-opus"
    assert decision.layer is RoutingLayer.DEFAULTS


# ---------------------------------------------------------------------- #
# Layer 2 — workspace override
# ---------------------------------------------------------------------- #


def test_layer2_workspace_override() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"reviewer": 3},
            "@gemini-pro": {"reviewer": 3},
        },
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [_participant("@claude-opus"), _participant("@gemini-pro")]
    config = WorkspaceConfig(routing_overrides={"reviewer": "@claude-opus"})
    decision = route(
        role="reviewer",
        deliberation=_delib(),
        participants=participants,
        config=config,
        defaults=defaults,
    )
    assert decision.handle == "@claude-opus"
    assert decision.layer is RoutingLayer.WORKSPACE


# ---------------------------------------------------------------------- #
# Layer 4 — fallback
# ---------------------------------------------------------------------- #


def test_layer4_fallback_when_no_fitness_for_role() -> None:
    defaults = RoutingDefaults(
        fitness={
            "@claude-opus": {"proposer": 3},
            "@haiku": {"proposer": 1},
        },
        cost={"@claude-opus": 5, "@haiku": 1},
    )
    # Asking for a role nobody is rated for.
    participants = [_participant("@claude-opus"), _participant("@haiku")]
    decision = route(
        role="exotic_role",
        deliberation=_delib(),
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.layer is RoutingLayer.FALLBACK
    # Highest-cost available wins the fallback (Opus over Haiku).
    assert decision.handle == "@claude-opus"
    assert decision.note  # carries an actionable explanation


def test_no_handle_available_when_everyone_is_red() -> None:
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"proposer": 3}},
        cost={"@claude-opus": 5},
    )
    participants = [_participant("@claude-opus", health="red")]
    with pytest.raises(NoHandleAvailableError) as exc_info:
        route(
            role="proposer",
            deliberation=_delib(),
            participants=participants,
            config=WorkspaceConfig(),
            defaults=defaults,
        )
    err = exc_info.value
    assert err.role == "proposer"
    assert any(a.rejected_because == "unhealthy" for a in err.alternatives)


# ---------------------------------------------------------------------- #
# Fitness inheritance for non-canonical handles
# ---------------------------------------------------------------------- #


def test_strict_policy_refuses_substitution_when_pin_unhealthy() -> None:
    """`unavailability_policy=strict` should NOT fall through Layer 1."""
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"proposer": 3}, "@gemini-pro": {"proposer": 2}},
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [
        _participant("@claude-opus", health="red"),  # the pin
        _participant("@gemini-pro"),  # would substitute under default policy
    ]
    delib = _delib(DeliberationRoles(proposer="@claude-opus"))
    config = WorkspaceConfig(unavailability_policy="strict")
    with pytest.raises(NoHandleAvailableError) as exc:
        route(
            role="proposer",
            deliberation=delib,
            participants=participants,
            config=config,
            defaults=defaults,
        )
    assert any("policy: strict" in (a.rejected_because or "") for a in exc.value.alternatives)


def test_strict_policy_refuses_substitution_for_workspace_override() -> None:
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"reviewer": 3}, "@gemini-pro": {"reviewer": 3}},
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [
        _participant("@claude-opus", health="red"),
        _participant("@gemini-pro"),
    ]
    config = WorkspaceConfig(
        routing_overrides={"reviewer": "@claude-opus"},
        unavailability_policy="strict",
    )
    with pytest.raises(NoHandleAvailableError):
        route(
            role="reviewer",
            deliberation=_delib(),
            participants=participants,
            config=config,
            defaults=defaults,
        )


def test_substitute_policy_falls_through_when_pin_unhealthy() -> None:
    """Default `substitute` should still pick the best replacement."""
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"proposer": 3}, "@gemini-pro": {"proposer": 2}},
        cost={"@claude-opus": 5, "@gemini-pro": 3},
    )
    participants = [
        _participant("@claude-opus", health="red"),
        _participant("@gemini-pro"),
    ]
    delib = _delib(DeliberationRoles(proposer="@claude-opus"))
    config = WorkspaceConfig()  # default substitute
    decision = route(
        role="proposer",
        deliberation=delib,
        participants=participants,
        config=config,
        defaults=defaults,
    )
    assert decision.handle == "@gemini-pro"


def test_strict_policy_blocks_layer4_fallback() -> None:
    """Strict refuses unrated fallback even when Layer 3 yields nothing."""
    defaults = RoutingDefaults(fitness={}, cost={"@claude-opus": 5})
    participants = [_participant("@claude-opus")]
    config = WorkspaceConfig(unavailability_policy="strict")
    with pytest.raises(NoHandleAvailableError):
        route(
            role="some-untracked-role",
            deliberation=_delib(),
            participants=participants,
            config=config,
            defaults=defaults,
        )


def test_inheritance_resolves_to_canonical_fitness() -> None:
    defaults = RoutingDefaults(
        fitness={"@claude-opus": {"synthesizer": 3, "proposer": 3}},
        cost={"@claude-opus": 5},
    )
    # Custom multi-account handle, inherits from the canonical Opus.
    participants = [_participant("@claude-work-opus", inherits="@claude-opus")]
    decision = route(
        role="synthesizer",
        deliberation=_delib(),
        participants=participants,
        config=WorkspaceConfig(),
        defaults=defaults,
    )
    assert decision.handle == "@claude-work-opus"
    assert decision.fitness == 3
    assert decision.cost == 5
