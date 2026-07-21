# Hermes Integration Progress

Branch: `agent/hermes-foundation`

This file is the durable implementation ledger for the Open Brain × Hermes work. Update it whenever a meaningful slice lands.

## Overall status

Current phase: **Actionable context and distribution**

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
- [x] Add safe `USER.md`, `MEMORY.md`, allowlisted context, sessions, skills, and cron discovery without automatic promotion.
- [x] Add structured project/task/decision/assertion/outcome retrieval.
- [x] Add revision-aware, token-bounded context packets with trust and freshness labels.
- [x] Add context feedback contracts and APIs.
- [x] Add a one-line pipx installer.
- [x] Add `openbrain update` with packaged, checksum-protected migrations.
- [x] Correct the package layout so CLI modules and SQL migrations ship in installed distributions.

### In progress

- [ ] Add context packet builder tests and API tests.
- [ ] Add provider adapter capability declarations and provider-specific normalization.
- [ ] Add rollback/tombstone metadata for staged imports.
- [ ] Add database-backed tests for event, identity, session, import, and context concurrency.
- [ ] Add update compatibility checks and documented rollback behavior.

## Next implementation slices

### Complete Slice 4 — actionable context

- context API validation and tests
- revision invalidation on project/task/decision mutations
- packet diversity limits
- feedback aggregation into assertion usefulness counters

### Slice 5 — Hermes provider

- upstream-compatible `OpenBrainMemoryProvider`
- durable local spool
- cached `prefetch` and background `queue_prefetch`
- `sync_turn`, `on_memory_write`, `on_session_switch`, `on_pre_compress`, `on_delegation`, and `on_session_end`
- graceful degradation when Open Brain is unavailable

### Distribution and updates

One-line installation target:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
```

Update target:

```bash
openbrain update
```

Before release, the installer URL must point to a reviewed default-branch script or a pinned release tag. Updates must check compatibility, apply only additive migrations, preserve the migration checksum ledger, and provide a documented rollback path.

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
- `POST /v1/context`
- `POST /v1/context/feedback`

## Validation status

The code has been reviewed structurally through the connected repository interface. Runtime tests have **not yet been executed in this environment** because a local checkout and GitHub CLI are unavailable. The draft PR must remain unmerged until CI or a local environment runs:

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
```

The packaged install path must additionally validate:

```bash
pipx install 'git+https://github.com/benclawbot/open-brain.git@agent/hermes-foundation'
openbrain --version
openbrain update --skip-migrations
```

Database integration tests should run against PostgreSQL with pgvector enabled.

## Known risks

- Migration `002_continuity_foundation.sql` is required before any `/v1` continuity endpoint is used.
- Database-backed idempotency, identity-link collision, import-run, and context tests are still missing.
- External identity aliases must never be silently reassigned between canonical users.
- Imported records still require reconciliation to distinguish durable facts, instructions, notes, obsolete content, and provider inference.
- Dry-run records are intentionally persisted for auditability but do not create assertions or mutate source systems.
- The one-line installer must not be advertised from `master` until the PR is merged and installation smoke tests pass.
- The Hermes provider has not been started; service contracts are being stabilized first.
