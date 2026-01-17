"""
Narrative Detector - Identify trending narratives and themes
"""
from typing import Dict, List, Set
from datetime import datetime, timedelta
from loguru import logger
import config


class NarrativeDetector:
    """Detects and scores narrative trends in token names and descriptions"""
    
    def __init__(self):
        self.narratives = config.HOT_NARRATIVES
        self.narrative_tracker: Dict[str, List[datetime]] = {}  # narrative -> [timestamps]
        
    async def start(self):
        """Initialize narrative detector"""
        active_count = sum(1 for n in self.narratives.values() if n.get('active', False))
        logger.info(f"✅ Narrative Detector initialized")
        logger.info(f"   📊 Tracking {active_count} narratives")
        return True
    
    def analyze_token(self, symbol: str, name: str = '', description: str = '') -> Dict:
        """
        Analyze token for narrative matches
        Returns matched narratives and scoring data
        """
        # Combine all text for analysis
        combined_text = f"{symbol} {name} {description}".lower()
        
        matched_narratives = []
        total_score = 0
        
        # Check each narrative
        for narrative_name, narrative_data in self.narratives.items():
            if not narrative_data.get('active', False):
                continue
            
            keywords = narrative_data.get('keywords', [])
            weight = narrative_data.get('weight', 1.0)
            
            # Check for keyword matches
            matches = [kw for kw in keywords if kw in combined_text]
            
            if matches:
                matched_narratives.append({
                    'name': narrative_name,
                    'keywords_matched': matches,
                    'weight': weight
                })
                
                # Track this narrative mention
                if narrative_name not in self.narrative_tracker:
                    self.narrative_tracker[narrative_name] = []
                self.narrative_tracker[narrative_name].append(datetime.utcnow())
        
        # Calculate score
        if matched_narratives:
            # Get the best matching narrative
            best_narrative = max(matched_narratives, key=lambda x: x['weight'])
            
            from config import WEIGHTS
            
            # Base score for hot narrative
            total_score += WEIGHTS['narrative_hot']
            
            # Bonus for multiple narratives
            if len(matched_narratives) > 1:
                total_score += WEIGHTS['narrative_multiple']
            
            # Check if this is a fresh narrative (< 48h of activity)
            if self._is_narrative_fresh(best_narrative['name']):
                total_score += WEIGHTS['narrative_fresh']
        
        return {
            'has_narrative': len(matched_narratives) > 0,
            'narratives': matched_narratives,
            'primary_narrative': matched_narratives[0]['name'] if matched_narratives else None,
            'score': min(total_score, 35)  # Cap at 35 points
        }
    
    def _is_narrative_fresh(self, narrative_name: str) -> bool:
        """Check if a narrative is less than 48 hours old"""
        if narrative_name not in self.narrative_tracker:
            return True
        
        mentions = self.narrative_tracker[narrative_name]
        if not mentions:
            return True
        
        # Check oldest mention
        oldest_mention = min(mentions)
        age_hours = (datetime.utcnow() - oldest_mention).total_seconds() / 3600
        
        return age_hours < 48
    
    def get_trending_narratives(self, hours: int = 24) -> List[Dict]:
        """Get narratives with most activity in recent hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        trending = []
        
        for narrative_name, mentions in self.narrative_tracker.items():
            recent_mentions = [m for m in mentions if m > cutoff]
            
            if recent_mentions:
                trending.append({
                    'name': narrative_name,
                    'mentions': len(recent_mentions),
                    'weight': self.narratives[narrative_name].get('weight', 1.0)
                })
        
        # Sort by mentions (descending)
        trending.sort(key=lambda x: x['mentions'], reverse=True)
        
        return trending
    
    def cleanup_old_data(self):
        """Remove narrative mentions older than 7 days"""
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        for narrative_name in list(self.narrative_tracker.keys()):
            self.narrative_tracker[narrative_name] = [
                m for m in self.narrative_tracker[narrative_name]
                if m > cutoff
            ]
            
            if not self.narrative_tracker[narrative_name]:
                del self.narrative_tracker[narrative_name]
    
    def update_narrative(self, narrative_name: str, active: bool = None, weight: float = None):
        """Dynamically update a narrative's status or weight"""
        if narrative_name in self.narratives:
            if active is not None:
                self.narratives[narrative_name]['active'] = active
                logger.info(f"📝 Narrative '{narrative_name}' set to {'active' if active else 'inactive'}")
            
            if weight is not None:
                self.narratives[narrative_name]['weight'] = weight
                logger.info(f"📝 Narrative '{narrative_name}' weight set to {weight}")
    
    def add_narrative(self, name: str, keywords: List[str], weight: float = 1.0):
        """Add a new narrative to track"""
        self.narratives[name] = {
            'keywords': keywords,
            'weight': weight,
            'active': True
        }
        logger.info(f"➕ Added new narrative: {name} (weight: {weight})")
