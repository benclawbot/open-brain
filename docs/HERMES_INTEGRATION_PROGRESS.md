# Hermes Integration Progress

Branch: `agent/hermes-foundation`

This file is the durable implementation ledger for the Open Brain × Hermes work. Update it whenever a meaningful slice lands.

## Overall status

Current phase: **Bootstrap import completion**

### Completed

- [x] Record the accepted architecture and non-negotiable design decisions.
- [x] Confirm upstream `NousResearch/hermes-agent` as the only Hermes integration target.
- [x] Define additive continuity schema covering identities, projects, tasks, sessions, events, assertions/evidence, decisions, outcomes, imports, and context revisions.
- [x] Preserve the existing `memory` table and APIs for backward compatibility.
- [x] Define strict, provenance-aware event contracts and idempotent event persistence.
- [x] Add checksum-protected additive migrations and the `/v1/events` API.
- [x] Add canonical identity resolution with cross-platform aliases.
- [x] Add Hermes session opening, closing, and reset/resume/branch/compression/rewind lineage.
- [x] Define a provider-neutral, resumable import adapter contract.
- [x] Add deterministic external IDs, SHA-256 hashes, dry-run/staged execution, cursor checkpoints, and source-change protection.
- [x] Add safe `USER.md` and `MEMORY.md` discovery without automatic promotion.
- [x] Add explicitly allowlisted context-file discovery with root-escape protection.
- [x] Add JSON/JSONL session summary and transcript import as episodic candidates.
- [x] Add skill discovery as procedural candidates requiring evaluation before activation.
- [x] Add cron discovery as automation candidates while retaining Hermes as executor.
- [x] Add contract tests for import parsing, resume safety, allowlist boundaries, session summaries, skills, and cron jobs.

### In progress

- [ ] Add provider adapter capability declarations and provider-specific normalization.
- [ ] Add rollback/tombstone metadata for staged imports.
- [ ] Add database-backed tests for event, identity, session, and import concurrency.
- [ ] Add structured active project/task/decision context lookup.

## Next implementation slices

### Slice 4 — actionable context

- active project/task/decision queries
- context revision increments
- compact context packet builder
- token and item budgets
- trust and freshness labels
- retrieval feedback contract

### Slice 5 — Hermes provider

- upstream-compatible `OpenBrainMemoryProvider`
- durable local spool
- cached `prefetch` and background `queue_prefetch`
- `sync_turn`, `on_memory_write`, `on_session_switch`, `on_pre_compress`, `on_delegation`, and `on_session_end`
- graceful degradation when Open Brain is unavailable

### Slice 6 — lifecycle and self-improvement

- consolidation and canonical assertion reconciliation
- demotion, archival, tombstones, and retention policies
- outcome evaluation and repeated-pattern detection
- improvement proposals with explicit authority boundaries

## API added so far

- `POST /v1/events`
- `POST /v1/identities/resolve`
- `POST /v1/sessions/open`
- `POST /v1/sessions/{session_id}/close`
- `POST /v1/imports/hermes/markdown`

## Validation status

The code has been reviewed structurally through the connected repository interface. Runtime tests have **not yet been executed in this environment** because a local checkout and GitHub CLI are unavailable. The draft PR must remain unmerged until CI or a local environment runs:

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
```

Database integration tests should run against PostgreSQL with pgvector enabled.

## Known risks

- Migration `002_continuity_foundation.sql` is required before any `/v1` continuity endpoint is used.
- Existing startup initializes the connection pool but does not automatically apply migrations; migration execution remains explicit for safety.
- Database-backed idempotency, identity-link collision, and import-run concurrency tests are still missing.
- External identity aliases must never be silently reassigned between canonical users.
- Imported records still require reconciliation to distinguish durable facts, instructions, notes, obsolete content, and provider inference.
- Dry-run records are intentionally persisted for auditability but do not create assertions or mutate source systems.
- The Hermes provider has not been started; service contracts are being stabilized first.
