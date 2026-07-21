# Open Brain

> A model-independent personal memory and agent-continuity service. Open Brain preserves evidence, projects, tasks, decisions, outcomes, and long-term learning so different agents and interfaces can continue the same work.

[![Verify](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml/badge.svg)](https://github.com/benclawbot/open-brain/actions/workflows/verify.yml)
[![License](https://img.shields.io/github/license/benclawbot/open-brain)](LICENSE)

## What Open Brain does

Open Brain is the durable knowledge layer behind AI agents. Agents remain responsible for reasoning, tools, browser or computer use, and execution. Open Brain is responsible for continuity and accumulated understanding.

It provides:

- semantic memory storage and hybrid search with PostgreSQL and pgvector;
- automatic tagging, entity extraction, trends, reports, REST, MCP, CLI, and dashboard interfaces;
- canonical user, agent, workspace, project, task, and session identities;
- cross-interface identity links for CLI, Telegram, Slack, Discord, and other gateways;
- append-only, provenance-aware events with idempotent ingestion;
- session lineage for new, reset, resume, branch, compression, and rewind transitions;
- structured assertions with supporting, contradicting, qualifying, and superseding evidence;
- first-class decisions, outcomes, import runs, and context revisions;
- safe bootstrap import of Hermes `USER.md`, `MEMORY.md`, explicitly allowlisted context files, session summaries or transcripts, skills, and cron jobs;
- resumable imports with dry-run mode, source hashes, checkpoints, duplicate suppression, and an audit ledger;
- compact actionable context packets containing current project state, tasks, decisions, assertions, outcomes, blockers, and next actions;
- trust and freshness labels, token budgets, item budgets, and retrieval feedback;
- a native upstream-compatible Hermes memory provider;
- local write spooling and cached recall when Open Brain is temporarily unavailable;
- checksum-protected additive database migrations;
- a one-line installer and `openbrain update` command.

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

Open Brain separates:

1. **Canonical evidence** — append-only events, imported records, sessions, tool results, and artifacts.
2. **Knowledge model** — current assertions, projects, tasks, decisions, procedures, and outcomes.
3. **Retrieval projections** — embeddings, indexes, revisions, caches, and compact context packets that can be rebuilt safely.

The Hermes design and implementation ledger are stored in:

- [`docs/HERMES_INTEGRATION_ARCHITECTURE.md`](docs/HERMES_INTEGRATION_ARCHITECTURE.md)
- [`docs/HERMES_INTEGRATION_PROGRESS.md`](docs/HERMES_INTEGRATION_PROGRESS.md)

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

Install Open Brain, then install its native Hermes provider:

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

The provider is installed into:

```text
$HERMES_HOME/plugins/openbrain
```

It implements:

```text
initialize
system_prompt_block
prefetch / queue_prefetch
sync_turn
openbrain_recall
openbrain_remember
on_memory_write
on_session_switch
on_pre_compress
on_delegation
on_session_end
shutdown
```

If Open Brain is unavailable, Hermes continues operating. Writes are appended to `$HERMES_HOME/openbrain-spool.jsonl` and replayed later.

### Install through another coding agent

Give Claude Code, Codex, Medusa, OpenCode, or another shell-capable agent this instruction:

```text
Install Open Brain from https://github.com/benclawbot/open-brain using the repository's official install.sh script. Review the script first. After installation, run `openbrain --version`. If this is Hermes, also run `openbrain install-hermes`, set OPENBRAIN_URL, and configure the openbrain memory provider. Report failed steps without deleting existing data.
```

Or execute directly:

```bash
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
openbrain --version
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

The updater:

1. upgrades the pipx-managed package;
2. loads migrations from the installed package;
3. verifies migration checksums;
4. applies only migrations that have not run before;
5. leaves existing data intact if migration execution fails.

Upgrade without database changes:

```bash
openbrain update --skip-migrations
```

Refresh an existing Hermes provider copy after upgrading Open Brain:

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

Apply migrations:

```bash
python scripts/migrate.py
```

Start the complete local stack:

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
openbrain install-hermes
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

Context packets contain selected current state rather than raw transcript fragments. Items carry trust labels such as `user_confirmed`, `tool_observed`, `curated_memory`, `inferred`, `stale`, or `contradicted`.

## Hermes bootstrap import

The import layer recognizes:

- `hermes.user_memory` — `USER.md`;
- `hermes.agent_memory` — `MEMORY.md`;
- `hermes.context` — explicitly allowlisted context files;
- `hermes.session` — summaries preferred over transcripts;
- `hermes.skill` — procedural candidates requiring evaluation;
- `hermes.cron` — structured automation candidates, still executed by Hermes;
- external memory providers — normalized through provider adapters.

Imports support dry-run and safe resume. A changed source fingerprint requires a new import run.

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
- tests;
- wheel creation;
- installed CLI execution;
- native Hermes provider copying.

## Project structure

```text
src/
├── api/                       REST endpoints
├── cli/                       command-line interface
├── continuity/                event, identity, and session contracts
├── context/                   actionable context and packet builder
├── db/                        persistence, migrations, and queries
├── importers/                 Hermes and provider import adapters
├── openbrain_hermes_plugin/   standalone Hermes memory provider
├── analytics/                 trends and reports
├── connectors/                source connectors
├── extractors/                entities and tagging
└── notifications/             notification integrations
```

## Status

Open Brain 0.2 is alpha software. The continuity foundation, Hermes bootstrap imports, actionable context APIs, native Hermes provider, installer, updater, and packaging path are implemented. Remaining maturity work includes broader database concurrency coverage, provider-specific normalization, staged-import rollback metadata, lifecycle automation, and self-improvement proposals.

## License

MIT.
