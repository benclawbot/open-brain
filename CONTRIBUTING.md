# Contributing to Open Brain

Open Brain handles sensitive memory. Contributions must preserve provenance, authority boundaries and a safe default installation.

## First development run

1. Use Python 3.11+ and Docker. Read [SECURITY](docs/SECURITY.md).
2. Clone the repository and install editable development dependencies:
   ```bash
   python -m pip install -e '.[dev]'
   ```
3. Start local services using `bash scripts/quickstart.sh`, then run:
   ```bash
   python scripts/migrate.py
   pytest -q
   ruff check src scripts tests --select E9,F401,F541,F63,F7,F82,E722,F841
   python -m build
   ```
4. Open a small PR explaining behavior changes, migration impact and tests.

## Contributor contracts

- Never commit real API keys, local `.env`, user memories, dumps, personal exports or production logs.
- Treat imported data and LLM inferences as *untrusted claims*, not canonical user facts. Preserve source attribution and immutable audit history.
- Add a **new** versioned SQL migration; never rewrite already applied migrations.
- Favor additive, reversible changes to the event/identity/knowledge model. Describe schema and API compatibility in the PR.
- Keep deployment interfaces loopback-bound by default and test explicit authentication controls.
- Include tests for both expected behavior and malformed/untrusted input. Run the existing provider-conformance suite when touching adapters.
- Do not push release tags or publish images as part of routine code changes.

## Useful guides

- [Five-minute memory example](docs/EXAMPLE-MEMORY-FLOW.md)
- [Backup/restore drill](docs/BACKUP-RESTORE.md)
- [Production readiness](docs/RELEASE_READINESS.md)
- [Architecture](docs/ARCHITECTURE.md)
