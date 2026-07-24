#!/usr/bin/env python3
"""
Sample data import script for Open Brain.
"""
import logging
from datetime import datetime, timedelta, timezone

from src.db import queries
from src.embedder import create_embedding
from src.extractors.entities import extract_entities
from src.extractors.tagger import auto_tag

logger = logging.getLogger(__name__)


SAMPLE_MEMORIES = [
    {
        'source': 'chat',
        'content': 'Discussed the new Python async features with the team today. Really impressed by asyncio improvements in Python 3.11.',
        'importance': 0.7
    },
    {
        'source': 'note',
        'content': 'Open Brain project milestone: MCP server is now running with 6 tools. Next: entity extraction optimization.',
        'importance': 0.9
    },
    {
        'source': 'email',
        'content': 'Email from CTO about Q4 roadmap. Key priorities: API redesign, performance optimization, and security audit.',
        'importance': 0.8
    },
    {
        'source': 'chat',
        'content': 'Coffee chat with Sarah about her new React project. She mentioned using Next.js 14 with App Router.',
        'importance': 0.5
    },
    {
        'source': 'note',
        'content': 'Todo: Fix memory leak in production. Symptoms: increasing memory usage over 24h. Related to Redis cache not being cleared.',
        'importance': 0.8
    },
    {
        'source': 'meeting',
        'content': 'Weekly standup: completed PostgreSQL migration, working on Kubernetes upgrade, blocked by AWS quota.',
        'importance': 0.6
    },
    {
        'source': 'note',
        'content': 'Interesting article about Ollama embeddings. nomic-embed-text model shows great performance for semantic search.',
        'importance': 0.6
    },
    {
        'source': 'chat',
        'content': 'Debugging session with team: found the bug in the authentication flow. Was missing token refresh for OAuth.',
        'importance': 0.7
    },
    {
        'source': 'note',
        'content': 'Ideas for Open Brain v2: vector search improvements, better entity recognition, weekly auto-reports.',
        'importance': 0.7
    },
    {
        'source': 'email',
        'content': 'Invoice from AWS: $245 for December. EC2 instances and RDS are the main cost drivers.',
        'importance': 0.5
    }
]


def import_samples():
    """Import sample memories into the database."""
    print("Importing sample memories...")
    
    # Check if we can create embeddings
    try:
        test_embedding = create_embedding("test")
        print(f"✓ Embeddings working ({len(test_embedding)} dimensions)")
    except Exception as e:
        print(f"⚠ Embeddings not available: {e}")
        print("  Memories will be stored without embeddings")
    
    for i, mem in enumerate(SAMPLE_MEMORIES):
        try:
            # Extract entities
            entities = extract_entities(mem['content'])
            
            # Auto-tag
            tags = auto_tag(mem['content'], entities, mem['source'])
            
            # Create embedding
            embedding = None
            try:
                embedding = create_embedding(mem['content'])
            except Exception as exc:
                logger.warning("Could not create embedding for sample memory: %s", exc)
            
            # Store memory
            queries.insert_memory(
                source=mem['source'],
                content=mem['content'],
                embedding=embedding,
                entities=entities,
                tags=list(tags.keys()),
                tag_sources=tags,
                importance=mem['importance'],
                original_date=datetime.now(timezone.utc) - timedelta(days=i)
            )
            
            print(f"✓ Imported: {mem['content'][:50]}...")
        
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    # Print stats
    stats = queries.get_memory_stats()
    print(f"\nTotal memories in database: {stats['total']}")
    print(f"Sources: {stats['by_source']}")
    print(f"Top tags: {list(stats['top_tags'].keys())[:5]}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Import sample data')
    parser.add_argument('--count', type=int, default=10, help='Number of samples')
    args = parser.parse_args()
    
    # Import only requested count
    import_samples()
