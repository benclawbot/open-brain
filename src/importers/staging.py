"""Validation and sealing controls for staged import runs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from ..db.connection import get_db_cursor


def seal_import_run(run_id: UUID, *, actor: str, expected_records: int | None = None) -> dict[str, Any]:
    """Seal a completed staging run after validating its immutable candidate set.

    Sealing is a deliberate operator boundary between discovery and promotion. A
    sealed run cannot accept further candidates or be resumed.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM import_run WHERE id = %s FOR UPDATE", (run_id,))
        run = cursor.fetchone()
        if run is None:
            raise ValueError(f"import run not found: {run_id}")

        config = run.get("config") or {}
        if isinstance(config, str):
            config = json.loads(config)
        if bool(config.get("dry_run")):
            raise ValueError("dry-run imports cannot be sealed")
        if run.get("rolled_back_at") is not None or run.get("status") == "rolled_back":
            raise ValueError("rolled-back imports cannot be sealed")
        if run.get("status") == "sealed":
            return dict(run)
        if run.get("status") != "staged":
            raise ValueError("only staged imports can be sealed")

        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE result = 'staged' AND rolled_back_at IS NULL) AS valid,
                   COUNT(*) FILTER (WHERE error IS NOT NULL) AS failed
            FROM import_record
            WHERE import_run_id = %s
            """,
            (run_id,),
        )
        counts = cursor.fetchone()
        total = int(counts["total"])
        valid = int(counts["valid"])
        failed = int(counts["failed"])
        if failed or valid != total:
            raise ValueError("import contains invalid, failed, or rolled-back records")
        if expected_records is not None and total != expected_records:
            raise ValueError(
                f"staged record count changed: expected {expected_records}, found {total}"
            )

        seal = {
            "actor": actor,
            "record_count": total,
            "source_fingerprint": config.get("source_fingerprint"),
        }
        cursor.execute(
            """
            UPDATE import_run
            SET status = 'sealed',
                config = config || jsonb_build_object('seal', %s::jsonb),
                completed_at = COALESCE(completed_at, NOW())
            WHERE id = %s
            RETURNING *
            """,
            (json.dumps(seal), run_id),
        )
        return dict(cursor.fetchone())
