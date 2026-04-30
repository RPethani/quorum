"""Auto-open the next ratification deliberation after the manifest locks.

Per the Ask UX overhaul (`docs-specs/asks-ux-overhaul.md`), the user
should never have to "start the first deliberation" themselves. Once
`outcome-manifest.md` is LOCKED, the conductor walks the manifest's
declared artifacts in order and opens a deliberation for each one,
one at a time:

  - On first call after ratification: open a deliberation that ratifies
    the first artifact named in the manifest.
  - When that deliberation reaches a terminal state (DECIDED /
    ABANDONED): open the next one.
  - When all artifacts have a deliberation (in any status), do nothing.

We keep the policy "one open ratification deliberation at a time" so
the user's attention is never split across simultaneous artifact
deliberations they didn't ask for.

Artifact discovery (v1): the manifest's body is scanned for filenames
matching `<lower-kebab>.md`. The first occurrence wins; duplicates and
`outcome-manifest.md` itself are excluded. This is intentionally
permissive — manifest templates can list artifacts however the author
wants (numbered list, narrative reference, frontmatter list); the
parser doesn't care.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from ..core.deliberation import load_deliberation
from ..paths import WorkspacePaths

# Whitelist the prefixes that count as a "fresh" filename start —
# beginning of line, whitespace, backtick, paren, bracket, quote,
# colon, comma. This excludes path components (`templates/foo.md`),
# compound suffixes (`a.config.md`), and dash continuations
# (`strategic-decision.md` extracted from `templates/strategic-...`).
_ARTIFACT_RE = re.compile(
    r"(?:^|(?<=[\s`(\[\"',:]))([a-z][a-z0-9_-]*\.md)\b",
    re.MULTILINE,
)
_EXCLUDE = {"outcome-manifest.md", "problem-statement.md", "readme.md"}


def maybe_open_next_artifact_deliberation(paths: WorkspacePaths) -> Path | None:
    """If the manifest is LOCKED and there's a next artifact without a
    ratifying deliberation, open one. Returns the new path, or None if
    nothing was created.
    """
    if not _manifest_is_locked(paths):
        return None
    artifacts = _list_manifest_artifacts(paths)
    if not artifacts:
        return None
    if _has_open_ratification_deliberation(paths):
        # Don't pile up. One ratification deliberation at a time.
        return None
    next_artifact = _first_artifact_without_deliberation(paths, artifacts)
    if next_artifact is None:
        return None
    return _open_artifact_deliberation(paths, next_artifact)


# ---------------------------------------------------------------------- #
# Manifest parsing
# ---------------------------------------------------------------------- #


def _manifest_is_locked(paths: WorkspacePaths) -> bool:
    if not paths.outcome_manifest.is_file():
        return False
    text = paths.outcome_manifest.read_text(encoding="utf-8")
    m = re.search(r"^status:\s*(\S+)\s*$", text, re.MULTILINE)
    return bool(m and m.group(1).upper() == "LOCKED")


def _list_manifest_artifacts(paths: WorkspacePaths) -> list[str]:
    """Return the ordered list of artifact filenames declared in the
    manifest body. De-duped, excluding the manifest itself.

    Also recognises an explicit `artifacts:` list in the frontmatter as
    a future-proof shortcut: if present, it overrides the body scan.
    """
    text = paths.outcome_manifest.read_text(encoding="utf-8")
    fm_match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if fm_match:
        explicit = _parse_frontmatter_artifacts(fm_match.group(1))
        if explicit:
            return explicit
        body = text[fm_match.end() :]
    else:
        body = text

    seen: set[str] = set()
    out: list[str] = []
    for match in _ARTIFACT_RE.finditer(body):
        name = match.group(1).lower()
        if name in _EXCLUDE or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _parse_frontmatter_artifacts(fm: str) -> list[str]:
    """Read `artifacts: [a.md, b.md]` or a YAML block list under
    `artifacts:` from the manifest's frontmatter. Returns [] if the
    field is missing or malformed."""
    flow = re.search(r"^artifacts:\s*\[(.*?)\]\s*$", fm, re.MULTILINE | re.DOTALL)
    if flow:
        items = [s.strip().strip("'\"") for s in flow.group(1).split(",")]
        return [x for x in items if x.endswith(".md") and x not in _EXCLUDE]
    block = re.search(
        r"^artifacts:\s*\n(?P<items>(?:\s*-\s*\S+\s*\n?)+)",
        fm,
        re.MULTILINE,
    )
    if block:
        out: list[str] = []
        for line in block.group("items").splitlines():
            stripped = line.strip()
            if not stripped.startswith("-"):
                continue
            name = stripped[1:].strip().strip("'\"")
            if name.endswith(".md") and name not in _EXCLUDE:
                out.append(name)
        return out
    return []


# ---------------------------------------------------------------------- #
# Deliberation discovery
# ---------------------------------------------------------------------- #


def _has_open_ratification_deliberation(paths: WorkspacePaths) -> bool:
    """True if any deliberation has `ratifies: <artifact>` and is not
    yet in a terminal state. Excludes the seed (#0001) which ratifies
    outcome-manifest.md itself."""
    if not paths.deliberations.is_dir():
        return False
    for path in paths.deliberations.glob("*.md"):
        try:
            meta = load_deliberation(path)
        except Exception:
            continue
        ratifies = str(meta.extras.get("ratifies", "") or "").strip().lower()
        if not ratifies or ratifies in _EXCLUDE:
            continue
        if meta.status.upper() not in {"DECIDED", "ABANDONED", "ARCHIVED"}:
            return True
    return False


def _first_artifact_without_deliberation(
    paths: WorkspacePaths, artifacts: list[str]
) -> str | None:
    """Return the first artifact in order that has no ratifying
    deliberation (open or terminal). The "in any status" check means a
    DECIDED ratification still counts as "done" — we only auto-open
    artifacts that nobody has touched yet."""
    if not paths.deliberations.is_dir():
        return artifacts[0] if artifacts else None
    ratified: set[str] = set()
    for path in paths.deliberations.glob("*.md"):
        try:
            meta = load_deliberation(path)
        except Exception:
            continue
        ratifies = str(meta.extras.get("ratifies", "") or "").strip().lower()
        if ratifies:
            ratified.add(ratifies)
    for name in artifacts:
        if name not in ratified:
            return name
    return None


# ---------------------------------------------------------------------- #
# Deliberation creation
# ---------------------------------------------------------------------- #


def _open_artifact_deliberation(
    paths: WorkspacePaths, artifact: str
) -> Path:
    """Create a new deliberation file that ratifies `artifact`.

    Tags every CLI-transport participant (so the loop has someone to
    propose / critique / synthesise) and pins the human as decider via
    frontmatter (`roles.decider`). The loop's planner picks up the
    ratification immediately on the next tick.
    """
    paths.deliberations.mkdir(parents=True, exist_ok=True)
    next_id = _next_deliberation_id(paths)
    title = _title_for_artifact(artifact)
    slug = _slugify(title) or "deliberation"
    target = paths.deliberations / f"{next_id}-{slug}.md"

    decider = _detect_decider(paths) or "@human"
    cli_handles = _detect_cli_handles(paths)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    tag_list = ", ".join(f'"{h}"' for h in cli_handles + [decider])

    body = (
        "---\n"
        f'id: "{next_id}"\n'
        f"title: {title}\n"
        "status: OPEN\n"
        "protocol_version: 0.1\n"
        f"created: {today}\n"
        "parent: null\n"
        "children: []\n"
        f"ratifies: {artifact}\n"
        "roles:\n"
        "  proposer: null\n"
        "  critics: []\n"
        "  synthesizer: null\n"
        f'  decider: "{decider}"\n'
        f"tags: [{tag_list}]\n"
        "relevant_context:\n"
        "  repos: []\n"
        "  docs: []\n"
        "  urls: []\n"
        "  notes: all\n"
        "final: false\n"
        "---\n\n"
        "## Question\n\n"
        f"{_question_for_artifact(artifact, title)}\n\n"
        "## Context\n\n"
        f"This deliberation produces the contents of `{artifact}` per the "
        "ratified outcome manifest. The conductor opened it automatically "
        "after the manifest was locked.\n\n"
        "## Open Questions\n\n"
        "## Decision\n\n"
        "## Contributions\n"
    )
    target.write_text(body, encoding="utf-8")
    return target


def _next_deliberation_id(paths: WorkspacePaths) -> str:
    used = 0
    pat = re.compile(r"^(\d+)-")
    for p in paths.deliberations.glob("*.md"):
        m = pat.match(p.name)
        if m:
            used = max(used, int(m.group(1)))
    return f"{used + 1:04d}"


def _title_for_artifact(artifact: str) -> str:
    base = artifact.removesuffix(".md").replace("-", " ").replace("_", " ")
    return f"Produce {base}"


def _question_for_artifact(artifact: str, title: str) -> str:
    return (
        f"What should `{artifact}` say? Propose its full contents per the "
        "outcome manifest's requirements. Critique should challenge gaps "
        "and unsupported claims. Synthesis should reconcile into a single "
        "candidate body. Decision is the human's call to lock it in."
    )


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    if not base:
        base = "deliberation"
    return base[:48]


def _detect_decider(paths: WorkspacePaths) -> str | None:
    """First manual-transport participant — that's our human."""
    from ..core.participants import parse_participants

    if not paths.participants.is_file():
        return None
    try:
        for p in parse_participants(paths.participants):
            if p.transport == "manual":
                return p.handle
    except Exception:
        return None
    return None


def _detect_cli_handles(paths: WorkspacePaths) -> list[str]:
    """All CLI-transport participants, in declaration order."""
    from ..core.participants import parse_participants

    if not paths.participants.is_file():
        return []
    try:
        return [p.handle for p in parse_participants(paths.participants) if p.transport == "cli"]
    except Exception:
        return []


__all__ = ["maybe_open_next_artifact_deliberation"]
