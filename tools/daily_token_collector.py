#!/usr/bin/env python3
"""
Daily Token Collector - Continuous ML Dataset Builder

Runs daily to collect top 50-100 tokens for ML training.
Builds dataset organically over time with diverse market conditions.

Features:
- Collects top gainers from DexScreener
- Tracks tokens across different market conditions
- Identifies patterns in successful vs failed tokens
- Saves whale wallets to database for real-time conviction boost

Run via cron: 0 0 * * * /path/to/daily_token_collector.py
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from loguru import logger

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import Database
from tools.historical_data_collector import HistoricalDataCollector


class DailyTokenCollector:
    """Collects top tokens daily for continuous ML dataset building"""

    def __init__(self):
        self.collector = HistoricalDataCollector()
        self.tokens_per_day = int(os.getenv('DAILY_COLLECTOR_COUNT', '50'))  # Default: 50 tokens/day

    async def get_daily_top_tokens(self, limit: int = 100) -> list:
        """
        Get top performing tokens from the last 24 hours

        Strategies:
        1. Top gainers (price change 24h)
        2. Top volume (sorted by 24h volume)
        3. Newly graduated from pump.fun

        Args:
            limit: Number of tokens to collect

        Returns:
            List of token addresses
        """
        logger.info("=" * 80)
        logger.info("📈 FETCHING DAILY TOP TOKENS")
        logger.info("=" * 80)
        logger.info(f"   Target: {limit} tokens from last 24 hours")
        logger.info(f"   Strategies: Top gainers + high volume + new graduates\n")

        token_addresses = set()
        tokens_data = []

        async with aiohttp.ClientSession(trust_env=True) as session:
            # Strategy 1: Get top gainers from DexScreener
            strategies = [
                ("Top Gainers", "https://api.dexscreener.com/token-boosts/top/v1"),
                ("Latest Profiles", "https://api.dexscreener.com/token-profiles/latest/v1"),
            ]

            for strategy_name, url in strategies:
                if len(token_addresses) >= limit:
                    break

                logger.info(f"📊 {strategy_name}...")

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            # Extract tokens
                            tokens = data if isinstance(data, list) else data.get('tokens', [])
                            logger.info(f"   Got {len(tokens)} tokens")

                            # Filter for Solana pump.fun tokens
                            for token in tokens:
                                if len(token_addresses) >= limit:
                                    break

                                # Get token address
                                token_addr = token.get('tokenAddress') or token.get('address')
                                if not token_addr or token_addr in token_addresses:
                                    continue

                                # Only Solana tokens
                                chain_id = token.get('chainId', '')
                                if chain_id != 'solana':
                                    continue

                                token_addresses.add(token_addr)

                                # Get full data from DexScreener
                                token_data = await self.collector.get_dexscreener_data(token_addr, session)
                                if token_data:
                                    tokens_data.append(token_data)

                                await asyncio.sleep(0.5)  # Rate limiting

                        else:
                            logger.warning(f"   Failed: HTTP {resp.status}")

                except Exception as e:
                    logger.error(f"   Error: {e}")

        logger.info(f"\n✅ Collected {len(tokens_data)} tokens for daily analysis")
        return tokens_data

    async def collect_daily(self):
        """Run daily collection"""
        logger.info("=" * 80)
        logger.info("🌅 DAILY TOKEN COLLECTION")
        logger.info("=" * 80)
        logger.info(f"   Date: {datetime.utcnow().date()}")
        logger.info(f"   Target: {self.tokens_per_day} tokens")
        logger.info("")

        # Initialize database
        await self.collector.initialize()

        # Get today's top tokens
        tokens_data = await self.get_daily_top_tokens(limit=self.tokens_per_day)

        if not tokens_data:
            logger.error("❌ No tokens collected!")
            return

        # Extract whales from each token
        if self.collector.helius_rpc_url:
            logger.info("\n" + "=" * 80)
            logger.info("🐋 EXTRACTING WHALE WALLETS")
            logger.info("=" * 80)

            for idx, token in enumerate(tokens_data, 1):
                logger.info(f"\n[{idx}/{len(tokens_data)}] {token['symbol']}...")

                whales = await self.collector.extract_whale_wallets(
                    token['token_address'],
                    token['symbol'],
                    token.get('price_usd', 0)
                )
                token['whale_wallets'] = whales
                token['whale_count'] = len(whales)

                # Track whales
                if token['outcome'] in ['100x+', '50x', '10x']:
                    for whale in whales:
                        self.collector.whale_wallets[whale]['win_count'] += 1

                await asyncio.sleep(1.5)  # Rate limit

        # Save results
        await self._save_daily_results(tokens_data)

        logger.info("\n" + "=" * 80)
        logger.info("✅ DAILY COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"   Collected: {len(tokens_data)} tokens")
        logger.info(f"   Whales found: {len(self.collector.whale_wallets)}")

    async def _save_daily_results(self, tokens_data: list):
        """Save daily collection results"""
        logger.info("\n" + "=" * 80)
        logger.info("💾 SAVING DAILY RESULTS")
        logger.info("=" * 80)

        # Load existing historical data
        historical_file = 'data/historical_training_data.json'
        existing_data = {}
        try:
            with open(historical_file, 'r') as f:
                existing_data = json.load(f)
                logger.info(f"   Existing: {existing_data.get('total_tokens', 0)} tokens")
        except FileNotFoundError:
            logger.info("   Creating new dataset")

        # Append today's tokens
        all_tokens = existing_data.get('tokens', []) + tokens_data

        # Save updated dataset
        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_tokens': len(all_tokens),
            'last_daily_collection': datetime.utcnow().date().isoformat(),
            'tokens_collected_today': len(tokens_data),
            'outcome_distribution': self.collector._get_outcome_distribution(all_tokens),
            'tokens': all_tokens
        }

        with open(historical_file, 'w') as f:
            json.dump(output, f, indent=2)
        logger.info(f"   ✅ Saved {historical_file}")
        logger.info(f"   Total: {len(all_tokens)} tokens (+{len(tokens_data)} new)")

        # Analyze and save successful whales
        successful_whales = []
        for wallet, data in self.collector.whale_wallets.items():
            token_count = len(data['tokens_bought'])
            if token_count >= 2:
                win_rate = (data['win_count'] / token_count) if token_count > 0 else 0
                if win_rate >= 0.5:
                    successful_whales.append({
                        'address': wallet,
                        'tokens_bought_count': token_count,
                        'wins': data['win_count'],
                        'win_rate': win_rate,
                        'tokens': data['tokens_bought']
                    })

        if successful_whales:
            successful_whales.sort(key=lambda x: x['win_rate'], reverse=True)

            whale_output = {
                'collected_at': datetime.utcnow().isoformat(),
                'total_whales': len(successful_whales),
                'whales': successful_whales
            }

            with open('data/successful_whale_wallets.json', 'w') as f:
                json.dump(whale_output, f, indent=2)
            logger.info(f"   ✅ Saved {len(successful_whales)} successful whales")

            # Save to database for real-time matching
            if self.collector.db:
                logger.info("\n📊 Updating whale database...")
                for whale in successful_whales:
                    is_early_whale = any(t.get('early_buyer', False) for t in whale['tokens'])

                    await self.collector.db.insert_whale_wallet({
                        'address': whale['address'],
                        'tokens_bought_count': whale['tokens_bought_count'],
                        'wins': whale['wins'],
                        'win_rate': whale['win_rate'],
                        'is_early_whale': is_early_whale
                    })

                    for token in whale['tokens']:
                        await self.collector.db.insert_whale_token_purchase(
                            whale['address'],
                            token
                        )

                logger.info(f"   ✅ Updated database with {len(successful_whales)} whales")
                logger.info("   🚀 Whales will boost conviction scores in real-time!")


async def main():
    """Run daily collection"""
    collector = DailyTokenCollector()
    await collector.collect_daily()


if __name__ == "__main__":
    asyncio.run(main())
