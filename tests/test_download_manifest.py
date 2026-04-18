"""Unit tests for shawn_bio_search.download.manifest."""

from __future__ import annotations

import json
from pathlib import Path

from shawn_bio_search.download import manifest as M


def test_new_manifest_defaults():
    m = M.new_manifest()
    assert m["schema_version"] == M.SCHEMA_VERSION
    assert m["entries"] == []
    assert "generated_at" in m


def test_save_and_load_roundtrip(tmp_path: Path):
    m = M.new_manifest(source_bundle="x.json", options={"workers": 4})
    M.merge_entry(m, {"kind": "paper", "key": "k1", "status": "planned"})
    path = tmp_path / "manifest.json"
    M.save_manifest(path, m)

    reloaded = M.load_manifest(path)
    assert reloaded["schema_version"] == M.SCHEMA_VERSION
    assert reloaded["source_bundle"] == "x.json"
    assert reloaded["options"] == {"workers": 4}
    assert len(reloaded["entries"]) == 1
    assert reloaded["entries"][0]["key"] == "k1"


def test_merge_entry_is_idempotent_by_kind_key():
    m = M.new_manifest()
    M.merge_entry(m, {"kind": "paper", "key": "k1", "status": "planned"})
    M.merge_entry(m, {"kind": "paper", "key": "k1", "status": "downloaded"})
    M.merge_entry(m, {"kind": "paper", "key": "k2", "status": "planned"})
    assert len(m["entries"]) == 2
    by_key = {e["key"]: e for e in m["entries"]}
    assert by_key["k1"]["status"] == "downloaded"
    assert by_key["k2"]["status"] == "planned"


def test_merge_entry_distinguishes_kinds():
    m = M.new_manifest()
    M.merge_entry(m, {"kind": "paper", "key": "k1"})
    M.merge_entry(m, {"kind": "dataset_file", "key": "k1"})
    assert len(m["entries"]) == 2


def test_load_manifest_rejects_non_object(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([1, 2, 3]))
    try:
        M.load_manifest(path)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-object manifest")


def test_save_manifest_is_atomic(tmp_path: Path):
    m = M.new_manifest()
    M.merge_entry(m, {"kind": "paper", "key": "k1"})
    path = tmp_path / "manifest.json"
    M.save_manifest(path, m)
    assert path.exists()
    for leftover in tmp_path.glob(".manifest-*"):
        raise AssertionError(f"tmp file left behind: {leftover}")


def test_find_entry_returns_match_or_none():
    m = M.new_manifest()
    M.merge_entry(m, {"kind": "paper", "key": "k1", "status": "planned"})
    hit = M.find_entry(m, "paper", "k1")
    assert hit is not None and hit["status"] == "planned"
    assert M.find_entry(m, "paper", "missing") is None
