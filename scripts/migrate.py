#!/usr/bin/env python3
"""Apply Open Brain SQL migrations in filename order."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.db.connection import get_db_connection, init_db


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "src" / "db" / "migrations"


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

    with get_db_connection() as connection:
        try:
            with connection.cursor() as cursor:
                _ensure_ledger(cursor)
                for path in sorted(MIGRATIONS.glob("*.sql")):
                    content = path.read_text(encoding="utf-8")
                    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    cursor.execute(
                        "SELECT checksum FROM schema_migration WHERE filename = %s",
                        (path.name,),
                    )
                    row = cursor.fetchone()
                    if row:
                        if row[0] != checksum:
                            raise RuntimeError(
                                f"Applied migration {path.name} changed on disk; add a new migration instead"
                            )
                        continue

                    cursor.execute(content)
                    cursor.execute(
                        "INSERT INTO schema_migration (filename, checksum) VALUES (%s, %s)",
                        (path.name, checksum),
                    )
                    applied.append(path.name)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return applied


if __name__ == "__main__":
    completed = apply_migrations()
    if completed:
        print("Applied migrations:")
        for filename in completed:
            print(f"- {filename}")
    else:
        print("Database is already up to date.")
