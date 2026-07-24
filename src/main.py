"""
Open Brain MCP Server.
FastMCP-based MCP server for memory operations.
"""
import os
import sys
from typing import Any, Dict, List

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .db import connection
from .db.attribution import insert_memory, search_memories
from .db.queries import (
    get_related_memories,
    get_memories_by_entity,
    get_today_memories,
    get_memory_stats,
)
from .embedder import create_embedding
from .extractors.entities import extract_entities
from .extractors.tagger import auto_tag
from .analytics.weekly_report import generate_weekly_report


def load_config() -> Dict:
    """Load configuration from settings.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'config', 'settings.yaml'
    )
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


CONFIG = load_config()


def init_server():
    """Initialize the server and database connection."""
    try:
        connection.init_db()
        print("Database connection initialized", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: Could not initialize database: {exc}", file=sys.stderr)


app = Server("openbrain")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="memory_search",
            description=(
                "Search memories by query, tags, transport source, authoring "
                "agent, or date range. Supports semantic search via embeddings."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text search query"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "Filter by transport sources"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                    "captured_by": {"type": "array", "items": {"type": "string"}, "description": "Filter by exact authoring agent or session identities"},
                    "date_from": {"type": "string", "description": "From date (ISO format)"},
                    "date_to": {"type": "string", "description": "To date (ISO format)"},
                },
            },
        ),
        Tool(
            name="memory_store",
            description="Store a new memory with auto-tagging, entity extraction, and optional agent attribution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "source": {"type": "string", "description": "Transport source (mcp, chat, note, email, etc.)", "default": "mcp"},
                    "captured_by": {"type": "string", "description": "Exact agent or session identity that authored the memory"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional user tags"},
                    "importance": {"type": "number", "description": "Importance 0-1", "default": 0.5},
                    "metadata": {"type": "object", "description": "Additional metadata"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="memory_get_related",
            description="Get memories related to a specific memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "UUID of the memory"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                },
                "required": ["memory_id"],
            },
        ),
        Tool(
            name="memory_get_entity",
            description="Get all memories containing a specific entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Type of entity (people, technologies, etc.)"},
                    "entity_name": {"type": "string", "description": "Name of the entity"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["entity_type", "entity_name"],
            },
        ),
        Tool(
            name="memory_today",
            description="Get memories created today.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
            },
        ),
        Tool(
            name="memory_stats",
            description="Get memory statistics including total count, by source, top tags, and weekly activity.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_weekly_report",
            description="Generate a weekly report of memory activity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to include", "default": 7},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "memory_search":
            return await handle_memory_search(arguments)
        if name == "memory_store":
            return await handle_memory_store(arguments)
        if name == "memory_get_related":
            return await handle_memory_get_related(arguments)
        if name == "memory_get_entity":
            return await handle_memory_get_entity(arguments)
        if name == "memory_today":
            return await handle_memory_today(arguments)
        if name == "memory_stats":
            return await handle_memory_stats(arguments)
        if name == "memory_weekly_report":
            return await handle_weekly_report(arguments)
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {str(exc)}")]


async def handle_memory_search(args: Dict) -> List[TextContent]:
    """Handle memory_search tool."""
    query = args.get("query", "")
    limit = args.get("limit", 5)
    sources = args.get("sources")
    tags = args.get("tags")
    captured_by = args.get("captured_by")
    date_from = args.get("date_from")
    date_to = args.get("date_to")

    embedding = None
    if query:
        try:
            embedding = create_embedding(query)
        except Exception as exc:
            print(f"Warning: Could not create embedding: {exc}", file=sys.stderr)

    results = search_memories(
        query=query,
        embedding=embedding,
        limit=limit,
        sources=sources,
        tags=tags,
        captured_by=captured_by,
        date_from=date_from,
        date_to=date_to,
    )
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_store(args: Dict) -> List[TextContent]:
    """Handle memory_store tool."""
    content = args["content"]
    source = args.get("source", "mcp")
    captured_by = args.get("captured_by")
    user_tags = args.get("tags", [])
    importance = args.get("importance", 0.5)
    metadata = args.get("metadata", {})

    entities = extract_entities(content)
    tags = auto_tag(content, entities, source, user_tags)

    embedding = None
    try:
        embedding = create_embedding(content)
    except Exception as exc:
        print(f"Warning: Could not create embedding: {exc}", file=sys.stderr)

    memory_id = insert_memory(
        source=source,
        captured_by=captured_by,
        content=content,
        embedding=embedding,
        entities=entities,
        tags=list(tags.keys()),
        tag_sources=tags,
        importance=importance,
        metadata=metadata,
    )

    return [TextContent(
        type="text",
        text=str({
            "id": str(memory_id),
            "status": "stored",
            "tags": list(tags.keys()),
            "captured_by": captured_by,
        }),
    )]


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
    results = get_memories_by_entity(
        args["entity_type"],
        args["entity_name"],
        args.get("limit", 10),
    )
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_today(args: Dict) -> List[TextContent]:
    """Handle memory_today tool."""
    results = get_today_memories(args.get("limit", 10))
    return [TextContent(type="text", text=format_memory_list(results))]


async def handle_memory_stats(args: Dict) -> List[TextContent]:
    """Handle memory_stats tool."""
    return [TextContent(type="text", text=str(get_memory_stats()))]


async def handle_weekly_report(args: Dict) -> List[TextContent]:
    """Handle memory_weekly_report tool."""
    return [TextContent(type="text", text=generate_weekly_report(args.get("days", 7)))]


def format_memory_list(memories: List[Dict]) -> str:
    """Format a list of memories for display."""
    if not memories:
        return "No memories found."

    lines = []
    for memory in memories:
        lines.append(f"ID: {memory.get('id')}")
        lines.append(f"Source: {memory.get('source')}")
        if memory.get("captured_by"):
            lines.append(f"Captured by: {memory.get('captured_by')}")
        lines.append(f"Content: {memory.get('content') or ''}")
        lines.append(f"Tags: {', '.join(memory.get('tags', []))}")
        lines.append(f"Created: {memory.get('created_at')}")
        lines.append("---")
    return "\n".join(lines)


async def main():
    """Main entry point."""
    init_server()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
