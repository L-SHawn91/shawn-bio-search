# shawn-bio-search — Claude Code Instructions

## Quick Start

```python
# MUST use Python 3.13+
import sys
sys.path.insert(0, '/Users/soohyunglee/GitHub/shawn-bio-search')
```

## Citation Verification (NEW)

```python
from shawn_bio_search.sources.pubmed import verify_citation

results = verify_citation(
    first_author="Turco",
    year="2017",
    context_keywords=["endometrial", "organoid", "hormone"],
    context_sentence="Long-term hormone-responsive organoid cultures of human endometrium",
    use_crossref=True,          # fallback to Crossref if PubMed fails
    use_semanticscholar=True,   # fallback to Semantic Scholar
)

# Results sorted by context_score (highest first)
for r in results[:3]:
    print(f"{r['_verification_confidence']} score={r['_context_score']:.2f}")
    print(f"  {r['first_author']} ({r['year']}) {r['title']}")
    print(f"  PMID:{r['pmid']} DOI:{r['doi']}")
```

### Confidence Levels
- **HIGH** (>=0.6): Correct paper with high certainty
- **MEDIUM** (>=0.35): Likely correct, manual check recommended
- **LOW** (>=0.15): Uncertain match
- **MISMATCH** (<0.15): Wrong paper (different field/species)

### Other Functions
- `fetch_by_pmid(["12345678"])` — direct PMID lookup
- `fetch_by_doi("10.1038/ncb3516")` — DOI search
- `search_advanced(first_author=..., tiab_words=..., year=...)` — structured query
- `fetch_pubmed(query, limit)` — backward-compatible plain text search

## Paper Search

```python
from shawn_bio_search import search_papers

results = search_papers(
    query="endometrial organoid",
    claim="Organoids model human endometrial function",
    max_results=10,
    project_mode="endometrial-organoid-review",
    sources=["pubmed", "europe_pmc", "openalex", "crossref"],
)
```

## Development

This tool is under active development. If a feature is missing or broken:
1. Read the source code to understand the issue
2. Fix it directly
3. Commit and push
