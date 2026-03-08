"""Scopus source module (requires API key)."""

import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List


def _get_json(url: str, headers: Dict[str, str]) -> Any:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return __import__("json").loads(resp.read().decode("utf-8"))


def fetch_scopus(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch papers from Scopus (requires SCOPUS_API_KEY)."""
    api_key = os.getenv("SCOPUS_API_KEY")
    if not api_key:
        return []
    
    url = (
        "https://api.elsevier.com/content/search/scopus?"
        + urllib.parse.urlencode({"query": query, "count": str(limit), "sort": "-citedby-count"})
    )
    headers = {"Accept": "application/json", "X-ELS-APIKey": api_key}
    
    inst = os.getenv("SCOPUS_INSTTOKEN")
    if inst:
        headers["X-ELS-Insttoken"] = inst
    
    try:
        data = _get_json(url, headers)
    except Exception:
        return []
    
    entries = data.get("search-results", {}).get("entry", [])
    
    out = []
    for e in entries:
        creator = e.get("dc:creator")
        out.append({
            "source": "scopus",
            "id": e.get("dc:identifier") or "",
            "title": e.get("dc:title") or "",
            "authors": [creator] if creator else [],
            "year": int((e.get("prism:coverDate") or "0")[:4] or 0),
            "doi": e.get("prism:doi"),
            "url": e.get("prism:url") or "",
            "abstract": "",
            "citations": int(e.get("citedby-count") or 0),
        })
    
    return out
