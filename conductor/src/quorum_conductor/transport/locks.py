"""Per-deliberation file lock.

Design-doc §10 mandates `fcntl.flock` on Linux/macOS to serialise
appends to a deliberation file across parallel invocations. This module
exposes a context manager that opens (creating if necessary) a lock
file beside the deliberation and holds an exclusive flock for the
duration of the `with` block. The lock is advisory — only processes
that opt in see it — which is what we want: external editors don't
contend with the conductor.
"""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def deliberation_lock(deliberation_path: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock on the deliberation while in scope.

    Lock is held on a sibling `.lock` file rather than the deliberation
    itself to avoid any chance of corrupting the data file via the
    lock fd.
    """
    deliberation_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = deliberation_path.with_suffix(deliberation_path.suffix + ".lock")
    with lock_path.open("a+") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
