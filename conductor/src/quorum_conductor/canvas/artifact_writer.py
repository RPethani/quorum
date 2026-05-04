"""Write parsed artifact emits to disk.

Per `docs-specs/canvas-redesign.md` D5 / S3, every artifact create
or update overwrites the file wholesale. The previous version is
*not* discarded — it's moved to the workspace's `.trash/` folder so
nothing is silently destroyed and we have a path to "undo" later if
the user asks for one.

Trash filenames carry a UTC timestamp so multiple revisions of the
same artifact accumulate without colliding::

    artifacts/requirements.md           (current)
    .trash/requirements.20260503T101530Z.md   (archived)
    .trash/requirements.20260503T093122Z.md   (older)

This module is the only sanctioned writer of `artifacts/*.md`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .artifacts import ArtifactEmit


@dataclass(frozen=True)
class ArtifactWriteResult:
    """Outcome of writing one artifact emit."""

    filename: str
    """Relative path under `artifacts/`, e.g. ``requirements.md``."""
    artifact_path: Path
    """Absolute path of the live file we wrote."""
    archived_path: Path | None
    """Absolute path of the prior version moved to ``.trash/``,
    or ``None`` if there was no prior version."""


def write_artifact(
    workspace: Path,
    emit: ArtifactEmit,
    *,
    now: datetime | None = None,
) -> ArtifactWriteResult:
    """Write *emit* to ``workspace/artifacts/<filename>``.

    If the artifact already exists, the prior version is moved to
    ``workspace/.trash/<stem>.<UTC-timestamp>.<ext>`` first. Parent
    directories under ``artifacts/`` are created on demand so emits
    can target nested paths (e.g. ``specs/api.md``).
    """
    artifacts_dir = workspace / "artifacts"
    trash_dir = workspace / ".trash"
    target = artifacts_dir / emit.filename

    archived: Path | None = None
    if target.exists():
        archived = _archive(target, trash_dir, now=now)

    target.parent.mkdir(parents=True, exist_ok=True)
    body = emit.body if emit.body.endswith("\n") else emit.body + "\n"
    target.write_text(body, encoding="utf-8")

    return ArtifactWriteResult(
        filename=emit.filename,
        artifact_path=target,
        archived_path=archived,
    )


def _archive(current: Path, trash_dir: Path, *, now: datetime | None) -> Path:
    trash_dir.mkdir(parents=True, exist_ok=True)
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    archived = trash_dir / f"{current.stem}.{ts}{current.suffix}"
    # Avoid clobbering if a duplicate timestamp ever appears (e.g.
    # tests that fix `now`); append a counter suffix.
    counter = 0
    while archived.exists():
        counter += 1
        archived = trash_dir / f"{current.stem}.{ts}.{counter}{current.suffix}"
    shutil.move(str(current), str(archived))
    return archived
