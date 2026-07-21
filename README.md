# Open Brain

> A model-independent personal memory and agent-continuity service. Open Brain preserves evidence, projects, tasks, decisions, outcomes, and long-term learning so different agents and interfaces can continue the same work.

[![Verify](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml/badge.svg)](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml)
[![License](https://img.shields.io/github/license/benclawbot/open-brain)](LICENSE)

## What Open Brain does

Open Brain is the durable knowledge layer behind AI agents. The agent remains responsible for reasoning, tools, browser or computer use, and execution. Open Brain is responsible for continuity and accumulated understanding.

It currently provides:

- semantic memory storage and hybrid search with PostgreSQL and pgvector;
- automatic tagging, entity extraction, trends, reports, REST, MCP, CLI, and dashboard interfaces;
- canonical user, agent, workspace, project, task, and session identities;
- cross-interface identity links so the same person can be recognized across CLI, Telegram, Slack, Discord, or another gateway;
- append-only, provenance-aware events with idempotent ingestion;
- session lineage for new, reset, resume, branch, compression, and rewind transitions;
- structured assertions with supporting, contradicting, qualifying, and superseding evidence;
- first-class decisions, outcomes, import runs, and context revisions;
- safe bootstrap import of Hermes `USER.md`, `MEMORY.md`, explicitly allowlisted context files, session summaries or transcripts, skills, and cron jobs;
- resumable imports with dry-run mode, source hashes, checkpoints, duplicate suppression, and an audit ledger;
- compact actionable context packets containing current project state, tasks, decisions, assertions, outcomes, blockers, and next actions;
- trust and freshness labels, token budgets, item budgets, and retrieval feedback;
- checksum-protected additive database migrations;
- a one-line pipx installer and `openbrain update` command.

Imported records are not silently promoted into truth. They remain provenance-rich candidates until reconciliation confirms whether they are durable facts, instructions, procedures, historical episodes, obsolete information, or provider inference.

## Architecture

```text
Hermes / Claude Code / Codex / Medusa / other agents
                         │
                 REST, MCP, or provider
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│                       Open Brain                          │
│                                                           │
│  Evidence       Knowledge model       Retrieval packets   │
│  ─────────      ───────────────       ─────────────────   │
│  events         identities            active context      │
│  sessions       projects/tasks        trust labels        │
│  imports        assertions            freshness           │
│  artifacts      decisions/outcomes    token budgets       │
└──────────────────────────┬────────────────────────────────┘
                           │
                           ▼
                  PostgreSQL + pgvector
```

Open Brain keeps three concerns separate:

1. **Canonical evidence** — append-only events, imported records, sessions, tool results, and artifacts.
2. **Knowledge model** — current assertions, projects, tasks, decisions, procedures, and outcomes.
3. **Retrieval projections** — embeddings, indexes, revisions, caches, and compact context packets that may be rebuilt safely.

The accepted Hermes integration design and implementation ledger live in:

- [`docs/HERMES_INTEGRATION_ARCHITECTURE.md`](docs/HERMES_INTEGRATION_ARCHITECTURE.md)
- [`docs/HERMES_INTEGRATION_PROGRESS.md`](docs/HERMES_INTEGRATION_PROGRESS.md)

## Installation

### One-line installation

Linux, macOS, WSL, or a coding-agent shell with Python 3.11+:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
```

The installer uses `pipx` so the `openbrain` command is isolated from system Python packages. Restart the shell if `~/.local/bin` was newly added to `PATH`.

Verify:

```bash
openbrain --version
openbrain --help
```

### Install through Hermes or another coding agent

Give the agent this instruction:

```text
Install Open Brain from https://github.com/benclawbot/open-brain using the repository's official install.sh script. Do not copy commands from third-party sources. After installation, run `openbrain --version`, configure PostgreSQL, apply migrations, and report any failed step without deleting existing data.
```

Or ask it to execute:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
openbrain --version
```

This works from Hermes, Claude Code, Codex, Medusa, OpenCode, or another coding agent that has permission to run shell commands. For restricted agents, clone the repository manually and review `install.sh` before execution.

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

The updater:

1. upgrades the pipx-managed Open Brain package;
2. loads migrations from the installed package;
3. verifies migration checksums;
4. applies only migrations that have not run before;
5. leaves existing data intact if migration execution fails.

Upgrade without touching the database:

```bash
openbrain update --skip-migrations
```

Database migrations are additive and recorded in `schema_migration`. An already-applied migration must never be edited; a new migration must be added instead.

## Database and configuration

Open Brain requires PostgreSQL. pgvector is recommended for semantic search.

Environment variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openbrain
DB_USER=postgres
DB_PASSWORD=change-me
DB_TIMEZONE=auto
```

Apply migrations:

```bash
python scripts/migrate.py
```

Or, from an installed package, run the update path after configuring the database:

```bash
openbrain update
```

For the complete local stack:

```bash
cp .env.example .env
docker compose up -d
python scripts/migrate.py
```

Default services:

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
openbrain update
```

## REST API

Existing semantic-memory endpoints remain available:

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

### Ingest an idempotent event

```bash
curl -X POST http://localhost:8000/v1/events \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type": "conversation.user_message",
    "idempotency_key": "hermes:session-42:message-18",
    "source_system": "hermes",
    "authority": "user_confirmed",
    "payload": {"content": "Use upstream Hermes, not my old fork."}
  }'
```

### Request actionable context

```bash
curl -X POST http://localhost:8000/v1/context \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "00000000-0000-0000-0000-000000000000",
    "max_items": 20,
    "token_budget": 1600
  }'
```

A context packet contains selected current state rather than raw transcript fragments. Items carry trust labels such as `user_confirmed`, `tool_observed`, `curated_memory`, `inferred`, `stale`, or `contradicted`.

## Hermes integration

The repository now contains the Open Brain side of the Hermes integration:

- identity resolution;
- session establishment and lineage;
- event ingestion;
- Hermes built-in-memory bootstrap import;
- session, skill, context, and cron discovery;
- actionable context packets;
- feedback contracts.

The native upstream-compatible Hermes `OpenBrainMemoryProvider` remains the next integration slice. Until it lands in upstream Hermes, Hermes can call Open Brain through REST or MCP. Open Brain remains usable by any other agent through the same interfaces.

The intended provider lifecycle is:

```text
initialize
prefetch / queue_prefetch
sync_turn
on_memory_write
on_session_switch
on_pre_compress
on_delegation
on_session_end
shutdown
```

Open Brain must never prevent Hermes from responding. If the service is unavailable, the provider will fall back to its last cached context and spool writes locally for later replay.

## Bootstrap import from Hermes

The import layer recognizes these source classes:

- `hermes.user_memory` — `USER.md`;
- `hermes.agent_memory` — `MEMORY.md`;
- `hermes.context` — explicitly allowlisted context files;
- `hermes.session` — summaries preferred over transcripts;
- `hermes.skill` — procedural candidates requiring evaluation;
- `hermes.cron` — structured automation candidates, still executed by Hermes;
- external memory providers — normalized through provider adapters.

Imports support dry-run and safe resume. A changed source fingerprint requires a new import run rather than silently resuming against different data.

## Memory lifecycle

The target lifecycle is:

```text
candidate → active → confirmed
                     ├→ superseded
                     ├→ contradicted
                     ├→ dormant
                     └→ archived → tombstoned → deleted
```

Open Brain prunes retrieval before storage. Old evidence may leave hot retrieval while remaining available for history, provenance, audit, and reconciliation. User-authored information is not automatically physically deleted.

## Security and authority

Authority is explicit. Typical ordering is:

1. direct user statement;
2. user-curated memory;
3. tool observation;
4. provider inference;
5. Open Brain inference;
6. assistant claim.

Sensitive records can carry sensitivity and retention classifications. Imported provider inference must remain distinguishable from user-confirmed truth.

The installer should be reviewed before execution in high-security environments. For reproducible deployment, pin installation to a reviewed release tag rather than `master`.

## Development and validation

```bash
pip install -e '.[dev]'
python scripts/migrate.py
pytest -q
python -m build
```

GitHub Actions validates:

- installation;
- PostgreSQL and pgvector migrations;
- tests;
- wheel creation;
- installed CLI smoke tests.

## Project structure

```text
src/
├── api/             REST endpoints
├── cli/             command-line interface
├── continuity/      event, identity, and session contracts
├── context/         actionable context models and packet builder
├── db/              persistence, migrations, and queries
├── importers/       Hermes and provider import adapters
├── analytics/       trends and reports
├── connectors/      existing source connectors
├── extractors/      entities and tagging
└── notifications/   notification integrations
```

## Status

Open Brain is alpha software. The continuity foundation and bootstrap/context contracts are implemented on the active integration work, while database concurrency tests, provider-specific normalization, staged-import rollback metadata, and the native Hermes provider still require completion and validation before a stable release.

## License

MIT.
