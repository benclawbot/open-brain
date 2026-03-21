"""
Open Brain MCP Server.
FastMCP-based MCP server for memory operations.
"""
import os
import sys
from typing import Any, Dict, List, Optional

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import AnyUrl

# Add src to path (so `from db import ...` etc. resolve correctly)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import connection, queries
from db.queries import (
    insert_memory,
    search_memories,
    get_memory_by_id,
    get_related_memories,
    get_memories_by_entity,
    get_today_memories,
    get_memory_stats
)
from embedder import create_embedding
from extractors.entities import extract_entities
from extractors.tagger import auto_tag
from analytics.trends import TrendAnalyzer
from analytics.weekly_report import generate_weekly_report


# Load configuration
def load_config() -> Dict:
    """Load configuration from settings.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'config', 'settings.yaml'
    )
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


CONFIG = load_config()


# Initialize database connection
def init_server():
    """Initialize the server and database connection."""
    try:
        connection.init_db()
        print("Database connection initialized", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}", file=sys.stderr)


# Create MCP server
app = Server("openbrain")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="memory_search",
            description="Search memories by query, tags, source, or date range. Supports semantic search via embeddings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text search query"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "Filter by sources"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                    "date_from": {"type": "string", "description": "From date (ISO format)"},
                    "date_to": {"type": "string", "description": "To date (ISO format)"}
                }
            }
        ),
        Tool(
            name="memory_store",
            description="Store a new memory with auto-tagging and entity extraction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "source": {"type": "string", "description": "Source (chat, note, email, etc.)", "default": "mcp"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional user tags"},
                    "importance": {"type": "number", "description": "Importance 0-1", "default": 0.5},
                    "metadata": {"type": "object", "description": "Additional metadata"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="memory_get_related",
            description="Get memories related to a specific memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "UUID of the memory"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5}
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="memory_get_entity",
            description="Get all memories containing a specific entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Type of entity (people, technologies, etc.)"},
                    "entity_name": {"type": "string", "description": "Name of the entity"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10}
                },
                "required": ["entity_type", "entity_name"]
            }
        ),
        Tool(
            name="memory_today",
            description="Get memories created today.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10}
                }
            }
        ),
        Tool(
            name="memory_stats",
            description="Get memory statistics including total count, by source, top tags, and weekly activity.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="memory_weekly_report",
            description="Generate a weekly report of memory activity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to include", "default": 7}
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls."""
    
    try:
        if name == "memory_search":
            return await handle_memory_search(arguments)
        elif name == "memory_store":
            return await handle_memory_store(arguments)
        elif name == "memory_get_related":
            return await handle_memory_get_related(arguments)
        elif name == "memory_get_entity":
            return await handle_memory_get_entity(arguments)
        elif name == "memory_today":
            return await handle_memory_today(arguments)
        elif name == "memory_stats":
            return await handle_memory_stats(arguments)
        elif name == "memory_weekly_report":
            return await handle_weekly_report(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_memory_search(args: Dict) -> List[TextContent]:
    """Handle memory_search tool."""
    query = args.get("query", "")
    limit = args.get("limit", 5)
    sources = args.get("sources")
    tags = args.get("tags")
    date_from = args.get("date_from")
    date_to = args.get("date_to")
    
    # Generate embedding for semantic search
    embedding = None
    if query:
        try:
            embedding = create_embedding(query)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}", file=sys.stderr)
    
    results = search_memories(
        query=query,
        embedding=embedding,
        limit=limit,
        sources=sources,
        tags=tags,
        date_from=date_from,
        date_to=date_to
    )
    
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_store(args: Dict) -> List[TextContent]:
    """Handle memory_store tool."""
    content = args["content"]
    source = args.get("source", "mcp")
    user_tags = args.get("tags", [])
    importance = args.get("importance", 0.5)
    metadata = args.get("metadata", {})
    
    # Extract entities
    entities = extract_entities(content)
    
    # Auto-tag
    tags = auto_tag(content, entities, source, user_tags)
    
    # Generate embedding
    embedding = None
    try:
        embedding = create_embedding(content)
    except Exception as e:
        print(f"Warning: Could not create embedding: {e}", file=sys.stderr)
    
    # Store in database
    memory_id = insert_memory(
        source=source,
        content=content,
        embedding=embedding,
        entities=entities,
        tags=list(tags.keys()),
        tag_sources=tags,
        importance=importance,
        metadata=metadata
    )
    
    return [TextContent(type="text", text=f"{{'id': '{memory_id}', 'status': 'stored', 'tags': {list(tags.keys())}}}")]


async def handle_memory_get_related(args: Dict) -> List[TextContent]:
    """Handle memory_get_related tool."""
    memory_id = args["memory_id"]
    limit = args.get("limit", 5)
    
    import uuid
    try:
        parsed_id = uuid.UUID(memory_id)
    except ValueError:
        return [TextContent(type="text", text=f"Invalid memory ID: {memory_id}")]
    results = get_related_memories(parsed_id, limit)
    
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_get_entity(args: Dict) -> List[TextContent]:
    """Handle memory_get_entity tool."""
    entity_type = args["entity_type"]
    entity_name = args["entity_name"]
    limit = args.get("limit", 10)
    
    results = get_memories_by_entity(entity_type, entity_name, limit)
    
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_today(args: Dict) -> List[TextContent]:
    """Handle memory_today tool."""
    limit = args.get("limit", 10)
    
    results = get_today_memories(limit)
    
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_stats(args: Dict) -> List[TextContent]:
    """Handle memory_stats tool."""
    stats = get_memory_stats()
    
    return [TextContent(type="text", text=str(stats))]


async def handle_weekly_report(args: Dict) -> List[TextContent]:
    """Handle memory_weekly_report tool."""
    days = args.get("days", 7)
    
    report = generate_weekly_report(days)
    
    return [TextContent(type="text", text=report)]


def format_memory_list(memories: List[Dict]) -> str:
    """Format a list of memories for display."""
    if not memories:
        return "No memories found."
    
    lines = []
    for mem in memories:
        lines.append(f"ID: {mem.get('id')}")
        lines.append(f"Source: {mem.get('source')}")
        lines.append(f"Content: {(mem.get('content') or '')[:100]}...")
        lines.append(f"Tags: {', '.join(mem.get('tags', []))}")
        lines.append(f"Created: {mem.get('created_at')}")
        lines.append("---")
    
    return "\n".join(lines)


async def main():
    """Main entry point."""
    init_server()
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
