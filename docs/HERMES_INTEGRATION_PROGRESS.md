# Hermes Integration Progress

Branch: `agent/provider-normalization`

This file is the durable implementation ledger for the Open Brain × Hermes work. Update it whenever a meaningful slice lands.

## Overall status

Current phase: **Provider normalization**

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
- [x] Add context contract tests.
- [x] Implement the upstream-compatible `OpenBrainMemoryProvider`.
- [x] Add cached prefetch and background `queue_prefetch`.
- [x] Add non-blocking `sync_turn` event delivery.
- [x] Add `openbrain_recall` and `openbrain_remember` tools.
- [x] Add session switch, pre-compress, memory-write, delegation, session-end, and shutdown hooks.
- [x] Add deterministic provider idempotency keys and canonical Open Brain session scope.
- [x] Add a durable JSONL spool and replay when Open Brain is unavailable.
- [x] Add a one-line pipx installer.
- [x] Add `openbrain install-hermes` for standalone Hermes plugin installation.
- [x] Add `openbrain update` with packaged, checksum-protected migrations.
- [x] Correct the package layout so CLI modules, SQL migrations, and Hermes plugin assets ship in installed distributions.
- [x] Add wheel, migration, CLI, and Hermes plugin smoke checks in GitHub Actions.
- [x] Rewrite the README with complete capabilities, architecture, installation, Hermes setup, generic agent setup, updates, APIs, and operational boundaries.
- [x] Declare external-provider import capabilities.
- [x] Add read-only Mem0, Honcho, and Hindsight export normalization.
- [x] Preserve provider IDs, source instances, timestamps, confidence, entities, relationships, custom metadata, and raw-record hashes.
- [x] Add provider discovery and resumable dry-run/staged import APIs.

### Deferred maturity work

- [ ] Add provider-specific normalization for additional external memory systems.
- [ ] Add direct authenticated provider API clients; the current slice consumes exported/API-supplied records.
- [ ] Add rollback/tombstone metadata for staged imports.
- [ ] Expand database concurrency tests for event, identity, session, import, and context races.
- [ ] Increment context revisions automatically on every project/task/decision mutation.
- [ ] Aggregate retrieval feedback into assertion usefulness and harmfulness counters.
- [ ] Add packet diversity policies beyond the current importance and token budgets.
- [ ] Add lifecycle automation for consolidation, demotion, archival, and tombstones.
- [ ] Add evidence-backed self-improvement proposals and evaluation outcomes.

## Distribution

One-line installation:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
```

Native Hermes provider:

```bash
openbrain install-hermes
export OPENBRAIN_URL=http://127.0.0.1:8000
hermes memory setup
```

Updates:

```bash
openbrain update
openbrain install-hermes --force
```

`openbrain update` applies only packaged additive migrations whose checksums are not already present in `schema_migration`. Existing data is not deleted when a migration fails.

## APIs

- `POST /v1/events`
- `POST /v1/identities/resolve`
- `POST /v1/sessions/open`
- `POST /v1/sessions/{session_id}/close`
- `POST /v1/imports/hermes/markdown`
- `GET /v1/imports/providers`
- `POST /v1/imports/providers`
- `POST /v1/context`
- `POST /v1/context/feedback`

The existing semantic-memory, analytics, MCP, CLI, dashboard, and report interfaces remain available.

## Validation status

GitHub Actions validates:

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
python -m build
```

The built wheel is installed into a fresh virtual environment. CI then verifies:

```bash
openbrain --version
openbrain install-hermes --hermes-home /tmp/hermes-smoke
```

PR #18 must not merge until the latest `Verify` run passes.

## Known risks

- Migration `002_continuity_foundation.sql` is required before continuity endpoints are used.
- Imported records still require reconciliation to distinguish durable facts, instructions, notes, obsolete content, and provider inference.
- Provider adapters currently normalize caller-supplied exports/API records and do not hold provider credentials.
- Dry-run records are intentionally persisted for auditability but do not create assertions or mutate source systems.
- The installer tracks the default branch unless the user pins a reviewed release tag.
- This remains alpha software despite the completed first-party Hermes integration.
