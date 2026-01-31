"""
SOL Price Utility - Fetches and caches live SOL/USD price
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from loguru import logger

# Cache
_sol_price_cache = {
    'price': 150.0,  # Default fallback
    'last_updated': None,
    'cache_duration': timedelta(minutes=5)
}


async def get_sol_price() -> float:
    """
    Get current SOL price in USD.
    Caches for 5 minutes to avoid rate limits.
    Falls back to last known price on error.
    """
    global _sol_price_cache

    now = datetime.utcnow()

    # Return cached price if still valid
    if _sol_price_cache['last_updated']:
        age = now - _sol_price_cache['last_updated']
        if age < _sol_price_cache['cache_duration']:
            return _sol_price_cache['price']

    # Fetch fresh price
    try:
        async with aiohttp.ClientSession() as session:
            # Use CoinGecko simple price API (free, no key needed)
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('solana', {}).get('usd', 0)
                    if price > 0:
                        _sol_price_cache['price'] = price
                        _sol_price_cache['last_updated'] = now
                        logger.debug(f"💰 SOL price updated: ${price:.2f}")
                        return price
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch SOL price: {e}")

    # Return cached/default on error
    return _sol_price_cache['price']


def get_sol_price_sync() -> float:
    """
    Synchronous version - returns cached price only.
    Use get_sol_price() for async code.
    """
    return _sol_price_cache['price']
