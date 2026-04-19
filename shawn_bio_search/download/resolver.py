"""Resolve a paper record to an OA PDF URL.

Never fabricates URLs and never uses paywall-bypass services. Returns the
sentinel ``""`` when no OA copy is known.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

# Statuses match the allowed set in the plan. Keep in sync with runner.
Resolution = str  # "direct" | "biorxiv" | "medrxiv" | "epmc" | "unpaywall" | "none" | "paywalled" | "not-article"


def _doi(record: Dict[str, Any]) -> str:
    return (record.get("doi") or "").strip()


def _url(record: Dict[str, Any]) -> str:
    return (record.get("url") or "").strip()


def _encoded_doi(doi: str) -> str:
    return urllib.parse.quote(doi, safe="")


_PMCID_RE = re.compile(r"PMC\d+", re.IGNORECASE)


def _pmcid(record: Dict[str, Any]) -> str:
    for key in ("pmcid", "pmc_id", "pmc"):
        v = record.get(key)
        if v:
            m = _PMCID_RE.search(str(v))
            if m:
                return m.group(0).upper()
    for key in ("abstract", "url", "id"):
        v = record.get(key)
        if v:
            m = _PMCID_RE.search(str(v))
            if m:
                return m.group(0).upper()
    return ""


def _epmc_pdf_url(pmcid: str) -> str:
    return f"https://europepmc.org/articles/{pmcid}/pdf/{pmcid}.pdf"


def _biorxiv_pdf(doi: str, host: str) -> str:
    return f"https://www.{host}.org/content/{_encoded_doi(doi)}.full.pdf"


def _via_unpaywall(doi: str) -> Tuple[str, Resolution]:
    """DOI -> OA URL via Unpaywall. Returns ("", "paywalled"|"none")."""
    if not doi:
        return ("", "none")
    try:
        from ..sources.unpaywall import fetch_unpaywall_by_doi
    except ImportError:
        return ("", "none")
    rec = fetch_unpaywall_by_doi(doi)
    if not rec:
        return ("", "none")
    if not rec.get("is_oa"):
        return ("", "paywalled")
    url = (rec.get("url") or "").strip()
    if not url:
        return ("", "paywalled")
    return (url, "unpaywall")


def _resolve_arxiv(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    url = _url(record)
    if url.endswith(".pdf"):
        return (url, "direct")
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^?\s]+)", url)
    if m:
        arxiv_id = m.group(1).rstrip(".pdf")
        return (f"https://arxiv.org/pdf/{arxiv_id}.pdf", "direct")
    return (url, "direct") if url else ("", "none")


def _resolve_unpaywall_source(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    if not record.get("is_oa", True):
        return ("", "paywalled")
    url = _url(record)
    return (url, "direct") if url else ("", "none")


def _resolve_semanticscholar(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    pdf_url = (record.get("pdf_url") or record.get("openAccessPdf") or "").strip()
    if pdf_url:
        return (pdf_url, "direct")
    url = _url(record)
    if url.lower().endswith(".pdf"):
        return (url, "direct")
    if use_unpaywall:
        return _via_unpaywall(_doi(record))
    return ("", "none")


def _resolve_core(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    url = _url(record)
    if url:
        return (url, "direct")
    if use_unpaywall:
        return _via_unpaywall(_doi(record))
    return ("", "none")


def _resolve_biorxiv(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    doi = _doi(record)
    if doi:
        return (_biorxiv_pdf(doi, "biorxiv"), "biorxiv")
    return ("", "none")


def _resolve_medrxiv(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    doi = _doi(record)
    if doi:
        return (_biorxiv_pdf(doi, "medrxiv"), "medrxiv")
    return ("", "none")


def _resolve_europe_pmc(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    pmcid = _pmcid(record)
    if pmcid:
        return (_epmc_pdf_url(pmcid), "epmc")
    if use_unpaywall:
        return _via_unpaywall(_doi(record))
    return ("", "none")


def _resolve_pubmed(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    pmcid = _pmcid(record)
    if pmcid:
        return (_epmc_pdf_url(pmcid), "epmc")
    if use_unpaywall:
        return _via_unpaywall(_doi(record))
    return ("", "none")


def _resolve_via_doi(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    if use_unpaywall:
        return _via_unpaywall(_doi(record))
    return ("", "none")


def _resolve_direct_then_unpaywall(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    url = _url(record)
    if url.lower().endswith(".pdf"):
        return (url, "direct")
    if use_unpaywall:
        oa, status = _via_unpaywall(_doi(record))
        if oa:
            return (oa, status)
    return ("", "none")


def _resolve_not_article(record: Dict[str, Any], *, use_unpaywall: bool) -> Tuple[str, Resolution]:
    return ("", "not-article")


_RESOLVERS: Dict[str, Callable[..., Tuple[str, Resolution]]] = {
    "arxiv": _resolve_arxiv,
    "unpaywall": _resolve_unpaywall_source,
    "semantic_scholar": _resolve_semanticscholar,
    "semanticscholar": _resolve_semanticscholar,
    "core": _resolve_core,
    "biorxiv": _resolve_biorxiv,
    "medrxiv": _resolve_medrxiv,
    "europe_pmc": _resolve_europe_pmc,
    "pubmed": _resolve_pubmed,
    "crossref": _resolve_via_doi,
    "openalex": _resolve_via_doi,
    "scopus": _resolve_via_doi,
    "f1000research": _resolve_via_doi,
    "doaj": _resolve_via_doi,
    "google_scholar": _resolve_direct_then_unpaywall,
    "openaire": _resolve_direct_then_unpaywall,
    "clinicaltrials": _resolve_not_article,
    "scival": _resolve_not_article,
}


def resolve_pdf_url(record: Dict[str, Any], *, use_unpaywall: bool = True) -> Tuple[str, Resolution]:
    """Return (url, resolution) for a paper record.

    ``resolution`` is one of: ``direct``, ``biorxiv``, ``medrxiv``, ``epmc``,
    ``unpaywall``, ``none``, ``paywalled``, ``not-article``.
    """
    source = (record.get("source") or "").strip().lower()
    resolver = _RESOLVERS.get(source)
    if resolver is None:
        return _resolve_direct_then_unpaywall(record, use_unpaywall=use_unpaywall)
    return resolver(record, use_unpaywall=use_unpaywall)
