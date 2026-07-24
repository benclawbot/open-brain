"""Execution service for dry-run and resumable imports."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..db.import_queries import (
    create_import_run,
    get_import_run,
    record_import_candidate,
    seen_external_hashes,
    update_import_run,
)
from .base import ImportAdapter


class ImportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    status: str
    dry_run: bool
    records_seen: int
    records_imported: int
    records_merged: int
    records_rejected: int
    cursor: dict


def run_import(
    adapter: ImportAdapter,
    *,
    source_system: str,
    source_instance: str | None = None,
    dry_run: bool = True,
    resume_run_id: UUID | None = None,
) -> ImportSummary:
    """Execute one deterministic import pass.

    Candidates are persisted only as import records. Dry runs finish in the
    ``previewed`` state. Real imports finish in the ``staged`` state and require
    an explicit validation seal before any later promotion step.
    """
    if resume_run_id:
        existing = get_import_run(resume_run_id)
        if existing is None:
            raise ValueError(f"import run not found: {resume_run_id}")
        if existing.get("status") in {"sealed", "rolled_back"}:
            raise ValueError(f"{existing['status']} imports cannot be resumed")
        run_id = UUID(str(existing["id"]))
        config = existing.get("config") or {}
        if isinstance(config, str):
            import json

            config = json.loads(config)
        previous_fingerprint = config.get("source_fingerprint")
        current_fingerprint = adapter.source_fingerprint()
        if previous_fingerprint and previous_fingerprint != current_fingerprint:
            raise ValueError("source fingerprint changed; start a new import run")
        dry_run = bool(config.get("dry_run", dry_run))
    else:
        created = create_import_run(
            source_system,
            source_instance,
            {"adapter": type(adapter).__qualname__},
            dry_run=dry_run,
            source_fingerprint=adapter.source_fingerprint(),
        )
        run_id = UUID(str(created["id"]))

    seen = seen_external_hashes(run_id)
    counters = {"seen": 0, "imported": 0, "merged": 0, "rejected": 0}
    cursor = {"ordinal": 0}

    try:
        for ordinal, candidate in enumerate(adapter.discover(), start=1):
            counters["seen"] += 1
            cursor = {"ordinal": ordinal, "external_id": candidate.external_id}
            key = (candidate.external_id, candidate.external_hash)
            if key in seen:
                counters["merged"] += 1
                continue

            inserted = record_import_candidate(
                run_id,
                candidate,
                operation="preview" if dry_run else "stage",
                result="previewed" if dry_run else "staged",
            )
            if inserted:
                counters["imported"] += 1
                seen.add(key)
            else:
                counters["merged"] += 1

            update_import_run(
                run_id,
                status="running",
                cursor_value=cursor,
                records_seen=counters["seen"],
                records_imported=counters["imported"],
                records_merged=counters["merged"],
                records_rejected=counters["rejected"],
            )

        final_status = "previewed" if dry_run else "staged"
        update_import_run(
            run_id,
            status=final_status,
            cursor_value=cursor,
            records_seen=counters["seen"],
            records_imported=counters["imported"],
            records_merged=counters["merged"],
            records_rejected=counters["rejected"],
        )
    except Exception as exc:
        update_import_run(
            run_id,
            status="failed",
            cursor_value=cursor,
            records_seen=counters["seen"],
            records_imported=counters["imported"],
            records_merged=counters["merged"],
            records_rejected=counters["rejected"] + 1,
            error=str(exc),
        )
        raise

    return ImportSummary(
        run_id=run_id,
        status=final_status,
        dry_run=dry_run,
        records_seen=counters["seen"],
        records_imported=counters["imported"],
        records_merged=counters["merged"],
        records_rejected=counters["rejected"],
        cursor=cursor,
    )
