"""
Gmail takeout connector.
Imports emails from Gmail takeout export.
"""
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class GmailConnector:
    """Import emails from Gmail takeout export."""
    
    def __init__(self, export_path: str):
        """
        Initialize with path to Gmail takeout export.
        
        Args:
            export_path: Path to the unzipped Gmail takeout folder or MBOX file
        """
        self.export_path = Path(export_path)
        self.imported_count = 0
    
    def find_mbox_files(self) -> List[Path]:
        """Find all MBOX files in the export."""
        mbox_files = []
        
        # Look for MBOX files
        mbox_files.extend(self.export_path.glob("*.mbox"))
        mbox_files.extend(self.export_path.glob("**/*.mbox"))
        
        # Also check for JSON exports
        json_files = []
        json_files.extend(self.export_path.glob("*.json"))
        json_files.extend(self.export_path.glob("**/*.json"))
        
        return mbox_files, json_files
    
    def import_emails(self, limit: Optional[int] = None) -> Dict:
        """
        Import emails from Gmail takeout.
        
        Args:
            limit: Maximum number of emails to import
            
        Returns:
            Dictionary with import statistics
        """
        mbox_files, json_files = self.find_mbox_files()
        
        total_imported = 0
        
        # Import JSON files first (simpler format)
        for json_file in json_files:
            try:
                result = self._import_json(json_file, limit - total_imported if limit else None)
                total_imported += result.get('imported', 0)
            except Exception as e:
                print(f"Error importing {json_file}: {e}")
        
        # Then import MBOX files
        for mbox_file in mbox_files:
            try:
                result = self._import_mbox(mbox_file, limit - total_imported if limit else None)
                total_imported += result.get('imported', 0)
            except Exception as e:
                print(f"Error importing {mbox_file}: {e}")
        
        return {
            'source': 'gmail',
            'imported': total_imported,
            'total_processed': total_imported
        }
    
    def _import_json(self, json_file: Path, limit: Optional[int] = None) -> Dict:
        """Import emails from JSON format."""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        messages = data.get('messages', data if isinstance(data, list) else [])
        
        if limit:
            messages = messages[:limit]
        
        for msg in messages:
            self._process_email(msg)
        
        return {
            'imported': self.imported_count,
            'source': 'json'
        }
    
    def _import_mbox(self, mbox_file: Path, limit: Optional[int] = None) -> Dict:
        """Import emails from MBOX format (simplified parser)."""
        imported = 0
        
        with open(mbox_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Simple MBOX parsing - split by From lines
        messages = content.split('\nFrom ')
        
        for msg_text in messages[1:]:  # Skip first empty split
            if limit and imported >= limit:
                break
            
            try:
                self._parse_mbox_message(msg_text)
                imported += 1
            except Exception as e:
                print(f"Error parsing message: {e}")
        
        return {'imported': imported}
    
    def _parse_mbox_message(self, msg_text: str) -> None:
        """Parse a single MBOX message."""
        lines = msg_text.split('\n')
        
        # Extract headers
        headers = {}
        body_lines = []
        in_body = False
        
        for line in lines:
            if not in_body and ':' in line:
                key, value = line.split(':', 1)
                headers[key.lower()] = value.strip()
            elif not in_body and line == '':
                in_body = True
            elif in_body:
                body_lines.append(line)
        
        # Extract key fields
        subject = headers.get('subject', 'No Subject')
        from_addr = headers.get('from', 'Unknown')
        date_str = headers.get('date', '')
        body = '\n'.join(body_lines)
        
        # Create content
        content = f"[Email] From: {from_addr}\nSubject: {subject}\n\n{body}"
        
        # Process the email
        self._process_email_content(content, from_addr, subject, date_str)
    
    def _process_email(
        self, 
        msg: Dict,
        from_addr: Optional[str] = None,
        subject: Optional[str] = None,
        date_str: Optional[str] = None
    ) -> None:
        """Process a single email and store it."""
        # Extract email fields
        if from_addr is None:
            from_addr = msg.get('from', {}).get('name', msg.get('from', 'Unknown'))
        if subject is None:
            subject = msg.get('subject', 'No Subject')
        if date_str is None:
            date_str = msg.get('date', '')
        
        payload = msg.get('payload', {})
        headers = {h['name']: h['value'] for h in payload.get('headers', [])}
        
        # Get body
        body = ''
        parts = payload.get('parts', [])
        for part in parts:
            if part.get('mimeType') == 'text/plain':
                body = part.get('body', {}).get('data', '')
                # Decode base64 if needed
                if body:
                    import base64
                    try:
                        body = base64.urlsafe_b64decode(body).decode('utf-8')
                    except:
                        pass
                break
        
        if not body:
            body = payload.get('body', {}).get('data', '')
        
        # Build content
        content = f"[Email] From: {from_addr}\nSubject: {subject}\n\n{body}"
        
        self._process_email_content(content, from_addr, subject, date_str)
    
    def _process_email_content(
        self, 
        content: str, 
        from_addr: str, 
        subject: str, 
        date_str: str
    ) -> None:
        """Store email as a memory."""
        # Extract entities and tags
        entities = extract_entities(content)
        tags = auto_tag(content, entities, 'gmail')
        
        # Generate embedding
        embedding = None
        try:
            embedding = create_embedding(content)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")
        
        # Store memory
        memory_id = insert_memory(
            source='gmail',
            content=content,
            embedding=embedding,
            entities=entities,
            tags=list(tags.keys()),
            tag_sources=tags,
            importance=0.5,
            metadata={
                'email_from': from_addr,
                'email_subject': subject,
                'email_date': date_str
            }
        )
        
        if memory_id:
            self.imported_count += 1


def import_gmail(export_path: str, limit: Optional[int] = None) -> Dict:
    """Convenience function to import Gmail export."""
    connector = GmailConnector(export_path)
    return connector.import_emails(limit)

