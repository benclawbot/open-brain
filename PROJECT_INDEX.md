# Project Index

## What this is
Open Brain is a personal semantic memory system: it stores notes/messages as embeddings in PostgreSQL+pgvector and exposes retrieval via REST API, dashboard, and MCP-oriented tooling.

## Structure
- config/ — runtime settings (provider/model/ports)
- src/api/ — FastAPI endpoints
- src/db/ — schema, connection, queries
- src/embedder/ — embedding provider adapters (OpenRouter/OpenAI/Ollama/custom)
- src/extractors/ — entity extraction and auto-tagging
- src/analytics/ — trends and weekly report generation
- ui/ — Streamlit dashboard
- scripts/ — startup/check/setup utilities
- tests/ — core tests
- docker-compose.yml — postgres + api + dashboard stack

## Architecture
- PostgreSQL + pgvector is the source of truth for memory records and semantic similarity.
- API layer enriches content (entities/tags + embeddings) before insert.
- Search combines semantic ranking (vector distance) with optional filters.
- Docker startup path initializes DB schema automatically when needed.

## Conventions
- Prefer config-driven behavior via config/settings.yaml and env vars.
- Keep DB schema and embedder dimensions aligned (currently 1536 for text-embedding-3-small).
- Keep startup scripts idempotent and safe under `set -e`.
- Validate API response models against actual DB return types.

## Anti-patterns to avoid
- Do not use vector distance expressions as boolean WHERE predicates.
- Do not hardcode embedding dimensions inconsistently across schema/config/runtime.
- Do not rely on non-zero shell exit codes without explicit handling under `set -e`.

## Key files
- src/api/main.py — API models and endpoints.
- src/db/queries.py — insert/search SQL behavior.
- src/db/schema.sql — table definition and pgvector shape.
- src/embedder/__init__.py — provider-specific embedding behavior.
- scripts/startup.sh — container boot and DB setup flow.
- docker-compose.yml — service wiring and health checks.
