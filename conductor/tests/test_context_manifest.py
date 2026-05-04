"""Tests for `context.manifest`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from quorum_conductor.context.manifest import (
    SCHEMA_VERSION,
    ContextEntry,
    ContextManifest,
    ManifestError,
    allocate_id,
    find_entry,
    load_manifest,
    manifest_path,
    save_manifest,
)


def _entry(
    *,
    id: str = "ctx-0001",
    kind: str = "doc",
    name: str = "thing",
    source: str = "/tmp/thing",
    body: str = "",
    digest_status: str = "",
) -> ContextEntry:
    return ContextEntry(
        id=id,
        kind=kind,
        name=name,
        added_at=datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC),
        source=source,
        body=body,
        digest_status=digest_status,
    )


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    m = load_manifest(tmp_path)
    assert m.schema_version == SCHEMA_VERSION
    assert m.next_id_counter == 0
    assert m.entries == []


def test_save_load_round_trip(tmp_path: Path) -> None:
    repo = _entry(
        id="ctx-0001",
        kind="repo",
        name="v2-app",
        source="/repos/v2-app",
        digest_status="pending",
    )
    doc = _entry(id="ctx-0002", kind="doc", name="spec.md", source="/docs/spec.md")
    note = _entry(id="ctx-0003", kind="note", name="thought", source="", body="some text")
    m = ContextManifest(next_id_counter=3, entries=[repo, doc, note])
    save_manifest(tmp_path, m)

    loaded = load_manifest(tmp_path)
    assert loaded == m


def test_save_writes_yaml_at_expected_path(tmp_path: Path) -> None:
    save_manifest(tmp_path, ContextManifest())
    assert manifest_path(tmp_path).is_file()
    assert "schema_version: 1" in manifest_path(tmp_path).read_text(encoding="utf-8")


def test_allocate_id_bumps_counter() -> None:
    m = ContextManifest(next_id_counter=4)
    new_id, m2 = allocate_id(m)
    assert new_id == "ctx-0005"
    assert m2.next_id_counter == 5
    assert m.next_id_counter == 4  # original unchanged (frozen)


def test_find_entry_returns_match_or_none() -> None:
    e = _entry(id="ctx-0042")
    m = ContextManifest(entries=[e])
    assert find_entry(m, "ctx-0042") == e
    assert find_entry(m, "ctx-9999") is None


def test_save_is_atomic_no_tmp_left(tmp_path: Path) -> None:
    save_manifest(tmp_path, ContextManifest(next_id_counter=1, entries=[_entry()]))
    parent = manifest_path(tmp_path).parent
    leftover_tmps = [p for p in parent.iterdir() if p.suffix == ".tmp"]
    assert leftover_tmps == []


def test_load_rejects_invalid_yaml(tmp_path: Path) -> None:
    p = manifest_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("this: is: not: valid: yaml:\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_load_rejects_unknown_kind(tmp_path: Path) -> None:
    p = manifest_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "schema_version: 1\n"
        "next_id_counter: 1\n"
        "entries:\n"
        "  - id: ctx-0001\n"
        "    kind: bogus\n"
        "    name: x\n"
        "    added_at: '2026-05-04T10:00:00Z'\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_repo_entry_persists_digest_fields(tmp_path: Path) -> None:
    e = ContextEntry(
        id="ctx-0001",
        kind="repo",
        name="v2-app",
        added_at=datetime(2026, 5, 4, 10, 0, 0, tzinfo=UTC),
        source="/repos/v2-app",
        digest_status="ready",
        digest_summary="42 files; TS + Python",
        digest_at=datetime(2026, 5, 4, 10, 5, 0, tzinfo=UTC),
        source_git_ref="abc1234",
    )
    save_manifest(tmp_path, ContextManifest(next_id_counter=1, entries=[e]))
    [back] = load_manifest(tmp_path).entries
    assert back == e


def test_note_entry_persists_body(tmp_path: Path) -> None:
    e = _entry(id="ctx-0001", kind="note", name="n", source="", body="multi\nline body")
    save_manifest(tmp_path, ContextManifest(next_id_counter=1, entries=[e]))
    [back] = load_manifest(tmp_path).entries
    assert back.body == "multi\nline body"
