"""
Open Brain CLI.
Command-line interface for memory operations.
"""
import argparse
import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv

# Load .env from open-brain project root
_dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path)

from .search import search_memories_cmd
from .store import store_memory_cmd
from .stats import stats_cmd
from .import_data import import_cmd
from .report import report_cmd
from .serve import serve_cmd


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='openbrain',
        description='Open Brain - Memory management CLI'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search memories')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', '-n', type=int, default=10, help='Max results')
    search_parser.add_argument('--source', '-s', help='Filter by source')
    search_parser.add_argument('--tag', '-t', help='Filter by tag')
    search_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Store command
    store_parser = subparsers.add_parser('store', help='Store a new memory')
    store_parser.add_argument('content', help='Content to store')
    store_parser.add_argument('--source', default='cli', help='Source (default: cli)')
    store_parser.add_argument('--tag', '-t', action='append', help='Add tag')
    store_parser.add_argument('--importance', '-i', type=float, default=0.5, help='Importance 0-1')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import from source')
    import_parser.add_argument('source', choices=['telegram', 'whatsapp', 'claude_code', 'gmail', 'file'], help='Source type')
    import_parser.add_argument('path', help='Path to import from')
    import_parser.add_argument('--limit', '-n', type=int, help='Limit number of imports')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate weekly report')
    report_parser.add_argument('--days', '-d', type=int, default=7, help='Number of days')
    report_parser.add_argument('--output', '-o', help='Output file')
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start API server')
    serve_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    serve_parser.add_argument('--port', '-p', type=int, default=8000, help='Port to bind to')
    serve_parser.add_argument('--reload', action='store_true', help='Auto-reload on changes')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'search':
            return search_memories_cmd(args)
        elif args.command == 'store':
            return store_memory_cmd(args)
        elif args.command == 'stats':
            return stats_cmd(args)
        elif args.command == 'import':
            return import_cmd(args)
        elif args.command == 'report':
            return report_cmd(args)
        elif args.command == 'serve':
            return serve_cmd(args)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

