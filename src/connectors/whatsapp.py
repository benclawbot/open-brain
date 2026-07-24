"""
WhatsApp export connector.
Imports messages from WhatsApp chat export.
"""
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class WhatsAppConnector:
    """Import messages from WhatsApp chat export."""
    
    # Pattern to parse WhatsApp message format
    MESSAGE_PATTERN = re.compile(
        r'(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*'
        r'([^:]+):\s*(.+)'
    )
    
    def __init__(self, export_path: str):
        """
        Initialize with path to WhatsApp chat export.
        
        Args:
            export_path: Path to the WhatsApp chat text file
        """
        self.export_path = Path(export_path)
        self.imported_count = 0
    
    def import_chat(self, limit: Optional[int] = None) -> Dict:
        """
        Import messages from the WhatsApp chat export.
        
        Args:
            limit: Maximum number of messages to import
            
        Returns:
            Dictionary with import statistics
        """
        if not self.export_path.exists():
            raise FileNotFoundError(f"Export file not found: {self.export_path}")
        
        messages = []
        with open(self.export_path, 'r', encoding='utf-8') as f:
            for line in f:
                parsed = self._parse_message(line)
                if parsed:
                    messages.append(parsed)
        
        if limit:
            messages = messages[:limit]
        
        for msg in messages:
            self._process_message(msg)
        
        return {
            'source': 'whatsapp',
            'imported': self.imported_count,
            'total_processed': len(messages)
        }
    
    def _parse_message(self, line: str) -> Optional[Dict]:
        """Parse a single WhatsApp message line."""
        match = self.MESSAGE_PATTERN.match(line.strip())
        if not match:
            return None
        
        date_str, sender, text = match.groups()
        
        # Try to parse the date
        try:
            # Handle both formats: MM/DD/YY, HH:MM and MM/DD/YYYY, HH:MM AM/PM
            date_str = date_str.replace(',', '')
            if ',' not in date_str:
                # Already in simple format
                pass
            parsed_date = datetime.strptime(
                date_str,
                '%m/%d/%Y %I:%M %p',
            ).replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
        except ValueError:
            try:
                parsed_date = datetime.strptime(
                    date_str,
                    '%m/%d/%y %H:%M',
                ).replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
            except ValueError:
                parsed_date = datetime.now(timezone.utc)
        
        return {
            'date': parsed_date,
            'sender': sender.strip(),
            'text': text.strip()
        }
    
    def _process_message(self, msg: Dict) -> None:
        """Process a single message and store it."""
        text = msg['text']
        if not text.strip():
            return
        
        # Build content with context
        content = f"[WhatsApp] {msg['sender']}: {text}"
        
        # Extract entities and tags
        entities = extract_entities(text)
        tags = auto_tag(content, entities, 'whatsapp')
        
        # Generate embedding
        embedding = None
        try:
            embedding = create_embedding(text)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")
        
        # Store memory
        memory_id = insert_memory(
            source='whatsapp',
            content=content,
            embedding=embedding,
            entities=entities,
            tags=list(tags.keys()),
            tag_sources=tags,
            importance=0.5,
            metadata={
                'whatsapp_date': msg['date'].isoformat(),
                'whatsapp_sender': msg['sender']
            }
        )
        
        if memory_id:
            self.imported_count += 1


def import_whatsapp(export_path: str, limit: Optional[int] = None) -> Dict:
    """Convenience function to import WhatsApp export."""
    connector = WhatsAppConnector(export_path)
    return connector.import_chat(limit)
