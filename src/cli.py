"""Open Brain command-line entrypoint."""

from __future__ import annotations

import argparse
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _version() -> str:
    try:
        return version("openbrain")
    except PackageNotFoundError:
        return "development"


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def update_command(skip_migrations: bool = False) -> int:
    """Upgrade the pipx installation and apply additive migrations."""
    try:
        _run(["pipx", "upgrade", "openbrain"])
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(
            "Update requires a pipx-managed installation. Reinstall with the official one-line installer.",
            file=sys.stderr,
        )
        return getattr(exc, "returncode", 1) or 1

    if not skip_migrations:
        migration_script = Path(__file__).resolve().parents[1] / "scripts" / "migrate.py"
        if migration_script.exists():
            try:
                _run([sys.executable, str(migration_script)])
            except subprocess.CalledProcessError as exc:
                print(
                    "Package updated, but database migration failed. Existing data was not deleted.",
                    file=sys.stderr,
                )
                return exc.returncode or 1
        else:
            print("Package updated; migration script was not found in this installation.", file=sys.stderr)
            return 1

    print(f"Open Brain is up to date ({_version()}).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openbrain")
    parser.add_argument("--version", action="version", version=f"Open Brain {_version()}")
    subcommands = parser.add_subparsers(dest="command")

    update = subcommands.add_parser("update", help="Upgrade Open Brain and apply additive migrations")
    update.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Upgrade the package without applying database migrations",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "update":
        return update_command(skip_migrations=args.skip_migrations)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
