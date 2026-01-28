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
import feedparser
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import numpy as np


# RSS sources (crypto/Solana-focused, high-signal)
# Expanded from 7 to 17 sources for better coverage
RSS_SOURCES = [
    # Major crypto news
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/feed",
    "https://decrypt.co/feed",
    "https://www.coingecko.com/en/rss",

    # DeFi/Protocol focused
    "https://www.thedefiant.io/feed",  # DeFi trends
    "https://thedefiant.io/api/feed",  # Alternative DeFi feed

    # Solana ecosystem
    "https://solana.com/blog/rss.xml",  # Official Solana blog
    "https://solana.news/feed/",  # Solana-specific news

    # Research & Analytics
    "https://messari.io/rss",  # Deep crypto research
    "https://research.binance.com/en/rss",  # Binance research

    # Web3/Blockchain Tech
    "https://www.alchemy.com/blog/rss.xml",  # Web3 infrastructure
    "https://blog.chain.link/feed/",  # Oracles/DeFi tech

    # Community/Culture
    "https://www.bankless.com/feed",  # Bankless media
    "https://newsletter.banklesshq.com/feed",  # Bankless newsletter

    # NFT/Gaming (trending narratives)
    "https://nftnow.com/feed/",  # NFT news
    "https://decrypt.co/feed/nft",  # Decrypt NFT section
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
        self.narrative_history = []  # Track narrative evolution over time
        self.max_history = 24  # Keep last 24 updates (6 hours @ 15min intervals)

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
                min_topic_size=2,  # Minimum for small article sets
                nr_topics="auto",  # Auto-reduce similar topics
                verbose=False  # Reduce log spam
            )
            logger.info("✅ BERTopic model initialized")

    async def fetch_rss_feeds(self) -> List[str]:
        """
        Fetch articles from all RSS sources concurrently

        Returns:
            List of article texts (title + summary)
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)  # Only last 24h for relevance

        async def fetch_single_feed(url: str) -> List[str]:
            """Fetch a single RSS feed with timeout"""
            articles = []
            try:
                loop = asyncio.get_event_loop()
                feed = await asyncio.wait_for(
                    loop.run_in_executor(None, feedparser.parse, url),
                    timeout=15  # 15 second timeout per feed
                )

                for entry in feed.entries:
                    # Get publish date - be lenient, don't skip dateless articles
                    pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                    if pub_date:
                        try:
                            pub_dt = datetime(*pub_date[:6])
                            if pub_dt <= cutoff:
                                continue
                        except (TypeError, ValueError):
                            pass  # Bad date format, include article anyway

                    link = getattr(entry, 'link', None) or entry.get('id', '')
                    if link and link in self.article_cache:
                        continue

                    # Extract text (title + summary/content)
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")

                    if not summary:
                        content_list = entry.get("content", [])
                        if content_list:
                            summary = content_list[0].get("value", "")

                    text = f"{title} {summary}".strip()
                    if len(text) < 20:
                        continue

                    articles.append(text)
                    if link:
                        self.article_cache[link] = datetime.utcnow()

                return articles

            except asyncio.TimeoutError:
                logger.debug(f"   ⏱️  RSS feed timed out: {url}")
                return []
            except Exception as e:
                logger.debug(f"   ⚠️  RSS feed failed: {url} ({e})")
                return []

        # Fetch all feeds concurrently
        logger.info(f"   📡 Fetching {len(RSS_SOURCES)} RSS feeds concurrently...")
        results = await asyncio.gather(*[fetch_single_feed(url) for url in RSS_SOURCES])

        new_articles = []
        feeds_ok = 0
        for result in results:
            if result:
                feeds_ok += 1
                new_articles.extend(result)

        logger.info(f"   📰 Fetched {len(new_articles)} articles from {feeds_ok}/{len(RSS_SOURCES)} working feeds")
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

            if len(articles) < 3:
                if self.current_topics is None:
                    logger.warning(f"   ⚠️ FIRST NARRATIVE UPDATE: Only {len(articles)} articles found (need 3+). RSS feeds may be failing or empty.")
                else:
                    logger.warning(f"   ⚠️ Too few articles ({len(articles)}), keeping previous narratives")
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

            # Store in history for momentum tracking
            self.narrative_history.append({
                'timestamp': datetime.utcnow(),
                'topics': result['topics'],
                'article_count': result['article_count']
            })

            # Trim history to max size
            if len(self.narrative_history) > self.max_history:
                self.narrative_history = self.narrative_history[-self.max_history:]

            return result

        except Exception as e:
            logger.error(f"   ❌ Error updating narratives: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_narrative_momentum(self, topic_words: List[str]) -> Tuple[float, str]:
        """
        Calculate momentum score for a narrative based on history

        Args:
            topic_words: List of words defining the narrative

        Returns:
            Tuple of (momentum_multiplier, reason)
            - momentum_multiplier: 1.0-1.5x boost for trending narratives
            - reason: Explanation
        """
        if len(self.narrative_history) < 3:
            return 1.0, "Insufficient history"

        try:
            # Count appearances of similar topics in recent history
            topic_text = ' '.join(topic_words).lower()
            recent_appearances = 0
            old_appearances = 0

            # Check last 3 updates (recent)
            for update in self.narrative_history[-3:]:
                for topic in update['topics']:
                    hist_topic = ' '.join(topic['words']).lower()
                    # Simple overlap check (can be improved with embeddings)
                    overlap = len(set(topic_text.split()) & set(hist_topic.split()))
                    if overlap >= 2:  # At least 2 words in common
                        recent_appearances += 1
                        break

            # Check older updates (3-6 updates back)
            if len(self.narrative_history) >= 6:
                for update in self.narrative_history[-6:-3]:
                    for topic in update['topics']:
                        hist_topic = ' '.join(topic['words']).lower()
                        overlap = len(set(topic_text.split()) & set(hist_topic.split()))
                        if overlap >= 2:
                            old_appearances += 1
                            break

            # Calculate momentum
            if recent_appearances >= 3:
                if old_appearances == 0:
                    # New and gaining traction
                    return 1.5, "Emerging hot narrative (new trend)"
                elif recent_appearances > old_appearances:
                    # Growing
                    return 1.3, "Growing narrative (momentum up)"
                else:
                    # Sustained
                    return 1.2, "Sustained narrative (consistent)"
            elif recent_appearances >= 2:
                return 1.1, "Recent narrative (warming up)"
            else:
                return 1.0, "New narrative (first appearance)"

        except Exception as e:
            logger.error(f"Error calculating momentum: {e}")
            return 1.0, "Error calculating momentum"

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

            # Award base points based on similarity
            base_points = 0
            reason = ""

            if max_sim > 0.7:
                # Very strong match
                base_points = 25
                reason = f"Strong match to '{best_topic['name']}' narrative"
            elif max_sim > 0.5:
                # Strong match
                base_points = 20
                reason = f"Matches '{best_topic['name']}' narrative"
            elif max_sim > 0.4:
                # Medium match
                base_points = 15
                reason = f"Weak match to '{best_topic['name']}' narrative"
            elif max_sim > 0.3:
                # Weak match
                base_points = 10
                reason = f"Partial match to '{best_topic['name']}'"
            else:
                reason = f"No strong narrative match (max sim: {max_sim:.2f})"

            # Apply momentum multiplier if we have a match
            points = base_points
            if base_points > 0 and best_topic:
                momentum_mult, momentum_reason = self.get_narrative_momentum(best_topic['words'])
                if momentum_mult > 1.0:
                    points = int(base_points * momentum_mult)
                    reason = f"{reason} + {momentum_reason}"
                    logger.info(f"   📈 Momentum boost: {base_points} → {points} pts ({momentum_mult:.1f}x)")

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
        self._loop_count = 0
        logger.info(f"🔄 Starting narrative update loop (every {self.update_interval}s)")
        logger.info(f"   📡 RSS sources configured: {len(RSS_SOURCES)}")

        while self.is_running:
            try:
                self._loop_count += 1
                logger.info(f"\n📰 [Narrative Loop #{self._loop_count}] Updating from RSS feeds...")
                await self.update_narratives()

                # Log trending narratives with momentum
                trending = self.get_trending_narratives()
                if trending:
                    logger.info(f"\n🔥 TOP TRENDING NARRATIVES (with momentum):")
                    for i, narrative in enumerate(trending[:3], 1):
                        logger.info(
                            f"   {i}. {narrative['name']} - "
                            f"Score: {narrative['trending_score']:.1f} "
                            f"({narrative['doc_count']} docs × {narrative['momentum_score']:.1f}x momentum) "
                            f"- {narrative['momentum_reason']}"
                        )

                logger.info(f"✅ Narrative update complete. Next update in {self.update_interval}s\n")

            except Exception as e:
                logger.error(f"❌ Narrative loop error: {e}")

            await asyncio.sleep(self.update_interval)

    def get_trending_narratives(self) -> List[Dict]:
        """
        Get narratives ranked by momentum/trending score

        Returns:
            List of narratives with momentum scores
        """
        if not self.current_topics or not self.current_topics.get('topics'):
            return []

        trending = []
        for topic in self.current_topics['topics']:
            momentum_mult, momentum_reason = self.get_narrative_momentum(topic['words'])
            trending.append({
                'name': topic['name'],
                'words': topic['words'],
                'doc_count': topic['doc_count'],
                'momentum_score': momentum_mult,
                'momentum_reason': momentum_reason,
                'trending_score': topic['doc_count'] * momentum_mult  # Combined score
            })

        # Sort by trending score
        trending.sort(key=lambda x: x['trending_score'], reverse=True)
        return trending

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
