# Installation and updates

## One-line install

```sh
curl -fsSL https://raw.githubusercontent.com/benclawbot/open-brain/master/install.sh | sh
```

The installer verifies Python 3.11+, installs or upgrades Open Brain through `pipx`, detects Hermes, installs the bundled Hermes provider when Hermes is present, and runs `openbrain doctor`.

Set `OPENBRAIN_INSTALL_HERMES=0` to skip automatic Hermes wiring. Set `OPENBRAIN_REPO_URL` to install from a fork.

## Hermes

Automatic installation copies the packaged provider into `${HERMES_HOME:-~/.hermes}/plugins/openbrain`. Manual repair is available with:

```sh
openbrain install-hermes --force
```

Then set `OPENBRAIN_URL` and select `openbrain` from `hermes memory setup`.

## Other coding agents

Open Brain exposes an HTTP API and MCP-compatible server surfaces. For agents without a native provider:

1. Start Open Brain with `openbrain serve`.
2. Set `OPENBRAIN_URL` to the service URL.
3. Configure the agent to call the context, event ingestion, and feedback endpoints, or connect through the repository's MCP integration.
4. Run `openbrain doctor --json` in provisioning checks.

Agent-specific adapters should remain thin: identity and task scope go into Open Brain requests; durable memory policy remains server-side.

## Updates

```sh
openbrain version-check
openbrain update
```

`version-check` is offline-safe. `update` upgrades the pipx installation and applies additive migrations. When package upgrade succeeds but migration fails, it exits non-zero and reports that existing data was not deleted.

## Diagnostics

```sh
openbrain doctor
openbrain doctor --json
```

The command reports Python, pipx, Hermes, Hermes provider, database configuration, service URL, and installed version readiness.
