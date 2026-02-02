"""
Narrative Detector - Identify trending narratives and themes
ENHANCED: Now supports both static narratives and real-time RSS-based detection
"""
from typing import Dict, List, Set, Optional
from datetime import datetime, timedelta
from loguru import logger
import config

# Import realtime detector
try:
    from trackers.realtime_narrative_detector import get_narrative_detector
    REALTIME_AVAILABLE = True
    logger.info("✅ Realtime narrative detector loaded (RSS + BERTopic)")
except ImportError as e:
    REALTIME_AVAILABLE = False
    logger.warning(f"⚠️  Realtime narrative detector not available: {e}")


class NarrativeDetector:
    """
    Detects and scores narrative trends in token names and descriptions

    Two modes:
    1. Static: Uses predefined HOT_NARRATIVES (fast, low resource)
    2. Realtime: Uses RSS + BERTopic for emerging narratives (more accurate)
    """

    def __init__(self):
        self.narratives = config.HOT_NARRATIVES
        self.narrative_tracker: Dict[str, List[datetime]] = {}  # narrative -> [timestamps]
        self.realtime_detector = None
        self.use_realtime = getattr(config, 'ENABLE_REALTIME_NARRATIVES', False)

    async def start(self):
        """Initialize narrative detector"""
        self.use_static = getattr(config, 'ENABLE_STATIC_NARRATIVES', True)
        active_count = sum(1 for n in self.narratives.values() if n.get('active', False))

        logger.info(f"✅ Narrative Detector initialized")
        logger.info(f"   📊 Static narratives: {'ENABLED' if self.use_static else 'DISABLED'} ({active_count} configured)")

        # Initialize realtime detector if enabled
        if self.use_realtime and REALTIME_AVAILABLE:
            logger.info(f"   🔄 Enabling real-time RSS narrative detection")
            self.realtime_detector = get_narrative_detector(
                update_interval=getattr(config, 'NARRATIVE_UPDATE_INTERVAL', 900)  # 15 min default
            )
            # Start background loop
            import asyncio
            asyncio.create_task(self.realtime_detector.narrative_loop())
            logger.info(f"   ✅ Real-time narrative loop started (RSS + BERTopic)")
        elif self.use_realtime and not REALTIME_AVAILABLE:
            logger.error(f"   ❌ REAL-TIME NARRATIVES BROKEN: Dependencies missing!")
            logger.error(f"      feedparser/bertopic/sentence-transformers not installed")
            logger.error(f"      Run: pip install feedparser bertopic sentence-transformers")
            logger.error(f"      ⚠️  Narrative scoring will be {'ZERO' if not self.use_static else 'static-only'}")
        elif not self.use_realtime:
            logger.info(f"   ℹ️  Real-time narratives disabled in config")

        if not self.use_static and not (self.use_realtime and REALTIME_AVAILABLE):
            logger.warning(f"   ⚠️  WARNING: Both static and real-time narratives are inactive!")
            logger.warning(f"      Narrative score will always be 0 until real-time dependencies are installed")

        return True
    
    def analyze_token(self, symbol: str, name: str = '', description: str = '') -> Dict:
        """
        Analyze token for narrative matches
        Returns matched narratives and scoring data

        Uses real-time RSS detection if enabled, otherwise static narratives
        """
        # Try realtime detection first (if enabled and available)
        realtime_score = 0
        realtime_reason = ""

        if self.use_realtime and self.realtime_detector:
            realtime_score, realtime_reason = self.realtime_detector.get_narrative_boost(
                name, symbol, description
            )

        # Static narrative analysis (if enabled)
        combined_text = f"{symbol} {name} {description}".lower()
        matched_narratives = []
        static_score = 0

        use_static = getattr(self, 'use_static', True)  # Default True for backwards compat
        if use_static:
            # Check static narratives
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

            # Calculate static score
            if matched_narratives:
                best_narrative = max(matched_narratives, key=lambda x: x['weight'])

                from config import WEIGHTS

                static_score += WEIGHTS['narrative_hot']

                if len(matched_narratives) > 1:
                    static_score += WEIGHTS['narrative_multiple']

                if self._is_narrative_fresh(best_narrative['name']):
                    static_score += WEIGHTS['narrative_fresh']

        # Use max of realtime or static (realtime usually wins)
        final_score = max(realtime_score, static_score)

        return {
            'has_narrative': final_score > 0,
            'narratives': matched_narratives,
            'primary_narrative': matched_narratives[0]['name'] if matched_narratives else None,
            'score': min(final_score, 7),  # Cap at 7 points (100-point budget)
            'realtime_score': realtime_score,
            'static_score': static_score,
            'realtime_reason': realtime_reason if realtime_score > 0 else None
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
