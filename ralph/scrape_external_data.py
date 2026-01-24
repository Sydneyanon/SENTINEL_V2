#!/usr/bin/env python3
"""
External Data Scraper for Ralph
Scrapes DexScreener for successful tokens and checks which KOLs bought them.
This gives Ralph real data to learn from without waiting for our own signals.

OPT-044/046/048: Learn from the entire pump.fun ecosystem
"""
import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
import sys

# Add parent directory to path so we can import from main codebase
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helius_fetcher import HeliusDataFetcher
from data.curated_wallets import KOL_WALLETS


class ExternalDataScraper:
    """Scrapes external sources for successful token data"""

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

    async def fetch_trending_tokens_dexscreener(self, min_volume_24h: int = 50000) -> List[Dict]:
        """
        Fetch trending Solana tokens from DexScreener (FREE API)

        Args:
            min_volume_24h: Minimum 24h volume in USD

        Returns:
            List of token data with price history
        """
        logger.info("🔍 Fetching trending tokens from DexScreener...")

        url = "https://api.dexscreener.com/latest/dex/search/?q=SOL"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"❌ DexScreener API error: {response.status}")
                        return []

                    data = await response.json()
                    pairs = data.get('pairs', [])

                    # Filter for Solana, pump.fun, and significant volume
                    solana_tokens = []
                    for pair in pairs:
                        if pair.get('chainId') != 'solana':
                            continue

                        volume_24h = float(pair.get('volume', {}).get('h24', 0))
                        if volume_24h < min_volume_24h:
                            continue

                        # Check if it's a pump.fun token (look for pump.fun in URLs or raydium pairs)
                        base_token = pair.get('baseToken', {})
                        token_address = base_token.get('address')

                        if not token_address:
                            continue

                        # Get price change data
                        price_change = pair.get('priceChange', {})

                        solana_tokens.append({
                            'address': token_address,
                            'symbol': base_token.get('symbol'),
                            'name': base_token.get('name'),
                            'price_usd': float(pair.get('priceUsd', 0)),
                            'volume_24h': volume_24h,
                            'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                            'price_change_24h': float(price_change.get('h24', 0)),
                            'price_change_6h': float(price_change.get('h6', 0)),
                            'price_change_1h': float(price_change.get('h1', 0)),
                            'created_at': pair.get('pairCreatedAt'),
                            'dex_url': pair.get('url'),
                        })

                    logger.info(f"✅ Found {len(solana_tokens)} Solana tokens with >${min_volume_24h} volume")
                    return solana_tokens

            except Exception as e:
                logger.error(f"❌ Error fetching from DexScreener: {e}")
                return []

    async def check_kol_involvement(self, token_address: str, created_at: Optional[int] = None) -> Dict:
        """
        Check which wallets bought this token (both our KOLs and unknown wallets)

        This does TWO things:
        1. Validates our KOLs: Did they buy this winner?
        2. Discovers new KOLs: Which unknown wallets bought it?

        Args:
            token_address: Token contract address
            created_at: Token creation timestamp (unix ms)

        Returns:
            Dict with KOL involvement data + discovered wallets
        """
        # Use Helius Enhanced Transactions API to get token holders
        # This costs ~1-2 credits but gives us rich data
        try:
            api_key = os.getenv('HELIUS_API_KEY')
            if not api_key:
                logger.error("❌ HELIUS_API_KEY not set")
                return self._empty_result()

            # Get token holders (who currently holds the token)
            # This is cheaper than getting all transactions
            holders_data = await self.helius.get_token_holders(token_address, limit=100)

            if not holders_data:
                return self._empty_result()

            # Extract wallet addresses
            holders = holders_data.get('result', {}).get('value', [])

            our_kols_found = []
            new_wallets_found = []

            for holder in holders:
                wallet = holder.get('address')
                balance = holder.get('amount', 0)

                if not wallet or balance == 0:
                    continue

                # Check if it's one of our tracked KOLs
                if wallet in self.our_kol_wallets:
                    our_kols_found.append({
                        'wallet': wallet,
                        'balance': balance
                    })
                else:
                    # Potential new KOL to track
                    new_wallets_found.append({
                        'wallet': wallet,
                        'balance': balance
                    })

            return {
                'our_kols_involved': [k['wallet'] for k in our_kols_found],
                'our_kol_count': len(our_kols_found),
                'new_wallets': [w['wallet'] for w in new_wallets_found[:20]],  # Top 20 holders
                'new_wallet_count': len(new_wallets_found),
            }

        except Exception as e:
            logger.error(f"❌ Error checking involvement for {token_address[:8]}: {e}")
            return self._empty_result()

    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'our_kols_involved': [],
            'our_kol_count': 0,
            'new_wallets': [],
            'new_wallet_count': 0,
        }

    async def analyze_successful_tokens(self, min_gain_percent: float = 200, max_tokens: int = 500) -> tuple[List[Dict], Dict]:
        """
        Find tokens that mooned and check if our KOLs bought them
        ALSO discovers new potential KOLs!

        Args:
            min_gain_percent: Minimum gain % to consider (200 = 3x)
            max_tokens: Maximum tokens to analyze (default 500, can go up to 1000+)

        Returns:
            Tuple of (token_results, discovered_kols)
        """
        logger.info(f"🚀 Analyzing tokens that gained >{min_gain_percent}% in 24h...")

        # Get trending tokens
        tokens = await self.fetch_trending_tokens_dexscreener(min_volume_24h=50000)

        # Filter for big winners
        winners = []
        for token in tokens:
            gain_24h = token.get('price_change_24h', 0)

            if gain_24h >= min_gain_percent:
                winners.append(token)

        logger.info(f"✅ Found {len(winners)} tokens that gained >{min_gain_percent}%")

        # Track which wallets appear in multiple winners (potential new KOLs)
        wallet_appearances = {}  # wallet -> [token_address, ...]

        # Check KOL involvement for each winner
        results = []
        credits_used = 0

        # Limit to max_tokens to control credit usage
        # 500 tokens = ~1000 credits (0.01% of remaining budget)
        # 1000 tokens = ~2000 credits (0.02% of remaining budget)
        tokens_to_analyze = min(len(winners), max_tokens)

        for i, token in enumerate(winners[:tokens_to_analyze]):
            logger.info(f"📊 Checking {i+1}/{tokens_to_analyze}: {token['symbol']} ({token['price_change_24h']:.0f}% gain)")

            kol_data = await self.check_kol_involvement(
                token['address'],
                token.get('created_at')
            )

            credits_used += 2  # Approximate

            # Track new wallets for discovery
            for wallet in kol_data.get('new_wallets', []):
                if wallet not in wallet_appearances:
                    wallet_appearances[wallet] = []
                wallet_appearances[wallet].append({
                    'token': token['symbol'],
                    'gain': token['price_change_24h']
                })

            # Combine token data with KOL data
            result = {
                **token,
                **kol_data,
                'outcome': self._classify_outcome(token['price_change_24h'])
            }

            results.append(result)

            # Log if KOLs were involved
            if kol_data.get('our_kol_count', 0) > 0:
                logger.info(f"   ✅ {kol_data['our_kol_count']} of our KOLs bought this!")

            if kol_data.get('new_wallet_count', 0) > 0:
                logger.info(f"   🔍 {kol_data['new_wallet_count']} other wallets holding")

            # Rate limit to avoid API throttling
            await asyncio.sleep(0.5)

        # Find wallets that bought 2+ winners (potential new KOLs to track)
        discovered_kols = {}
        for wallet, appearances in wallet_appearances.items():
            if len(appearances) >= 2:  # Bought 2+ winners
                avg_gain = sum(a['gain'] for a in appearances) / len(appearances)
                discovered_kols[wallet] = {
                    'winner_count': len(appearances),
                    'tokens': [a['token'] for a in appearances],
                    'avg_gain': avg_gain,
                    'max_gain': max(a['gain'] for a in appearances)
                }

        logger.info(f"💰 Analysis complete. Used ~{credits_used} Helius credits")
        logger.info(f"🎯 Discovered {len(discovered_kols)} potential new KOLs (bought 2+ winners)")

        return results, discovered_kols

    def _classify_outcome(self, price_change_24h: float) -> str:
        """Classify token outcome based on 24h price change"""
        if price_change_24h >= 10000:
            return '100x'
        elif price_change_24h >= 5000:
            return '50x'
        elif price_change_24h >= 1000:
            return '10x'
        elif price_change_24h >= 500:
            return '5x'
        elif price_change_24h >= 200:
            return '2x'
        elif price_change_24h >= -50:
            return 'hold'
        else:
            return 'loss'

    async def save_results(self, results: List[Dict], discovered_kols: Dict,
                          filename: str = 'external_data.json'):
        """Save scraping results to file"""
        filepath = os.path.join(os.path.dirname(__file__), filename)

        # Add metadata
        data = {
            'scraped_at': datetime.utcnow().isoformat(),
            'token_count': len(results),
            'kol_wallets_tracked': len(self.our_kol_wallets),
            'discovered_kols_count': len(discovered_kols),
            'tokens': results,
            'discovered_kols': discovered_kols
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"💾 Saved {len(results)} tokens + {len(discovered_kols)} discovered KOLs to {filepath}")

        # Generate summary
        self._print_summary(results, discovered_kols)

    def _print_summary(self, results: List[Dict], discovered_kols: Dict):
        """Print summary statistics"""
        total = len(results)

        if total == 0:
            print("\n" + "="*70)
            print("📊 EXTERNAL DATA ANALYSIS SUMMARY")
            print("="*70)
            print("\n⚠️  No tokens found. This might be due to:")
            print("   - No internet access")
            print("   - No tokens met the criteria (200%+ gain)")
            print("   - DexScreener API issues")
            print("\n" + "="*70)
            return

        with_our_kols = len([r for r in results if r.get('our_kol_count', 0) > 0])

        # Outcome distribution
        outcomes = {}
        for r in results:
            outcome = r.get('outcome', 'unknown')
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

        # KOL success rate
        our_kol_tokens = [r for r in results if r.get('our_kol_count', 0) > 0]
        no_kol_tokens = [r for r in results if r.get('our_kol_count', 0) == 0]

        print("\n" + "="*70)
        print("📊 EXTERNAL DATA ANALYSIS SUMMARY")
        print("="*70)
        print(f"\n📈 Token Distribution:")
        print(f"   Total tokens analyzed: {total}")
        print(f"   Tokens with OUR KOLs: {with_our_kols} ({with_our_kols/total*100:.1f}%)")
        print(f"   Tokens without our KOLs: {total - with_our_kols} ({(total-with_our_kols)/total*100:.1f}%)")

        print(f"\n🎯 Outcome Distribution:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: x[1], reverse=True):
            print(f"   {outcome}: {count} ({count/total*100:.1f}%)")

        if our_kol_tokens:
            avg_gain_with_kols = sum(r.get('price_change_24h', 0) for r in our_kol_tokens) / len(our_kol_tokens)
            print(f"\n💡 Key Insights (Our KOLs):")
            print(f"   Avg gain (with our KOLs): {avg_gain_with_kols:.0f}%")

            if no_kol_tokens:
                avg_gain_no_kols = sum(r.get('price_change_24h', 0) for r in no_kol_tokens) / len(no_kol_tokens)
                print(f"   Avg gain (no our KOLs): {avg_gain_no_kols:.0f}%")
                print(f"   Our KOL advantage: {avg_gain_with_kols - avg_gain_no_kols:.0f}% higher gains")

        # Discovered KOLs
        if discovered_kols:
            print(f"\n🔍 Discovered Potential New KOLs:")
            print(f"   Total discovered: {len(discovered_kols)}")
            print(f"   Top 10 by winner count:")

            sorted_kols = sorted(discovered_kols.items(),
                               key=lambda x: x[1]['winner_count'],
                               reverse=True)[:10]

            for i, (wallet, data) in enumerate(sorted_kols, 1):
                print(f"\n   {i}. {wallet[:8]}...{wallet[-4:]}")
                print(f"      Winners bought: {data['winner_count']}")
                print(f"      Avg gain: {data['avg_gain']:.0f}%")
                print(f"      Max gain: {data['max_gain']:.0f}%")
                print(f"      Tokens: {', '.join(data['tokens'][:3])}{'...' if len(data['tokens']) > 3 else ''}")

        print("\n" + "="*70)


async def main():
    """Main scraping workflow"""
    # Configurable parameters
    MIN_GAIN = 200  # 200% = 3x minimum
    MAX_TOKENS = 500  # Analyze up to 500 tokens (can increase to 1000+)

    logger.info("🚀 Starting external data scraper...")
    logger.info("📋 Configuration:")
    logger.info(f"   Minimum gain: {MIN_GAIN}% (3x)")
    logger.info(f"   Max tokens to analyze: {MAX_TOKENS}")
    logger.info(f"   Estimated cost: ~{MAX_TOKENS * 2} Helius credits")
    logger.info("")
    logger.info("📋 Process:")
    logger.info("   1. Fetch trending Solana tokens from DexScreener (FREE)")
    logger.info("   2. Filter for big winners (200%+ gains)")
    logger.info("   3. Check which of OUR KOLs bought them")
    logger.info("   4. DISCOVER new wallets that bought 2+ winners")
    logger.info("")

    scraper = ExternalDataScraper()

    # Scrape and analyze
    results, discovered_kols = await scraper.analyze_successful_tokens(
        min_gain_percent=MIN_GAIN,
        max_tokens=MAX_TOKENS
    )

    # Save results
    await scraper.save_results(results, discovered_kols)

    logger.info("")
    logger.info("✅ Scraping complete!")
    logger.info(f"📊 Analyzed {len(results)} successful tokens")
    logger.info(f"🔍 Discovered {len(discovered_kols)} potential new KOLs")
    logger.info("")
    logger.info("💡 Next steps:")
    logger.info("   1. Review ralph/external_data.json")
    logger.info("   2. Ralph can analyze this data to:")
    logger.info("      - Validate current KOL performance")
    logger.info("      - Add discovered wallets to curated_wallets.py")
    logger.info("      - Learn patterns that predict winners")


if __name__ == "__main__":
    asyncio.run(main())
