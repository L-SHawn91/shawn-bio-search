"""Source modules for biomedical literature search."""

from .pubmed import fetch_pubmed
from .europe_pmc import fetch_europe_pmc
from .openalex import fetch_openalex
from .crossref import fetch_crossref
from .clinicaltrials import fetch_clinicaltrials
from .biorxiv import fetch_biorxiv
from .medrxiv import fetch_medrxiv
from .scopus import fetch_scopus
from .google_scholar import fetch_google_scholar
from .semanticscholar import fetch_semanticscholar
from .arxiv import fetch_arxiv
from .openaire import fetch_openaire
from .core import fetch_core
from .unpaywall import fetch_unpaywall, fetch_unpaywall_by_doi
from .f1000research import fetch_f1000research
from .doaj import fetch_doaj

ALL_SOURCES = [
    "pubmed",
    "europe_pmc",
    "openalex",
    "crossref",
    "clinicaltrials",
    "biorxiv",
    "medrxiv",
    "semantic_scholar",
    "scopus",
    "google_scholar",
    "arxiv",
    "openaire",
    "core",
    "unpaywall",
    "f1000research",
    "doaj",
]

__all__ = [
    "fetch_pubmed",
    "fetch_europe_pmc",
    "fetch_openalex",
    "fetch_crossref",
    "fetch_clinicaltrials",
    "fetch_biorxiv",
    "fetch_medrxiv",
    "fetch_semanticscholar",
    "fetch_scopus",
    "fetch_google_scholar",
    "fetch_arxiv",
    "fetch_openaire",
    "fetch_core",
    "fetch_unpaywall",
    "fetch_unpaywall_by_doi",
    "fetch_f1000research",
    "fetch_doaj",
    "ALL_SOURCES",
]
