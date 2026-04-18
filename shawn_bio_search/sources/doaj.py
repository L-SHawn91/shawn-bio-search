"""DOAJ (Directory of Open Access Journals) article search (free).

Covers peer-reviewed open access articles. API docs:
https://doaj.org/api/docs
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List

from ._http import build_url, http_json

_API = "https://doaj.org/api/v3/search/articles/"


def _first_identifier(idents: List[Dict[str, Any]], target_type: str) -> str:
    for ident in idents or []:
        if isinstance(ident, dict) and ident.get("type") == target_type and ident.get("id"):
            return str(ident.get("id"))
    return ""


def fetch_doaj(query: str, limit: int) -> List[Dict[str, Any]]:
    if not query.strip():
        return []

    # Query path is embedded in the URL for DOAJ; quote it.
    encoded = urllib.parse.quote(query, safe="")
    url = build_url(_API + encoded, {
        "pageSize": max(1, min(limit, 100)),
        "page": 1,
    })

    try:
        data = http_json(url, timeout=30)
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for r in (data.get("results") or [])[:limit]:
        bib = r.get("bibjson") or {}
        authors = [a.get("name") for a in (bib.get("author") or []) if isinstance(a, dict) and a.get("name")]
        idents = bib.get("identifier") or []
        doi = _first_identifier(idents, "doi")
        journal = (bib.get("journal") or {}).get("title") or ""

        best_url = ""
        for link in (bib.get("link") or []):
            if isinstance(link, dict) and link.get("url"):
                best_url = link["url"]
                if link.get("type") == "fulltext":
                    break
        if not best_url and doi:
            best_url = f"https://doi.org/{doi}"

        out.append({
            "source": "doaj",
            "id": str(r.get("id") or ""),
            "title": bib.get("title") or "",
            "authors": authors,
            "year": int(bib.get("year") or 0),
            "doi": doi,
            "journal": journal,
            "url": best_url,
            "abstract": bib.get("abstract") or "",
            "citations": 0,
        })

    return out
