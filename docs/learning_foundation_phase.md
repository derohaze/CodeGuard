# 1. Executive Summary
This phase introduces a production-shaped learning data foundation for Khwarizm without training models. It captures internal security outcomes, ingests external security knowledge, normalizes both into versioned schemas, stores large payloads safely in chunked Mongo documents, and evaluates behavior through benchmark suites.

Implemented baseline is provider-compatible today (external LLM providers remain unchanged) and future-ready for fine-tuning/reranking exports.

# 2. Architecture Changes
- Added `backend/app/infrastructure/learning/` package with boundaries:
  - `archive.py`: internal run/session/finding/patch/verification/feedback archival.
  - `ingestion.py`: external source fetch + parser + normalization + persistence orchestration.
  - `external_parsers.py`: deterministic source parsers (`cwe`, `owasp`, `semgrep`, `codeql`, `juliet`, fallback).
  - `ingestion_validation.py`: source/input validation and sanitization.
  - `normalization.py`: canonical mappers and status normalization.
  - `chunking.py`: chunk generation/reassembly and policy metadata.
  - `repository.py`: Mongo persistence with upsert/dedup behavior.
  - `benchmark.py`: suite runner and metrics/artifacts persistence.
  - `benchmark_seed_data.py`: default detection seed cases (Juliet-aligned).
  - `bootstrap.py`: startup bootstrap for benchmark skeleton/seeding.
- Added API layer:
  - `POST /api/v1/learning/archive/sessions/{session_id}`
  - `POST /api/v1/learning/external-ingestion`
  - `GET /api/v1/learning/knowledge/search`
  - `POST /api/v1/learning/feedback`
  - `POST /api/v1/learning/benchmarks/run`
- Added application use-cases/DTOs for learning actions.

# 3. MongoDB Collection Design
Collections:
- `learning_archive_runs`
- `learning_archive_items`
- `learning_archive_chunks`
- `external_knowledge_sources`
- `external_knowledge_items`
- `external_knowledge_chunks`
- `benchmark_suites`
- `benchmark_cases`
- `benchmark_runs`
- `feedback_events`
- `normalization_failures`
- `ingestion_audit`

Key indexes:
- Archive dedup: `(record_type, content_fingerprint)` unique.
- External dedup: `(source_name, source_version, item_fingerprint)` unique.
- Benchmark case dedup: `(suite_name, content_fingerprint)` unique.
- Chunk integrity: `(parent_item_id, sequence)` unique.
- Query indexes:
  - status + created/updated
  - language/framework
  - vulnerability_category
  - source_name/source_version
  - repository_fingerprint
  - benchmark suite/status

# 4. Schema Definitions
Versioned canonical models in `backend/app/infrastructure/learning/schemas.py`:
- `NormalizedFindingRecord`
- `NormalizedPatchRecord`
- `NormalizedBenchmarkCase`
- `NormalizedSecurityPattern`
- `NormalizedFrameworkRule`
- `NormalizedFeedbackEvent`
- `ExternalKnowledgeSourceSpec`
- `ExternalKnowledgeSearchQuery`

Status vocabulary:
- `suspected`, `candidate`, `validated`, `rejected`, `false_positive`
- `patch_generated`, `patch_approved`, `patch_rejected`
- `applied`, `verified_fixed`, `verified_partial`, `validation_failed`, `rolled_back`

# 5. Chunking and 16MB Safety Strategy
Policy defaults:
- chunk size: `8192` chars
- overlap for code-like content: `0`
- overlap for prose/docs: `256`

Per parent item metadata:
- `chunk_count`
- `parent_checksum`
- `chunk_size_chars`
- `overlap_chars`
- `chunk_policy_version`
- `original_length`

Per chunk metadata:
- `sequence`
- `content_checksum`
- `content_length`
- `content_type`

Safety rules:
- large bodies never embedded in parent metadata documents.
- one chunk per document keeps each record far below Mongo 16MB hard cap.

# 6. External Data Ingestion Plan
Pipeline stages:
1. Validate source spec (name/version/type/endpoint scheme).
2. Fetch source with rate limit and retry backoff.
3. Cache raw payload before parsing.
4. Parse with source-specific parser.
5. Sanitize/validate parsed items.
6. Normalize into canonical model.
7. Persist with dedup-aware upsert.
8. Record success/failure audit.

Controls:
- Default max rate: `10 req/sec`
- Retry: exponential backoff + jitter
- Source-level override: `requests_per_second`
- Raw payload checksum persisted in audit details.

# 7. Normalization Rules
- Raw statuses are mapped into canonical status vocabulary.
- Missing values are tolerated where optional.
- `content_fingerprint` generated from stable canonical payloads.
- `raw_reference` always preserved for provenance.
- Dedup strategy:
  - archive: record type + fingerprint
  - external items: source + version + fingerprint
  - benchmark cases: suite + fingerprint

# 8. Benchmark and Evaluation Plan
Execution order:
- Step 0 benchmark skeleton at startup (suite records + seed cases).

Suites:
- `detection`: detection rate, FP rate, evidence presence, category/severity coverage.
- `remediation`: correctness/completeness/regression/minimality proxies.
- `verification`: consistency/failure rates.
- `ingestion_normalization`: parser correctness, normalization failure rate, idempotency proxy.

Ground truth:
- human-approved findings from audit trail
- Juliet seed benchmark cases

Artifacts:
- benchmark runs persist `metrics`, `status`, `artifacts`, timestamps in `benchmark_runs`.

# 9. Testing Plan
Unit tests:
- normalization status mapping and schema shapes
- chunk split/reassembly and checksum metadata
- parser behavior for source-specific payloads
- ingestion validation/sanitization rules
- retrieval scoring behavior

Integration tests:
- Mongo repository persistence/dedup/chunk writes end-to-end (`test_learning_repository_integration.py`)
- re-ingestion idempotency
- benchmark suite run behavior

Regression:
- full backend test suite run before merge.

# 10. Failure Modes and Safeguards
Handled failure modes:
- source fetch failure: ingestion audit `failed`
- parse/normalize/item failure: `normalization_failures` record + continue
- dedup collision: upsert skip path
- invalid source spec or malformed item: validation exception, audited
- chunking on large payloads: metadata + chunk documents only

Safeguards:
- no model training/inference changes introduced
- provider layer untouched
- raw payload captured before parsing for reproducibility
- deterministic retrieval with explicit scoring, no hidden ML ranking

# 11. Milestone Roadmap
M0 (Done): Benchmark Skeleton
- suite bootstrap
- benchmark run model
- seed ground truth cases

M1 (Done): Learning Archive Foundation
- archive collection models
- internal finding/patch/verification/feedback archival

M2 (Done): External Ingestion Foundation
- downloader, parser layer, normalization, persistence
- raw cache + ingestion audits + failure logging

M3 (Done): Retrieval Layer v1
- keyword + metadata filtering
- deterministic scoring and pagination

M4 (Done): Storage/Integrity Hardening
- chunk policy + checksums + dedup indexes

M5 (Done): Tests and Bootstrap Verification
- unit/integration tests and startup bootstrap validation

# 12. Definition of Done for Each Milestone
M0 DoD:
- benchmark suite records exist
- benchmark run creation/finalization works
- seed cases inserted idempotently

M1 DoD:
- archive endpoints persist canonical records
- status vocabulary enforced via normalization
- feedback and verification outcomes preserved

M2 DoD:
- ingestion supports fetch/parse/normalize/store
- rerun does not duplicate items
- failures captured in `normalization_failures`/`ingestion_audit`

M3 DoD:
- retrieval supports keyword + metadata filters + pagination
- deterministic scoring returned in API response

M4 DoD:
- large bodies chunked safely
- chunk reassembly/checksums validated
- unique indexes prevent silent duplicates

M5 DoD:
- tests pass
- benchmark suites runnable
- startup bootstrap succeeds without manual migration steps
