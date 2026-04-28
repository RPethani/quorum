"""Conductor core: participants, routing-defaults, deliberation metadata, routing engine.

Pure-logic layer. No subprocess, no I/O beyond reading workspace files.
The conductor's loop (Phase 4f) drives this; the routing engine itself
has no notion of time or concurrency.
"""

from .config import WorkspaceConfig, load_workspace_config
from .deliberation import DeliberationMeta, DeliberationRoles, load_deliberation
from .participants import Participant, parse_participants
from .routing import (
    Alternative,
    NoHandleAvailableError,
    RoutingDecision,
    RoutingLayer,
    route,
)
from .routing_defaults import RoutingDefaults, load_routing_defaults
from .validator import (
    FullMoveValidation,
    render_validation_feedback,
    required_sections_for,
    validate_move,
)

__all__ = [
    "Alternative",
    "DeliberationMeta",
    "DeliberationRoles",
    "FullMoveValidation",
    "NoHandleAvailableError",
    "Participant",
    "RoutingDecision",
    "RoutingDefaults",
    "RoutingLayer",
    "WorkspaceConfig",
    "load_deliberation",
    "load_routing_defaults",
    "load_workspace_config",
    "parse_participants",
    "render_validation_feedback",
    "required_sections_for",
    "route",
    "validate_move",
]
