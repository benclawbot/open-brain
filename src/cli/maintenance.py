"""CLI adapter for maintenance orchestration."""

from __future__ import annotations

import json
from uuid import UUID

from ..maintenance import MaintenanceOptions, run_maintenance


def maintenance_cmd(args) -> int:
    options = MaintenanceOptions(
        dry_run=not args.apply,
        proposal_limit=args.proposal_limit,
        cache_max_rows=args.cache_max_rows,
        tombstone_retention_days=args.tombstone_retention_days,
        compact_project_id=UUID(args.project_id) if args.project_id else None,
        compact_task_id=UUID(args.task_id) if args.task_id else None,
        compaction_min_events=args.compaction_min_events,
        compaction_max_events=args.compaction_max_events,
    )
    report = run_maintenance(options)
    print(json.dumps(report, indent=2, default=str))
    return 1 if report["summary"]["failed"] else 0
