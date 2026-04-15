# AGENTS.md

## Project Context
See PROJECT_INDEX.md for architecture, conventions, and structure — read it before modifying code.

## Working Rules
- Make minimal, targeted changes.
- Verify with runnable checks (API health + memory create/search).
- Keep schema, config, and runtime behavior consistent.
- If changing startup/infra scripts, test fresh-container behavior (`docker compose up -d --build`).
