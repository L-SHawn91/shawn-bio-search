"""End-to-end smoke tests for the download pipeline.

Uses the local fixture bundle and monkeypatches the fetcher so no network
traffic leaves the test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shawn_bio_search.download import fetcher, manifest, runner

FIXTURE = Path(__file__).with_suffix("").parent / "fixtures" / "bundle_min.json"


def test_plan_only_from_fixture(tmp_path: Path):
    dest = tmp_path / "downloads"
    m = runner.plan_from_bundle(FIXTURE, dest, use_unpaywall=False)
    kinds = {e["kind"] for e in m["entries"]}
    assert "paper" in kinds
    assert "dataset_instruction" in kinds  # SRA -> external tool

    # CT entry becomes 'skipped'
    statuses = {e["key"]: e["status"] for e in m["entries"] if e["kind"] == "paper"}
    assert any(status == "skipped" for status in statuses.values())

    # biorxiv entry gets a .full.pdf URL.
    biorxiv = next(
        e for e in m["entries"]
        if e["kind"] == "paper" and e.get("source") == "biorxiv"
    )
    assert biorxiv["planned_url"].endswith(".full.pdf")
    assert biorxiv["status"] == "planned"


def test_execute_marks_downloaded_and_resume_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "downloads"
    dest.mkdir()
    manifest_path = dest / "manifest.json"

    m = runner.plan_from_bundle(FIXTURE, dest, kinds=["papers"], use_unpaywall=False)
    manifest.save_manifest(manifest_path, m)

    def _fake_download(url, dest_path, *, max_bytes=None, resume=True, expect_pdf=False, **_):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = b"%PDF-1.4 stub"
        dest_path.write_bytes(payload)
        return {
            "bytes": len(payload),
            "sha256": "deadbeef",
            "elapsed_s": 0.01,
            "http_status": 200,
            "status": "downloaded",
            "error": None,
        }

    monkeypatch.setattr(runner, "download_to_path", _fake_download)

    runner.execute_manifest(manifest_path, dest, workers=1)
    m = manifest.load_manifest(manifest_path)
    statuses = [e.get("status") for e in m["entries"] if e["kind"] == "paper"]
    assert "downloaded" in statuses

    downloaded = [e for e in m["entries"] if e["kind"] == "paper" and e["status"] == "downloaded"]
    for e in downloaded:
        assert (dest / e["dest_path"]).exists()

    # Second pass must not re-run any downloads.
    call_count = {"n": 0}

    def _should_not_be_called(*args, **kwargs):
        call_count["n"] += 1
        return _fake_download(*args, **kwargs)

    monkeypatch.setattr(runner, "download_to_path", _should_not_be_called)
    runner.execute_manifest(manifest_path, dest, workers=1)
    assert call_count["n"] == 0


def test_dry_run_preserves_manifest(tmp_path: Path):
    dest = tmp_path / "downloads"
    m = runner.plan_from_bundle(FIXTURE, dest, kinds=["papers"], use_unpaywall=False)
    manifest_path = dest / "manifest.json"
    manifest.save_manifest(manifest_path, m)
    runner.execute_manifest(manifest_path, dest, dry_run=True)
    reloaded = manifest.load_manifest(manifest_path)
    assert len(reloaded["entries"]) == len(m["entries"])
