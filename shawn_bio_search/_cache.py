"""SQLite-backed TTL cache for HTTP responses.

Defaults to ON. Disable with `SBS_DISABLE_CACHE=1` (or `--no-cache` on the
CLI, which sets the same env var). TTL via `SBS_CACHE_TTL_DAYS` (default 7).
Storage location via `SBS_CACHE_DIR` (default `~/.cache/shawn-bio-search/`).

Only idempotent reads are cached: GET requests with no body. 4xx/5xx
responses are never stored (they bypass the cache layer entirely because
they raise before `put` is called).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_TTL_SECONDS = 7 * 24 * 3600


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def is_disabled() -> bool:
    return _truthy(os.environ.get("SBS_DISABLE_CACHE", ""))


def ttl_seconds() -> int:
    raw = os.environ.get("SBS_CACHE_TTL_DAYS", "").strip()
    if not raw:
        return DEFAULT_TTL_SECONDS
    try:
        return max(0, int(float(raw) * 24 * 3600))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def cache_dir() -> Path:
    override = os.environ.get("SBS_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "shawn-bio-search"


def cache_path() -> Path:
    return cache_dir() / "http_cache.sqlite"


_LOCK = threading.Lock()
_CONNS: Dict[str, sqlite3.Connection] = {}


def _conn() -> sqlite3.Connection:
    path = str(cache_path())
    conn = _CONNS.get(path)
    if conn is not None:
        return conn
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS http_cache (
            key TEXT PRIMARY KEY,
            stored_at INTEGER NOT NULL,
            body BLOB NOT NULL
        )
        """
    )
    _CONNS[path] = conn
    return conn


def reset_for_tests() -> None:
    """Drop in-memory connection handles (forces re-open on next call)."""
    with _LOCK:
        for conn in _CONNS.values():
            try:
                conn.close()
            except sqlite3.Error:
                pass
        _CONNS.clear()


def make_key(
    url: str,
    headers: Optional[Dict[str, str]],
    data: Optional[bytes],
    method: Optional[str],
) -> str:
    h = hashlib.sha256()
    h.update((method or "GET").upper().encode())
    h.update(b"\n")
    h.update(url.encode("utf-8"))
    h.update(b"\n")
    if headers:
        items = sorted(
            (k.lower(), v) for k, v in headers.items() if k.lower() != "user-agent"
        )
        for k, v in items:
            h.update(f"{k}:{v}\n".encode("utf-8"))
    if data:
        h.update(b"\n")
        h.update(data)
    return h.hexdigest()


def get(key: str) -> Optional[bytes]:
    if is_disabled():
        return None
    ttl = ttl_seconds()
    if ttl <= 0:
        return None
    with _LOCK:
        cur = _conn().execute(
            "SELECT body, stored_at FROM http_cache WHERE key = ?", (key,)
        )
        row = cur.fetchone()
    if row is None:
        return None
    body, stored_at = row
    if int(time.time()) - int(stored_at) > ttl:
        return None
    return bytes(body)


def put(key: str, body: bytes) -> None:
    if is_disabled():
        return
    if ttl_seconds() <= 0:
        return
    with _LOCK:
        _conn().execute(
            "INSERT OR REPLACE INTO http_cache(key, stored_at, body) VALUES (?, ?, ?)",
            (key, int(time.time()), body),
        )


def clear() -> int:
    """Drop every cached entry. Returns rows deleted."""
    with _LOCK:
        cur = _conn().execute("DELETE FROM http_cache")
        return cur.rowcount or 0


def stats() -> Tuple[int, int]:
    """Return `(entry_count, total_bytes)` for the current cache file."""
    with _LOCK:
        cur = _conn().execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(body)),0) FROM http_cache"
        )
        row = cur.fetchone()
    return (int(row[0]), int(row[1]))
