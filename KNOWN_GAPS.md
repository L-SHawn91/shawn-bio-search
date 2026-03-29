# SHawn Bio Search Known Gaps

## Current gaps

### 1. Runtime deployment path is not yet standardized
The current workspace skill copy should be replaced by a repo-source deployment pattern.

### 2. Retrieval bundle schema still needs repeated field validation
Real-world use is still needed to confirm which fields are always stable enough for downstream wrappers.

### 3. Local paper-store integration needs clearer signaling
Local reuse exists conceptually, but downstream interpretation benefits from more explicit fields and cleaner surfacing.

### 4. Search-quality tuning remains ongoing
Source weighting, deduplication, and query expansion still need repeated project-level validation.

## Working assumptions to verify

- PubMed / Europe PMC / OpenAlex fast bundles are sufficient for many first-pass review tasks
- downstream wrappers benefit from clearer directness and evidence-candidate signals
- local paper-store hits should be surfaced more consistently

## Current operating stance

Use this repo as the retrieval backbone and improve it through repeated real-world biomedical search tasks.
