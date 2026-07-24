# Changelog

All notable changes to Open Brain are documented in this file. The project follows Semantic Versioning. Already-applied database migrations are immutable; upgrades add new migrations rather than editing migration history.

## [Unreleased]

### Changed
- Default docker-compose stack now ships an `ollama` service running the `nomic-embed-text` model (768-dim). The api no longer requires an external embeddings API key for a working local stack.
- Default API host port changed from `8000` to `8765`. Port 8000 is held by the Windows IP Helper service (`iphlpsvc`) on many Windows hosts, which prevents the api container from binding. Override with `API_PORT` in `.env`.
- `scripts/setup_db.py` now honours `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER` environment variables, matching the pattern used by `check_db.py`. The api container's compose-injected values (e.g. `postgres:5432`) now apply correctly on first run.
- `scripts/startup.sh` now invokes `scripts/migrate.py` after `setup_db.py`. The README always claimed the API applied migrations on startup; the code now matches the documentation.
- `src/db/connection.py` registers `psycopg2.extras.UUID_adapter` at import time. Queries that bind `uuid.UUID` parameters (`get_memory_by_id`, etc.) no longer raise `ProgrammingError: can't adapt type 'UUID'`.

### Added
- `scripts/quickstart.sh` brings up the docker stack, waits for the api to become healthy, ensures the embedding model is available, and (with `--with-hermes`) wires Open Brain into a locally-installed Hermes as the active memory provider. Idempotent.
- Migration `015_embedding_dim_change.sql` alters `memory.embedding` from `vector(1536)` to `vector(768)` and rebuilds the HNSW index to match the new Ollama-backed default embedder.
- `.gitattributes` forces LF line endings for `*.sh`, `*.py`, `*.sql`, and similar source files so Windows checkouts no longer reintroduce CRLF into shell scripts.
- `.gitignore` now excludes `.env`; `.env.example` is the single source of truth for non-secret defaults.

### Security
- Removed the previously-checked-in `.env` from version control. Operators should `cp .env.example .env` (or let `openbrain configure --project-root .` generate the secrets) before first run.

## [1.0.0] - 2026-07-22

### Added

- Canonical identities for users, agents, workspaces, projects, tasks, and sessions.
- Append-only, provenance-aware event ingestion with idempotency controls.
- Session lineage for resume, branch, compression, delegation, rewind, and close transitions.
- Structured assertions with supporting, contradicting, qualifying, and superseding evidence.
- Actionable context packets with trust labels, freshness, and token budgets.
- PostgreSQL and pgvector-backed semantic memory and hybrid retrieval.
- REST, MCP, CLI, dashboard, analytics, reporting, tagging, and entity extraction interfaces.
- Native Hermes memory provider with local write spooling, cached recall, and replay.
- Provider SDK and conformance suite.
- Medusa, Codex, and Claude Code lifecycle adapters with automatic source and `captured_by` attribution.
- Deployment authentication boundaries, secure configuration validation, request limits, health probes, structured diagnostics, and operator runbooks.
- Database retry behavior, concurrency coverage, pool-saturation handling, and migration matrices.
- Durable contradiction reconciliation, lifecycle review queues, and immutable automation receipts.
- Staged import preview, sealing, resumability, conflict reporting, rollback metadata, and atomic failure behavior.
- Retrieval feedback aggregation, diagnostics, proposal generation, explicit human approval, and immutable proposal/application receipts.
- Machine-readable `openbrain-release-check` readiness gate with JSON output and non-zero failure status.

### Changed

- Promoted package status from alpha `0.2.0` to production/stable `1.0.0`.
- Unified proposal review request contracts across lifecycle, consolidation, and pruning workflows.
- Hardened installer and updater behavior around migration checksums and data preservation.

### Operational requirements

A production deployment is ready only after automatic checks pass and operators explicitly attest that TLS, backups, restore drills, monitoring, and migration records have been verified. Open Brain deliberately does not infer these external controls from configuration alone.

[1.0.0]: https://github.com/benclawbot/open-brain/releases/tag/v1.0.0
