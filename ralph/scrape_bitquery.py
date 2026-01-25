#!/usr/bin/env python3
"""
BitQuery Scraper: Find REAL runners (40-60% bonding → $1M+ MCAP)

BitQuery advantages:
- Bonding curve progress tracking (exact %)
- Historical market cap data
- Token graduation timestamps
- GraphQL for complex queries

Strategy:
1. Find tokens currently at $1M-$50M MCAP
2. Query their bonding curve history (when were they at 40-60%?)
3. Check which wallets bought at 40-60% stage
4. Train ML: "Wallet X buying at 50% bonding = becomes $XM runner"
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


class BitQueryScraper:
    """Scrape pump.fun runners using BitQuery GraphQL API"""

    def __init__(self):
        self.api_key = os.getenv('BITQUERY_API_KEY')
        if not self.api_key:
            logger.warning("⚠️  BITQUERY_API_KEY not set - will use free tier")

        self.endpoint = "https://streaming.bitquery.io/graphql"
        self.headers = {
            'Content-Type': 'application/json',
        }
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'

    async def query_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute GraphQL query against BitQuery"""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers=self.headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"❌ BitQuery API error: {response.status}")
                        logger.error(f"Response: {text[:500]}")
                        return {}

                    data = await response.json()

                    if 'errors' in data:
                        logger.error(f"❌ GraphQL errors: {data['errors']}")
                        return {}

                    return data.get('data', {})

            except Exception as e:
                logger.error(f"❌ Error querying BitQuery: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return {}

    async def get_current_runners(self, min_mcap: int = 1000000, max_mcap: int = 50000000) -> List[Dict]:
        """
        Find tokens currently at $1M-$50M market cap

        Args:
            min_mcap: Minimum market cap ($1M default)
            max_mcap: Maximum market cap ($50M default)

        Returns:
            List of runner tokens
        """
        logger.info(f"🔍 Querying BitQuery for runners (${min_mcap/1e6:.1f}M - ${max_mcap/1e6:.1f}M MCAP)...")

        # GraphQL query to find tokens with high market caps
        # Filter for recent trades, calculate MCAP = 1B × Price
        query = """
        query GetRunners($minPrice: Float!, $maxPrice: Float!) {
          Solana {
            DEXTradeByTokens(
              limit: {count: 100}
              orderBy: {descending: Block_Time}
              where: {
                Transaction: {Result: {Success: true}}
                Trade: {
                  Currency: {MintAddress: {notIn: ["So11111111111111111111111111111111111111112"]}}
                  PriceInUSD: {ge: $minPrice, le: $maxPrice}
                  Dex: {ProgramAddress: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}}
                }
              }
            ) {
              Trade {
                Currency {
                  MintAddress
                  Symbol
                  Name
                }
                PriceInUSD
                Dex {
                  ProgramAddress
                }
              }
              Block {
                Time
              }
              Transaction {
                Signature
              }
            }
          }
        }
        """

        # Calculate price range from MCAP range
        # MCAP = 1B × Price, so Price = MCAP / 1B
        min_price = min_mcap / 1_000_000_000
        max_price = max_mcap / 1_000_000_000

        variables = {
            'minPrice': min_price,
            'maxPrice': max_price
        }

        data = await self.query_graphql(query, variables)

        if not data or 'Solana' not in data:
            logger.warning("⚠️  No data returned from BitQuery")
            return []

        trades = data.get('Solana', {}).get('DEXTradeByTokens', [])

        # Group by token (latest trade per token)
        token_map = {}
        for trade_data in trades:
            trade = trade_data.get('Trade', {})
            currency = trade.get('Currency', {})
            mint = currency.get('MintAddress')

            if not mint or mint in token_map:
                continue

            price_usd = float(trade.get('PriceInUSD', 0))
            mcap = price_usd * 1_000_000_000

            token_map[mint] = {
                'address': mint,
                'symbol': currency.get('Symbol', 'UNKNOWN'),
                'name': currency.get('Name', 'Unknown'),
                'current_price': price_usd,
                'current_mcap': mcap,
                'last_trade_time': trade_data.get('Block', {}).get('Time'),
                'last_trade_sig': trade_data.get('Transaction', {}).get('Signature')
            }

        runners = list(token_map.values())
        logger.info(f"✅ Found {len(runners)} unique runners")

        # Sort by MCAP descending
        runners.sort(key=lambda x: x['current_mcap'], reverse=True)

        return runners

    async def get_bonding_curve_history(self, token_address: str) -> Optional[Dict]:
        """
        Get bonding curve progression for a token
        Find when it was at 40-60% bonding curve

        Args:
            token_address: Token mint address

        Returns:
            Dict with bonding curve milestones
        """
        logger.info(f"   📊 Querying bonding curve history for {token_address[:8]}...")

        # Query for DEX pool balance changes to track bonding curve progress
        # Bonding curve progress = 100 - ((balance - 206,900,000) × 100 / 793,100,000)
        query = """
        query GetBondingCurve($tokenAddress: String!) {
          Solana {
            DEXPools(
              where: {
                Pool: {
                  Base: {Currency: {MintAddress: {is: $tokenAddress}}}
                  Dex: {ProgramAddress: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}}
                }
              }
              orderBy: {ascending: Block_Time}
              limit: {count: 1000}
            ) {
              Pool {
                Base {
                  Amount
                }
              }
              Block {
                Time
              }
            }
          }
        }
        """

        variables = {'tokenAddress': token_address}
        data = await self.query_graphql(query, variables)

        if not data or 'Solana' not in data:
            return None

        pools = data.get('Solana', {}).get('DEXPools', [])

        if not pools:
            logger.info(f"      ⏭️  No bonding curve data found")
            return None

        # Calculate bonding curve progress at different times
        milestones = {
            '40_percent': None,
            '50_percent': None,
            '60_percent': None,
            '100_percent': None  # Graduation
        }

        initial_reserves = 793_100_000
        graduated_balance = 206_900_000

        for pool_data in pools:
            balance = float(pool_data.get('Pool', {}).get('Base', {}).get('Amount', 0))
            timestamp = pool_data.get('Block', {}).get('Time')

            if balance <= 0:
                continue

            # Calculate progress: 100 - ((balance - 206,900,000) × 100 / 793,100,000)
            if balance <= graduated_balance:
                progress = 100
            else:
                progress = 100 - ((balance - graduated_balance) * 100 / initial_reserves)

            # Record milestones
            if 38 <= progress <= 42 and not milestones['40_percent']:
                milestones['40_percent'] = timestamp
            elif 48 <= progress <= 52 and not milestones['50_percent']:
                milestones['50_percent'] = timestamp
            elif 58 <= progress <= 62 and not milestones['60_percent']:
                milestones['60_percent'] = timestamp
            elif progress >= 99 and not milestones['100_percent']:
                milestones['100_percent'] = timestamp

        # Log found milestones
        found_count = sum(1 for v in milestones.values() if v)
        logger.info(f"      ✅ Found {found_count}/4 bonding curve milestones")

        return milestones if found_count > 0 else None

    async def save_results(self, runners: List[Dict]):
        """Save runner analysis to JSON"""
        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'source': 'BitQuery GraphQL API',
            'total_runners': len(runners),
            'runners': runners
        }

        output_path = os.path.join(os.path.dirname(__file__), 'bitquery_runners.json')

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Saved {len(runners)} runners to {output_path}")

        # Print summary
        print("\n" + "="*70)
        print("📊 BITQUERY RUNNER ANALYSIS SUMMARY")
        print("="*70)

        if len(runners) > 0:
            avg_mcap = sum(r['current_mcap'] for r in runners) / len(runners)
            with_milestones = sum(1 for r in runners if r.get('bonding_milestones'))

            print(f"\n✅ Analyzed {len(runners)} runners")
            print(f"   Average MCAP: ${avg_mcap/1e6:.2f}M")
            print(f"   With bonding curve data: {with_milestones}/{len(runners)}")

            print(f"\n🎯 Top 10 Runners:")
            for i, r in enumerate(runners[:10], 1):
                milestones = r.get('bonding_milestones', {})
                had_40_60 = milestones.get('40_percent') and milestones.get('60_percent')
                status = "✅ Has 40-60% data" if had_40_60 else "⏭️  Missing data"
                print(f"   {i}. ${r['symbol']}: ${r['current_mcap']/1e6:.2f}M - {status}")

        print("\n" + "="*70)


async def main():
    """Main workflow"""
    MAX_RUNNERS = 50  # Start with 50 to test (BitQuery may have rate limits)

    logger.info("🚀 Starting BitQuery RUNNER scraper...")
    logger.info("📋 Strategy:")
    logger.info("   1. Find tokens with $1M-$50M MCAP (current runners)")
    logger.info("   2. Query bonding curve history (when at 40-60%?)")
    logger.info("   3. Identify wallets that bought at 40-60% stage")
    logger.info("   4. Train ML: 'Buying at X% bonding = becomes $XM runner'")
    logger.info("")
    logger.info(f"📊 Target: {MAX_RUNNERS} runners")
    logger.info("")

    scraper = BitQueryScraper()

    # Get current runners
    runners = await scraper.get_current_runners()

    if len(runners) == 0:
        logger.error("❌ No runners found - check BitQuery API access")
        return

    # Analyze top runners (limit to avoid rate limits)
    analyze_count = min(len(runners), MAX_RUNNERS)
    logger.info(f"\n📊 Analyzing bonding curve history for top {analyze_count} runners...\n")

    for i, runner in enumerate(runners[:analyze_count]):
        logger.info(f"📈 {i+1}/{analyze_count}: ${runner['symbol']} - ${runner['current_mcap']/1e6:.2f}M MCAP")

        # Get bonding curve milestones
        milestones = await scraper.get_bonding_curve_history(runner['address'])
        runner['bonding_milestones'] = milestones

        # Rate limit (BitQuery free tier)
        await asyncio.sleep(2)

    # Save results
    await scraper.save_results(runners[:analyze_count])

    logger.info("\n✅ BitQuery runner analysis complete!")
    logger.info(f"📊 Collected data for {analyze_count} runners")
    logger.info("\n💡 Next: Train ML with bonding curve milestone data")


if __name__ == "__main__":
    asyncio.run(main())
