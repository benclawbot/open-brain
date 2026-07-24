# Open Brain memory provider for Hermes

This standalone plugin connects upstream `NousResearch/hermes-agent` to an Open Brain REST service.

Install from the Open Brain CLI:

```bash
openbrain install-hermes
```

Then configure Hermes:

```bash
hermes memory setup
```

The OpenBrain installer generates and loads the local URL and API key automatically. Explicit `OPENBRAIN_URL` and `OPENBRAIN_API_KEY` environment variables can override them for remote deployments.

Select `openbrain` as the active provider when prompted, or set `memory.provider: openbrain` in the active Hermes configuration.

Optional scope variables:

```bash
export OPENBRAIN_PROJECT_ID=<uuid>
export OPENBRAIN_TASK_ID=<uuid>
export OPENBRAIN_TIMEOUT=3
```

The provider supplies:

- cached semantic and structured prefetch;
- non-blocking turn synchronization;
- session reset/resume/branch/compression/rewind lineage;
- mirroring of curated `USER.md` and `MEMORY.md` writes;
- delegation and session-boundary events;
- `openbrain_recall` and `openbrain_remember` tools;
- a local JSONL spool when Open Brain is unavailable.

The spool lives at `$HERMES_HOME/openbrain-spool.jsonl` and is replayed after connectivity returns.
