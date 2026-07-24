#!/usr/bin/env python3
"""
Sandbox CLI - Execute commands in OpenSandbox

Usage:
    python -m src.sandbox.cli run "echo hello"
    python -m src.sandbox.cli run "pip install requests" --sandbox
    python -m src.sandbox.cli check
"""

import asyncio
import argparse
import sys
from src.sandbox import SandboxExecutor, DirectExecutor, get_executor


async def check_server():
    """Check if OpenSandbox server is running."""
    executor = SandboxExecutor()
    if executor.is_available():
        print("✓ OpenSandbox server is running")
        return True
    else:
        print("✗ OpenSandbox server not available")
        print("  Start with: opensandbox-server")
        return False


async def run_command(args):
    """Execute a command."""
    # Determine mode
    mode = "sandbox" if args.sandbox else "direct"
    
    # Get executor
    executor = get_executor(mode=mode)
    
    print(f"Executing in {mode} mode: {args.command[:50]}{'...' if len(args.command) > 50 else ''}")
    
    # Run
    result = await executor.run(
        args.command,
        timeout=args.timeout,
        ephemeral=not args.persist
    )
    
    # Output
    if result.success:
        print(f"\n✓ Exit code: {result.exit_code}")
        print(f"  Duration: {result.duration_ms}ms")
    else:
        print(f"\n✗ Exit code: {result.exit_code}")
        if result.error:
            print(f"  Error: {result.error}")
    
    if result.stdout:
        print("\n--- stdout ---")
        print(result.stdout[:2000] if len(result.stdout) > 2000 else result.stdout)
    
    if result.stderr:
        print("\n--- stderr ---")
        print(result.stderr[:2000] if len(result.stderr) > 2000 else result.stderr)
    
    return 0 if result.success else 1


async def run_python(args):
    """Run Python code."""
    executor = SandboxExecutor() if args.sandbox else DirectExecutor()
    
    print(f"Running Python in {'sandbox' if args.sandbox else 'direct'} mode...")
    
    result = await executor.run_python(args.code, timeout=args.timeout)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return 0 if result.success else 1


def main():
    parser = argparse.ArgumentParser(description="OpenBrain Sandbox CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Check command
    subparsers.add_parser("check", help="Check if sandbox server is running")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a shell command")
    run_parser.add_argument("command", help="Command to execute")
    run_parser.add_argument("--sandbox", "-s", action="store_true", help="Run in sandbox")
    run_parser.add_argument("--timeout", "-t", type=int, default=60, help="Timeout in seconds")
    run_parser.add_argument("--persist", "-p", action="store_true", help="Don't destroy sandbox after")
    
    # Run Python
    py_parser = subparsers.add_parser("python", help="Run Python code")
    py_parser.add_argument("code", help="Python code")
    py_parser.add_argument("--sandbox", "-s", action="store_true", help="Run in sandbox")
    py_parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds")
    
    args = parser.parse_args()
    
    if args.command == "check":
        return 0 if asyncio.run(check_server()) else 1
    elif args.command == "run":
        return asyncio.run(run_command(args))
    elif args.command == "python":
        return asyncio.run(run_python(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
