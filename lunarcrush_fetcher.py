"""
LunarCrush API Integration
Fetches social sentiment, trending data, and influencer metrics
"""
import os
import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from loguru import logger


class LunarCrushFetcher:
    """Fetches social sentiment and trending data from LunarCrush API"""

    def __init__(self):
        self.api_key = os.getenv('LUNARCRUSH_API_KEY')
        self.base_url = "https://lunarcrush.com/api4/public"

        if not self.api_key:
            logger.warning("⚠️ LUNARCRUSH_API_KEY not set - social sentiment disabled")

        # Cache for social data (30 minutes)
        self.cache = {}
        self.cache_ttl_minutes = 30

    async def get_coin_social_metrics(self, symbol: str) -> Optional[Dict]:
        """
        Get social metrics for a coin symbol

        Returns:
            {
                'galaxy_score': float,  # 0-100 proprietary score
                'alt_rank': int,        # Overall rank
                'sentiment': float,     # 1-5 sentiment score
                'social_volume': int,   # Mentions across platforms
                'social_volume_24h_change': float,  # % change
                'tweet_volume': int,
                'reddit_posts': int,
                'news_articles': int,
                'social_contributors': int,
                'social_dominance': float,
                'price_correlation': float,  # Social to price correlation
                'trending_rank': int,
            }
        """
        if not self.api_key:
            return None

        # Check cache
        cache_key = f"coin:{symbol}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_age = datetime.now() - cached_data['timestamp']
            if cache_age < timedelta(minutes=self.cache_ttl_minutes):
                logger.debug(f"💾 Using cached LunarCrush data for {symbol}")
                return cached_data['data']

        try:
            logger.debug(f"🔍 Fetching LunarCrush data for {symbol}")

            async with aiohttp.ClientSession() as session:
                headers = {'Authorization': f'Bearer {self.api_key}'}

                # Get coin data
                url = f"{self.base_url}/coins/{symbol}/v1"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"LunarCrush API error {response.status} for {symbol}")
                        return None

                    data = await response.json()

                    if not data or 'data' not in data:
                        logger.debug(f"No LunarCrush data for {symbol}")
                        return None

                    coin_data = data['data']

                    # Extract metrics
                    metrics = {
                        'galaxy_score': coin_data.get('galaxy_score', 0),
                        'alt_rank': coin_data.get('alt_rank', 0),
                        'sentiment': coin_data.get('sentiment', 0),
                        'social_volume': coin_data.get('social_volume', 0),
                        'social_volume_24h_change': coin_data.get('social_volume_24h_change', 0),
                        'tweet_volume': coin_data.get('tweets', 0),
                        'reddit_posts': coin_data.get('reddit_posts', 0),
                        'news_articles': coin_data.get('news', 0),
                        'social_contributors': coin_data.get('social_contributors', 0),
                        'social_dominance': coin_data.get('social_dominance', 0),
                        'price_correlation': coin_data.get('correlation_rank', 0),
                        'trending_rank': coin_data.get('trending_rank', 0) if coin_data.get('trending_rank') else 999,
                    }

                    # Cache the result
                    self.cache[cache_key] = {
                        'data': metrics,
                        'timestamp': datetime.now()
                    }

                    logger.info(f"✅ LunarCrush: {symbol} - Galaxy: {metrics['galaxy_score']}, Sentiment: {metrics['sentiment']}, Volume: {metrics['social_volume']}")

                    return metrics

        except Exception as e:
            logger.error(f"❌ Error fetching LunarCrush data: {e}")
            return None

    async def get_trending_coins(self, limit: int = 50) -> List[Dict]:
        """
        Get current trending coins

        Returns:
            List of coin symbols with metrics
        """
        if not self.api_key:
            return []

        # Check cache
        cache_key = "trending"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_age = datetime.now() - cached_data['timestamp']
            if cache_age < timedelta(minutes=self.cache_ttl_minutes):
                logger.debug("💾 Using cached trending data")
                return cached_data['data']

        try:
            logger.debug(f"🔍 Fetching top {limit} trending coins from LunarCrush")

            async with aiohttp.ClientSession() as session:
                headers = {'Authorization': f'Bearer {self.api_key}'}

                url = f"{self.base_url}/coins/list/v2?sort=galaxy_score&limit={limit}"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"LunarCrush trending API error {response.status}")
                        return []

                    data = await response.json()

                    if not data or 'data' not in data:
                        return []

                    trending = []
                    for coin in data['data']:
                        trending.append({
                            'symbol': coin.get('symbol', '').upper(),
                            'name': coin.get('name', ''),
                            'galaxy_score': coin.get('galaxy_score', 0),
                            'alt_rank': coin.get('alt_rank', 0),
                            'sentiment': coin.get('sentiment', 0),
                            'social_volume': coin.get('social_volume', 0),
                        })

                    # Cache the result
                    self.cache[cache_key] = {
                        'data': trending,
                        'timestamp': datetime.now()
                    }

                    logger.info(f"✅ Fetched {len(trending)} trending coins from LunarCrush")

                    return trending

        except Exception as e:
            logger.error(f"❌ Error fetching trending coins: {e}")
            return []

    async def is_token_trending(self, symbol: str, top_n: int = 100) -> bool:
        """Check if token is in top N trending"""
        trending = await self.get_trending_coins(limit=top_n)
        return any(coin['symbol'] == symbol.upper() for coin in trending)

    async def get_sentiment_score(self, symbol: str) -> float:
        """Get sentiment score (1-5 scale) for a token"""
        metrics = await self.get_coin_social_metrics(symbol)
        if metrics:
            return metrics.get('sentiment', 0)
        return 0

    async def get_social_volume_change(self, symbol: str) -> float:
        """Get 24h social volume change percentage"""
        metrics = await self.get_coin_social_metrics(symbol)
        if metrics:
            return metrics.get('social_volume_24h_change', 0)
        return 0


# Global instance
_lunarcrush_fetcher = None

def get_lunarcrush_fetcher() -> LunarCrushFetcher:
    """Get global LunarCrush fetcher instance"""
    global _lunarcrush_fetcher
    if _lunarcrush_fetcher is None:
        _lunarcrush_fetcher = LunarCrushFetcher()
    return _lunarcrush_fetcher


# Example usage
if __name__ == "__main__":
    async def test():
        fetcher = LunarCrushFetcher()

        # Test coin metrics
        metrics = await fetcher.get_coin_social_metrics("SOL")
        if metrics:
            print(f"Galaxy Score: {metrics['galaxy_score']}")
            print(f"Sentiment: {metrics['sentiment']}")
            print(f"Social Volume: {metrics['social_volume']}")
            print(f"24h Change: {metrics['social_volume_24h_change']}%")

        # Test trending
        trending = await fetcher.get_trending_coins(limit=10)
        print(f"\nTop 10 Trending:")
        for coin in trending[:10]:
            print(f"  {coin['symbol']}: Galaxy {coin['galaxy_score']}, Sentiment {coin['sentiment']}")

        # Test if specific token is trending
        is_trending = await fetcher.is_token_trending("BTC", top_n=50)
        print(f"\nBTC in top 50: {is_trending}")

    asyncio.run(test())
