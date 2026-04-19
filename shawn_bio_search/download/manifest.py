"""Manifest schema and atomic I/O for the download pipeline.

The manifest is the source of truth for planning and resumption. Entries are
keyed by (kind, key) so repeated planning is idempotent.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_manifest(
    *,
    source_bundle: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "source_bundle": source_bundle or "",
        "options": dict(options or {}),
        "entries": [],
    }


def load_manifest(path: Path) -> Dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"manifest root must be an object: {path}")
    if "entries" not in data or not isinstance(data["entries"], list):
        raise ValueError(f"manifest missing entries list: {path}")
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("options", {})
    return data


def save_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Write manifest atomically (tmp file + fsync + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".manifest-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _entry_key(entry: Dict[str, Any]) -> tuple:
    return (entry.get("kind", ""), entry.get("key", ""))


def merge_entry(manifest: Dict[str, Any], entry: Dict[str, Any]) -> None:
    """Insert or replace an entry by (kind, key). In place."""
    entries = manifest.setdefault("entries", [])
    target = _entry_key(entry)
    for i, existing in enumerate(entries):
        if _entry_key(existing) == target:
            entries[i] = entry
            return
    entries.append(entry)


def merge_entries(manifest: Dict[str, Any], batch: Iterable[Dict[str, Any]]) -> None:
    for entry in batch:
        merge_entry(manifest, entry)


def find_entry(manifest: Dict[str, Any], kind: str, key: str) -> Optional[Dict[str, Any]]:
    for e in manifest.get("entries", []):
        if e.get("kind") == kind and e.get("key") == key:
            return e
    return None
