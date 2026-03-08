"""PubMed/NCBI source module."""

import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List


def _get_json(url: str, headers: Dict[str, str] = None) -> Any:
    """Fetch JSON from URL."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return __import__("json").loads(resp.read().decode("utf-8"))


def fetch_pubmed(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch papers from PubMed.
    
    Optional: Set NCBI_API_KEY environment variable for higher rate limits.
    """
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max(1, min(limit, 100))),
    }
    key = os.getenv("NCBI_API_KEY")
    if key:
        search_params["api_key"] = key
    
    search_url = f"{base}/esearch.fcgi?{urllib.parse.urlencode(search_params)}"
    data = _get_json(search_url)
    ids = data.get("esearchresult", {}).get("idlist", [])
    
    if not ids:
        return []
    
    # Fetch summary
    sum_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    if key:
        sum_params["api_key"] = key
    summary_url = f"{base}/esummary.fcgi?{urllib.parse.urlencode(sum_params)}"
    summary = _get_json(summary_url).get("result", {})
    
    # Fetch abstracts
    fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
    if key:
        fetch_params["api_key"] = key
    fetch_url = f"{base}/efetch.fcgi?{urllib.parse.urlencode(fetch_params)}"
    
    abstract_map: Dict[str, str] = {}
    try:
        xml_text = urllib.request.urlopen(fetch_url, timeout=30).read().decode("utf-8", "ignore")
        root = ET.fromstring(xml_text)
        for art in root.findall(".//PubmedArticle"):
            pid = art.findtext(".//PMID", default="").strip()
            parts = []
            for ab in art.findall(".//Abstract/AbstractText"):
                txt = "".join(ab.itertext()).strip()
                if txt:
                    parts.append(txt)
            if pid and parts:
                abstract_map[pid] = " ".join(parts)
    except Exception:
        pass
    
    out = []
    for pid in ids:
        doc = summary.get(pid) or {}
        authors = [a.get("name") for a in (doc.get("authors") or []) if a.get("name")]
        elocation = doc.get("elocationid") or ""
        doi_match = re.search(r"10\.[^\s;]+", elocation)
        
        out.append({
            "source": "pubmed",
            "id": f"pmid:{pid}",
            "title": doc.get("title") or "",
            "authors": authors,
            "year": int((doc.get("pubdate") or "0")[:4] or 0),
            "doi": doi_match.group(0) if doi_match else None,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            "abstract": abstract_map.get(pid, ""),
            "citations": 0,
        })
    
    return out
