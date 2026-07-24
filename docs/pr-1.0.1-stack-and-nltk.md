# PR: make the local stack work end-to-end + NLTK fix

> If you are reading this on a PR, the commits in this branch are
> `010ded5` (docker stack + one-line install) and `b05f502` (NLTK fix).
> The e2e test in `tests/e2e/test_api.py` and this file are added on top.

## Summary

The `1.0.0` release of Open Brain shipped with a docker-compose stack and
a CLI installer that, in practice, did not work end-to-end on a fresh
clone. The api container failed to start, the schema setup ignored the
container's runtime env vars, the `get_memory_by_id` endpoint crashed on
UUID parameters, and entity extraction silently fell through. NLTK had
also been renamed in 3.8.2+ and the runtime data files were never
baked into the image. This PR fixes the stack, ships a one-line
installer, and includes an e2e test suite that exercises every route in
the OpenAPI schema (39 steps, all green).

## What's in here

### Bug fixes (in order of how much they hurt a fresh install)

* `scripts/startup.sh`, `scripts/backup.sh`, `scripts/healthcheck.sh`, `install.sh`
  were committed with CRLF line endings. On Linux the kernel tried to
  exec `/bin/bash\r` as the interpreter path, so every shell script in
  the project failed with "required file not found". The api container
  could not start at all. A new `.gitattributes` pins `*.sh` as
  `text eol=lf` so Windows checkouts stop reintroducing the CRLF.

* `scripts/setup_db.py` did not honour `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`
  env vars. Without this, the api container tried to connect to
  `localhost:5433` instead of the compose-internal `postgres:5432`.
  Now matches the pattern `check_db.py` already used.

* `scripts/startup.sh` did not call `scripts/migrate.py`. The README
  always claimed the api applies pending migrations on startup; only
  the CLI did. The new migration `015_embedding_dim_change.sql`
  therefore would not apply on a fresh deployment. Now fixed.

* `src/db/connection.py` did not register the psycopg2 UUID adapter.
  Any query binding a `uuid.UUID` parameter (e.g. `GET /memories/{id}`)
  raised `ProgrammingError: can't adapt type 'UUID'`.

* `src/extractors/entities.py` only looked for the old NLTK 3.7 resource
  names (`punkt`, `averaged_perceptron_tagger`, `maxent_ne_chunker`).
  NLTK 3.8.2+ renamed them (`punkt_tab`, `averaged_perceptron_tagger_eng`,
  `maxent_ne_chunker_tab`), so entity extraction silently fell through
  to the bare exception handler. Now looks for the new names first and
  falls back to the old ones.

### Stack changes

* `docker-compose.yml` adds an `ollama` service running
  `nomic-embed-text` (274 MB, 768-dim). The api `depends_on` it.
  Embeddings are now local; no external API key required. The
  OpenRouter key on the previous 1.0.0 .env was being rejected with
  HTTP 401 "User not found" on real installs.

* Default API host port changed from `8000` to `8765`. The Windows
  IP Helper service (`iphlpsvc`) often holds port 8000, which prevents
  the api container from binding on Windows hosts. Override with
  `API_PORT` in `.env` if you need a different port.

* `src/db/schema.sql`: `embedding vector(1536)` → `vector(768)` to
  match the default embedder. New migration alters the column on
  existing databases and rebuilds the HNSW index.

* `Dockerfile` pre-downloads NLTK data into the image so entity
  extraction works on cold starts with no network round-trip.

### One-line install

* `scripts/quickstart.sh` brings up the docker stack, waits for the
  api to become healthy, ensures the embedding model is available,
  and (with `--with-hermes`) wires Open Brain into a locally-installed
  Hermes as the active memory provider. Idempotent.

  ```
  git clone https://github.com/benclawbot/open-brain.git
  cd open-brain
  bash scripts/quickstart.sh --with-hermes
  ```

### Repository hygiene

* `.gitignore` now excludes `.env`. `.env.example` is the single
  source of truth for non-secret defaults.
* The previously-checked-in `.env` (which contained real OpenRouter
  credentials, now invalidated) was removed from the index via
  `git rm --cached .env`. The history of that file still contains the
  old key; rewriting history is out of scope for this PR and the key
  no longer works against the OpenRouter API (HTTP 401).

## Verification

A new e2e test suite at `tests/e2e/test_api.py` exercises every
category of route documented in the OpenAPI schema. The current run:

```
=== 1. Health and root === 5/5
=== 2. Memory CRUD === 8/8  (NER: people=['Ben Clawbot'], locations=['Brain','Paris'], orgs=['Acme Corp','PostgreSQL'])
=== 3. Analytics === 3/3
=== 4. Continuity === 6/6
=== 5. Context === 4/4
=== 6. Review workflows === 7/7
=== 7. Maintenance === 2/2
=== 8. Imports === 5/5
=== 9. Auth === 3/3
```

`pytest tests/e2e/ -v` reports 10/10 passing. `python tests/e2e/test_api.py`
runs the same suite standalone without pytest and exits non-zero on
any failure. The suite auto-skips when the api is not reachable, so
the rest of `pytest tests/` (the unit suite) still passes in CI
without a running stack.

## Migration notes for operators

Operators on a previous 1.0.0 install will need to:

1. `git pull`
2. Recreate `.env` from the new `.env.example` (since `.env` is no
   longer tracked). The api key in `~/.config/openbrain/.env` is
   preserved across `openbrain configure --project-root .` runs.
3. `docker compose down` then `docker compose up -d --build` (the
   new image bakes the NLTK data and adds the ollama service).
4. The new migration `015_embedding_dim_change.sql` alters the
   `memory.embedding` column to `vector(768)`. The HNSW index is
   rebuilt as part of the migration. Existing embeddings stored at
   1536 dimensions will need to be regenerated; the migration drops
   the prior index but does not attempt to convert the column.

## Risk

* Touched files: scripts/*.sh, src/db/{connection,schema}.py/sql,
  config/settings.yaml, docker-compose.yml, Dockerfile,
  .env.example, .gitignore, .gitattributes, README.md, CHANGELOG.md.
* All changes are inside the project repo; no system files modified.
* Existing data: 3 stored memories on my dev install (no embeddings,
  since the OpenRouter key was already broken). Migration 015 alters
  the column type and rebuilds the HNSW index — safe because the
  embeddings are NULL, but if you restore a backup with 1536-dim
  vectors stored, the migration would fail and you'd need a different
  recovery path.
* Rollback: `git revert b05f502^..b05f502` (this PR), or
  `git checkout 946f5ce` to drop the docker stack changes too.
  Reverting the schema migration requires `ALTER TABLE memory
  ALTER COLUMN embedding TYPE vector(1536)` and re-running any
  embedding jobs.

## Known follow-ups not in this PR

* NLTK `punkt_tab` data is baked in, but `nltk.downloader -d
  /usr/local/share/nltk_data` prints noisy downloader banners to
  the build log. The banner is one line; not worth a `--no-deprecated`
  flag hunt for this PR.
* The OpenRouter API key is still in the index of an early commit
  (long-since invalidated by OpenRouter, but a real scrub with
  `git filter-repo` would clean it up for hygiene).
* The README still describes the standalone pipx install as the
  primary path. The docker stack is now the recommended path. A small
  docs pass to flip the ordering would be welcome.
* The Streamlit dashboard at `:8501` is not yet covered by the e2e
  test (urllib + FastAPI JSON is the natural shape; Streamlit's
  HTML-rendered state is harder to assert against). Manual smoke is
  sufficient for the dashboard; a Playwright check would be a
  separate PR.
