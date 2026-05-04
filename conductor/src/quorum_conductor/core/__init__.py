"""Conductor core utilities — kept after the protocol retirement.

Only the bits the canvas surface still uses live here:

- `participants`: parse `registers/participants.md`.
- `participants_edit`: append rows to it (from the UI's "+ Add" flow).

Cost tracking will be rewired against canvas events later — for now
the canvas state.yaml's `cost` block is updated lazily by future code
paths and read via `canvas.state.load_state`.
"""

from .participants import Participant, ParticipantsParseError, parse_participants
from .participants_edit import (
    NewParticipant,
    ParticipantsEditError,
    append_participant,
)

__all__ = [
    "NewParticipant",
    "Participant",
    "ParticipantsEditError",
    "ParticipantsParseError",
    "append_participant",
    "parse_participants",
]
