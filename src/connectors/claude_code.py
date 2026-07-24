"""
Claude Code session log connector.
Imports conversations from Claude Code session logs.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class ClaudeCodeConnector:
    """Import sessions from Claude Code session logs."""
    
    def __init__(self, sessions_path: str):
        """
        Initialize with path to Claude Code sessions directory.
        
        Args:
            sessions_path: Path to Claude Code session logs
        """
        self.sessions_path = Path(sessions_path)
        self.imported_count = 0
    
    def find_sessions(self) -> List[Path]:
        """Find all session JSON files."""
        session_files = []
        
        # Look for common session file patterns
        patterns = [
            "*.json",
            "sessions/*.json",
            "**/*.json"
        ]
        
        for pattern in patterns:
            session_files.extend(self.sessions_path.glob(pattern))
        
        # Filter to likely session files
        return [f for f in session_files if f.is_file()]
    
    def import_sessions(self, limit: Optional[int] = None) -> Dict:
        """
        Import all Claude Code sessions.
        
        Args:
            limit: Maximum number of sessions to import
            
        Returns:
            Dictionary with import statistics
        """
        session_files = self.find_sessions()
        
        if not session_files:
            return {
                'source': 'claude_code',
                'imported': 0,
                'total_processed': 0,
                'error': 'No session files found'
            }
        
        if limit:
            session_files = session_files[:limit]
        
        for session_file in session_files:
            try:
                self._import_session(session_file)
            except Exception as e:
                print(f"Error importing session {session_file}: {e}")
        
        return {
            'source': 'claude_code',
            'imported': self.imported_count,
            'total_processed': len(session_files)
        }
    
    def _import_session(self, session_file: Path) -> None:
        """Import a single Claude Code session file."""
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different session formats
        messages = data.get('messages', [])
        if not messages and isinstance(data, list):
            messages = data
        
        # Get session metadata
        session_id = data.get('id', session_file.stem)
        session_name = data.get('name', session_file.stem)
        created_at = data.get('created_at', data.get('timestamp', ''))
        
        for msg in messages:
            self._process_message(msg, session_id, session_name, created_at)
    
    def _process_message(
        self, 
        msg: Dict, 
        session_id: str, 
        session_name: str,
        created_at: str
    ) -> None:
        """Process a single message and store it."""
        # Extract content based on message format
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        
        # Handle different content formats
        if isinstance(content, list):
            # Claude Code often uses content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    text_parts.append(block.get('text', ''))
                else:
                    text_parts.append(str(block))
            text = ' '.join(text_parts)
        else:
            text = str(content) if content else ''
        
        if not text.strip():
            return
        
        # Build content with context
        content_str = f"[Claude Code - {role}] {text}"
        
        # Extract entities and tags
        entities = extract_entities(text)
        tags = auto_tag(content_str, entities, 'claude_code')
        
        # Generate embedding
        embedding = None
        try:
            embedding = create_embedding(text)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")
        
        # Store memory
        memory_id = insert_memory(
            source='claude_code',
            content=content_str,
            embedding=embedding,
            entities=entities,
            tags=list(tags.keys()),
            tag_sources=tags,
            importance=0.6,  # Claude Code sessions are usually important
            metadata={
                'session_id': session_id,
                'session_name': session_name,
                'role': role,
                'created_at': created_at
            }
        )
        
        if memory_id:
            self.imported_count += 1


def import_claude_code(sessions_path: str, limit: Optional[int] = None) -> Dict:
    """Convenience function to import Claude Code sessions."""
    connector = ClaudeCodeConnector(sessions_path)
    return connector.import_sessions(limit)
