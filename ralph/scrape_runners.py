#!/usr/bin/env python3
"""
Runner Detection: Find tokens that went 40-60% bonding → $1M+ MCAP

Strategy:
1. Get current high MCAP tokens ($1M-$10M+) from DexScreener
2. For each, check when it was at 40-60% bonding curve
3. Identify KOLs who bought at that early stage (the golden signal!)
4. Train ML on: "KOLs buying at 40-60% + these patterns = $1M+ runner"

This is the REAL alpha - catching runners early, not after graduation.
"""
import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helius_fetcher import HeliusDataFetcher
from data.curated_wallets import KOL_WALLETS


class RunnerScraper:
    """Find tokens that became runners from 40-60% bonding"""

    def __init__(self):
        self.helius = HeliusDataFetcher()
        self.our_kol_wallets = set()
        self._load_our_kols()

    def _load_our_kols(self):
        """Load our tracked KOL wallets"""
        for tier, wallets in KOL_WALLETS.items():
            for wallet_data in wallets:
                if isinstance(wallet_data, dict):
                    self.our_kol_wallets.add(wallet_data['address'])
                else:
                    self.our_kol_wallets.add(wallet_data)
        logger.info(f"📋 Loaded {len(self.our_kol_wallets)} KOL wallets to track")

    async def get_current_runners(self, min_mcap: int = 1000000, max_mcap: int = 50000000) -> List[Dict]:
        """
        Get tokens that are currently high MCAP ($1M-$50M)
        These are the runners we want to learn from

        Args:
            min_mcap: Minimum market cap ($1M default)
            max_mcap: Maximum market cap ($50M default - beyond this = outliers)

        Returns:
            List of runner tokens with current data
        """
        logger.info(f"🔍 Fetching current runners ($${min_mcap/1e6:.1f}M - ${max_mcap/1e6:.1f}M MCAP)...")

        url = "https://api.dexscreener.com/latest/dex/search?q=pump.fun"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"❌ DexScreener API error: {response.status}")
                        return []

                    data = await response.json()
                    pairs = data.get('pairs', [])

                    logger.info(f"📊 DexScreener returned {len(pairs)} pump.fun pairs")

                    # Filter for runners (high MCAP)
                    runners = []
                    for pair in pairs:
                        fdv = float(pair.get('fdv', 0))

                        if min_mcap <= fdv <= max_mcap:
                            base_token = pair.get('baseToken', {})
                            runners.append({
                                'address': base_token.get('address'),
                                'symbol': base_token.get('symbol'),
                                'name': base_token.get('name'),
                                'current_mcap': fdv,
                                'current_price': float(pair.get('priceUsd', 0)),
                                'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                                'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                                'created_at': pair.get('pairCreatedAt'),
                                'dex_url': pair.get('url')
                            })

                    logger.info(f"✅ Found {len(runners)} runners in target range")

                    # Sort by MCAP descending (biggest runners first)
                    runners.sort(key=lambda x: x['current_mcap'], reverse=True)

                    return runners

            except Exception as e:
                logger.error(f"❌ Error fetching runners: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return []

    async def find_early_signal(self, token_address: str, created_at: Optional[int] = None) -> Dict:
        """
        Find when this token was at 40-60% bonding curve
        Check which KOLs bought at that stage (the golden signal!)

        Args:
            token_address: Token mint address
            created_at: Token creation timestamp

        Returns:
            Dict with early signal data (KOLs who bought at 40-60% bonding)
        """
        logger.info(f"   🔎 Analyzing early signal for {token_address[:8]}...")

        # Check current holders to see if our KOLs hold this token
        # If they hold it now, they likely bought early (first 2 hours)
        # This is a proxy for "bought at 40-60% bonding"

        try:
            holder_data = await self.helius.get_holder_metrics(token_address)

            if not holder_data:
                return {}

            # Check which of our KOLs are holders
            holders = holder_data.get('top_holders', [])
            kols_found = []

            for holder in holders:
                wallet = holder.get('address')
                if wallet in self.our_kol_wallets:
                    kols_found.append({
                        'wallet': wallet,
                        'balance': holder.get('balance', 0),
                        'percentage': holder.get('percentage', 0)
                    })

            if kols_found:
                logger.info(f"      ✅ {len(kols_found)} KOLs are holders (likely bought early)")
            else:
                logger.info(f"      ⏭️  No KOLs are holders")

            return {
                'kols_found': kols_found,
                'kol_count': len(kols_found)
            }

        except Exception as e:
            logger.error(f"      ❌ Error checking KOL involvement: {e}")
            return {}

    async def analyze_runners(self, max_tokens: int = 100) -> List[Dict]:
        """
        Main analysis: Find runners and identify early signals

        Args:
            max_tokens: Maximum runners to analyze

        Returns:
            List of runners with early signal data
        """
        # Get current runners
        runners = await self.get_current_runners()

        if len(runners) == 0:
            logger.warning("⚠️  No runners found")
            return []

        # Analyze early signals for each runner
        results = []
        tokens_to_analyze = min(len(runners), max_tokens)

        logger.info(f"\n📊 Analyzing early signals for {tokens_to_analyze} runners...\n")

        for i, runner in enumerate(runners[:tokens_to_analyze]):
            logger.info(f"📈 {i+1}/{tokens_to_analyze}: ${runner['symbol']} - ${runner['current_mcap']/1e6:.2f}M MCAP")

            # Find early signal (KOLs who bought at 40-60%)
            early_signal = await self.find_early_signal(
                runner['address'],
                runner.get('created_at')
            )

            # Get current on-chain metrics
            onchain_metrics = await self.helius.get_holder_metrics(runner['address'])

            # Combine data
            runner_data = {
                **runner,
                'early_signal': early_signal,
                'onchain_metrics': onchain_metrics,
                'outcome': 'RUNNER',  # All of these became runners
                'gain_multiple': runner['current_mcap'] / 60000,  # Assume graduated at $60k
            }

            results.append(runner_data)

            # Rate limit
            await asyncio.sleep(2)  # 2 seconds between tokens

        return results

    async def save_results(self, runners: List[Dict]):
        """Save runner analysis to JSON"""
        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_runners': len(runners),
            'runners': runners
        }

        output_path = os.path.join(os.path.dirname(__file__), 'runner_data.json')

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Saved {len(runners)} runners to {output_path}")

        # Print summary
        print("\n" + "="*70)
        print("📊 RUNNER ANALYSIS SUMMARY")
        print("="*70)

        if len(runners) > 0:
            avg_mcap = sum(r['current_mcap'] for r in runners) / len(runners)
            with_kols = sum(1 for r in runners if r['early_signal'].get('kols_found'))

            print(f"\n✅ Analyzed {len(runners)} runners")
            print(f"   Average MCAP: ${avg_mcap/1e6:.2f}M")
            print(f"   Had KOL early signal: {with_kols}/{len(runners)} ({with_kols/len(runners)*100:.0f}%)")

            print(f"\n🎯 Top 10 Runners:")
            for i, r in enumerate(runners[:10], 1):
                kol_count = len(r['early_signal'].get('kols_found', []))
                print(f"   {i}. ${r['symbol']}: ${r['current_mcap']/1e6:.2f}M ({kol_count} early KOLs)")

        print("\n" + "="*70)


async def main():
    """Main workflow"""
    MAX_RUNNERS = 100  # Analyze top 100 runners

    logger.info("🚀 Starting RUNNER scraper (40-60% bonding → $1M+ MCAP)...")
    logger.info("📋 Strategy:")
    logger.info("   1. Find tokens with $1M-$50M MCAP (current runners)")
    logger.info("   2. Check which KOLs bought in first 2 hours (40-60% bonding window)")
    logger.info("   3. Train ML on: 'KOL X buying at 40-60% = becomes $XM runner'")
    logger.info("")
    logger.info(f"📊 Target: {MAX_RUNNERS} runners")
    logger.info("")

    scraper = RunnerScraper()

    # Analyze runners
    results = await scraper.analyze_runners(max_tokens=MAX_RUNNERS)

    # Save results
    await scraper.save_results(results)

    logger.info("\n✅ Runner analysis complete!")
    logger.info(f"📊 Collected data for {len(results)} runners")
    logger.info("\n💡 Next: Train ML with: python ralph/ml_pipeline.py --train --data ralph/runner_data.json")


if __name__ == "__main__":
    asyncio.run(main())
