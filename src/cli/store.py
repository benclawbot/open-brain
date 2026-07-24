"""
Store command for CLI.
"""
import sys
from argparse import Namespace

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


def store_memory_cmd(args: Namespace) -> int:
    """Handle the store command."""
    content = args.content
    source = args.source
    user_tags = args.tag or []
    importance = args.importance
    
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
        metadata={}
    )
    
    print("Memory stored successfully!")
    print(f"ID: {memory_id}")
    print(f"Tags: {', '.join(tags.keys())}")
    
    return 0
