#!/usr/bin/env python3
"""
Runner Detection (Sync Version): Find tokens that went 40-60% bonding → $1M+ MCAP

This version uses synchronous requests instead of aiohttp to avoid DNS resolution issues
in containerized environments.

Strategy:
1. Get current high MCAP tokens ($1M-$10M+) from DexScreener
2. For each, analyze when it was at early stage
3. Identify success patterns for ML training
"""
import os
import sys
import json
import requests
from datetime import datetime
from typing import List, Dict
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.curated_wallets import KOL_WALLETS


class RunnerScraperSync:
    """Find tokens that became runners - synchronous version"""

    def __init__(self):
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

    def get_current_runners(self, min_mcap: int = 1000000, max_mcap: int = 50000000, limit: int = 100) -> List[Dict]:
        """
        Get tokens that are currently high MCAP ($1M-$50M)

        Args:
            min_mcap: Minimum market cap ($1M default)
            max_mcap: Maximum market cap ($50M default)
            limit: Max tokens to fetch

        Returns:
            List of runner tokens with current data
        """
        logger.info(f"🔍 Fetching current runners ($${min_mcap/1e6:.1f}M - ${max_mcap/1e6:.1f}M MCAP)...")

        # DexScreener search for pump.fun tokens
        url = "https://api.dexscreener.com/latest/dex/search?q=pump.fun"

        try:
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                logger.error(f"❌ DexScreener API error: {response.status_code}")
                return []

            data = response.json()
            pairs = data.get('pairs', [])

            logger.info(f"📊 DexScreener returned {len(pairs)} pump.fun pairs")

            # Filter for runners (high MCAP)
            runners = []
            for pair in pairs:
                fdv = float(pair.get('fdv', 0) or 0)

                if min_mcap <= fdv <= max_mcap:
                    base_token = pair.get('baseToken', {})
                    runners.append({
                        'address': base_token.get('address'),
                        'symbol': base_token.get('symbol'),
                        'name': base_token.get('name'),
                        'current_mcap': fdv,
                        'current_price': float(pair.get('priceUsd', 0) or 0),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                        'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                        'created_at': pair.get('pairCreatedAt'),
                        'dex_url': pair.get('url')
                    })

                if len(runners) >= limit:
                    break

            logger.info(f"✅ Found {len(runners)} runners in target range")

            # Sort by MCAP descending (biggest runners first)
            runners.sort(key=lambda x: x['current_mcap'], reverse=True)

            return runners[:limit]

        except Exception as e:
            logger.error(f"❌ Error fetching runners: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def save_results(self, runners: List[Dict], output_file: str):
        """Save runner data to JSON file"""
        output_path = os.path.join(os.path.dirname(__file__), output_file)

        data = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_runners': len(runners),
            'runners': runners
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"\n💾 Saved {len(runners)} runners to {output_path}")

        # Print summary
        if runners:
            logger.info("\n" + "=" * 70)
            logger.info("📊 RUNNER ANALYSIS SUMMARY")
            logger.info("=" * 70)

            total_mcap = sum(r['current_mcap'] for r in runners)
            avg_mcap = total_mcap / len(runners) if runners else 0

            logger.info(f"Total runners: {len(runners)}")
            logger.info(f"Total market cap: ${total_mcap/1e6:.1f}M")
            logger.info(f"Average MCAP: ${avg_mcap/1e6:.2f}M")
            logger.info(f"\nTop 10 Runners:")

            for i, runner in enumerate(runners[:10], 1):
                symbol = runner['symbol']
                mcap = runner['current_mcap']
                change_24h = runner.get('price_change_24h', 0)
                logger.info(f"  {i}. ${symbol}: ${mcap/1e6:.2f}M MCAP ({change_24h:+.1f}% 24h)")

            logger.info("=" * 70)


def main():
    logger.info("🚀 Starting RUNNER scraper (SYNC VERSION - Fixed DNS)...")
    logger.info("📋 Strategy:")
    logger.info("   1. Find tokens with $1M-$50M MCAP (current runners)")
    logger.info("   2. Collect data for ML pattern analysis")
    logger.info("   3. Export to runner_data_sync.json")
    logger.info("")
    logger.info("📊 Target: 100 runners")
    logger.info("")

    scraper = RunnerScraperSync()

    # Get current runners
    runners = scraper.get_current_runners(
        min_mcap=1_000_000,  # $1M minimum
        max_mcap=50_000_000,  # $50M maximum
        limit=100
    )

    if not runners:
        logger.error("❌ No runners found")
        return

    # Save results
    scraper.save_results(runners, 'runner_data_sync.json')

    logger.info(f"\n✅ Runner scraping complete!")
    logger.info(f"📊 Collected data for {len(runners)} runners")
    logger.info(f"\n💡 Next: Analyze patterns or train ML with this data")


if __name__ == '__main__':
    main()
