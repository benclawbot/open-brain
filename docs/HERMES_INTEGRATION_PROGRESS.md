# Hermes Integration Progress

Branch: `agent/hermes-foundation`

This file is the durable implementation ledger for the Open Brain × Hermes work. Update it whenever a meaningful slice lands.

## Overall status

Current phase: **Foundation / event ingestion**

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

### In progress

- [ ] Add database-backed tests for duplicate event delivery and payload preservation.
- [ ] Add canonical identity resolution and cross-platform identity linking.
- [ ] Add Hermes session creation and lineage transitions.
- [ ] Add structured active project/task/decision context lookup.

### Next implementation slices

#### Slice 2 — identity and sessions

- canonical user, agent, workspace, and platform-user resolution
- stable cross-gateway user identity
- idempotent session establishment
- reset/resume/branch/compression/rewind lineage
- tests for session switching and duplicate initialization

#### Slice 3 — bootstrap import

- import ledger and adapter protocol
- Hermes `USER.md` importer
- Hermes `MEMORY.md` importer
- context-file importer
- session summary/transcript importer
- dry-run, resume, source hashes, and rollback metadata

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

## Validation status

The code has been reviewed structurally through the connected repository interface. Runtime tests have **not yet been executed in this environment** because a local checkout and GitHub CLI are unavailable. The draft PR must remain unmerged until CI or a local environment runs:

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
```

Database integration tests should run against PostgreSQL with pgvector enabled.

## Known risks

- The new API requires migration `002_continuity_foundation.sql` before `/v1/events` is used.
- Existing startup initializes the connection pool but does not automatically apply migrations; migration execution remains explicit for safety.
- Database-backed idempotency tests are still missing.
- The Hermes provider has not been started; service contracts are being stabilized first.
