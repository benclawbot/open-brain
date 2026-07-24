"""Open Brain command-line interface."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from src.runtime_config import configure_runtime_environment, load_runtime_environment
from src.version import get_version

load_runtime_environment()


def _version() -> str:
    return get_version()


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def update_cmd(skip_migrations: bool = False) -> int:
    """Upgrade a pipx-managed installation and apply additive migrations."""
    try:
        _run(["pipx", "upgrade", "openbrain"])
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print("Update requires a pipx-managed installation. Reinstall with the official one-line installer.", file=sys.stderr)
        return getattr(exc, "returncode", 1) or 1
    if not skip_migrations:
        try:
            from src.db.migrate import apply_migrations
            applied = apply_migrations()
        except Exception as exc:
            print(f"Package updated, but database migration failed: {exc}. Existing data was not deleted.", file=sys.stderr)
            return 1
        if applied:
            print("Applied migrations: " + ", ".join(applied))
    print(f"Open Brain is up to date ({_version()}).")
    return 0


def install_hermes_cmd(hermes_home: str | None = None, force: bool = False) -> int:
    """Install the packaged Open Brain provider into Hermes' plugin directory."""
    home = Path(hermes_home or os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().resolve()
    destination = home / "plugins" / "openbrain"
    if destination.exists() and not force:
        print(f"Hermes plugin already exists at {destination}. Use --force to replace it.", file=sys.stderr)
        return 1
    source = Path(__file__).resolve().parents[1] / "openbrain_hermes_plugin"
    required = ("__init__.py", "plugin.yaml", "README.md")
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        print("Installed package is missing Hermes provider files: " + ", ".join(missing), file=sys.stderr)
        return 1
    destination.mkdir(parents=True, exist_ok=True)
    for name in required:
        shutil.copy2(source / name, destination / name)
    print(f"Installed the Open Brain Hermes provider at {destination}")
    print("Run `hermes memory setup` and select `openbrain`; credentials load automatically.")
    return 0


def configure_cmd(project_root: str | None = None) -> int:
    """Create or reuse private credentials without printing the secret."""
    path = configure_runtime_environment(Path(project_root) if project_root else None)
    print(f"Open Brain credentials configured at {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="openbrain", description="Open Brain - shared memory and continuity for people and AI agents")
    parser.add_argument("--version", action="version", version=f"Open Brain {_version()}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", "-n", type=int, default=10)
    search_parser.add_argument("--source", "-s")
    search_parser.add_argument("--tag", "-t")
    search_parser.add_argument("--json", action="store_true")

    store_parser = subparsers.add_parser("store", help="Store a new memory")
    store_parser.add_argument("content")
    store_parser.add_argument("--source", default="cli")
    store_parser.add_argument("--tag", "-t", action="append")
    store_parser.add_argument("--importance", "-i", type=float, default=0.5)

    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--json", action="store_true")

    import_parser = subparsers.add_parser("import", help="Import from source")
    import_parser.add_argument("source", choices=["telegram", "whatsapp", "claude_code", "gmail", "file"])
    import_parser.add_argument("path")
    import_parser.add_argument("--limit", "-n", type=int)

    report_parser = subparsers.add_parser("report", help="Generate weekly report")
    report_parser.add_argument("--days", "-d", type=int, default=7)
    report_parser.add_argument("--output", "-o")

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", "-p", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    update_parser = subparsers.add_parser("update", help="Upgrade Open Brain and apply additive migrations")
    update_parser.add_argument("--skip-migrations", action="store_true")

    configure_parser = subparsers.add_parser(
        "configure",
        help="Generate private local credentials",
    )
    configure_parser.add_argument("--project-root")

    hermes_parser = subparsers.add_parser("install-hermes", help="Install the native Hermes memory provider")
    hermes_parser.add_argument("--hermes-home")
    hermes_parser.add_argument("--force", action="store_true")

    maintenance_parser = subparsers.add_parser("maintenance", help="Run bounded maintenance orchestration")
    maintenance_parser.add_argument("--apply", action="store_true")
    maintenance_parser.add_argument("--proposal-limit", type=int, default=500)
    maintenance_parser.add_argument("--cache-max-rows", type=int, default=5000)
    maintenance_parser.add_argument("--tombstone-retention-days", type=int, default=90)
    maintenance_parser.add_argument("--project-id")
    maintenance_parser.add_argument("--task-id")
    maintenance_parser.add_argument("--compaction-min-events", type=int, default=8)
    maintenance_parser.add_argument("--compaction-max-events", type=int, default=200)

    version_parser = subparsers.add_parser("version-check", help="Check for a newer release")
    version_parser.add_argument("--json", action="store_true")
    doctor_parser = subparsers.add_parser("doctor", help="Check installation and integrations")
    doctor_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    try:
        if args.command == "search":
            from .search import search_memories_cmd
            return search_memories_cmd(args)
        if args.command == "store":
            from .store import store_memory_cmd
            return store_memory_cmd(args)
        if args.command == "stats":
            from .stats import stats_cmd
            return stats_cmd(args)
        if args.command == "import":
            from .import_data import import_cmd
            return import_cmd(args)
        if args.command == "report":
            from .report import report_cmd
            return report_cmd(args)
        if args.command == "serve":
            from .serve import serve_cmd
            return serve_cmd(args)
        if args.command == "update":
            return update_cmd(skip_migrations=args.skip_migrations)
        if args.command == "configure":
            return configure_cmd(args.project_root)
        if args.command == "install-hermes":
            return install_hermes_cmd(args.hermes_home, args.force)
        if args.command == "maintenance":
            from .maintenance import maintenance_cmd
            return maintenance_cmd(args)
        if args.command in {"version-check", "doctor"}:
            from .productization import doctor_cmd, version_check_cmd
            return version_check_cmd(as_json=args.json) if args.command == "version-check" else doctor_cmd(as_json=args.json)
        parser.print_help()
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
