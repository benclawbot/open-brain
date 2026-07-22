# Coding-agent host wiring

Open Brain uses one shared host configuration path for Medusa, Codex, and Claude Code.

## Runtime configuration

Configure the Open Brain service URL, authentication token, and timeout in the host environment:

```bash
export OPENBRAIN_URL=https://brain.example.com
export OPENBRAIN_API_KEY=<your-api-key>
export OPENBRAIN_TIMEOUT=5
```

Every provider request carries the configured authorization header, provider identity, capture-agent identity, and a matching `captured_by` event field. This keeps transport and author attribution distinct while allowing all agents to share one Open Brain deployment.

## Install

```bash
openbrain-adapters install medusa
openbrain-adapters install codex
openbrain-adapters install claude
```

Host files are written beneath `~/.config/openbrain/hosts/` with mode `0600`. Existing files are preserved unless `--overwrite` is supplied.

## Diagnose

```bash
openbrain-adapters doctor codex
```

The command checks both `/health` and database-backed `/ready`, returning a non-zero exit status when the deployment is not ready.

## Status and uninstall

```bash
openbrain-adapters status medusa
openbrain-adapters uninstall medusa
```

The command does not edit undocumented host internals. Host wrappers load the generated environment file before constructing the native adapter or invoking the Open Brain REST contract.
