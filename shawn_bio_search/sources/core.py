"""CORE source module (free API key: https://core.ac.uk/services/api).

CORE is the largest open-access paper aggregator (300M+ records).
Skipped silently when `CORE_API_KEY` is not configured.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from ._http import build_url, http_json

_API = "https://api.core.ac.uk/v3/search/works"


def fetch_core(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch works from CORE. Requires `CORE_API_KEY`."""
    api_key = os.getenv("CORE_API_KEY")
    if not api_key or not query.strip():
        return []

    url = build_url(_API, {
        "q": query,
        "limit": max(1, min(limit, 100)),
    })
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        data = http_json(url, headers=headers, timeout=30)
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for r in (data.get("results") or [])[:limit]:
        authors = []
        for a in (r.get("authors") or []):
            name = a.get("name") if isinstance(a, dict) else str(a)
            if name:
                authors.append(name)

        doi = r.get("doi") or ""
        url_best = (
            r.get("downloadUrl")
            or r.get("sourceFulltextUrls", [None])[0]
            or (f"https://doi.org/{doi}" if doi else "")
            or r.get("id") and f"https://core.ac.uk/works/{r.get('id')}"
            or ""
        )

        out.append({
            "source": "core",
            "id": str(r.get("id") or ""),
            "title": r.get("title") or "",
            "authors": authors,
            "year": int(r.get("yearPublished") or 0),
            "doi": doi,
            "url": url_best,
            "abstract": r.get("abstract") or "",
            "citations": int(r.get("citationCount") or 0),
        })

    return out
