"""
Auto-tagging for Open Brain.
Uses keyword and pattern-based tagging layers.
"""
import os
import re
from typing import Dict, List, Optional

import yaml


class TagConfig:
    """Configuration for tagger."""
    
    _instance: Optional['TagConfig'] = None
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'config', 'settings.yaml'
            )
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.deny_list = set(config['tags'].get('deny_list', []))
        self.default_tags = config['tags'].get('default_tags', ['auto'])
    
    @classmethod
    def get_instance(cls, config_path: str = None) -> 'TagConfig':
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance


class Tagger:
    """
    Multi-layer auto-tagger for Open Brain.
    
    Layers:
    1. Keyword-based tagging
    2. Pattern-based tagging
    3. Entity-based tagging
    4. Default tags
    """
    
    def __init__(self, config_path: str = None):
        config = TagConfig.get_instance(config_path)
        
        self.deny_list = config.deny_list
        self.default_tags = config.default_tags
        
        self._initialize_keyword_patterns()
        self._initialize_pattern_rules()
    
    def _initialize_keyword_patterns(self):
        """Initialize keyword-to-tag mappings."""
        self.keyword_tags = {
            # Programming languages
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'java': 'java',
            'rust': 'rust',
            'go': 'go',
            'c++': 'cpp',
            'cpp': 'cpp',
            
            # Frameworks & Libraries
            'react': 'react',
            'vue': 'vue',
            'angular': 'angular',
            'node': 'nodejs',
            'node.js': 'nodejs',
            'django': 'django',
            'flask': 'flask',
            'fastapi': 'fastapi',
            'express': 'express',
            
            # Databases
            'postgresql': 'postgresql',
            'postgres': 'postgresql',
            'mysql': 'mysql',
            'mongodb': 'mongodb',
            'redis': 'redis',
            'elasticsearch': 'elasticsearch',
            
            # Cloud & DevOps
            'aws': 'aws',
            'azure': 'azure',
            'gcp': 'gcp',
            'kubernetes': 'kubernetes',
            'k8s': 'kubernetes',
            'docker': 'docker',
            'terraform': 'terraform',
            
            # AI/ML
            'machine learning': 'ml',
            'deep learning': 'ml',
            'neural': 'ml',
            'gpt': 'openai',
            'llm': 'llm',
            'ollama': 'ollama',
            'embedding': 'embeddings',
            
            # Project types
            'bug': 'bug',
            'fix': 'bug',
            'issue': 'issue',
            'feature': 'feature',
            'refactor': 'refactor',
            'test': 'testing',
            'deployment': 'deployment',
            'deploy': 'deployment',
            
            # Communication
            'meeting': 'meeting',
            'call': 'meeting',
            'email': 'email',
            'slack': 'slack',
            'discord': 'discord',
            
            # Personal
            'personal': 'personal',
            'work': 'work',
            'important': 'important',
            'urgent': 'urgent',
            'idea': 'idea',
            'note': 'note',
            'question': 'question',
        }
    
    def _initialize_pattern_rules(self):
        """Initialize regex pattern rules."""
        self.pattern_tags = [
            # Code patterns
            (r'def\s+\w+\s*\(', 'function'),
            (r'class\s+\w+', 'class'),
            (r'import\s+\w+', 'import'),
            (r'from\s+\w+\s+import', 'import'),
            (r'async\s+def', 'async'),
            (r'@pytest\.fixture', 'pytest'),
            
            # URLs and links
            (r'https?://', 'url'),
            (r'github\.com', 'github'),
            
            # Error patterns
            (r'error|fail|exception', 'error', re.IGNORECASE),
            (r'warning|warn', 'warning', re.IGNORECASE),
            
            # Question patterns
            (r'\?$', 'question'),
            (r'how\s+to', 'how-to'),
            (r'why\s+', 'question'),
            (r'what\s+is', 'question'),
            
            # Task patterns
            (r'todo:|fixme:|hack:', 'todo'),
            (r'\[x\]', 'completed'),
            (r'\[ \]', 'pending'),
        ]
    
    def tag(
        self,
        text: str,
        entities: Optional[Dict[str, List[str]]] = None,
        source: Optional[str] = None,
        user_tags: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Apply auto-tagging to text.
        
        Args:
            text: Text to tag
            entities: Optional extracted entities
            source: Source of the content
            user_tags: User-provided tags (highest priority)
        
        Returns:
            Dictionary mapping tags to their sources
        """
        tags: Dict[str, str] = {}
        text_lower = text.lower()
        
        # Layer 1: Keyword-based tagging
        for keyword, tag in self.keyword_tags.items():
            if keyword in text_lower:
                if tag not in self.deny_list:
                    tags[tag] = 'keyword'
        
        # Layer 2: Pattern-based tagging
        for pattern_args in self.pattern_tags:
            pattern = pattern_args[0]
            tag = pattern_args[1]
            flags = pattern_args[2] if len(pattern_args) > 2 else 0
            
            if re.search(pattern, text, flags):
                if tag not in self.deny_list:
                    tags[tag] = 'pattern'
        
        # Layer 3: Entity-based tagging
        if entities:
            # Technology entities
            tech = entities.get('technologies', [])
            for t in tech:
                if t not in self.deny_list:
                    tags[t] = 'entity'
            
            # Hashtags from content
            hashtags = entities.get('hashtags', [])
            for h in hashtags:
                tag = h.lstrip('#')
                if tag not in self.deny_list:
                    tags[tag] = 'entity'
            
            # People → tag as 'people'
            if entities.get('people'):
                tags['people'] = 'entity'
        
        # Layer 4: Source-based tagging
        if source:
            tags[source] = 'source'
        
        # Layer 5: User tags (highest priority)
        if user_tags:
            for tag in user_tags:
                if tag not in self.deny_list:
                    tags[tag] = 'user'
        
        # Layer 6: Default tags
        for tag in self.default_tags:
            if tag not in tags and tag not in self.deny_list:
                tags[tag] = 'default'
        
        return tags
    
    def extract_tags(
        self,
        text: str,
        entities: Optional[Dict[str, List[str]]] = None,
        source: Optional[str] = None,
        user_tags: Optional[List[str]] = None
    ) -> List[str]:
        """
        Extract just the tag names.
        
        Args:
            text: Text to tag
            entities: Optional extracted entities
            source: Source of the content
            user_tags: User-provided tags
        
        Returns:
            List of tag names
        """
        tag_sources = self.tag(text, entities, source, user_tags)
        return list(tag_sources.keys())


def get_tagger(config_path: str = None) -> Tagger:
    """Get a tagger instance."""
    return Tagger(config_path)


def auto_tag(
    text: str,
    entities: Optional[Dict[str, List[str]]] = None,
    source: Optional[str] = None,
    user_tags: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Auto-tag text and return tags with their sources.
    
    Args:
        text: Text to tag
        entities: Optional extracted entities
        source: Source of the content
        user_tags: User-provided tags (highest priority)
    
    Returns:
        Dictionary mapping tags to their sources (e.g., {'python': 'keyword', 'important': 'user'})
    """
    return get_tagger().tag(text, entities, source, user_tags)
