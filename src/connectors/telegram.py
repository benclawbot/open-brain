"""
Telegram export connector.
Imports messages from Telegram JSON export.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class TelegramConnector:
    """Import messages from Telegram export (JSON format)."""
    
    def __init__(self, export_path: str):
        """
        Initialize with path to Telegram export directory.
        
        Args:
            export_path: Path to the unzipped Telegram export folder
        """
        self.export_path = Path(export_path)
        self.imported_count = 0
    
    def find_messages_file(self) -> Optional[Path]:
        """Find the messages JSON file in the export."""
        # Telegram usually saves as result.json or messages.json
        possible_files = [
            self.export_path / "result.json",
            self.export_path / "messages.json",
            self.export_path / "messages.json",
        ]
        
        for f in possible_files:
            if f.exists():
                return f
        
        # Try to find any JSON file
        for f in self.export_path.glob("*.json"):
            return f
        
        return None
    
    def import_messages(self, limit: Optional[int] = None) -> Dict:
        """
        Import all messages from the Telegram export.
        
        Args:
            limit: Maximum number of messages to import
            
        Returns:
            Dictionary with import statistics
        """
        messages_file = self.find_messages_file()
        if not messages_file:
            raise FileNotFoundError(f"No messages file found in {self.export_path}")
        
        with open(messages_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        messages = data.get('messages', data if isinstance(data, list) else [])
        
        if limit:
            messages = messages[:limit]
        
        for msg in messages:
            self._process_message(msg)
        
        return {
            'source': 'telegram',
            'imported': self.imported_count,
            'total_processed': len(messages)
        }
    
    def _process_message(self, msg: Dict) -> None:
        """Process a single message and store it."""
        # Extract text content
        text = msg.get('text', '')
        if not text or isinstance(text, list):
            # Handle rich text (list of text and entities)
            if isinstance(text, list):
                text = ''.join([t.get('text', '') if isinstance(t, dict) else str(t) for t in text])
            else:
                return  # Skip media-only messages
        
        if not text.strip():
            return
        
        # Extract metadata
        date = msg.get('date', '')
        from_name = msg.get('from', 'Unknown')
        
        # Build content with context
        content = f"[Telegram] {from_name}: {text}"
        
        # Extract entities and tags
        entities = extract_entities(text)
        tags = auto_tag(content, entities, 'telegram')
        
        # Generate embedding
        embedding = None
        try:
            embedding = create_embedding(text)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")
        
        # Store memory
        memory_id = insert_memory(
            source='telegram',
            content=content,
            embedding=embedding,
            entities=entities,
            tags=list(tags.keys()),
            tag_sources=tags,
            importance=0.5,
            metadata={
                'telegram_date': date,
                'telegram_from': from_name,
                'message_type': msg.get('type', 'message')
            }
        )
        
        if memory_id:
            self.imported_count += 1
    
    def get_chats(self) -> List[Dict]:
        """Get list of chats in the export."""
        result_file = self.export_path / "result.json"
        if not result_file.exists():
            return []
        
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('chats', {}).get('list', [])


def import_telegram(export_path: str, limit: Optional[int] = None) -> Dict:
    """Convenience function to import Telegram export."""
    connector = TelegramConnector(export_path)
    return connector.import_messages(limit)
