"""
Import command for CLI.
"""
import sys
from argparse import Namespace

from ..connectors.telegram import import_telegram
from ..connectors.whatsapp import import_whatsapp
from ..connectors.claude_code import import_claude_code
from ..connectors.gmail import import_gmail
from ..connectors.file_watcher import import_folder


def import_cmd(args: Namespace) -> int:
    """Handle the import command."""
    source = args.source
    path = args.path
    limit = args.limit
    
    print(f"Importing from {source}...")
    print(f"Path: {path}")
    
    try:
        if source == 'telegram':
            result = import_telegram(path, limit)
        elif source == 'whatsapp':
            result = import_whatsapp(path, limit)
        elif source == 'claude_code':
            result = import_claude_code(path, limit)
        elif source == 'gmail':
            result = import_gmail(path, limit)
        elif source == 'file':
            result = import_folder(path)
        else:
            print(f"Unknown source: {source}")
            return 1
        
        print("\nImport complete!")
        print(f"Imported: {result.get('imported', 0)}")
        print(f"Total processed: {result.get('total_processed', 0)}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
