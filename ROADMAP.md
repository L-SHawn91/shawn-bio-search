# SHawn Bio Search Roadmap

## Current direction

SHawn Bio Search should remain the retrieval and normalization backbone for biomedical research workflows.

It should feed:
- `SHawn-academic-research` for project-aware interpretation and bundle generation
- other downstream research or writing tools that need auditable retrieval bundles

## Near-term priorities

1. stabilize retrieval bundle outputs
2. improve DOI / PMID / PMCID / accession enrichment quality
3. improve deduplication and source weighting
4. improve local paper-store and Zotero-aware signals
5. standardize runtime skill deployment from the repo source

## Active improvement themes

### 1. Search quality
- strengthen source-aware ranking
- preserve high-yield biomedical source priority
- improve query expansion without overbroad drift

### 2. Retrieval bundle quality
- keep author / year / title / DOI fields stable
- expose directness and evidence-candidate usefulness more clearly
- support downstream contradiction-aware interpretation

### 3. Local context integration
- improve local file and Zotero hit surfacing
- make reuse of local paper stores more visible to downstream wrappers

### 4. Operational fit
- act as the retrieval layer, not the manuscript-facing interpretation layer
- remain easy to consume by `SHawn-academic-research`

## Real-world validation path

Recommended first recurring validation cases:
- Endometrial organoid review retrieval
- Reviewer contradiction support retrieval
- Figure evidence pack retrieval
- Regenerative materials shortlist retrieval

## Principle

This repository should improve through repeated real-world retrieval use, not by collapsing into the synthesis layer.
