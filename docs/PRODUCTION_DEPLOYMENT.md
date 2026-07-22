# Production deployment

This runbook describes the minimum safe baseline for exposing Open Brain outside a trusted local machine.

## Required configuration

Set these values through a secret manager or protected environment file:

```env
OPENBRAIN_ENV=production
OPENBRAIN_API_KEY=<long random secret>
OPENBRAIN_AUTH_REQUIRED=true
DB_PASSWORD=<database secret>
```

Production mode enables authentication by default and refuses to construct the API when no API key is configured. Clients may send either:

```http
Authorization: Bearer <key>
```

or:

```http
X-API-Key: <key>
```

The root and health probes remain unauthenticated so infrastructure can monitor the service. All memory, continuity, analytics, and documentation routes are protected.

## Reverse proxy and TLS

Do not expose Uvicorn directly to the public internet. Terminate TLS at a maintained reverse proxy or managed ingress, then forward to Open Brain over a private network.

Recommended proxy controls:

- TLS 1.2 or newer;
- HTTP-to-HTTPS redirect;
- a request-body limit no larger than `OPENBRAIN_MAX_REQUEST_BYTES`;
- connection and upstream timeouts;
- access logs with secret-bearing headers redacted;
- an IP or identity allow-list where practical.

Set `OPENBRAIN_TRUST_PROXY_HEADERS=true` only when every request reaches Open Brain through a trusted proxy that overwrites `X-Forwarded-For`. Leaving it false prevents clients from spoofing rate-limit identities.

## CORS

Set an explicit comma-separated allow-list:

```env
OPENBRAIN_CORS_ORIGINS=https://brain.example.com
```

Never use a wildcard origin with credentialed browser access.

## Probes

- `GET /health/live` verifies that the process and event loop respond.
- `GET /health/ready` verifies database initialization and executes `SELECT 1`.

Use liveness only to restart a stuck process. Use readiness to decide whether the instance should receive traffic.

## Request limits and rate limiting

Defaults:

```env
OPENBRAIN_MAX_REQUEST_BYTES=1048576
OPENBRAIN_RATE_LIMIT_REQUESTS=120
OPENBRAIN_RATE_LIMIT_WINDOW_SECONDS=60
```

The built-in limiter protects a single process. Multi-process or horizontally scaled deployments should also enforce a shared limit at the ingress or API gateway.

## Logging

Each response includes `X-Request-ID`. Request logs are emitted as structured JSON with method, path, status, duration, and a one-way client identifier hash. API keys and request bodies are not logged.

Forward logs to durable storage and alert on:

- readiness failures;
- repeated 401, 413, or 429 responses;
- database connection exhaustion;
- migration failures;
- sustained elevated latency or 5xx rates.

## Backup policy

Use PostgreSQL-native backups. A minimum baseline is:

1. nightly encrypted logical or physical backups;
2. point-in-time recovery when the deployment tier supports it;
3. retention across at least two independent failure windows;
4. a separate storage account or host;
5. quarterly restore drills.

Before every application upgrade:

1. record the deployed Open Brain version and migration checksum state;
2. take a database backup or storage snapshot;
3. verify that the backup is readable;
4. apply migrations before shifting traffic;
5. confirm `/health/ready` and a read/write smoke test.

## Restore drill

Restore into an isolated database first. Do not overwrite the active database during validation.

1. provision a clean PostgreSQL instance with the required extensions;
2. restore the selected backup;
3. install the exact Open Brain release that created or last migrated it;
4. run `python scripts/migrate.py` to apply only newer additive migrations;
5. start the API and verify readiness;
6. search known memories and store a disposable test memory;
7. compare row counts and migration receipts with the source environment;
8. destroy the isolated instance or promote it through an explicit recovery decision.

## Upgrade and rollback

Application rollback is safe only when the older version understands the current additive schema. Never edit or delete an already-applied migration.

If migration execution fails, keep the previous application version serving against the unchanged database, inspect the migration error, and restore from backup only when the database was modified outside a transaction or validation detects corruption.

## Deployment checklist

- [ ] production mode enabled
- [ ] API key stored outside source control
- [ ] TLS termination configured
- [ ] explicit CORS origins configured
- [ ] trusted proxy headers disabled unless the proxy is controlled
- [ ] ingress and application request limits aligned
- [ ] liveness and readiness probes configured
- [ ] logs and alerts configured
- [ ] encrypted backups scheduled
- [ ] restore drill completed
- [ ] release version and migration state recorded
