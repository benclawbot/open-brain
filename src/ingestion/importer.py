"""
Bulk importer for Open Brain.
Handles importing data from various formats.
"""
import csv
import json
from pathlib import Path
from typing import Dict

from ..db import queries
from ..extractors.entities import extract_entities
from ..extractors.tagger import auto_tag


class Importer:
    """Bulk import data into Open Brain."""
    
    def __init__(self):
        self.stats = {
            'imported': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def import_json(
        self,
        file_path: str,
        source: str = 'import',
        content_field: str = 'content',
        **kwargs
    ) -> Dict[str, int]:
        """
        Import memories from JSON file.
        
        Args:
            file_path: Path to JSON file
            source: Source name for imported memories
            content_field: Field name containing content
            **kwargs: Additional fields for insert_memory
        
        Returns:
            Import statistics
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            items = data
        else:
            items = [data]
        
        for item in items:
            try:
                content = item.get(content_field)
                if not content:
                    self.stats['skipped'] += 1
                    continue
                
                # Extract and tag
                entities = extract_entities(content)
                tags = auto_tag(content, entities, source)
                
                # Import
                queries.insert_memory(
                    source=source,
                    content=content,
                    embedding=None,  # Generate in batch for efficiency
                    entities=entities,
                    tags=list(tags.keys()),
                    tag_sources=tags,
                    metadata=item
                )
                
                self.stats['imported'] += 1
            
            except Exception as e:
                print(f"Error importing item: {e}")
                self.stats['failed'] += 1
        
        return self.stats
    
    def import_csv(
        self,
        file_path: str,
        source: str = 'import',
        content_column: str = 'content'
    ) -> Dict[str, int]:
        """
        Import memories from CSV file.
        
        Args:
            file_path: Path to CSV file
            source: Source name for imported memories
            content_column: Column name containing content
        
        Returns:
            Import statistics
        """
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    content = row.get(content_column)
                    if not content:
                        self.stats['skipped'] += 1
                        continue
                    
                    entities = extract_entities(content)
                    tags = auto_tag(content, entities, source)
                    
                    queries.insert_memory(
                        source=source,
                        content=content,
                        entities=entities,
                        tags=list(tags.keys()),
                        tag_sources=tags,
                        metadata=dict(row)
                    )
                    
                    self.stats['imported'] += 1
                
                except Exception as e:
                    print(f"Error importing row: {e}")
                    self.stats['failed'] += 1
        
        return self.stats
    
    def import_text_lines(
        self,
        file_path: str,
        source: str = 'import'
    ) -> Dict[str, int]:
        """
        Import memories from text file (one line = one memory).
        
        Args:
            file_path: Path to text file
            source: Source name for imported memories
        
        Returns:
            Import statistics
        """
        with open(file_path, 'r') as f:
            for line in f:
                content = line.strip()
                if not content:
                    self.stats['skipped'] += 1
                    continue
                
                try:
                    entities = extract_entities(content)
                    tags = auto_tag(content, entities, source)
                    
                    queries.insert_memory(
                        source=source,
                        content=content,
                        entities=entities,
                        tags=list(tags.keys()),
                        tag_sources=tags
                    )
                    
                    self.stats['imported'] += 1
                
                except Exception as e:
                    print(f"Error importing line: {e}")
                    self.stats['failed'] += 1
        
        return self.stats


def import_file(
    file_path: str,
    source: str = 'import',
    format: str = None
) -> Dict[str, int]:
    """
    Convenience function to import a file.
    
    Args:
        file_path: Path to file
        source: Source name
        format: File format (json, csv, txt) - auto-detected if None
    
    Returns:
        Import statistics
    """
    importer = Importer()
    
    path = Path(file_path)
    
    if format is None:
        format = path.suffix.lstrip('.')
    
    if format == 'json':
        return importer.import_json(file_path, source)
    elif format == 'csv':
        return importer.import_csv(file_path, source)
    elif format == 'txt':
        return importer.import_text_lines(file_path, source)
    else:
        raise ValueError(f"Unsupported format: {format}")
