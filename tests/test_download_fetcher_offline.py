"""Offline tests for fetcher.download_to_path — monkeypatch urlopen + head_info."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from shawn_bio_search.download import fetcher


class _FakeResp(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/pdf"):
        super().__init__(body)
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _install_fake_urlopen(monkeypatch: pytest.MonkeyPatch, payload: bytes, status: int = 200):
    def fake(req, timeout=30, context=None):
        return _FakeResp(payload, status=status)
    monkeypatch.setattr("shawn_bio_search.download.fetcher.urllib.request.urlopen", fake)


def _install_head(monkeypatch: pytest.MonkeyPatch, total: Optional[int], ctype: str = "application/pdf"):
    def fake_head(url: str, *, timeout: int = 20) -> Dict[str, Any]:
        return {"status": 200, "content_length": total, "content_type": ctype}
    monkeypatch.setattr(fetcher, "head_info", fake_head)


def test_downloads_pdf_and_validates_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    body = b"%PDF-1.4 contents"
    _install_head(monkeypatch, len(body))
    _install_fake_urlopen(monkeypatch, body)

    dest = tmp_path / "paper.pdf"
    result = fetcher.download_to_path("https://example.com/paper.pdf", dest, expect_pdf=True)

    assert result["status"] == "downloaded"
    assert result["bytes"] == len(body)
    assert dest.read_bytes() == body
    assert not dest.with_suffix(dest.suffix + ".part").exists()


def test_rejects_non_pdf_body_when_expect_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    body = b"<html>not a pdf</html>"
    _install_head(monkeypatch, len(body), ctype="text/html")
    _install_fake_urlopen(monkeypatch, body)

    dest = tmp_path / "paper.pdf"
    result = fetcher.download_to_path("https://example.com/paper.pdf", dest, expect_pdf=True)

    assert result["status"] == "wrong-content-type"
    assert not dest.exists()


def test_too_large_via_head_length(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _install_head(monkeypatch, 100_000)

    def _no_get(*args, **kwargs):
        raise AssertionError("urlopen should not be called when HEAD size exceeds cap")
    monkeypatch.setattr("shawn_bio_search.download.fetcher.urllib.request.urlopen", _no_get)

    dest = tmp_path / "big.bin"
    result = fetcher.download_to_path(
        "https://example.com/big.bin", dest, max_bytes=1024
    )
    assert result["status"] == "too-large"
    assert not dest.exists()


def test_resume_skips_when_size_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    body = b"hello world"
    _install_head(monkeypatch, len(body), ctype="application/octet-stream")

    dest = tmp_path / "data.bin"
    dest.write_bytes(body)

    def _no_get(*args, **kwargs):
        raise AssertionError("urlopen should not be called when file is already complete")
    monkeypatch.setattr("shawn_bio_search.download.fetcher.urllib.request.urlopen", _no_get)

    result = fetcher.download_to_path(
        "https://example.com/data.bin", dest, expect_pdf=False
    )
    assert result["status"] == "skipped"
    assert result["bytes"] == len(body)
