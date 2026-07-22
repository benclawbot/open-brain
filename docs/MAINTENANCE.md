# Automated maintenance

Open Brain exposes one bounded maintenance workflow through both the CLI and API.

```bash
# Safe default: inspect only
openbrain maintenance

# Persist proposal generation, cache cleanup, and scoped compaction
openbrain maintenance --apply --project-id PROJECT_UUID
```

API equivalent:

```http
POST /v1/maintenance/run
```

## Steps

1. Generate assertion-consolidation proposals.
2. Generate assertion-pruning proposals.
3. Clean expired and overflow context-cache entries.
4. Report active tombstones beyond the configured retention period.
5. Compact a supplied project or task scope.

## Safety properties

- Dry-run is the default.
- Every limit is validated before execution.
- Each step is independently isolated; one failure does not stop later steps.
- Tombstone retention is report-only and never silently deletes reversible history.
- Compaction remains scoped and provenance-preserving.
- The result is a machine-readable audit report containing options, timings, status, results, and errors.

The command is suitable for cron or another scheduler because it exits non-zero when any isolated step fails while still emitting the complete report.
