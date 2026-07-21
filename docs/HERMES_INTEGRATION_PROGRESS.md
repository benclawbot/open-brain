# Hermes Integration Progress

Branch: `agent/hermes-foundation`

This file is the durable implementation ledger for the Open Brain × Hermes work. Update it whenever a meaningful slice lands.

## Overall status

Current phase: **Bootstrap import foundation**

### Completed

- [x] Record the accepted architecture and non-negotiable design decisions.
- [x] Confirm upstream `NousResearch/hermes-agent` as the only Hermes integration target.
- [x] Define additive continuity schema covering identities, projects, tasks, sessions, events, assertions/evidence, decisions, outcomes, imports, and context revisions.
- [x] Preserve the existing `memory` table and APIs for backward compatibility.
- [x] Define strict Pydantic event contracts with namespaced event types, timezone-aware timestamps, scope, authority, sensitivity, and retention policy.
- [x] Implement idempotent event persistence using a unique idempotency key.
- [x] Expose `POST /v1/events` through the FastAPI application.
- [x] Add a checksum-protected additive SQL migration runner.
- [x] Add initial contract tests for event validation, scope, and authority.
- [x] Add canonical user, agent, workspace, and platform-user identity contracts.
- [x] Add optional external identity aliases for stable cross-gateway resolution.
- [x] Implement idempotent identity resolution and metadata merging.
- [x] Implement session opening and closing APIs.
- [x] Preserve reset/resume/branch/compression/rewind lineage.
- [x] Reject branch, resume, or compression lineage when the required parent is missing.
- [x] Add identity and session contract tests.
- [x] Define a provider-neutral, resumable import adapter contract.
- [x] Add deterministic external IDs and SHA-256 source hashes.
- [x] Add safe Hermes `USER.md` and `MEMORY.md` discovery.
- [x] Preserve file path, section, ordinal, line form, source fingerprint, and authority on imported candidates.
- [x] Keep imported records as candidates for reconciliation rather than silently promoting every line as truth.
- [x] Add bootstrap-import parser tests.

### In progress

- [ ] Persist import runs and import-record outcomes through the existing ledger tables.
- [ ] Add dry-run and resumable import orchestration.
- [ ] Add context-file discovery with explicit allowlists.
- [ ] Add session summary/transcript import.
- [ ] Add database-backed tests for duplicate event delivery and payload preservation.
- [ ] Add database-backed tests for duplicate identity resolution and session initialization.
- [ ] Add structured active project/task/decision context lookup.

### Next implementation slices

#### Complete Slice 3 — bootstrap import

- import-run persistence and checkpoints
- dry-run, resume, and rollback metadata
- context-file importer
- session summary/transcript importer
- skills and cron discovery
- provider adapter capability declarations

#### Slice 4 — actionable context

- active project/task/decision queries
- context revision increments
- compact context packet builder
- token and item budgets
- trust and freshness labels
- retrieval feedback contract

#### Slice 5 — Hermes provider

- upstream-compatible `OpenBrainMemoryProvider`
- durable local spool
- cached `prefetch` and background `queue_prefetch`
- `sync_turn`, `on_memory_write`, `on_session_switch`, `on_pre_compress`, `on_delegation`, and `on_session_end`
- graceful degradation when Open Brain is unavailable

#### Slice 6 — lifecycle and self-improvement

- consolidation and canonical assertion reconciliation
- demotion, archival, tombstones, and retention policies
- outcome evaluation and repeated-pattern detection
- improvement proposals with explicit authority boundaries

## API added so far

- `POST /v1/events`
- `POST /v1/identities/resolve`
- `POST /v1/sessions/open`
- `POST /v1/sessions/{session_id}/close`

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
- Database-backed idempotency and identity-link collision tests are still missing.
- External identity aliases must never be silently reassigned between canonical users; this requires an integration test under concurrent delivery.
- Markdown imports preserve curated authority but still require reconciliation to distinguish durable facts, instructions, notes, and obsolete content.
- The Hermes provider has not been started; service contracts are being stabilized first.
