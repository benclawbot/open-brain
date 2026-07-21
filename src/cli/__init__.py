"""Open Brain command-line interface."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

from dotenv import load_dotenv

_dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path)

from .import_data import import_cmd
from .report import report_cmd
from .search import search_memories_cmd
from .serve import serve_cmd
from .stats import stats_cmd
from .store import store_memory_cmd


def _version() -> str:
    try:
        return version("openbrain")
    except PackageNotFoundError:
        return "development"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def update_cmd(skip_migrations: bool = False) -> int:
    """Upgrade a pipx-managed installation and apply additive migrations."""
    try:
        _run(["pipx", "upgrade", "openbrain"])
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(
            "Update requires a pipx-managed installation. Reinstall with the official one-line installer.",
            file=sys.stderr,
        )
        return getattr(exc, "returncode", 1) or 1

    if not skip_migrations:
        try:
            from db.migrate import apply_migrations

            applied = apply_migrations()
        except Exception as exc:
            print(
                f"Package updated, but database migration failed: {exc}. Existing data was not deleted.",
                file=sys.stderr,
            )
            return 1
        if applied:
            print("Applied migrations: " + ", ".join(applied))

    print(f"Open Brain is up to date ({_version()}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="openbrain",
        description="Open Brain - shared memory and continuity for people and AI agents",
    )
    parser.add_argument("--version", action="version", version=f"Open Brain {_version()}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    search_parser.add_argument("--source", "-s", help="Filter by source")
    search_parser.add_argument("--tag", "-t", help="Filter by tag")
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")

    store_parser = subparsers.add_parser("store", help="Store a new memory")
    store_parser.add_argument("content", help="Content to store")
    store_parser.add_argument("--source", default="cli", help="Source (default: cli)")
    store_parser.add_argument("--tag", "-t", action="append", help="Add tag")
    store_parser.add_argument("--importance", "-i", type=float, default=0.5, help="Importance 0-1")

    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")

    import_parser = subparsers.add_parser("import", help="Import from source")
    import_parser.add_argument(
        "source",
        choices=["telegram", "whatsapp", "claude_code", "gmail", "file"],
        help="Source type",
    )
    import_parser.add_argument("path", help="Path to import from")
    import_parser.add_argument("--limit", "-n", type=int, help="Limit number of imports")

    report_parser = subparsers.add_parser("report", help="Generate weekly report")
    report_parser.add_argument("--days", "-d", type=int, default=7, help="Number of days")
    report_parser.add_argument("--output", "-o", help="Output file")

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")

    update_parser = subparsers.add_parser("update", help="Upgrade Open Brain and apply additive migrations")
    update_parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Upgrade the package without applying database migrations",
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "search":
            return search_memories_cmd(args)
        if args.command == "store":
            return store_memory_cmd(args)
        if args.command == "stats":
            return stats_cmd(args)
        if args.command == "import":
            return import_cmd(args)
        if args.command == "report":
            return report_cmd(args)
        if args.command == "serve":
            return serve_cmd(args)
        if args.command == "update":
            return update_cmd(skip_migrations=args.skip_migrations)
        parser.print_help()
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
