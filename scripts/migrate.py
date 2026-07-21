#!/usr/bin/env python3
"""Apply packaged Open Brain SQL migrations."""

from db.migrate import apply_migrations


if __name__ == "__main__":
    completed = apply_migrations()
    if completed:
        print("Applied migrations:")
        for filename in completed:
            print(f"- {filename}")
    else:
        print("Database is already up to date.")
