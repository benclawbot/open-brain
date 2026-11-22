# PostgreSQL backup and isolated restore drill

Open Brain stores canonical events, identities, knowledge, migrations and projections in PostgreSQL/pgvector. A Docker volume is **not** itself a validated backup.

## Backup (local compose stack)

Run from a trusted checkout with the compose stack healthy:

```bash
umask 077
docker compose exec -T postgres pg_dump -U postgres -d openbrain -Fc > openbrain-backup.dump
ls -lh openbrain-backup.dump
```

The dump contains private memories and possibly credentials or personal data. Protect it as sensitive material, keep it out of Git, encrypt off-host copies, and define retention/deletion policies.

## Isolated restore test

Do **not** restore over a live Open Brain database. Restore to a disposable, isolated PostgreSQL+pgvector instance or a new database and validate read-only queries first:

```bash
# In a dedicated TEST compose stack / postgres instance:
docker compose exec -T postgres createdb -U postgres openbrain_restore_drill
docker compose exec -T postgres pg_restore -U postgres --no-owner --no-acl \
  -d openbrain_restore_drill < openbrain-backup.dump
docker compose exec -T postgres psql -U postgres -d openbrain_restore_drill \
  -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
```

Ensure the target has the required PostgreSQL and pgvector versions. Validate expected migration entries, count representative tables, and run read-only API queries against the isolated instance. Then securely dispose of the disposable database according to your retention policy.

A completed restore drill is one of the operator controls required by `openbrain-release-check`. Document the drill date, artifact digest, environment, verification steps and responsible operator. Do not claim production readiness based only on having a dump.
