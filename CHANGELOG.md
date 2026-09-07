# Changelog

All notable changes to Open Brain are documented in this file. The project follows Semantic Versioning. Already-applied database migrations are immutable; upgrades add new migrations rather than editing migration history.

## [Unreleased]

## [1.0.2] - 2026-09-07

### Fixed
- Capped the MCP Python SDK dependency to `mcp>=1.0.0,<2.0.0`, preventing fresh installs from resolving the incompatible 2.x API while Open Brain still uses the 1.x server decorators.
- Added bounded chunking, pooling, and validation for oversized embedding inputs so provider context limits no longer make memory storage fail outright.
- Added shared embedding regeneration for REST and MCP, with safe NULL-only replacement by default and an explicit force mode for embedding-model migrations.
- Made migration `015_embedding_dim_change.sql` safe on databases where the legacy `memory` table is not present yet.
- Added `001_base_schema.sql` to the packaged migration chain so an empty PostgreSQL + pgvector database can be initialized from a pip/pipx install.
- Added `openbrain migrate` as the supported installed-package database bootstrap/update command.
- Fixed e2e pytest collection so the standalone API runner skips cleanly when the API stack is unavailable instead of aborting the full test suite during module import.

### Changed
- Documented the standalone PostgreSQL + pgvector bootstrap flow in the README and installation guide.
- Aligned package and Hermes plugin release metadata on version `1.0.2`.
- Added release automation that publishes a tagged GitHub release with wheel and source-distribution artifacts only after `Verify` succeeds on `master`.

## [1.0.1] - 2026-07-24

### Fixed
- Made the local Docker stack work from a fresh clone by enforcing LF shell-script line endings, honoring database environment variables, running migrations during API startup, and registering psycopg2 UUID adaptation.
- Updated NLTK resource handling for the 3.8.2+ resource-name changes and baked the required data into the API image.

### Changed
- Switched the default local embedding service to Ollama with `nomic-embed-text` (768 dimensions), removing the need for an external embeddings API key for the default stack.
- Changed the default host API port from `8000` to `8765` to avoid common Windows port conflicts.
- Added migration `015_embedding_dim_change.sql` to align `memory.embedding` with the 768-dimensional default model and rebuild the HNSW index.
- Removed the checked-in `.env`; `.env.example` is now the non-secret source of defaults and generated credentials remain private.
- Added `.gitattributes` so Windows checkouts do not reintroduce CRLF into scripts and source files.

### Added
- Added `scripts/quickstart.sh` for idempotent local stack bootstrap and optional Hermes wiring.
- Added the API e2e suite covering health, memory, continuity, context, review workflows, maintenance, imports, and authentication behavior.

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

[1.0.2]: https://github.com/benclawbot/open-brain/releases/tag/v1.0.2
[1.0.1]: https://github.com/benclawbot/open-brain/releases/tag/v1.0.1
[1.0.0]: https://github.com/benclawbot/open-brain/releases/tag/v1.0.0
