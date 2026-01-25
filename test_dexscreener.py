#!/usr/bin/env python3
"""
Quick test script to verify DexScreener API works on Railway Pro
"""
import asyncio
import aiohttp
from loguru import logger

async def test_dexscreener():
    """Test DexScreener API endpoints"""

    logger.info("=" * 80)
    logger.info("🧪 TESTING DEXSCREENER API ON RAILWAY PRO")
    logger.info("=" * 80)

    # Known token for testing (BONK - a popular Solana token)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK

    async with aiohttp.ClientSession(trust_env=True) as session:

        # Test 1: Get specific token data
        logger.info("\n📊 Test 1: Fetching specific token data (BONK)...")
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{test_token}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                logger.info(f"   Status: {resp.status}")

                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        pair = pairs[0]
                        symbol = pair.get('baseToken', {}).get('symbol', 'UNKNOWN')
                        price = pair.get('priceUsd', 0)
                        mcap = pair.get('fdv', 0)
                        volume = pair.get('volume', {}).get('h24', 0)

                        logger.info(f"   ✅ SUCCESS!")
                        logger.info(f"   Symbol: {symbol}")
                        logger.info(f"   Price: ${float(price):.8f}")
                        logger.info(f"   Market Cap: ${float(mcap):,.0f}")
                        logger.info(f"   Volume 24h: ${float(volume):,.0f}")
                    else:
                        logger.warning(f"   ⚠️  No pairs found in response")
                elif resp.status == 403:
                    logger.error(f"   ❌ FORBIDDEN - IP might be blocked")
                elif resp.status == 429:
                    logger.error(f"   ❌ RATE LIMITED - Too many requests")
                else:
                    logger.error(f"   ❌ FAILED - HTTP {resp.status}")

        except Exception as e:
            logger.error(f"   ❌ ERROR: {e}")

        # Test 2: Latest boosts endpoint
        logger.info("\n📊 Test 2: Fetching latest token boosts...")
        try:
            url = "https://api.dexscreener.com/token-boosts/latest/v1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                logger.info(f"   Status: {resp.status}")

                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        logger.info(f"   ✅ SUCCESS! Got {len(data)} boosted tokens")
                        if data:
                            first = data[0]
                            logger.info(f"   First token: {first.get('tokenAddress', 'N/A')[:12]}...")
                    else:
                        logger.info(f"   ✅ SUCCESS! Response type: {type(data)}")
                elif resp.status == 403:
                    logger.error(f"   ❌ FORBIDDEN - IP might be blocked")
                elif resp.status == 429:
                    logger.error(f"   ❌ RATE LIMITED - Too many requests")
                else:
                    logger.error(f"   ❌ FAILED - HTTP {resp.status}")

        except Exception as e:
            logger.error(f"   ❌ ERROR: {e}")

        # Test 3: Latest profiles endpoint
        logger.info("\n📊 Test 3: Fetching latest token profiles...")
        try:
            url = "https://api.dexscreener.com/token-profiles/latest/v1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                logger.info(f"   Status: {resp.status}")

                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        logger.info(f"   ✅ SUCCESS! Got {len(data)} token profiles")
                        if data:
                            first = data[0]
                            logger.info(f"   First token: {first.get('tokenAddress', 'N/A')[:12]}...")
                    else:
                        logger.info(f"   ✅ SUCCESS! Response type: {type(data)}")
                elif resp.status == 403:
                    logger.error(f"   ❌ FORBIDDEN - IP might be blocked")
                elif resp.status == 429:
                    logger.error(f"   ❌ RATE LIMITED - Too many requests")
                else:
                    logger.error(f"   ❌ FAILED - HTTP {resp.status}")

        except Exception as e:
            logger.error(f"   ❌ ERROR: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("✅ TEST COMPLETE")
    logger.info("=" * 80)
    logger.info("\nIf all tests passed with status 200, DexScreener is working!")
    logger.info("If you got 403/429 errors, the IP might still be blocked/rate limited.")

if __name__ == "__main__":
    asyncio.run(test_dexscreener())
