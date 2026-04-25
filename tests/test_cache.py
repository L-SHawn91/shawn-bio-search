"""Offline tests for the SQLite TTL HTTP cache."""

from __future__ import annotations

import time

from shawn_bio_search import _cache
from shawn_bio_search.sources import _http


def _isolate(monkeypatch, tmp_path):
    """Point the cache at a fresh per-test sqlite file."""
    monkeypatch.setenv("SBS_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("SBS_DISABLE_CACHE", raising=False)
    monkeypatch.delenv("SBS_CACHE_TTL_DAYS", raising=False)
    _cache.reset_for_tests()


def test_put_then_get_round_trips(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    key = _cache.make_key("https://example.test/a", None, None, None)
    _cache.put(key, b"hello")
    assert _cache.get(key) == b"hello"


def test_get_returns_none_on_miss(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    key = _cache.make_key("https://example.test/missing", None, None, None)
    assert _cache.get(key) is None


def test_disabled_cache_bypasses_storage(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("SBS_DISABLE_CACHE", "1")
    key = _cache.make_key("https://example.test/x", None, None, None)
    _cache.put(key, b"ignored")
    assert _cache.get(key) is None


def test_zero_ttl_bypasses_storage(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("SBS_CACHE_TTL_DAYS", "0")
    key = _cache.make_key("https://example.test/y", None, None, None)
    _cache.put(key, b"ignored")
    assert _cache.get(key) is None


def test_expired_entry_returns_none(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("SBS_CACHE_TTL_DAYS", "1")
    key = _cache.make_key("https://example.test/z", None, None, None)
    _cache.put(key, b"old")
    # Backdate the row to look 8 days old.
    conn = _cache._conn()
    conn.execute(
        "UPDATE http_cache SET stored_at = ? WHERE key = ?",
        (int(time.time()) - 8 * 24 * 3600, key),
    )
    assert _cache.get(key) is None


def test_clear_removes_all(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    for i in range(3):
        _cache.put(_cache.make_key(f"https://example.test/{i}", None, None, None), b"x")
    assert _cache.stats()[0] == 3
    assert _cache.clear() == 3
    assert _cache.stats() == (0, 0)


def test_make_key_is_deterministic_and_ignores_user_agent(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    a = _cache.make_key(
        "https://example.test/q?x=1",
        {"User-Agent": "one", "Accept": "application/json"},
        None,
        None,
    )
    b = _cache.make_key(
        "https://example.test/q?x=1",
        {"User-Agent": "two", "Accept": "application/json"},
        None,
        None,
    )
    assert a == b


def test_make_key_separates_distinct_urls(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    a = _cache.make_key("https://example.test/q?x=1", None, None, None)
    b = _cache.make_key("https://example.test/q?x=2", None, None, None)
    assert a != b


def test_http_open_serves_second_call_from_cache(tmp_path, monkeypatch):
    """End-to-end: a GET that hits the network once, then cache."""
    _isolate(monkeypatch, tmp_path)
    calls = {"n": 0}

    class _FakeResp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return self._payload

    def _fake_urlopen(req, timeout=None, context=None):  # noqa: ARG001
        calls["n"] += 1
        return _FakeResp(b'{"ok": true}')

    monkeypatch.setattr(_http.urllib.request, "urlopen", _fake_urlopen)

    first = _http.http_json("https://example.test/api?q=1")
    second = _http.http_json("https://example.test/api?q=1")

    assert first == {"ok": True}
    assert second == {"ok": True}
    assert calls["n"] == 1, "second call should be served from cache"


def test_http_open_does_not_cache_post(tmp_path, monkeypatch):
    """POST (data is not None) must always hit the network."""
    _isolate(monkeypatch, tmp_path)
    calls = {"n": 0}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"ok": true}'

    def _fake_urlopen(req, timeout=None, context=None):  # noqa: ARG001
        calls["n"] += 1
        return _FakeResp()

    monkeypatch.setattr(_http.urllib.request, "urlopen", _fake_urlopen)

    _http.http_json("https://example.test/post", data=b"payload", method="POST")
    _http.http_json("https://example.test/post", data=b"payload", method="POST")

    assert calls["n"] == 2, "POST requests must not be cached"
