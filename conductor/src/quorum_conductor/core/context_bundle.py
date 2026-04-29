"""Per-invocation context bundle assembly (design-doc §1.8).

Three layers, always assembled in this order:

  Layer 1 — Standing bundle (always included):
    * problem-statement.md
    * outcome-manifest.md
    * registers/glossary.md
    * registers/open-questions.md
    * registers/summarized-decisions.md
    * all files under context/notes/
    * context/index.md (if present)

  Layer 2 — Deliberation-declared context (conditional):
    Read `relevant_context` from the deliberation's frontmatter and
    include named repo digests, document digests/raw, and cached URL
    captures. Notes are always included as part of Layer 1.

  Layer 3 — On-demand reads inside the agent's invocation. Not assembled
    here; the agent reads source files itself when it needs to verify
    something specific. Logged via events.jsonl by the invoker.

Output format: a single Markdown blob that gets rendered into the prompt
under `## STANDING CONTEXT` and `## DELIBERATION CONTEXT` headings. The
agent treats these as authoritative for the workspace's current state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..paths import WorkspacePaths
from .deliberation import DeliberationMeta

# Per-file inclusion ceilings. The conductor never silently truncates;
# it includes a header noting how many bytes were elided.
_MAX_SECTION_BYTES = 50_000


@dataclass(frozen=True)
class BundleEntry:
    """One named section within a bundle."""

    title: str
    path: Path
    body: str
    truncated_bytes: int = 0


@dataclass(frozen=True)
class StandingBundle:
    entries: tuple[BundleEntry, ...] = field(default_factory=tuple)

    def to_markdown(self) -> str:
        if not self.entries:
            return ""
        parts: list[str] = ["## STANDING CONTEXT", ""]
        parts.append(
            "These files are included on every invocation per design-doc §1.8 "
            "(\"Layer 1 — Standing context bundle\"). Trust them as the "
            "current state of the workspace."
        )
        parts.append("")
        for e in self.entries:
            parts.append(f"### {e.title}")
            parts.append(f"_path: `{e.path.name}`_")
            if e.truncated_bytes:
                parts.append(
                    f"_(truncated; {e.truncated_bytes} bytes elided)_"
                )
            parts.append("")
            parts.append(e.body)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"


@dataclass(frozen=True)
class DeliberationBundle:
    """Layer-2 context: digests / raw files referenced by frontmatter."""

    repos: tuple[BundleEntry, ...] = field(default_factory=tuple)
    docs: tuple[BundleEntry, ...] = field(default_factory=tuple)
    urls: tuple[BundleEntry, ...] = field(default_factory=tuple)

    def to_markdown(self) -> str:
        if not (self.repos or self.docs or self.urls):
            return ""
        parts: list[str] = ["## DELIBERATION CONTEXT", ""]
        parts.append(
            "These context sources are declared in this deliberation's "
            "`relevant_context` frontmatter (design-doc §1.8 \"Layer 2\"). "
            "If you need details the digests don't carry, read source on "
            "demand and the events log will record it."
        )
        parts.append("")
        for label, items in (("Repos", self.repos), ("Documents", self.docs), ("Web URLs", self.urls)):
            if not items:
                continue
            parts.append(f"### {label}")
            parts.append("")
            for e in items:
                parts.append(f"#### {e.title}")
                parts.append(f"_path: `{e.path.name}`_")
                if e.truncated_bytes:
                    parts.append(
                        f"_(truncated; {e.truncated_bytes} bytes elided)_"
                    )
                parts.append("")
                parts.append(e.body)
                parts.append("")
        return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def assemble_standing_bundle(paths: WorkspacePaths) -> StandingBundle:
    """Read every Layer-1 file that exists and build a StandingBundle."""
    entries: list[BundleEntry] = []

    for title, path in (
        ("Problem statement", paths.problem_statement),
        ("Outcome manifest", paths.outcome_manifest),
        ("Glossary", paths.glossary),
        ("Open questions register", paths.open_questions),
        ("Summarised decisions", paths.summarized_decisions),
        ("Context index", paths.context_index),
    ):
        entry = _read_entry(title, path)
        if entry is not None:
            entries.append(entry)

    # Notes — every file under context/notes/.
    if paths.context_notes.is_dir():
        for note_path in sorted(paths.context_notes.glob("*.md")):
            entry = _read_entry(f"Note · {note_path.stem}", note_path)
            if entry is not None:
                entries.append(entry)

    return StandingBundle(entries=tuple(entries))


def assemble_deliberation_bundle(
    paths: WorkspacePaths, meta: DeliberationMeta
) -> DeliberationBundle:
    """Read repos / docs / URLs declared in the deliberation's frontmatter."""
    relevant = _relevant_context(meta)
    repos = tuple(_collect_repo_entries(paths, relevant.get("repos", [])))
    docs = tuple(_collect_doc_entries(paths, relevant.get("docs", [])))
    urls = tuple(_collect_url_entries(paths, relevant.get("urls", [])))
    return DeliberationBundle(repos=repos, docs=docs, urls=urls)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _read_entry(title: str, path: Path) -> BundleEntry | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw.strip():
        return None
    truncated = 0
    if len(raw) > _MAX_SECTION_BYTES:
        truncated = len(raw) - _MAX_SECTION_BYTES
        raw = raw[:_MAX_SECTION_BYTES]
    text = raw.decode("utf-8", "replace")
    return BundleEntry(title=title, path=path, body=text, truncated_bytes=truncated)


def _relevant_context(meta: DeliberationMeta) -> dict[str, Any]:
    raw = meta.extras.get("relevant_context") or {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _collect_repo_entries(
    paths: WorkspacePaths, names: Any
) -> list[BundleEntry]:
    if not isinstance(names, list):
        return []
    out: list[BundleEntry] = []
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        digest = paths.context_repos / name / "digest.md"
        entry = _read_entry(f"Repo · {name}", digest)
        if entry is not None:
            out.append(entry)
    return out


def _collect_doc_entries(
    paths: WorkspacePaths, names: Any
) -> list[BundleEntry]:
    if not isinstance(names, list):
        return []
    out: list[BundleEntry] = []
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        digested = paths.context_docs / "digested" / f"{name}.md"
        if digested.is_file():
            entry = _read_entry(f"Document · {name} (digest)", digested)
        else:
            raw = next(
                iter(
                    p
                    for p in (paths.context_docs / "raw").glob(f"{name}.*")
                    if p.is_file()
                ),
                None,
            )
            if raw is None:
                continue
            entry = _read_entry(f"Document · {name} (raw)", raw)
        if entry is not None:
            out.append(entry)
    return out


def _collect_url_entries(
    paths: WorkspacePaths, names: Any
) -> list[BundleEntry]:
    if not isinstance(names, list):
        return []
    out: list[BundleEntry] = []
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        cached = paths.context_web / "cached" / f"{name}.md"
        entry = _read_entry(f"URL · {name}", cached)
        if entry is not None:
            out.append(entry)
    return out


# Lightweight context-manifest helpers — used by Phase-6b's `add-repo`
# command. Kept here so the bundle assembler and the CLI agree on the
# canonical YAML shape.


def load_context_manifest(paths: WorkspacePaths) -> dict[str, Any]:
    if not paths.context_manifest.is_file():
        return {"schema_version": "0.1", "repos": [], "docs": [], "urls": [], "notes": []}
    raw = yaml.safe_load(paths.context_manifest.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {"schema_version": "0.1", "repos": [], "docs": [], "urls": [], "notes": []}
    raw.setdefault("schema_version", "0.1")
    for key in ("repos", "docs", "urls", "notes"):
        raw.setdefault(key, [])
    return raw


def save_context_manifest(paths: WorkspacePaths, manifest: dict[str, Any]) -> None:
    paths.context_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.context_manifest.write_text(
        yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
