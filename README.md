# Open Brain

> A model-independent personal memory and agent-continuity service. Open Brain preserves evidence, projects, tasks, decisions, outcomes, and long-term learning so different agents and interfaces can continue the same work.

[![Verify](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml/badge.svg)](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml)
[![License](https://img.shields.io/github/license/benclawbot/open-brain)](LICENSE)

## What Open Brain does

Open Brain is the durable knowledge layer behind AI agents. Agents remain responsible for reasoning, tools, browser or computer use, and execution. Open Brain is responsible for continuity, provenance, retrieval, and accumulated understanding.

It provides:

- semantic memory storage and hybrid search with PostgreSQL and pgvector;
- automatic tagging, entity extraction, trends, reports, REST, MCP, CLI, and dashboard interfaces;
- canonical user, agent, workspace, project, task, and session identities;
- append-only, provenance-aware events with idempotent ingestion;
- session lineage for new, reset, resume, branch, compression, delegation, and rewind transitions;
- structured assertions with supporting, contradicting, qualifying, and superseding evidence;
- compact actionable context packets with trust labels, freshness, and token budgets;
- a native upstream-compatible Hermes memory provider;
- a universal provider SDK with typed recall, remember, capability, scope, and lifecycle contracts;
- conformance-backed adapters for Medusa, Codex, and Claude Code;
- local write spooling and replay for supported offline-capable integrations;
- checksum-protected additive database migrations;
- a one-line installer and `openbrain update` command.

Imported or provider-supplied records are not silently promoted into truth. They retain authority and provenance until reconciliation determines whether they are durable facts, instructions, procedures, historical episodes, stale information, or inference.

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

Open Brain separates:

1. **Canonical evidence** — append-only events, imported records, sessions, tool results, and artifacts.
2. **Knowledge model** — current assertions, projects, tasks, decisions, procedures, and outcomes.
3. **Retrieval projections** — embeddings, indexes, revisions, caches, and context packets that can be rebuilt safely.

## Agent integrations

| Agent | Integration | Lifecycle coverage | Offline behavior |
|---|---|---|---|
| Hermes | Native upstream-compatible memory provider | recall, remember, prefetch, turn sync, session switch, compression, delegation, session end | local spool and cached recall |
| Medusa | Provider SDK adapter | session start/end, user and assistant messages, tool results, compression, delegation | local spool and replay |
| Codex | Explicit host lifecycle bridge | session start/end, user and assistant messages, tool results, compression | host-controlled failure handling |
| Claude Code | Explicit host lifecycle bridge | session start/end, user and assistant messages, tool results, compression | host-controlled failure handling |
| Other agents | REST, MCP, or provider SDK | capability-dependent | integration-defined |

The Codex and Claude Code bridges deliberately avoid undocumented local transcript formats. A host wrapper supplies stable session, workspace, version, and scope identifiers and calls explicit lifecycle methods.

Integration documentation:

- [`docs/HERMES_INTEGRATION_ARCHITECTURE.md`](docs/HERMES_INTEGRATION_ARCHITECTURE.md)
- [`docs/HERMES_INTEGRATION_PROGRESS.md`](docs/HERMES_INTEGRATION_PROGRESS.md)
- [`docs/MEDUSA_ADAPTER.md`](docs/MEDUSA_ADAPTER.md)
- [`docs/CODEX_ADAPTER.md`](docs/CODEX_ADAPTER.md)
- [`docs/CLAUDE_CODE_ADAPTER.md`](docs/CLAUDE_CODE_ADAPTER.md)

## Installation

### One-line installation

Linux, macOS, WSL, or a coding-agent shell with Python 3.11+:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
```

The installer uses `pipx`, keeping Open Brain isolated from system Python packages.

Verify:

```bash
openbrain --version
openbrain --help
```

### Install from Hermes

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
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

### Install through another coding agent

Give Claude Code, Codex, Medusa, OpenCode, or another shell-capable agent this instruction:

```text
Install Open Brain from https://github.com/benclawbot/open-brain using the repository's official install.sh script. Review the script first. After installation, run `openbrain --version`. If this is Hermes, also run `openbrain install-hermes`, set OPENBRAIN_URL, and configure the openbrain memory provider. Report failed steps without deleting existing data.
```

Agents without shell access can use the REST or MCP interfaces after Open Brain is deployed elsewhere.

### Development installation

```bash
git clone https://github.com/benclawbot/open-brain.git
cd open-brain
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Updating

```bash
openbrain update
```

The updater upgrades the pipx-managed package, verifies migration checksums, applies only new migrations, and leaves existing data intact if migration execution fails.

Refresh an existing Hermes provider copy after upgrading:

```bash
openbrain install-hermes --force
```

Already-applied migrations must never be edited. Add a new migration instead.

## Database and configuration

Open Brain requires PostgreSQL. pgvector is recommended for semantic retrieval.

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openbrain
DB_USER=postgres
DB_PASSWORD=change-me
DB_TIMEZONE=auto
```

Start the complete local stack:

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

## Provider SDK and conformance

The provider SDK normalizes:

- provider identity and version;
- declared capabilities;
- recall and remember requests;
- canonical user, project, and task scope;
- deterministic idempotency keys;
- authority labels;
- health checks and transport behavior.

`run_provider_conformance()` validates descriptor integrity, declared capabilities, scoped recall and remember behavior, and duplicate-safe ingestion. Adapters can call `require_success()` to fail validation with a structured report.

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

1. direct user statement;
2. user-curated memory;
3. tool observation;
4. provider inference;
5. Open Brain inference;
6. assistant claim.

Sensitive records can carry sensitivity and retention classifications. Provider inference remains distinguishable from user-confirmed truth.

Review `install.sh` before execution in high-security environments. For reproducible deployment, pin installation to a reviewed release tag rather than `master`.

## Development and validation

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
python -m build
```

GitHub Actions validates:

- package installation;
- PostgreSQL and pgvector migrations;
- the full test suite;
- provider conformance tests;
- wheel creation;
- installed CLI execution;
- native Hermes provider copying and smoke tests.

## Project structure

```text
src/
├── api/                         REST endpoints
├── cli/                         command-line interface
├── continuity/                  event, identity, and session contracts
├── context/                     actionable context and packet builder
├── db/                          persistence, migrations, and queries
├── importers/                   Hermes and provider import adapters
├── providers/                   universal provider SDK and conformance
├── openbrain_hermes_plugin/     standalone Hermes memory provider
├── openbrain_medusa_adapter/    Medusa lifecycle adapter
├── openbrain_codex_adapter/     Codex lifecycle adapter
├── openbrain_claude_adapter/    Claude Code lifecycle adapter
├── analytics/                   trends and reports
├── connectors/                  source connectors
├── extractors/                  entities and tagging
└── notifications/               notification integrations
```

## Status

Open Brain 0.2 is alpha software. Implemented foundations now include the continuity model, Hermes bootstrap imports, actionable context APIs, native Hermes provider, universal provider SDK, conformance runner, Medusa adapter, Codex adapter, Claude Code adapter, installer, updater, and package validation path.

Remaining maturity work includes broader database concurrency coverage, staged-import rollback metadata, richer reconciliation automation, lifecycle policy automation, adapter packaging and host wiring ergonomics, production deployment hardening, and self-improvement proposal workflows.

## License

MIT.
