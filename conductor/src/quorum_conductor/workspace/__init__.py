"""Workspace utilities — kept after the protocol retirement.

The protocol-era lifecycle (init / state / archive / bootstrapper /
status / asks / deliberation files) has been retired. What remains:

- `identity`: best-effort default human handle detection.
- `process`: PID/PGID helpers used by the service launcher.
- `services`: start / stop / status for the conductor server + UI.
"""

from . import services
from .identity import default_human_handle

__all__ = ["default_human_handle", "services"]
