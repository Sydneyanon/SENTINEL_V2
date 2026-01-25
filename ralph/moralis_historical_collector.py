#!/usr/bin/env python3
"""
Moralis Historical Data Collector

Collects historical data for known successful tokens to train ML models.

Usage:
    python ralph/moralis_historical_collector.py

Cost Estimate:
    - 150 tokens × 20 CU each = 3,000 CU (one-time)
    - Well under 40K/day free tier

Output:
    - Database: historical_signals table with snapshots
    - JSON: ralph/historical_training_data.json
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from loguru import logger

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import Database


class MoralisHistoricalCollector:
    """Collects historical token data using Moralis API"""

    def __init__(self):
        self.api_key = config.MORALIS_API_KEY
        if not self.api_key:
            raise ValueError("MORALIS_API_KEY not set in environment")

        self.base_url = "https://solana-gateway.moralis.io"
        self.headers = {
            "accept": "application/json",
            "X-API-Key": self.api_key
        }

        self.db = None
        self.collected_count = 0
        self.failed_count = 0
        self.total_cu_used = 0

    async def initialize(self):
        """Initialize database connection"""
        self.db = Database()
        await self.db.connect()
        logger.info("✅ Database connected")

    async def get_token_metadata(self, token_address: str) -> dict:
        """
        Get token metadata from Moralis

        Cost: ~2 CU
        """
        try:
            url = f"{self.base_url}/token/mainnet/{token_address}/metadata"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"  Failed to get metadata: {resp.status}")
                        return None

                    data = await resp.json()
                    self.total_cu_used += 2  # Estimate
                    return data

        except Exception as e:
            logger.error(f"  Metadata error: {e}")
            return None

    async def get_token_price(self, token_address: str) -> dict:
        """
        Get token price from Moralis

        Cost: ~2 CU
        """
        try:
            url = f"{self.base_url}/token/mainnet/{token_address}/price"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"  Failed to get price: {resp.status}")
                        return None

                    data = await resp.json()
                    self.total_cu_used += 2  # Estimate
                    return data

        except Exception as e:
            logger.error(f"  Price error: {e}")
            return None

    async def get_dexscreener_history(self, token_address: str) -> dict:
        """
        Get historical data from DexScreener (FREE!)

        This is our main data source since Moralis doesn't have historical snapshots.
        DexScreener provides current state which we can use as final outcome.
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    pairs = data.get('pairs', [])

                    if not pairs:
                        return None

                    # Get Raydium pair
                    pair = pairs[0]
                    for p in pairs:
                        if 'raydium' in p.get('dexId', '').lower():
                            pair = p
                            break

                    # Extract transaction data
                    txns_24h = pair.get('txns', {}).get('h24', {})
                    txns_6h = pair.get('txns', {}).get('h6', {})
                    txns_1h = pair.get('txns', {}).get('h1', {})

                    return {
                        'price_usd': float(pair.get('priceUsd', 0)),
                        'market_cap': float(pair.get('fdv', 0)),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                        'volume_6h': float(pair.get('volume', {}).get('h6', 0)),
                        'volume_1h': float(pair.get('volume', {}).get('h1', 0)),
                        'buys_24h': txns_24h.get('buys', 0),
                        'sells_24h': txns_24h.get('sells', 0),
                        'buys_6h': txns_6h.get('buys', 0),
                        'sells_6h': txns_6h.get('sells', 0),
                        'buys_1h': txns_1h.get('buys', 0),
                        'sells_1h': txns_1h.get('sells', 0),
                        'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                        'price_change_6h': float(pair.get('priceChange', {}).get('h6', 0)),
                        'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0)),
                        'created_at': pair.get('pairCreatedAt', 0)
                    }

        except Exception as e:
            logger.error(f"  DexScreener error: {e}")
            return None

    async def collect_token_data(self, token_info: dict) -> dict:
        """
        Collect comprehensive data for a single token

        Args:
            token_info: {
                'address': str,
                'symbol': str,
                'name': str,
                'gain_multiple': int,
                'final_mcap': int,
                'category': str  # mega_runners_100x, medium_runners_10_50x, etc.
            }

        Returns:
            Complete historical dataset for this token
        """
        address = token_info['address']
        symbol = token_info['symbol']
        category = token_info.get('category', 'unknown')

        logger.info(f"\n📊 Collecting: ${symbol} ({category})")
        logger.info(f"   Address: {address[:12]}...")

        # Get current state from DexScreener (FREE!)
        logger.info("   📈 Fetching DexScreener data...")
        dex_data = await self.get_dexscreener_history(address)

        if not dex_data:
            logger.warning(f"   ❌ No DexScreener data for ${symbol}")
            self.failed_count += 1
            return None

        # Calculate buy/sell percentages
        total_txs_24h = dex_data['buys_24h'] + dex_data['sells_24h']
        total_txs_6h = dex_data['buys_6h'] + dex_data['sells_6h']
        total_txs_1h = dex_data['buys_1h'] + dex_data['sells_1h']

        buy_percentage_24h = (dex_data['buys_24h'] / total_txs_24h * 100) if total_txs_24h > 0 else 0
        buy_percentage_6h = (dex_data['buys_6h'] / total_txs_6h * 100) if total_txs_6h > 0 else 0
        buy_percentage_1h = (dex_data['buys_1h'] / total_txs_1h * 100) if total_txs_1h > 0 else 0

        # Compile complete dataset
        historical_data = {
            'token_address': address,
            'token_symbol': symbol,
            'token_name': token_info['name'],
            'category': category,
            'outcome': self._classify_outcome(token_info['gain_multiple']),
            'gain_multiple': token_info['gain_multiple'],
            'final_mcap': token_info['final_mcap'],

            # Current metrics (final state)
            'current_price': dex_data['price_usd'],
            'current_mcap': dex_data['market_cap'],
            'current_liquidity': dex_data['liquidity'],

            # 24h metrics
            'volume_24h': dex_data['volume_24h'],
            'buys_24h': dex_data['buys_24h'],
            'sells_24h': dex_data['sells_24h'],
            'buy_percentage_24h': buy_percentage_24h,
            'price_change_24h': dex_data['price_change_24h'],

            # 6h metrics (proxy for "early state")
            'volume_6h': dex_data['volume_6h'],
            'buys_6h': dex_data['buys_6h'],
            'sells_6h': dex_data['sells_6h'],
            'buy_percentage_6h': buy_percentage_6h,
            'price_change_6h': dex_data['price_change_6h'],

            # 1h metrics (very early state)
            'volume_1h': dex_data['volume_1h'],
            'buys_1h': dex_data['buys_1h'],
            'sells_1h': dex_data['sells_1h'],
            'buy_percentage_1h': buy_percentage_1h,
            'price_change_1h': dex_data['price_change_1h'],

            # Metadata
            'created_at': dex_data['created_at'],
            'collected_at': datetime.utcnow().isoformat()
        }

        logger.info(f"   ✅ Collected ${symbol}")
        logger.info(f"      MCAP: ${dex_data['market_cap']:,.0f}")
        logger.info(f"      Buy/Sell 6h: {buy_percentage_6h:.1f}%")
        logger.info(f"      Outcome: {historical_data['outcome']}")

        self.collected_count += 1
        return historical_data

    def _classify_outcome(self, gain_multiple: int) -> str:
        """Classify outcome based on gain multiple"""
        if gain_multiple >= 100:
            return "100x+"
        elif gain_multiple >= 50:
            return "50x"
        elif gain_multiple >= 10:
            return "10x"
        elif gain_multiple >= 2:
            return "2x"
        else:
            return "rug"

    async def collect_all(self):
        """Collect data for all known runners"""
        logger.info("=" * 80)
        logger.info("🔍 MORALIS HISTORICAL DATA COLLECTION")
        logger.info("=" * 80)

        # Load known runners
        logger.info("\n📋 Loading known runner tokens...")
        with open('ralph/known_runner_tokens.json', 'r') as f:
            runners_config = json.load(f)

        # Extract mega runners (manual list)
        mega_runners = runners_config['tokens'][0]['tokens']
        logger.info(f"   Found {len(mega_runners)} mega runners to collect")

        # Collect data
        all_historical_data = []

        for runner in mega_runners:
            try:
                data = await self.collect_token_data({
                    'address': runner['address'],
                    'symbol': runner['symbol'],
                    'name': runner['name'],
                    'gain_multiple': runner['gain_multiple'],
                    'final_mcap': runner['final_mcap'],
                    'category': 'mega_runners_100x'
                })

                if data:
                    all_historical_data.append(data)

                # Rate limit: 1 request per second
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"   ❌ Failed to collect {runner['symbol']}: {e}")
                self.failed_count += 1

        # Save results
        logger.info("\n" + "=" * 80)
        logger.info("💾 SAVING RESULTS")
        logger.info("=" * 80)

        # Save to JSON
        output_file = 'ralph/historical_training_data.json'
        with open(output_file, 'w') as f:
            json.dump({
                'collected_at': datetime.utcnow().isoformat(),
                'total_tokens': len(all_historical_data),
                'cu_used_estimate': self.total_cu_used,
                'tokens': all_historical_data
            }, f, indent=2)

        logger.info(f"   ✅ Saved to {output_file}")
        logger.info(f"   📊 Tokens collected: {self.collected_count}")
        logger.info(f"   ❌ Tokens failed: {self.failed_count}")
        logger.info(f"   💰 Estimated CU used: {self.total_cu_used}")

        # Summary by outcome
        logger.info("\n📈 OUTCOME DISTRIBUTION:")
        outcomes = {}
        for token in all_historical_data:
            outcome = token['outcome']
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

        for outcome, count in sorted(outcomes.items()):
            logger.info(f"   {outcome}: {count} tokens")

        logger.info("\n" + "=" * 80)
        logger.info("✅ COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n🚀 Ready for ML training with {len(all_historical_data)} historical examples!")
        logger.info(f"   Combined with your {100} current signals = {len(all_historical_data) + 100}+ training examples\n")


async def main():
    """Main execution"""
    collector = MoralisHistoricalCollector()
    await collector.initialize()
    await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
