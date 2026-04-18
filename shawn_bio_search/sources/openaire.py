"""OpenAIRE Graph source module (free, no API key required).

OpenAIRE aggregates open-access research from European and global repositories.
Docs: https://graph.openaire.eu/docs/apis/search-api/
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._http import build_url, http_json

_API = "https://api.openaire.eu/search/publications"


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        inner = value.get("$") or value.get("content") or value.get("value")
        return str(inner) if inner else ""
    return str(value)


def fetch_openaire(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search OpenAIRE for open-access biomedical publications."""
    if not query.strip():
        return []

    url = build_url(_API, {
        "keywords": query,
        "size": max(1, min(limit, 50)),
        "format": "json",
    })

    try:
        data = http_json(url, timeout=30)
    except Exception:
        return []

    results = (
        data.get("response", {})
        .get("results", {})
        .get("result", [])
    )
    results = _as_list(results)

    out: List[Dict[str, Any]] = []
    for r in results[:limit]:
        metadata = (
            r.get("metadata", {})
            .get("oaf:entity", {})
            .get("oaf:result", {})
        )
        if not metadata:
            continue

        title = _extract_text(_as_list(metadata.get("title"))[0] if metadata.get("title") else "")

        authors: List[str] = []
        for creator in _as_list(metadata.get("creator")):
            name = _extract_text(creator)
            if name:
                authors.append(name)

        # Extract DOI and URL from pid entries
        doi = ""
        best_url = ""
        for pid in _as_list(metadata.get("pid")):
            if not isinstance(pid, dict):
                continue
            classid = pid.get("@classid") or pid.get("classid")
            value = _extract_text(pid)
            if classid == "doi" and value:
                doi = value

        for child in _as_list(metadata.get("children", {}).get("instance")):
            if not isinstance(child, dict):
                continue
            webresource = _as_list(child.get("webresource"))
            for w in webresource:
                link = _extract_text(w.get("url") if isinstance(w, dict) else "")
                if link.startswith("http"):
                    best_url = link
                    break
            if best_url:
                break

        abstract = ""
        for d in _as_list(metadata.get("description")):
            text = _extract_text(d)
            if text:
                abstract = text
                break

        date = _extract_text(metadata.get("dateofacceptance")) or _extract_text(metadata.get("relevantdate"))
        year = 0
        if len(date) >= 4 and date[:4].isdigit():
            year = int(date[:4])

        if not best_url and doi:
            best_url = f"https://doi.org/{doi}"

        out.append({
            "source": "openaire",
            "id": _extract_text(r.get("header", {}).get("dri:objIdentifier")) if isinstance(r.get("header"), dict) else "",
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "url": best_url,
            "abstract": abstract,
            "citations": 0,
        })

    return out
