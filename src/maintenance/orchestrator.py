"""Run bounded maintenance steps with dry-run and failure isolation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import UUID, uuid4

try:
    from ..compaction.engine import CompactionPolicy, compact_scope
    from ..context.cache import cleanup_context_cache, context_cache_stats
    from ..db.connection import get_db_cursor
    from ..db.consolidation_queries import generate_consolidation_proposals
    from ..db.pruning_queries import generate_pruning_proposals
except ImportError:
    from compaction.engine import CompactionPolicy, compact_scope
    from context.cache import cleanup_context_cache, context_cache_stats
    from db.connection import get_db_cursor
    from db.consolidation_queries import generate_consolidation_proposals
    from db.pruning_queries import generate_pruning_proposals


@dataclass(frozen=True)
class MaintenanceOptions:
    dry_run: bool = True
    proposal_limit: int = 500
    cache_max_rows: int = 5000
    tombstone_retention_days: int = 90
    compact_project_id: UUID | None = None
    compact_task_id: UUID | None = None
    compaction_min_events: int = 8
    compaction_max_events: int = 200

    def validate(self) -> None:
        if not 1 <= self.proposal_limit <= 2000:
            raise ValueError("proposal_limit must be between 1 and 2000")
        if self.cache_max_rows < 1:
            raise ValueError("cache_max_rows must be positive")
        if self.tombstone_retention_days < 1:
            raise ValueError("tombstone_retention_days must be positive")
        if not 2 <= self.compaction_min_events <= self.compaction_max_events <= 2000:
            raise ValueError("invalid compaction event limits")


def _tombstone_retention_report(days: int) -> dict[str, int]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE reversed_at IS NULL) AS active,
                   COUNT(*) FILTER (
                       WHERE reversed_at IS NULL
                         AND created_at < NOW() - (%s * INTERVAL '1 day')
                   ) AS past_retention
            FROM assertion_tombstones
            """,
            (days,),
        )
        row = cursor.fetchone()
    return {"active": int(row["active"]), "past_retention": int(row["past_retention"])}


def _run_step(name: str, operation: Callable[[], Any]) -> dict[str, Any]:
    started = perf_counter()
    try:
        result = operation()
        return {
            "name": name,
            "status": "succeeded",
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "result": result,
        }
    except Exception as exc:  # Failure isolation is a product requirement.
        return {
            "name": name,
            "status": "failed",
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_maintenance(options: MaintenanceOptions) -> dict[str, Any]:
    """Run all maintenance checks and return a complete auditable report."""
    options.validate()
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    steps: list[dict[str, Any]] = []

    steps.append(
        _run_step(
            "consolidation_proposals",
            lambda: {
                "would_generate": options.dry_run,
                "created": 0 if options.dry_run else len(
                    generate_consolidation_proposals(limit=options.proposal_limit, minimum_score=0.5)
                ),
            },
        )
    )
    steps.append(
        _run_step(
            "pruning_proposals",
            lambda: {
                "would_generate": options.dry_run,
                "created": 0 if options.dry_run else len(
                    generate_pruning_proposals(limit=options.proposal_limit)
                ),
            },
        )
    )
    steps.append(
        _run_step(
            "cache_cleanup",
            lambda: {
                "before": context_cache_stats(),
                "cleanup": {"dry_run": True} if options.dry_run else cleanup_context_cache(
                    max_rows=options.cache_max_rows
                ),
            },
        )
    )
    steps.append(
        _run_step(
            "tombstone_retention",
            lambda: {
                "retention_days": options.tombstone_retention_days,
                **_tombstone_retention_report(options.tombstone_retention_days),
                "action": "report_only",
            },
        )
    )

    if options.compact_project_id or options.compact_task_id:
        policy = CompactionPolicy(
            minimum_events=options.compaction_min_events,
            maximum_events=options.compaction_max_events,
        )
        steps.append(
            _run_step(
                "compaction",
                lambda: compact_scope(
                    project_id=options.compact_project_id,
                    task_id=options.compact_task_id,
                    policy=policy,
                    dry_run=options.dry_run,
                ),
            )
        )
    else:
        steps.append({
            "name": "compaction",
            "status": "skipped",
            "duration_ms": 0,
            "result": {"reason": "no project_id or task_id supplied"},
        })

    failed = sum(step["status"] == "failed" for step in steps)
    return {
        "run_id": str(run_id),
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": options.dry_run,
        "options": {
            **asdict(options),
            "compact_project_id": str(options.compact_project_id) if options.compact_project_id else None,
            "compact_task_id": str(options.compact_task_id) if options.compact_task_id else None,
        },
        "summary": {
            "steps": len(steps),
            "succeeded": sum(step["status"] == "succeeded" for step in steps),
            "failed": failed,
            "skipped": sum(step["status"] == "skipped" for step in steps),
        },
        "status": "completed_with_failures" if failed else "completed",
        "steps": steps,
    }
