# Open Brain

> A model-independent personal memory and agent-continuity service for durable evidence, decisions, tasks, outcomes, and long-term learning across agents and interfaces.

[![Verify](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml/badge.svg)](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml)
[![License](https://img.shields.io/github/license/benclawbot/open-brain)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)

## Overview

Open Brain is the durable knowledge layer behind AI agents. Agents remain responsible for reasoning, tools, browser or computer use, and execution. Open Brain provides continuity, provenance, retrieval, lifecycle management, and accumulated understanding.

It separates three concerns:

1. **Canonical evidence** — append-only events, imported records, sessions, tool results, and artifacts.
2. **Knowledge model** — current assertions, projects, tasks, decisions, procedures, and outcomes.
3. **Retrieval projections** — embeddings, indexes, revisions, caches, and context packets that can be rebuilt safely.

Imported or provider-supplied records are never silently promoted into truth. They retain authority and provenance until reconciliation classifies them as durable facts, instructions, procedures, historical episodes, stale information, or inference.

## Capabilities

- PostgreSQL and pgvector-backed semantic memory and hybrid search
- canonical user, agent, workspace, project, task, and session identities
- append-only, provenance-aware events with idempotent ingestion
- session lineage for resume, branch, compression, delegation, rewind, and close transitions
- structured assertions with supporting, contradicting, qualifying, and superseding evidence
- compact actionable context packets with trust labels, freshness, and token budgets
- REST, MCP, CLI, dashboard, analytics, reports, tagging, and entity extraction
- native Hermes memory provider with local spool, cached recall, and replay
- universal provider SDK and conformance suite
- Medusa, Codex, and Claude Code lifecycle adapters
- staged, resumable imports with preview, sealing, conflicts, rollback metadata, and atomic failure behavior
- contradiction reconciliation, lifecycle automation, review queues, and immutable receipts
- retrieval feedback, diagnostics, self-improvement proposals, and explicit human approval
- checksum-protected additive database migrations
- production readiness validation through `openbrain-release-check`

## Architecture

```text
Hermes       Medusa       Codex       Claude Code       other agents
   │            │            │              │                │
 native      provider     provider       provider         REST / MCP
 provider      SDK          SDK            SDK
   └────────────┴────────────┴──────────────┴────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         Open Brain                           │
│                                                              │
│  Evidence        Knowledge model        Retrieval packets    │
│  ─────────       ───────────────        ─────────────────    │
│  events          identities             active context       │
│  sessions        projects/tasks         trust labels         │
│  imports         assertions             freshness            │
│  artifacts       decisions/outcomes     token budgets        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                    PostgreSQL + pgvector
```

## Agent integrations

| Agent | Integration | Lifecycle coverage | Offline behavior |
|---|---|---|---|
| Hermes | Native upstream-compatible memory provider | recall, remember, prefetch, turn sync, session switch, compression, delegation, session end | local spool and cached recall |
| Medusa | Provider SDK adapter | session start/end, user and assistant messages, tool results, compression, delegation | local spool and replay |
| Codex | Explicit host lifecycle bridge | session start/end, user and assistant messages, tool results, compression | host-controlled failure handling |
| Claude Code | Explicit host lifecycle bridge | session start/end, user and assistant messages, tool results, compression | host-controlled failure handling |
| Other agents | REST, MCP, or provider SDK | capability-dependent | integration-defined |

The Codex and Claude Code bridges deliberately avoid undocumented local transcript formats. A host wrapper supplies stable session, workspace, version, and scope identifiers and calls explicit lifecycle methods.

Integration guides:

- [`docs/HERMES_INTEGRATION_ARCHITECTURE.md`](docs/HERMES_INTEGRATION_ARCHITECTURE.md)
- [`docs/HERMES_INTEGRATION_PROGRESS.md`](docs/HERMES_INTEGRATION_PROGRESS.md)
- [`docs/MEDUSA_ADAPTER.md`](docs/MEDUSA_ADAPTER.md)
- [`docs/CODEX_ADAPTER.md`](docs/CODEX_ADAPTER.md)
- [`docs/CLAUDE_CODE_ADAPTER.md`](docs/CLAUDE_CODE_ADAPTER.md)

## Installation

Open Brain requires Python 3.11+ and PostgreSQL. pgvector is recommended for semantic retrieval.

For a reproducible v1.0.0 installation, review and run the release-pinned installer:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/v1.0.0/install.sh | sh
```

Verify:

```bash
openbrain --version
openbrain --help
```

The installer uses `pipx`, keeping Open Brain isolated from system Python packages.

### Hermes

```bash
openbrain install-hermes
export OPENBRAIN_URL=http://127.0.0.1:8000
hermes memory setup
```

Select `openbrain` as the active memory provider when prompted.

Optional scope variables:

```bash
export OPENBRAIN_PROJECT_ID=<project-uuid>
export OPENBRAIN_TASK_ID=<task-uuid>
export OPENBRAIN_TIMEOUT=3
```

If Open Brain is unavailable, Hermes continues operating. Writes are appended to `$HERMES_HOME/openbrain-spool.jsonl` and replayed later.

### Development

```bash
git clone https://github.com/benclawbot/open-brain.git
cd open-brain
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Database and local stack

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openbrain
DB_USER=postgres
DB_PASSWORD=change-me
DB_TIMEZONE=auto
```

```bash
cp .env.example .env
docker compose up -d
python scripts/migrate.py
```

| Service | Address |
|---|---|
| REST API | `http://localhost:8000` |
| API documentation | `http://localhost:8000/docs` |
| MCP server | `http://localhost:8080` |
| Dashboard | `http://localhost:8501` |
| PostgreSQL | `localhost:5432` |

Already-applied migrations must never be edited. Add a new migration instead.

## CLI

```bash
openbrain search "what did I decide about Hermes?"
openbrain store "Use upstream NousResearch/hermes-agent" --source cli --tag hermes
openbrain stats
openbrain import file ./notes.md
openbrain report --days 7
openbrain serve --host 127.0.0.1 --port 8000
openbrain install-hermes
openbrain update
```

## REST API

Semantic-memory endpoints:

```text
POST /memories
POST /memories/search
GET  /memories/{memory_id}
GET  /stats
GET  /trends
GET  /report/weekly
```

Continuity endpoints:

```text
POST /v1/events
POST /v1/identities/resolve
POST /v1/sessions/open
POST /v1/sessions/{session_id}/close
POST /v1/imports/hermes/markdown
POST /v1/context
POST /v1/context/feedback
```

Context packets contain selected current state rather than raw transcript fragments. Items carry labels such as `user_confirmed`, `tool_observed`, `curated_memory`, `inferred`, `stale`, or `contradicted`.

## Memory lifecycle

```text
candidate → active → confirmed
                     ├→ superseded
                     ├→ contradicted
                     ├→ dormant
                     └→ archived → tombstoned → deleted
```

Open Brain prunes retrieval before storage. Old evidence can leave hot retrieval while remaining available for history, provenance, audit, and reconciliation. User-authored information is not automatically physically deleted.

## Security and authority

Typical authority ordering:

1. direct user statement
2. user-curated memory
3. tool observation
4. provider inference
5. Open Brain inference
6. assistant claim

Sensitive records can carry sensitivity and retention classifications. Provider inference remains distinguishable from user-confirmed truth.

Review `install.sh` before execution in high-security environments. Use a reviewed release tag rather than the moving `master` branch for reproducible deployment.

## Production readiness

Run the machine-readable gate before deployment:

```bash
openbrain-release-check --help
```

The gate validates production mode, authentication, API-key strength, and explicit CORS configuration. It also requires operator attestations for controls that cannot be inferred safely from application configuration:

- TLS termination verified
- backups verified
- restore drill completed
- monitoring enabled
- migration records confirmed

A deployment is not certified merely because configuration files exist. See [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md).

## Validation

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
python -m build
```

GitHub Actions validates package installation, PostgreSQL and pgvector migrations, the full test suite, provider conformance, wheel creation, installed CLI execution, and Hermes provider installation smoke tests.

## Project structure

```text
src/
├── api/                         REST endpoints
├── cli/                         command-line interface
├── continuity/                  event, identity, and session contracts
├── context/                     actionable context and packet builder
├── db/                          persistence, migrations, and queries
├── importers/                   staged and provider imports
├── providers/                   universal provider SDK and conformance
├── release/                     production readiness checks
├── openbrain_hermes_plugin/     standalone Hermes memory provider
├── openbrain_medusa_adapter/    Medusa lifecycle adapter
├── openbrain_codex_adapter/     Codex lifecycle adapter
├── openbrain_claude_adapter/    Claude Code lifecycle adapter
├── analytics/                   trends and reports
├── connectors/                  source connectors
├── extractors/                  entities and tagging
└── notifications/               notification integrations
```

## Release status

**Open Brain 1.0.0 is the first production/stable release.** The coordinated production-readiness train delivered deployment hardening, database resilience, real adapter host wiring, durable reconciliation, staged imports, unified proposal review workflows, and a machine-readable release gate.

Production readiness still depends on the target environment. Operators must run the readiness gate and verify external controls such as TLS, backups, restore drills, and monitoring before serving real data.

See [`CHANGELOG.md`](CHANGELOG.md) for release details.

## License

MIT.
