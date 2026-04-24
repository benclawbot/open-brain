"""
Trend detection for Open Brain.
Analyzes memory patterns over time.
"""
import sys
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import queries


class TrendAnalyzer:
    """Analyze trends in stored memories."""
    
    def __init__(self, weeks: int = 4):
        self.weeks = weeks
    
    def get_tag_trends(self) -> Dict[str, Dict[str, int]]:
        """
        Get tag trends over the configured time period.
        
        Returns:
            Dictionary with current and previous period counts
        """
        current_period = queries.get_trending_tags(weeks=self.weeks, limit=20)
        previous_period = queries.get_trending_tags(
            weeks=self.weeks * 2,
            limit=20
        )
        
        # Calculate trends
        trends = {}
        all_tags = set(current_period.keys()) | set(previous_period.keys())
        
        for tag in all_tags:
            current = current_period.get(tag, 0)
            previous = previous_period.get(tag, 0)
            
            # Calculate change
            if previous == 0:
                change = current  # New tag
            else:
                change = current - previous
            
            trends[tag] = {
                'current': current,
                'previous': previous,
                'change': change,
                'trend': 'up' if change > 0 else ('down' if change < 0 else 'stable')
            }
        
        return trends
    
    def get_top_trending(self, limit: int = 10) -> List[Dict]:
        """Get the top trending tags."""
        trends = self.get_tag_trends()
        
        # Sort by change
        sorted_trends = sorted(
            trends.items(),
            key=lambda x: x[1]['change'],
            reverse=True
        )
        
        return [
            {'tag': tag, **data}
            for tag, data in sorted_trends[:limit]
        ]
    
    def get_source_distribution(self) -> Dict[str, int]:
        """Get memory distribution by source."""
        stats = queries.get_memory_stats()
        return stats.get('by_source', {})
    
    def get_activity_timeline(self, days: int = 30) -> Dict[str, int]:
        """
        Get daily memory counts for the last N days.
        
        Returns:
            Dictionary mapping dates to counts
        """
        timeline = {}
        
        with queries.get_db_cursor() as cursor:
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM memory
                WHERE created_at >= CURRENT_DATE - (%s * INTERVAL '1 day')
                GROUP BY DATE(created_at)
                ORDER BY date
            """, (days,))
            
            for row in cursor.fetchall():
                timeline[str(row['date'])] = row['count']
        
        return timeline
    
    def get_peak_activity_hours(self) -> Dict[int, int]:
        """Get memory counts by hour of day."""
        with queries.get_db_cursor() as cursor:
            cursor.execute("""
                SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count
                FROM memory
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY EXTRACT(HOUR FROM created_at)
                ORDER BY hour
            """)
            
            return {int(row['hour']): row['count'] for row in cursor.fetchall()}
    
    def get_entity_trends(self) -> Dict[str, Dict[str, int]]:
        """Get trends for extracted entities."""
        trends = {}
        
        with queries.get_db_cursor() as cursor:
            cursor.execute("""
                SELECT entities, created_at
                FROM memory
                WHERE created_at >= CURRENT_DATE - (%s * INTERVAL '1 week')
            """, (self.weeks,))
            
            # Count entity occurrences
            entity_counts: Dict[str, int] = {}
            
            for row in cursor.fetchall():
                entities = row['entities']
                if isinstance(entities, str):
                    import json
                    entities = json.loads(entities)
                
                for entity_type, entity_list in entities.items():
                    if isinstance(entity_list, list):
                        for entity in entity_list:
                            key = f"{entity_type}:{entity}"
                            entity_counts[key] = entity_counts.get(key, 0) + 1
            
            # Convert to trend format
            for entity, count in sorted(
                entity_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]:
                entity_type, name = entity.split(':', 1)
                if entity_type not in trends:
                    trends[entity_type] = {}
                trends[entity_type][name] = count
        
        return trends
    
    def get_weekly_summary(self) -> Dict:
        """Get a summary for the current week."""
        stats = queries.get_memory_stats()
        
        return {
            'total_this_week': stats.get('this_week', 0),
            'total_this_month': stats.get('this_month', 0),
            'total_all_time': stats.get('total', 0),
            'top_tags': list(stats.get('top_tags', {}).keys())[:10],
            'sources': stats.get('by_source', {}),
            'trending': self.get_top_trending(5)
        }


def get_trend_analyzer(weeks: int = 4) -> TrendAnalyzer:
    """Get a trend analyzer instance."""
    return TrendAnalyzer(weeks)
