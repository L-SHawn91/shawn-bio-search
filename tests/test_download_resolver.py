"""Unit tests for shawn_bio_search.download.resolver."""

from __future__ import annotations

import pytest

from shawn_bio_search.download import resolver


def test_biorxiv_builds_pdf_url_from_doi():
    url, res = resolver.resolve_pdf_url(
        {"source": "biorxiv", "doi": "10.1101/2024.01.02.123456"},
        use_unpaywall=False,
    )
    assert url == "https://www.biorxiv.org/content/10.1101%2F2024.01.02.123456.full.pdf"
    assert res == "biorxiv"


def test_medrxiv_builds_pdf_url_from_doi():
    url, res = resolver.resolve_pdf_url(
        {"source": "medrxiv", "doi": "10.1101/2024.05.06.24300000"},
        use_unpaywall=False,
    )
    assert url.startswith("https://www.medrxiv.org/content/10.1101%2F")
    assert url.endswith(".full.pdf")
    assert res == "medrxiv"


def test_biorxiv_without_doi_returns_none():
    url, res = resolver.resolve_pdf_url({"source": "biorxiv"}, use_unpaywall=False)
    assert url == ""
    assert res == "none"


def test_arxiv_normalises_abs_to_pdf():
    url, res = resolver.resolve_pdf_url(
        {"source": "arxiv", "url": "https://arxiv.org/abs/2401.12345"},
        use_unpaywall=False,
    )
    assert url == "https://arxiv.org/pdf/2401.12345.pdf"
    assert res == "direct"


def test_arxiv_keeps_existing_pdf_url():
    url, res = resolver.resolve_pdf_url(
        {"source": "arxiv", "url": "https://arxiv.org/pdf/2401.12345.pdf"},
        use_unpaywall=False,
    )
    assert url == "https://arxiv.org/pdf/2401.12345.pdf"
    assert res == "direct"


def test_europe_pmc_uses_pmcid():
    url, res = resolver.resolve_pdf_url(
        {"source": "europe_pmc", "pmcid": "PMC1234567"},
        use_unpaywall=False,
    )
    assert url == "https://europepmc.org/articles/PMC1234567/pdf/PMC1234567.pdf"
    assert res == "epmc"


def test_europe_pmc_extracts_pmcid_from_url():
    url, res = resolver.resolve_pdf_url(
        {"source": "europe_pmc", "url": "https://europepmc.org/article/PMC/PMC7654321"},
        use_unpaywall=False,
    )
    assert "PMC7654321" in url
    assert res == "epmc"


def test_clinicaltrials_is_skipped_as_not_article():
    url, res = resolver.resolve_pdf_url(
        {"source": "clinicaltrials", "url": "https://clinicaltrials.gov/study/NCT01"},
        use_unpaywall=False,
    )
    assert url == ""
    assert res == "not-article"


def test_semantic_scholar_prefers_pdf_url_field():
    url, res = resolver.resolve_pdf_url(
        {
            "source": "semantic_scholar",
            "pdf_url": "https://example.com/paper.pdf",
            "url": "https://www.semanticscholar.org/paper/abc",
        },
        use_unpaywall=False,
    )
    assert url == "https://example.com/paper.pdf"
    assert res == "direct"


def test_semantic_scholar_without_pdf_and_no_unpaywall_returns_none():
    url, res = resolver.resolve_pdf_url(
        {"source": "semantic_scholar", "doi": "10.1/abc", "url": "https://example.com/landing"},
        use_unpaywall=False,
    )
    assert url == ""
    assert res == "none"


def test_unpaywall_source_uses_its_url_when_is_oa():
    url, res = resolver.resolve_pdf_url(
        {"source": "unpaywall", "url": "https://example.com/oa.pdf", "is_oa": True},
        use_unpaywall=False,
    )
    assert url == "https://example.com/oa.pdf"
    assert res == "direct"


def test_unpaywall_source_marks_paywalled_when_not_oa():
    url, res = resolver.resolve_pdf_url(
        {"source": "unpaywall", "url": "https://doi.org/10.1/x", "is_oa": False},
        use_unpaywall=False,
    )
    assert url == ""
    assert res == "paywalled"


def test_crossref_without_unpaywall_returns_none():
    url, res = resolver.resolve_pdf_url(
        {"source": "crossref", "doi": "10.1/abc"},
        use_unpaywall=False,
    )
    assert url == ""
    assert res == "none"


def test_unknown_source_falls_back_to_direct_pdf_url():
    url, res = resolver.resolve_pdf_url(
        {"source": "future_source", "url": "https://example.com/paper.pdf"},
        use_unpaywall=False,
    )
    assert url == "https://example.com/paper.pdf"
    assert res == "direct"


def test_crossref_paywalled_via_unpaywall(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "_via_unpaywall",
        lambda doi: ("", "paywalled"),
    )
    url, res = resolver.resolve_pdf_url(
        {"source": "crossref", "doi": "10.1/closed"},
        use_unpaywall=True,
    )
    assert url == ""
    assert res == "paywalled"


def test_crossref_oa_via_unpaywall(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "_via_unpaywall",
        lambda doi: ("https://example.com/oa.pdf", "unpaywall"),
    )
    url, res = resolver.resolve_pdf_url(
        {"source": "crossref", "doi": "10.1/open"},
        use_unpaywall=True,
    )
    assert url == "https://example.com/oa.pdf"
    assert res == "unpaywall"
