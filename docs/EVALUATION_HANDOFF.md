# Evaluation Handoff (bio-search → downstream consumers)

This document describes what signals `SHawn-bio-search` contributes to the downstream `REPORT.md` evaluation score defined in `SHawn-academic-research/references/OUTPUT_BUNDLE.md`.

The score has six axes (total 100): `project-awareness` (15), `search rigor` (20), `evidence mapping` (25), `citation discipline` (15), `output bundle quality` (15), `actionability` (10).

`SHawn-bio-search` is a producer of several inputs that feed three of those axes.

## Axes bio-search contributes to

### 1. search rigor (0–20)

Primary contributor. Derived on the wrapper side from:

- `SEARCH_LOG.md` sections — number of sources queried, query-expansion flag, retrieval warnings.
- `SEARCH_RESULTS.json` envelope — presence of `effective_query`, total result count.

To support a high search-rigor score, `SEARCH_LOG.md` should clearly list:

- original query and effective query
- sources actually queried (and which were skipped or failed)
- whether query expansion ran
- any retrieval-side warnings

### 2. project-awareness (0–15)

Partial contributor via local-library awareness:

- ratio of `local_library.found = true` in `SEARCH_RESULTS.json` results
- ratio of `zotero_match = true`

The full axis value is ultimately determined by wrapper-side project-folder resolution, but strong local-library signaling from bio-search raises the ceiling.

### 3. citation discipline (0–15) — pre-check

DOI completeness ratio across `SEARCH_RESULTS.json` results is a necessary precondition for a high citation-discipline score downstream. Bio-search should:

- populate `doi` whenever a source resolver returned one
- flag missing DOIs in `SEARCH_LOG.md` under "retrieval warnings" rather than silently dropping them

## Axes bio-search does NOT directly contribute to

| Axis | Ownership |
|------|-----------|
| `evidence mapping` (25) | `SHawn-paper-mapping` verification + `SHawn-academic-research` claim-bucket interpretation |
| `output bundle quality` (15) | wrapper-side final-artifact presence |
| `actionability` (10) | manual reviewer judgment + wrapper-side integration |

Bio-search should not attempt to compute or inject these scores into its own outputs.

## Operational guidance

Keep retrieval-side outputs rich but narrow:

- include per-result `evidence_score` (float 0–1) and `evidence_label` (`support` | `contradict` | `uncertain` | `retrieval-hint`) when the retrieval heuristic produces them
- include `access.status`, `access.downloadable`, `local_library.found` so downstream scoring can see provenance
- do not inject wrapper-facing verdict language into retrieval outputs
- prefer emitting `EVIDENCE_CANDIDATES.json` when the caller supplies `--claim` (so claim-aware scoring is unlocked downstream)

## Related documents

- `docs/OUTPUT_SCHEMA.md` — machine-facing output contract
- `docs/DUAL_ENGINE_BOUNDARY.md` — retrieval vs analysis split
- `SHawn-academic-research/docs/INPUT_SCHEMA_FROM_BIO_SEARCH.md` — wrapper-side ingest contract
- `SHawn-academic-research/references/OUTPUT_BUNDLE.md` — full REPORT.md axis definitions and scoring rules
