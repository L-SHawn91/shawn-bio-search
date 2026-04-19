"""arXiv source module (free, no API key).

Focuses on the quantitative biology (q-bio) category but accepts any query.
arXiv returns Atom XML; we parse with the stdlib ElementTree.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from ._http import build_url, http_text

_API = "http://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _first(elem: ET.Element, path: str) -> str:
    node = elem.find(path, _NS)
    return (node.text or "").strip() if node is not None and node.text else ""


def _year_from_date(text: str) -> int:
    m = re.match(r"(\d{4})", text or "")
    return int(m.group(1)) if m else 0


def fetch_arxiv(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch papers from arXiv biased toward q-bio when the query lacks a category."""
    if not query.strip():
        return []

    # Scope to q-bio unless the caller already added a category filter.
    if "cat:" in query:
        search_query = query
    else:
        search_query = f"(cat:q-bio.* OR all:{query}) AND all:{query}"

    url = build_url(_API, {
        "search_query": search_query,
        "start": 0,
        "max_results": max(1, min(limit, 100)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    })

    try:
        text = http_text(url, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    out: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", _NS):
        arxiv_id = _first(entry, "atom:id")
        # arxiv_id looks like http://arxiv.org/abs/2401.01234v1
        short_id = arxiv_id.rsplit("/", 1)[-1] if arxiv_id else ""

        title = re.sub(r"\s+", " ", _first(entry, "atom:title")).strip()
        summary = re.sub(r"\s+", " ", _first(entry, "atom:summary")).strip()
        published = _first(entry, "atom:published")

        authors: List[str] = []
        for a in entry.findall("atom:author", _NS):
            name = a.find("atom:name", _NS)
            if name is not None and name.text:
                authors.append(name.text.strip())

        doi_node = entry.find("arxiv:doi", _NS)
        doi = (doi_node.text.strip() if doi_node is not None and doi_node.text else "") or ""

        pdf_url = ""
        for link in entry.findall("atom:link", _NS):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break

        out.append({
            "source": "arxiv",
            "id": short_id,
            "title": title,
            "authors": authors,
            "year": _year_from_date(published),
            "doi": doi,
            "url": arxiv_id or pdf_url,
            "abstract": summary,
            "citations": 0,  # arXiv does not provide citation counts
        })

    return out[:limit]
