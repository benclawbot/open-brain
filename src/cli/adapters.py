"""Install and diagnose Open Brain coding-agent host integrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from src.providers.host_config import HostAdapterConfig, install_env_file, uninstall_env_file

SUPPORTED_HOSTS = ("medusa", "codex", "claude")


def default_config_path(host: str) -> Path:
    return Path.home() / ".config" / "openbrain" / "hosts" / f"{host}.env"


def doctor(config: HostAdapterConfig) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    result: dict[str, object] = {
        "url": config.base_url,
        "authenticated": bool(config.api_key),
        "live": False,
        "ready": False,
    }
    try:
        with httpx.Client(base_url=config.base_url, timeout=config.timeout, headers=headers) as client:
            live = client.get("/health")
            live.raise_for_status()
            result["live"] = True
            ready = client.get("/ready")
            ready.raise_for_status()
            result["ready"] = True
    except httpx.HTTPError as exc:
        result["error"] = type(exc).__name__
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openbrain-adapters")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="write private host environment configuration")
    install.add_argument("host", choices=SUPPORTED_HOSTS)
    install.add_argument("--path", type=Path)
    install.add_argument("--overwrite", action="store_true")

    status = subparsers.add_parser("status", help="show the resolved host configuration")
    status.add_argument("host", choices=SUPPORTED_HOSTS)
    status.add_argument("--path", type=Path)

    diagnose = subparsers.add_parser("doctor", help="check liveness and readiness")
    diagnose.add_argument("host", choices=SUPPORTED_HOSTS)

    uninstall = subparsers.add_parser("uninstall", help="remove installed host configuration")
    uninstall.add_argument("host", choices=SUPPORTED_HOSTS)
    uninstall.add_argument("--path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = args.path or default_config_path(args.host) if hasattr(args, "path") else None

    if args.command == "install":
        installed = install_env_file(path, HostAdapterConfig.from_env(), overwrite=args.overwrite)
        print(json.dumps({"status": "installed", "host": args.host, "path": str(installed)}))
        return 0
    if args.command == "uninstall":
        removed = uninstall_env_file(path)
        print(json.dumps({"status": "removed" if removed else "absent", "host": args.host, "path": str(path)}))
        return 0
    if args.command == "status":
        print(json.dumps({"host": args.host, "path": str(path), "installed": path.exists()}))
        return 0
    if args.command == "doctor":
        result = doctor(HostAdapterConfig.from_env())
        result["host"] = args.host
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ready"] else 1
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
