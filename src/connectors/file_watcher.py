"""
File watcher connector.
Watches a folder for new Markdown files and imports them.
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ..db.queries import insert_memory
from ..embedder import create_embedding
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class FileWatcherConnector:
    """Watch folder for new Markdown files and import them."""
    
    def __init__(self, watch_path: str, processed_path: Optional[str] = None):
        """
        Initialize file watcher.
        
        Args:
            watch_path: Path to folder to watch for new files
            processed_path: Optional path to move processed files
        """
        self.watch_path = Path(watch_path)
        self.processed_path = Path(processed_path) if processed_path else None
        self.imported_count = 0
        self.seen_files = set()
        
        # Create processed path if it doesn't exist
        if self.processed_path:
            self.processed_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize seen files
        self._scan_existing()
    
    def _scan_existing(self) -> None:
        """Scan existing files to avoid re-importing."""
        if self.watch_path.exists():
            for f in self.watch_path.glob("*.md"):
                self.seen_files.add(f.absolute())
    
    def watch(self, interval: float = 5.0, callback: Optional[Callable] = None) -> None:
        """
        Watch the folder continuously for new files.
        
        Args:
            interval: Check interval in seconds
            callback: Optional callback function to call on new files
        """
        print(f"Watching {self.watch_path} for new Markdown files...")
        
        while True:
            new_files = self._check_new_files()
            
            for file_path in new_files:
                try:
                    self.import_file(file_path)
                    if callback:
                        callback(file_path)
                except Exception as e:
                    print(f"Error importing {file_path}: {e}")
            
            time.sleep(interval)
    
    def _check_new_files(self) -> List[Path]:
        """Check for new files in the watch folder."""
        new_files = []
        
        if not self.watch_path.exists():
            return new_files
        
        for file_path in self.watch_path.glob("*.md"):
            abs_path = file_path.absolute()
            if abs_path not in self.seen_files:
                self.seen_files.add(abs_path)
                new_files.append(file_path)
        
        return new_files
    
    def import_file(self, file_path: Path) -> Dict:
        """
        Import a single Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Dictionary with import results
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract frontmatter if present
        frontmatter = {}
        body = content
        
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                body = parts[2].strip()
                
                # Parse frontmatter
                for line in frontmatter_text.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        frontmatter[key.strip()] = value.strip()
        
        # Get title from frontmatter or first heading
        title = frontmatter.get('title', '')
        if not title:
            # Try first heading
            for line in body.split('\n'):
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break
        
        # Build content for storage
        full_content = f"# {title}\n\n{body}" if title else body
        
        # Extract entities and tags
        entities = extract_entities(body)
        tags = auto_tag(body, entities, 'file')
        
        # Add custom tags from frontmatter
        if 'tags' in frontmatter:
            frontmatter_tags = frontmatter['tags'].split(',')
            tags.update({t.strip(): 'frontmatter' for t in frontmatter_tags})
        
        # Generate embedding
        embedding = None
        try:
            embedding = create_embedding(body)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")
        
        # Store memory
        memory_id = insert_memory(
            source='file',
            content=full_content,
            embedding=embedding,
            entities=entities,
            tags=list(tags.keys()),
            tag_sources=tags,
            importance=frontmatter.get('importance', 0.5),
            metadata={
                'file_path': str(file_path),
                'file_name': file_path.name,
                'title': title,
                **frontmatter
            }
        )
        
        self.imported_count += 1
        
        # Move file to processed if path is set
        if self.processed_path:
            dest = self.processed_path / file_path.name
            file_path.rename(dest)
        
        return {
            'source': 'file',
            'imported': 1,
            'memory_id': str(memory_id),
            'file': str(file_path)
        }
    
    def import_all(self) -> Dict:
        """Import all existing Markdown files in the watch folder."""
        imported = 0
        
        for file_path in self.watch_path.glob("*.md"):
            try:
                result = self.import_file(file_path)
                imported += result.get('imported', 0)
            except Exception as e:
                print(f"Error importing {file_path}: {e}")
        
        return {
            'source': 'file',
            'imported': imported,
            'total': imported
        }


def watch_folder(watch_path: str, processed_path: Optional[str] = None) -> None:
    """Convenience function to start watching a folder."""
    connector = FileWatcherConnector(watch_path, processed_path)
    connector.watch()


def import_folder(watch_path: str, processed_path: Optional[str] = None) -> Dict:
    """Convenience function to import all files in a folder."""
    connector = FileWatcherConnector(watch_path, processed_path)
    return connector.import_all()
