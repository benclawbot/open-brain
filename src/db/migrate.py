"""Apply packaged Open Brain SQL migrations in filename order."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from importlib.resources import files

from src.db.connection import get_db_connection, init_db


_MIGRATION_NAME = re.compile(r"^(?P<sequence>\d+)_")
_LEGACY_DUPLICATE_SEQUENCES = {
    "011": frozenset(
        {
            "011_assertion_pruning_execution.sql",
            "011_context_retrieval_indexes.sql",
        }
    ),
}


def validate_migration_sequence(filenames: list[str]) -> None:
    """Reject ambiguous migration numbers except the documented v1.0 legacy pair."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for filename in filenames:
        match = _MIGRATION_NAME.match(filename)
        if not match:
            raise RuntimeError(f"invalid migration filename: {filename}")
        grouped[match.group("sequence")].add(filename)

    for sequence, names in grouped.items():
        if len(names) < 2:
            continue
        if _LEGACY_DUPLICATE_SEQUENCES.get(sequence) == frozenset(names):
            continue
        raise RuntimeError(
            f"duplicate migration sequence {sequence}: {', '.join(sorted(names))}"
        )


def _ensure_ledger(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration (
            filename TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def apply_migrations() -> list[str]:
    init_db()
    applied: list[str] = []
    migration_root = files("src.db.migrations")
    migration_files = sorted(
        item for item in migration_root.iterdir() if item.name.endswith(".sql")
    )
    validate_migration_sequence([resource.name for resource in migration_files])

    with get_db_connection() as connection:
        active_migration: str | None = None
        try:
            with connection.cursor() as cursor:
                _ensure_ledger(cursor)
                for resource in migration_files:
                    active_migration = resource.name
                    content = resource.read_text(encoding="utf-8")
                    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    cursor.execute(
                        "SELECT checksum FROM schema_migration WHERE filename = %s",
                        (resource.name,),
                    )
                    row = cursor.fetchone()
                    if row:
                        if row[0] != checksum:
                            raise RuntimeError(
                                f"Applied migration {resource.name} changed; add a new migration instead"
                            )
                        continue
                    cursor.execute(content)
                    cursor.execute(
                        "INSERT INTO schema_migration (filename, checksum) VALUES (%s, %s)",
                        (resource.name, checksum),
                    )
                    applied.append(resource.name)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if active_migration:
                raise RuntimeError(
                    f"Migration {active_migration} failed: {exc}"
                ) from exc
            raise
    return applied
