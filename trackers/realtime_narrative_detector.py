"""
Real-time Narrative Detection using RSS + BERTopic
Detects emerging crypto narratives from news sources without expensive APIs

Features:
- Fetches from 7+ crypto RSS feeds every 15-30 minutes
- Uses BERTopic to cluster emerging narratives
- Awards 0-25 bonus points for tokens matching hot narratives
- Self-contained, runs as background task
- Railway-optimized (low CPU/RAM)

Based on Grok recommendations for better early detection.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import feedparser
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import numpy as np


# RSS sources (crypto/Solana-focused, high-signal)
RSS_SOURCES = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/feed",
    "https://www.coingecko.com/en/rss",
    "https://decrypt.co/feed",
    "https://solana.com/blog/rss.xml",  # Solana-specific
    "https://www.thedefiant.io/feed",  # DeFi focused
]


class RealtimeNarrativeDetector:
    """
    Detects emerging crypto narratives from RSS feeds using BERTopic

    Updates every 15-30 minutes (configurable)
    Awards bonus points for tokens matching hot narratives
    """

    def __init__(self, update_interval_seconds: int = 900):
        """
        Initialize narrative detector

        Args:
            update_interval_seconds: How often to update narratives (default: 900 = 15min)
        """
        self.update_interval = update_interval_seconds
        self.article_cache = {}  # URL → timestamp to avoid duplicates
        self.current_topics = None  # Latest BERTopic results
        self.topic_model = None  # BERTopic instance (load once)
        self.embedder = None  # SentenceTransformer model
        self.last_update = None
        self.is_running = False

        logger.info(f"📰 RealtimeNarrativeDetector initialized (update every {update_interval_seconds}s)")

    def initialize_models(self):
        """
        Initialize BERTopic and embedding models (load once)
        Lazy loading to avoid startup delays
        """
        if self.embedder is None:
            logger.info("🔄 Loading SentenceTransformer (all-MiniLM-L6-v2)...")
            self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("✅ Embedder loaded")

        if self.topic_model is None:
            logger.info("🔄 Initializing BERTopic model...")
            self.topic_model = BERTopic(
                embedding_model=self.embedder,
                min_topic_size=3,  # Small for emerging topics (lowered from 5)
                nr_topics="auto",  # Auto-reduce similar topics
                verbose=False  # Reduce log spam
            )
            logger.info("✅ BERTopic model initialized")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_rss_feeds(self) -> List[str]:
        """
        Fetch articles from all RSS sources

        Returns:
            List of article texts (title + summary)
        """
        new_articles = []
        cutoff = datetime.utcnow() - timedelta(hours=24)  # Only last 24h for relevance

        for url in RSS_SOURCES:
            try:
                logger.debug(f"   📡 Fetching RSS: {url}")

                # feedparser is blocking, run in executor
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, url)

                for entry in feed.entries:
                    # Get publish date
                    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                    if not pub_date:
                        continue

                    pub_dt = datetime(*pub_date[:6])

                    # Skip old or duplicate articles
                    if pub_dt <= cutoff:
                        continue
                    if entry.link in self.article_cache:
                        continue

                    # Extract text (title + summary/content)
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")

                    # Try content if no summary
                    if not summary:
                        content_list = entry.get("content", [])
                        if content_list:
                            summary = content_list[0].get("value", "")

                    text = f"{title} {summary}".strip()
                    if len(text) < 20:  # Skip very short articles
                        continue

                    new_articles.append(text)
                    self.article_cache[entry.link] = pub_dt
                    logger.debug(f"      ✅ New article: {title[:50]}...")

            except Exception as e:
                logger.warning(f"   ⚠️  Failed to fetch {url}: {e}")
                continue

        logger.info(f"   📰 Fetched {len(new_articles)} new articles from {len(RSS_SOURCES)} sources")
        return new_articles

    async def update_narratives(self) -> Optional[Dict]:
        """
        Update narrative topics from latest RSS articles

        Returns:
            Dict with top topics and metadata
        """
        try:
            # Initialize models on first run
            self.initialize_models()

            # Fetch latest articles
            articles = await self.fetch_rss_feeds()

            if len(articles) < 5:
                logger.warning(f"   ⚠️  Too few articles ({len(articles)}), skipping update")
                return None

            logger.info(f"   🔄 Running BERTopic on {len(articles)} articles...")

            # Run BERTopic in executor (CPU intensive)
            loop = asyncio.get_event_loop()

            # Fit or update model
            if self.current_topics is None:
                # First run: full fit
                topics, probs = await loop.run_in_executor(
                    None,
                    self.topic_model.fit_transform,
                    articles
                )
            else:
                # Incremental update
                topics, probs = await loop.run_in_executor(
                    None,
                    self.topic_model.transform,
                    articles
                )

            # Get top topics
            topic_info = self.topic_model.get_topic_info()

            # Filter out outlier topic (-1)
            topic_info = topic_info[topic_info['Topic'] != -1]

            # Get top 5 emerging topics
            top_topics = topic_info.head(5)

            # Build result
            result = {
                'topics': [],
                'updated_at': datetime.utcnow(),
                'article_count': len(articles),
                'topic_count': len(top_topics)
            }

            logger.info(f"   ✅ Detected {len(top_topics)} emerging narratives:")
            for idx, row in top_topics.iterrows():
                topic_id = row['Topic']
                topic_name = row['Name']
                doc_count = row['Count']

                # Get top words for this topic
                topic_words = self.topic_model.get_topic(topic_id)
                if topic_words:
                    top_words = [word for word, _ in topic_words[:5]]
                else:
                    top_words = []

                result['topics'].append({
                    'id': topic_id,
                    'name': topic_name,
                    'words': top_words,
                    'doc_count': doc_count
                })

                logger.info(f"      📌 Topic {topic_id}: {topic_name} ({doc_count} docs) - {', '.join(top_words)}")

            self.current_topics = result
            self.last_update = datetime.utcnow()

            return result

        except Exception as e:
            logger.error(f"   ❌ Error updating narratives: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_narrative_boost(
        self,
        token_name: str,
        token_symbol: str,
        token_description: str = ""
    ) -> Tuple[int, str]:
        """
        Calculate narrative boost for a token

        Args:
            token_name: Token name (e.g., "AI Doge")
            token_symbol: Token symbol (e.g., "AIDOGE")
            token_description: Optional description

        Returns:
            Tuple of (points, reason)
            - points: 0-25 bonus points
            - reason: Explanation (e.g., "Matches 'AI agents' narrative")
        """
        if not self.current_topics or not self.current_topics.get('topics'):
            return 0, "No narratives loaded yet"

        if not self.embedder:
            return 0, "Embedder not initialized"

        try:
            # Combine token metadata into searchable text
            token_text = f"{token_name} {token_symbol} {token_description or ''}".lower()

            # Embed token text
            token_emb = self.embedder.encode([token_text])

            # Check similarity to each top topic
            max_sim = 0
            best_topic = None

            for topic in self.current_topics['topics']:
                # Get topic words
                topic_words = ' '.join(topic['words'])
                topic_emb = self.embedder.encode([topic_words])

                # Cosine similarity
                sim = np.dot(token_emb[0], topic_emb[0]) / (
                    np.linalg.norm(token_emb[0]) * np.linalg.norm(topic_emb[0])
                )

                if sim > max_sim:
                    max_sim = sim
                    best_topic = topic

            # Award points based on similarity
            points = 0
            reason = ""

            if max_sim > 0.7:
                # Very strong match
                points = 25
                reason = f"Strong match to '{best_topic['name']}' narrative"
            elif max_sim > 0.5:
                # Strong match
                points = 20
                reason = f"Matches '{best_topic['name']}' narrative"
            elif max_sim > 0.4:
                # Medium match
                points = 15
                reason = f"Weak match to '{best_topic['name']}' narrative"
            elif max_sim > 0.3:
                # Weak match
                points = 10
                reason = f"Partial match to '{best_topic['name']}'"
            else:
                reason = f"No strong narrative match (max sim: {max_sim:.2f})"

            if points > 0:
                logger.info(f"   🎯 Narrative boost: ${token_symbol} +{points} pts ({reason})")

            return points, reason

        except Exception as e:
            logger.error(f"   ❌ Error calculating narrative boost: {e}")
            return 0, f"Error: {e}"

    async def narrative_loop(self):
        """
        Main loop: Update narratives every X seconds
        Runs in background as asyncio task
        """
        self.is_running = True
        logger.info(f"🔄 Starting narrative update loop (every {self.update_interval}s)")

        while self.is_running:
            try:
                logger.info("\n📰 Updating narratives from RSS feeds...")
                await self.update_narratives()
                logger.info(f"✅ Narrative update complete. Next update in {self.update_interval}s\n")

            except Exception as e:
                logger.error(f"❌ Narrative loop error: {e}")

            await asyncio.sleep(self.update_interval)

    def stop(self):
        """Stop the narrative loop"""
        self.is_running = False
        logger.info("🛑 Stopping narrative update loop")


# Singleton instance
_detector_instance: Optional[RealtimeNarrativeDetector] = None


def get_narrative_detector(update_interval: int = 900) -> RealtimeNarrativeDetector:
    """
    Get or create singleton narrative detector

    Args:
        update_interval: Update interval in seconds (default: 900 = 15min)

    Returns:
        RealtimeNarrativeDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = RealtimeNarrativeDetector(update_interval)
    return _detector_instance


# Example usage
if __name__ == "__main__":
    async def test():
        detector = get_narrative_detector(update_interval=60)  # 1 min for testing

        # Start background loop
        loop_task = asyncio.create_task(detector.narrative_loop())

        # Wait for first update
        await asyncio.sleep(65)

        # Test scoring
        points, reason = detector.get_narrative_boost(
            "AI Doge",
            "AIDOGE",
            "An AI-powered meme token on Solana"
        )
        print(f"\nTest Result: {points} points - {reason}")

        # Stop
        detector.stop()
        await loop_task

    asyncio.run(test())
