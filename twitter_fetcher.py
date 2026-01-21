"""
Twitter API Integration (Free Tier Optimized)
Fetches tweet mentions and engagement data for conviction scoring

Free Tier Limits: 1,500 tweets/month (~50/day)
Strategy: Smart caching + only check high-conviction tokens
"""
import os
import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from loguru import logger


class TwitterFetcher:
    """Fetches Twitter mentions and engagement data (free tier optimized)"""

    def __init__(self):
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.base_url = "https://api.twitter.com/2"

        if not self.bearer_token:
            logger.warning("⚠️ TWITTER_BEARER_TOKEN not set - Twitter sentiment disabled")

        # Aggressive caching (2 hours) to conserve API calls
        self.cache = {}
        self.cache_ttl_minutes = 120  # 2 hours

        # Rate limiting tracker
        self.daily_calls = 0
        self.daily_limit = 45  # Stay under 50/day to be safe
        self.last_reset = datetime.now()

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        # Reset counter if new day
        if (datetime.now() - self.last_reset).days >= 1:
            self.daily_calls = 0
            self.last_reset = datetime.now()

        if self.daily_calls >= self.daily_limit:
            logger.warning(f"🚨 Twitter API daily limit reached ({self.daily_calls}/{self.daily_limit})")
            return False

        return True

    async def get_token_twitter_metrics(
        self,
        symbol: str,
        ca: str = None,
        max_results: int = 10
    ) -> Optional[Dict]:
        """
        Get Twitter metrics for a token (optimized for free tier)

        Args:
            symbol: Token symbol (e.g., "DOGE")
            ca: Contract address (optional, for more precise search)
            max_results: Number of tweets to fetch (default 10, max 100)

        Returns:
            {
                'mention_count': int,        # Number of tweets mentioning token
                'total_engagement': int,     # likes + retweets + replies
                'avg_engagement': float,     # Average per tweet
                'top_tweet_likes': int,      # Most liked tweet
                'recent_growth': bool,       # Mentions growing recently
                'has_buzz': bool,            # High engagement detected
            }
        """
        if not self.bearer_token:
            return None

        # Check rate limit
        if not self._check_rate_limit():
            return None

        # Check cache
        cache_key = f"token:{symbol}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_age = datetime.now() - cached_data['timestamp']
            if cache_age < timedelta(minutes=self.cache_ttl_minutes):
                logger.debug(f"💾 Using cached Twitter data for {symbol}")
                return cached_data['data']

        try:
            logger.debug(f"🐦 Fetching Twitter data for ${symbol}")

            # Build search query
            # Search for: token symbol + crypto keywords (filter noise)
            query = f"${symbol} (crypto OR token OR solana) -is:retweet"

            # If we have contract address, include it (more precise)
            if ca:
                query = f"({query}) OR {ca[:8]}"  # Search first 8 chars of CA

            async with aiohttp.ClientSession() as session:
                headers = {'Authorization': f'Bearer {self.bearer_token}'}

                # Recent search endpoint (last 7 days)
                url = f"{self.base_url}/tweets/search/recent"
                params = {
                    'query': query,
                    'max_results': max_results,
                    'tweet.fields': 'public_metrics,created_at',
                }

                async with session.get(url, headers=headers, params=params) as response:
                    # Increment call counter
                    self.daily_calls += 1
                    logger.debug(f"📊 Twitter API calls today: {self.daily_calls}/{self.daily_limit}")

                    if response.status == 429:  # Rate limited
                        logger.warning("⚠️ Twitter API rate limit hit")
                        return None

                    if response.status != 200:
                        logger.warning(f"Twitter API error {response.status} for ${symbol}")
                        return None

                    data = await response.json()

                    if not data or 'data' not in data:
                        logger.debug(f"No Twitter mentions for ${symbol}")
                        return self._empty_metrics()

                    tweets = data['data']
                    mention_count = len(tweets)

                    # Calculate engagement metrics
                    total_likes = 0
                    total_retweets = 0
                    total_replies = 0
                    top_tweet_likes = 0

                    for tweet in tweets:
                        metrics = tweet.get('public_metrics', {})
                        likes = metrics.get('like_count', 0)
                        retweets = metrics.get('retweet_count', 0)
                        replies = metrics.get('reply_count', 0)

                        total_likes += likes
                        total_retweets += retweets
                        total_replies += replies

                        if likes > top_tweet_likes:
                            top_tweet_likes = likes

                    total_engagement = total_likes + total_retweets + total_replies
                    avg_engagement = total_engagement / mention_count if mention_count > 0 else 0

                    # Determine if there's "buzz"
                    has_buzz = (
                        mention_count >= 5 and  # At least 5 mentions
                        avg_engagement >= 10    # Average 10+ engagements per tweet
                    ) or top_tweet_likes >= 100  # OR one tweet with 100+ likes

                    # Check growth (compare recent vs all tweets in time window)
                    # For simplicity, consider "recent growth" if we found mentions
                    recent_growth = mention_count >= 3

                    metrics = {
                        'mention_count': mention_count,
                        'total_engagement': total_engagement,
                        'avg_engagement': round(avg_engagement, 2),
                        'top_tweet_likes': top_tweet_likes,
                        'total_likes': total_likes,
                        'total_retweets': total_retweets,
                        'total_replies': total_replies,
                        'recent_growth': recent_growth,
                        'has_buzz': has_buzz,
                    }

                    # Cache the result
                    self.cache[cache_key] = {
                        'data': metrics,
                        'timestamp': datetime.now()
                    }

                    logger.info(
                        f"✅ Twitter: ${symbol} - "
                        f"{mention_count} mentions, "
                        f"{total_engagement} engagement, "
                        f"buzz: {has_buzz}"
                    )

                    return metrics

        except Exception as e:
            logger.error(f"❌ Error fetching Twitter data: {e}")
            return None

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'mention_count': 0,
            'total_engagement': 0,
            'avg_engagement': 0,
            'top_tweet_likes': 0,
            'total_likes': 0,
            'total_retweets': 0,
            'total_replies': 0,
            'recent_growth': False,
            'has_buzz': False,
        }

    async def check_token_buzz(self, symbol: str, ca: str = None) -> bool:
        """
        Quick check if token has Twitter buzz
        Returns True if significant engagement detected
        """
        metrics = await self.get_token_twitter_metrics(symbol, ca)
        if metrics:
            return metrics.get('has_buzz', False)
        return False

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status"""
        return {
            'daily_calls': self.daily_calls,
            'daily_limit': self.daily_limit,
            'remaining': self.daily_limit - self.daily_calls,
            'reset_at': self.last_reset + timedelta(days=1)
        }


# Global instance
_twitter_fetcher = None

def get_twitter_fetcher() -> TwitterFetcher:
    """Get global Twitter fetcher instance"""
    global _twitter_fetcher
    if _twitter_fetcher is None:
        _twitter_fetcher = TwitterFetcher()
    return _twitter_fetcher


# Example usage
if __name__ == "__main__":
    async def test():
        fetcher = TwitterFetcher()

        # Test token metrics
        metrics = await fetcher.get_token_twitter_metrics("BONK")
        if metrics:
            print(f"Mentions: {metrics['mention_count']}")
            print(f"Engagement: {metrics['total_engagement']}")
            print(f"Avg Engagement: {metrics['avg_engagement']}")
            print(f"Has Buzz: {metrics['has_buzz']}")

        # Check rate limit
        status = fetcher.get_rate_limit_status()
        print(f"\nRate Limit: {status['remaining']}/{status['daily_limit']} remaining")

    asyncio.run(test())
