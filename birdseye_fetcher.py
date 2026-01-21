"""
Birdseye API Integration
Fetches token data (price, mcap, liquidity, volume) from Birdseye API
Best for pump.fun and Raydium tokens on Solana
"""
from typing import Dict, Optional
import aiohttp
from loguru import logger
from datetime import datetime, timedelta


class BirdseyeFetcher:
    """Fetch token data from Birdseye API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key  # Optional - free tier works without key
        self.base_url = "https://public-api.birdeye.so"

        # Cache for token data (30-second TTL for real-time updates)
        self.cache = {}
        self.cache_ttl_seconds = 30

        logger.info("🦅 BirdseyeFetcher initialized")
        if api_key:
            logger.info("   ✅ Using API key")
        else:
            logger.info("   ⚠️  No API key - using free tier (rate limited)")

    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Get complete token data from Birdseye

        Args:
            token_address: Token mint address

        Returns:
            Dict with token data:
            {
                'token_address': str,
                'token_name': str,
                'token_symbol': str,
                'price_usd': float,
                'market_cap': float,
                'liquidity': float,
                'volume_24h': float,
                'volume_1h': float,
                'volume_5m': float,
                'price_change_5m': float,
                'price_change_1h': float,
                'price_change_24h': float,
                'holder_count': int,
                'creation_time': int (unix timestamp),
            }
        """
        try:
            # Check cache first
            cache_key = token_address
            if cache_key in self.cache:
                cached_data = self.cache[cache_key]
                cache_age = datetime.utcnow() - cached_data['timestamp']
                if cache_age.total_seconds() < self.cache_ttl_seconds:
                    logger.debug(f"   💾 Using cached Birdseye data for {token_address[:8]}")
                    return cached_data['data']

            logger.debug(f"   🦅 Fetching from Birdseye: {token_address[:8]}...")

            # Prepare headers
            headers = {
                'X-Chain': 'solana',
            }
            if self.api_key:
                headers['X-API-KEY'] = self.api_key

            # Fetch token overview (includes price, mcap, liquidity, volume)
            token_data = await self._get_token_overview(token_address, headers)

            if not token_data:
                logger.warning(f"   ⚠️ Birdseye returned no data for {token_address[:8]}")
                return None

            # Cache the result
            self.cache[cache_key] = {
                'data': token_data,
                'timestamp': datetime.utcnow()
            }

            logger.debug(f"   ✅ Birdseye: ${token_data['token_symbol']} - ${token_data['price_usd']:.8f}, mcap=${token_data['market_cap']:.0f}")

            return token_data

        except Exception as e:
            logger.error(f"❌ Birdseye API error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def _get_token_overview(self, token_address: str, headers: Dict) -> Optional[Dict]:
        """
        Get token overview from Birdseye API

        Endpoint: /defi/token_overview
        Docs: https://docs.birdeye.so/reference/get_defi-token-overview
        """
        try:
            url = f"{self.base_url}/defi/token_overview"
            params = {'address': token_address}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Birdseye API returned {resp.status}")
                        text = await resp.text()
                        logger.warning(f"   Response: {text[:200]}")
                        return None

                    data = await resp.json()

                    if not data.get('success'):
                        logger.warning(f"   ⚠️ Birdseye API returned success=false")
                        return None

                    token_info = data.get('data', {})

                    if not token_info:
                        logger.warning(f"   ⚠️ Birdseye returned empty data")
                        return None

                    # Parse token data
                    return self._parse_token_data(token_address, token_info)

        except Exception as e:
            logger.error(f"   ❌ Birdseye token_overview error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _parse_token_data(self, token_address: str, data: Dict) -> Dict:
        """Parse Birdseye API response into our format"""

        # Extract fields (handle missing data gracefully)
        return {
            'token_address': token_address,
            'token_name': data.get('name', 'Unknown'),
            'token_symbol': data.get('symbol', 'UNKNOWN'),
            'price_usd': float(data.get('price', 0)),
            'market_cap': float(data.get('mc', 0)),  # mc = market cap
            'liquidity': float(data.get('liquidity', 0)),
            'volume_24h': float(data.get('v24h', 0)),  # v24h = 24h volume
            'volume_1h': float(data.get('v1h', 0)) if 'v1h' in data else 0,
            'volume_5m': float(data.get('v5m', 0)) if 'v5m' in data else 0,
            'price_change_5m': float(data.get('price5mChangePercent', 0)) if 'price5mChangePercent' in data else 0,
            'price_change_1h': float(data.get('price1hChangePercent', 0)) if 'price1hChangePercent' in data else 0,
            'price_change_24h': float(data.get('price24hChangePercent', 0)) if 'price24hChangePercent' in data else 0,
            'holder_count': int(data.get('holder', 0)) if 'holder' in data else 0,
            'creation_time': int(data.get('creationTime', 0)) if 'creationTime' in data else 0,
            # Additional useful fields
            'real_sol_reserves': float(data.get('realSol', 0)) if 'realSol' in data else 0,
            'real_token_reserves': float(data.get('realToken', 0)) if 'realToken' in data else 0,
        }

    async def get_token_price(self, token_address: str) -> Optional[float]:
        """
        Quick method to just get current price

        Args:
            token_address: Token mint address

        Returns:
            Price in USD or None
        """
        token_data = await self.get_token_data(token_address)
        if token_data:
            return token_data.get('price_usd')
        return None

    async def get_token_security(self, token_address: str) -> Optional[Dict]:
        """
        Get token security info from Birdseye (optional - for future use)

        Endpoint: /defi/token_security
        Includes: top holders, freeze authority, mint authority, etc.
        """
        try:
            # Prepare headers
            headers = {
                'X-Chain': 'solana',
            }
            if self.api_key:
                headers['X-API-KEY'] = self.api_key

            url = f"{self.base_url}/defi/token_security"
            params = {'address': token_address}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()

                    if not data.get('success'):
                        return None

                    return data.get('data', {})

        except Exception as e:
            logger.debug(f"   Birdseye security check error: {e}")
            return None


# Global instance
_birdseye_fetcher = None

def get_birdseye_fetcher(api_key: Optional[str] = None) -> BirdseyeFetcher:
    """Get global Birdseye fetcher instance"""
    global _birdseye_fetcher
    if _birdseye_fetcher is None:
        _birdseye_fetcher = BirdseyeFetcher(api_key=api_key)
    return _birdseye_fetcher


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        fetcher = BirdseyeFetcher()

        # Test with a known pump.fun token
        test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC for testing

        print("Testing Birdseye API...")
        data = await fetcher.get_token_data(test_token)

        if data:
            print(f"\n✅ Success!")
            print(f"Symbol: {data['token_symbol']}")
            print(f"Name: {data['token_name']}")
            print(f"Price: ${data['price_usd']:.8f}")
            print(f"Market Cap: ${data['market_cap']:,.0f}")
            print(f"Liquidity: ${data['liquidity']:,.0f}")
            print(f"24h Volume: ${data['volume_24h']:,.0f}")
            print(f"Holders: {data['holder_count']:,}")
        else:
            print("❌ Failed to fetch data")

    asyncio.run(test())
