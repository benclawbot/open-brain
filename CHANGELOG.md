# Changelog

All notable changes to Open Brain are documented in this file.

The project follows Semantic Versioning. Already-applied database migrations are immutable; upgrades add new migrations rather than editing migration history.

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
