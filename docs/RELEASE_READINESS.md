# Release readiness gate

Run the release gate from the exact artifact and environment intended for production:

```bash
openbrain-release-check
```

The command prints a JSON report and exits with status `0` only when every automatic check and operator attestation passes. A failed or missing check exits with status `1`.

## Automatic checks

The gate verifies:

- `OPENBRAIN_ENV` is `production` or `prod`;
- `OPENBRAIN_AUTH_REQUIRED` is enabled;
- `OPENBRAIN_API_KEY` is not a known placeholder and contains at least 32 characters;
- `OPENBRAIN_CORS_ORIGINS` is a non-empty explicit allow-list without `*`.

## Operator attestations

Operational controls cannot be proven safely from application configuration alone. Set each variable only after verifying the corresponding control:

```env
OPENBRAIN_ATTEST_TLS=true
OPENBRAIN_ATTEST_BACKUP_VERIFIED=true
OPENBRAIN_ATTEST_RESTORE_DRILL=true
OPENBRAIN_ATTEST_MONITORING=true
OPENBRAIN_ATTEST_MIGRATIONS_RECORDED=true
```

These attest that:

- maintained TLS termination is active;
- a current encrypted backup exists and is readable;
- the documented isolated restore drill completed successfully;
- readiness, latency, and error monitoring is active;
- the release version and migration checksum state were recorded.

Attestations are intentionally explicit. The command never guesses that infrastructure controls exist and never treats a configured backup destination as proof that a usable backup or restore drill exists.

## Example

```bash
export OPENBRAIN_ENV=production
export OPENBRAIN_AUTH_REQUIRED=true
export OPENBRAIN_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export OPENBRAIN_CORS_ORIGINS=https://brain.example.com
export OPENBRAIN_ATTEST_TLS=true
export OPENBRAIN_ATTEST_BACKUP_VERIFIED=true
export OPENBRAIN_ATTEST_RESTORE_DRILL=true
export OPENBRAIN_ATTEST_MONITORING=true
export OPENBRAIN_ATTEST_MIGRATIONS_RECORDED=true

openbrain-release-check
```

Preserve the JSON output with the deployment record. A successful report is necessary but does not replace the production deployment runbook or post-deployment read/write smoke test.
