"""Low-level URL -> file fetcher with HEAD size check, resume, and atomic write.

Built on top of ``shawn_bio_search.sources._http`` so rate limiting, TLS
verification, User-Agent, and retry behaviour stay consistent with the rest of
the package.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from ..sources._http import USER_AGENT, _rate_limit


class DownloadError(RuntimeError):
    pass


def _context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _build_request(
    url: str,
    *,
    method: str = "GET",
    extra_headers: Optional[Dict[str, str]] = None,
) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, headers=headers, method=method)


def head_info(url: str, *, timeout: int = 20) -> Dict[str, Any]:
    """Return {'status','content_length','content_type'} using HEAD, falling back to ranged GET.

    Some servers (biorxiv, FTP-fronts) don't reply usefully to HEAD — we try,
    and on HTTP error >= 400 we degrade to a 0-0 Range GET to read headers.
    """
    host = urllib.parse.urlparse(url).hostname or ""
    _rate_limit(host)
    try:
        req = _build_request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
            return {
                "status": resp.status,
                "content_length": _int_or_none(resp.headers.get("Content-Length")),
                "content_type": resp.headers.get("Content-Type", ""),
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        pass

    _rate_limit(host)
    try:
        req = _build_request(url, method="GET", extra_headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
            total = None
            content_range = resp.headers.get("Content-Range", "")
            if "/" in content_range:
                try:
                    total = int(content_range.rsplit("/", 1)[-1])
                except ValueError:
                    total = None
            if total is None:
                total = _int_or_none(resp.headers.get("Content-Length"))
            return {
                "status": resp.status,
                "content_length": total,
                "content_type": resp.headers.get("Content-Type", ""),
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        status = getattr(exc, "code", 0) or 0
        return {"status": status, "content_length": None, "content_type": ""}


def _int_or_none(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def download_to_path(
    url: str,
    dest: Path,
    *,
    max_bytes: Optional[int] = None,
    resume: bool = True,
    expect_pdf: bool = False,
    timeout: int = 120,
    chunk_size: int = 64 * 1024,
) -> Dict[str, Any]:
    """Stream ``url`` into ``dest``. Returns a dict describing the outcome.

    Result keys:
      bytes, sha256, elapsed_s, http_status, status ("downloaded"|"skipped"|
      "too-large"|"wrong-content-type"|"failed"), error (str|None).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    head = head_info(url, timeout=min(timeout, 30))
    total = head.get("content_length")
    if max_bytes is not None and total is not None and total > max_bytes:
        return {
            "bytes": 0,
            "sha256": "",
            "elapsed_s": 0.0,
            "http_status": head.get("status"),
            "status": "too-large",
            "error": f"content-length {total} exceeds cap {max_bytes}",
        }

    resume_from = 0
    if resume and part.exists():
        resume_from = part.stat().st_size
        if total is not None and resume_from >= total:
            try:
                os.replace(part, dest)
            except OSError:
                pass

    if resume and dest.exists() and total is not None and dest.stat().st_size == total:
        return {
            "bytes": dest.stat().st_size,
            "sha256": _sha256_of_file(dest),
            "elapsed_s": 0.0,
            "http_status": head.get("status"),
            "status": "skipped",
            "error": None,
        }

    host = urllib.parse.urlparse(url).hostname or ""
    headers: Dict[str, str] = {}
    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"

    req = _build_request(url, method="GET", extra_headers=headers or None)
    start = time.monotonic()
    hasher = hashlib.sha256()
    bytes_written = 0

    try:
        _rate_limit(host)
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")

            if max_bytes is not None and total is None:
                remote_len = _int_or_none(resp.headers.get("Content-Length"))
                if remote_len is not None and remote_len + resume_from > max_bytes:
                    return {
                        "bytes": 0,
                        "sha256": "",
                        "elapsed_s": time.monotonic() - start,
                        "http_status": status,
                        "status": "too-large",
                        "error": f"content-length {remote_len} exceeds cap {max_bytes}",
                    }

            mode = "ab" if resume_from > 0 and status == 206 else "wb"
            if mode == "ab" and resume_from > 0:
                hasher = hashlib.sha256()
                with part.open("rb") as fh:
                    for block in iter(lambda: fh.read(chunk_size), b""):
                        hasher.update(block)
                bytes_written = resume_from

            with part.open(mode) as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    hasher.update(chunk)
                    bytes_written += len(chunk)
                    if max_bytes is not None and bytes_written > max_bytes:
                        fh.flush()
                        return {
                            "bytes": bytes_written,
                            "sha256": "",
                            "elapsed_s": time.monotonic() - start,
                            "http_status": status,
                            "status": "too-large",
                            "error": f"downloaded {bytes_written} exceeded cap {max_bytes}",
                        }
                fh.flush()
                os.fsync(fh.fileno())

            if expect_pdf:
                with part.open("rb") as fh:
                    head_bytes = fh.read(4)
                if head_bytes[:4] != b"%PDF":
                    return {
                        "bytes": bytes_written,
                        "sha256": hasher.hexdigest(),
                        "elapsed_s": time.monotonic() - start,
                        "http_status": status,
                        "status": "wrong-content-type",
                        "error": f"expected PDF, got content-type={ctype}",
                    }

            os.replace(part, dest)
            return {
                "bytes": bytes_written,
                "sha256": hasher.hexdigest(),
                "elapsed_s": time.monotonic() - start,
                "http_status": status,
                "status": "downloaded",
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "bytes": bytes_written,
            "sha256": "",
            "elapsed_s": time.monotonic() - start,
            "http_status": exc.code,
            "status": "failed",
            "error": f"HTTP {exc.code}: {exc.reason}",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "bytes": bytes_written,
            "sha256": "",
            "elapsed_s": time.monotonic() - start,
            "http_status": None,
            "status": "failed",
            "error": str(exc),
        }


def _sha256_of_file(path: Path, chunk_size: int = 64 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()
