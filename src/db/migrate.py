"""Apply packaged Open Brain SQL migrations in filename order."""

from __future__ import annotations

import hashlib
from importlib.resources import files

from src.db.connection import get_db_connection, init_db


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

    with get_db_connection() as connection:
        try:
            with connection.cursor() as cursor:
                _ensure_ledger(cursor)
                for resource in migration_files:
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
        except Exception:
            connection.rollback()
            raise
    return applied
