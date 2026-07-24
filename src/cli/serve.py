"""
Serve command for CLI.
"""
import sys
from argparse import Namespace

import uvicorn


def serve_cmd(args: Namespace) -> int:
    """Handle the serve command."""
    host = args.host
    port = args.port
    reload = args.reload
    
    print("Starting Open Brain API server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"API docs: http://{host}:{port}/docs")
    
    try:
        from ..api.main import app
    except ImportError:
        print("Error: Could not import API app", file=sys.stderr)
        return 1
    
    uvicorn.run(
        "src.api.main:app" if reload else app,
        host=host,
        port=port,
        reload=reload
    )
    
    return 0
