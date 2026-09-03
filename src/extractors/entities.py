"""
Entity extraction for Open Brain.
Uses basic NLP for named entity recognition.
"""
import re
from typing import Dict, List, Set

import nltk
from nltk import pos_tag, word_tokenize
from nltk.chunk import ne_chunk
from nltk.tree import Tree


# Download required NLTK data
def _ensure_nltk_data():
    """Ensure required NLTK data is downloaded.

    NLTK 3.8.2+ renamed the core English tokenization, POS tagging, and
    NE chunking resources: ``punkt`` -> ``punkt_tab``,
    ``averaged_perceptron_tagger`` -> ``averaged_perceptron_tagger_eng``,
    ``maxent_ne_chunker`` -> ``maxent_ne_chunker_tab``. The runtime call
    sites (``word_tokenize``, ``pos_tag``, ``ne_chunk``) require the new
    names. We look for the new names first and fall back to the old ones
    so the code works on NLTK versions before and after the rename.
    """
    pairs = [
        ('tokenizers/punkt_tab', 'punkt_tab'),
        ('tokenizers/punkt', 'punkt'),
        ('taggers/averaged_perceptron_tagger_eng', 'averaged_perceptron_tagger_eng'),
        ('taggers/averaged_perceptron_tagger', 'averaged_perceptron_tagger'),
        ('chunkers/maxent_ne_chunker_tab', 'maxent_ne_chunker_tab'),
        ('chunkers/maxent_ne_chunker', 'maxent_ne_chunker'),
        ('corpora/words', 'words'),
    ]
    for lookup, pkg in pairs:
        try:
            nltk.data.find(lookup)
        except LookupError:
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                # Network or disk failure is non-fatal; the chunker/tokenizer
                # will raise a clearer error at the call site if the data
                # is truly missing.
                continue


_ensure_nltk_data()


class EntityExtractor:
    """Extract entities from text using NLTK."""
    
    # Common entity patterns
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    URL_PATTERN = re.compile(r'https?://[^\s]+')
    PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
    DATE_PATTERN = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b')
    HASHTAG_PATTERN = re.compile(r'#\w+')
    MENTION_PATTERN = re.compile(r'@\w+')
    
    def __init__(self):
        self._initialize_entity_types()
    
    def _initialize_entity_types(self):
        """Initialize common entity keywords."""
        # Technology
        self.tech_keywords = {
            'python', 'javascript', 'java', 'rust', 'go', 'typescript',
            'react', 'vue', 'angular', 'node', 'docker', 'kubernetes',
            'aws', 'gcp', 'azure', 'postgresql', 'mysql', 'mongodb',
            'redis', 'elasticsearch', 'kafka', 'graphql', 'rest',
            'api', 'sdk', 'cli', 'ui', 'ux', 'html', 'css'
        }
        
        # People roles
        self.people_roles = {
            'ceo', 'cto', 'cfo', 'coo', 'president', 'founder',
            'developer', 'engineer', 'designer', 'manager', 'director',
            'vp', 'head', 'lead', 'senior', 'junior', 'intern'
        }
        
        # Project types
        self.project_keywords = {
            'project', 'feature', 'bug', 'task', 'issue', 'pr',
            'release', 'deploy', 'milestone', 'sprint', 'backlog'
        }
    
    def extract(self, text: str) -> Dict[str, List[str]]:
        """
        Extract all entities from text.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary mapping entity types to lists of entities
        """
        entities: Dict[str, Set[str]] = {
            'emails': set(),
            'urls': set(),
            'phones': set(),
            'dates': set(),
            'hashtags': set(),
            'mentions': set(),
            'people': set(),
            'organizations': set(),
            'locations': set(),
            'technologies': set(),
            'projects': set()
        }
        
        # Pattern-based extraction
        entities['emails'].update(self.EMAIL_PATTERN.findall(text))
        entities['urls'].update(self.URL_PATTERN.findall(text))
        entities['phones'].update(self.PHONE_PATTERN.findall(text))
        entities['dates'].update(self.DATE_PATTERN.findall(text))
        entities['hashtags'].update(self.HASHTAG_PATTERN.findall(text))
        entities['mentions'].update(self.MENTION_PATTERN.findall(text))
        
        # NLTK-based NER
        try:
            tokens = word_tokenize(text)
            tagged = pos_tag(tokens)
            tree = ne_chunk(tagged)
            
            for subtree in tree:
                if isinstance(subtree, Tree):
                    entity_name = ' '.join([word for word, _ in subtree.leaves()])
                    entity_type = subtree.label()
                    
                    if entity_type == 'PERSON':
                        entities['people'].add(entity_name)
                    elif entity_type == 'ORGANIZATION':
                        entities['organizations'].add(entity_name)
                    elif entity_type == 'GPE':
                        entities['locations'].add(entity_name)
        except Exception as e:
            import sys
            print(f"Warning: NER extraction failed: {e}", file=sys.stderr)
        
        # Keyword-based extraction
        words = set(text.lower().split())
        
        # Technologies
        entities['technologies'].update(words & self.tech_keywords)
        
        # Projects
        entities['projects'].update(words & self.project_keywords)
        
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in entities.items()}


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Convenience function to extract entities."""
    extractor = EntityExtractor()
    return extractor.extract(text)


def extract_people(text: str) -> List[str]:
    """Extract only people entities."""
    entities = extract_entities(text)
    return entities.get('people', [])


def extract_technologies(text: str) -> List[str]:
    """Extract only technology entities."""
    entities = extract_entities(text)
    return entities.get('technologies', [])
