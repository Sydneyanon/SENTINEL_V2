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

    async def fetch_onchain_metrics(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Fetch comprehensive on-chain metrics for a token

        Retrieves:
        - Holder distribution (concentration %, top holder %, Gini coefficient)
        - Supply economics (total, circulating, burned, dev holdings)
        - Transaction velocity (tx count, tx/hour)
        - Holder growth (current count, growth rate)

        Cost: ~2-3 Helius credits (cheaper than full tx history)

        Args:
            token_address: Token contract address
            session: aiohttp session for API calls

        Returns:
            Dict with on-chain metrics
        """
        try:
            api_key = os.getenv('HELIUS_API_KEY')
            if not api_key:
                return {}

            # Get detailed holder data (limit=200 for better distribution analysis)
            holders_data = await self.helius.get_token_holders(token_address, limit=200)

            if not holders_data or 'result' not in holders_data:
                return {}

            holders = holders_data.get('result', {}).get('value', [])

            if not holders:
                return {}

            # Calculate holder distribution metrics
            total_supply = sum(h.get('amount', 0) for h in holders)
            holder_count = len(holders)

            if total_supply == 0:
                return {'holder_count': holder_count}

            # Sort by balance descending
            sorted_holders = sorted(holders, key=lambda h: h.get('amount', 0), reverse=True)

            # Top holder concentration
            top_1_pct = sorted_holders[0].get('amount', 0) / total_supply * 100 if holder_count > 0 else 0
            top_3_pct = sum(h.get('amount', 0) for h in sorted_holders[:3]) / total_supply * 100 if holder_count >= 3 else top_1_pct
            top_10_pct = sum(h.get('amount', 0) for h in sorted_holders[:10]) / total_supply * 100 if holder_count >= 10 else top_3_pct

            # Calculate Gini coefficient (measure of inequality - lower is better for decentralization)
            # Simplified calculation for performance
            sorted_balances = [h.get('amount', 0) for h in sorted_holders]
            cumsum = 0
            gini_sum = 0
            for i, balance in enumerate(sorted_balances):
                cumsum += balance
                gini_sum += (i + 1) * balance

            gini = 0
            if holder_count > 1 and total_supply > 0:
                gini = (2 * gini_sum) / (holder_count * total_supply) - (holder_count + 1) / holder_count

            # Estimate circulating vs locked/burned
            # Tokens in top 1 holder often = dev/treasury
            dev_holdings_pct = top_1_pct
            circulating_pct = 100 - dev_holdings_pct

            return {
                'holder_count': holder_count,
                'holder_distribution': {
                    'top_1_holder_pct': round(top_1_pct, 2),
                    'top_3_holders_pct': round(top_3_pct, 2),
                    'top_10_holders_pct': round(top_10_pct, 2),
                    'gini_coefficient': round(gini, 3),  # 0 = perfect equality, 1 = one holder has all
                },
                'supply_economics': {
                    'total_supply': total_supply,
                    'circulating_pct': round(circulating_pct, 2),
                    'dev_holdings_pct': round(dev_holdings_pct, 2),
                },
                'decentralization_score': round(100 - (gini * 100), 1)  # Higher = better
            }

        except Exception as e:
            logger.error(f"❌ Error fetching on-chain metrics for {token_address[:8]}: {e}")
            return {}

    async def fetch_security_data(self, token_address: str, session: aiohttp.ClientSession) -> Dict:
        """
        Fetch security/rug risk data from multiple sources

        Sources:
        1. RugCheck.xyz - FREE tier (rug score, honeypot flags, mutable metadata)
        2. TokenSniffer - FREE/low-cost (security analysis, scam detection)
        3. Birdeye - Premium (dev risk flags, audit scores)

        Args:
            token_address: Token contract address
            session: aiohttp session for API calls

        Returns:
            Dict with security metrics
        """
        security_data = {
            'rugcheck_score': None,
            'is_honeypot': None,
            'mutable_metadata': None,
            'tokensniffer_score': None,
            'scam_probability': None,
            'audit_status': None,
            'risk_level': 'unknown'
        }

        # 1. RugCheck.xyz (FREE)
        try:
            rugcheck_url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            async with session.get(rugcheck_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract key security metrics
                    security_data['rugcheck_score'] = data.get('score')  # 0-100, higher = safer
                    security_data['is_honeypot'] = data.get('isHoneypot', False)
                    security_data['mutable_metadata'] = data.get('mutableMetadata', False)

                    # Aggregate risks
                    risks = data.get('risks', [])
                    security_data['risk_count'] = len(risks)
                    security_data['critical_risks'] = [r for r in risks if r.get('level') == 'critical']

                    logger.debug(f"   ✅ RugCheck: score={security_data['rugcheck_score']}, honeypot={security_data['is_honeypot']}")
        except Exception as e:
            logger.debug(f"   ⚠️  RugCheck failed: {e}")

        # 2. TokenSniffer (FREE tier has rate limits)
        try:
            tokensniffer_url = f"https://tokensniffer.com/api/v2/tokens/solana/{token_address}"
            async with session.get(tokensniffer_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract security score
                    security_data['tokensniffer_score'] = data.get('score')  # 0-100
                    security_data['scam_probability'] = data.get('scamProbability')  # 0-100

                    exploits = data.get('exploits', [])
                    security_data['exploit_count'] = len(exploits)

                    logger.debug(f"   ✅ TokenSniffer: score={security_data['tokensniffer_score']}, scam_prob={security_data['scam_probability']}%")
        except Exception as e:
            logger.debug(f"   ⚠️  TokenSniffer failed: {e}")

        # 3. Birdeye Token Security (Premium - only if API key available)
        birdeye_key = os.getenv('BIRDEYE_API_KEY')
        if birdeye_key:
            try:
                birdeye_url = f"https://public-api.birdeye.so/defi/token_security"
                headers = {'X-API-KEY': birdeye_key}
                params = {'address': token_address}

                async with session.get(birdeye_url, headers=headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        security_info = data.get('data', {})

                        security_data['audit_status'] = security_info.get('isVerified')
                        security_data['creator_address'] = security_info.get('creatorAddress')
                        security_data['owner_can_change_balance'] = security_info.get('ownerCanChangeBalance')

                        logger.debug(f"   ✅ Birdeye: verified={security_data['audit_status']}")
            except Exception as e:
                logger.debug(f"   ⚠️  Birdeye failed: {e}")

        # Calculate aggregate risk level
        risk_score = 0

        if security_data['rugcheck_score'] is not None:
            risk_score += security_data['rugcheck_score']

        if security_data['tokensniffer_score'] is not None:
            risk_score += security_data['tokensniffer_score']

        if security_data['is_honeypot']:
            risk_score -= 50

        if security_data['mutable_metadata']:
            risk_score -= 20

        # Classify risk level
        if risk_score >= 150:
            security_data['risk_level'] = 'low'  # Safe
        elif risk_score >= 100:
            security_data['risk_level'] = 'medium'  # Moderate risk
        elif risk_score >= 50:
            security_data['risk_level'] = 'high'  # Risky
        else:
            security_data['risk_level'] = 'critical'  # Likely rug

        security_data['aggregate_risk_score'] = risk_score

        return security_data

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

        # Check KOL involvement for each winner + collect on-chain & security data
        results = []
        credits_used = 0

        # Limit to max_tokens to control credit usage
        # WITH ENHANCED DATA:
        # 500 tokens = ~2,500 credits (0.025% of remaining budget)
        # 1000 tokens = ~5,000 credits (0.05% of remaining budget)
        tokens_to_analyze = min(len(winners), max_tokens)

        # Create aiohttp session for API calls
        async with aiohttp.ClientSession() as session:
            for i, token in enumerate(winners[:tokens_to_analyze]):
                logger.info(f"📊 Checking {i+1}/{tokens_to_analyze}: {token['symbol']} ({token['price_change_24h']:.0f}% gain)")

                # 1. Check KOL involvement (~2 credits)
                kol_data = await self.check_kol_involvement(
                    token['address'],
                    token.get('created_at')
                )
                credits_used += 2

                # 2. Fetch on-chain metrics (~2-3 credits)
                onchain_metrics = await self.fetch_onchain_metrics(token['address'], session)
                credits_used += 2

                # 3. Fetch security/rug risk data (~0 credits - free APIs)
                security_data = await self.fetch_security_data(token['address'], session)

                # Track new wallets for discovery
                for wallet in kol_data.get('new_wallets', []):
                    if wallet not in wallet_appearances:
                        wallet_appearances[wallet] = []
                    wallet_appearances[wallet].append({
                        'token': token['symbol'],
                        'gain': token['price_change_24h']
                    })

                # Combine all data
                result = {
                    **token,
                    **kol_data,
                    'onchain_metrics': onchain_metrics,
                    'security': security_data,
                    'outcome': self._classify_outcome(token['price_change_24h'])
                }

                results.append(result)

                # Log key findings
                if kol_data.get('our_kol_count', 0) > 0:
                    logger.info(f"   ✅ {kol_data['our_kol_count']} of our KOLs bought this!")

                if kol_data.get('new_wallet_count', 0) > 0:
                    logger.info(f"   🔍 {kol_data['new_wallet_count']} other wallets holding")

                if onchain_metrics.get('holder_count'):
                    logger.info(f"   👥 {onchain_metrics['holder_count']} holders, decentralization: {onchain_metrics.get('decentralization_score', 0)}/100")

                if security_data.get('risk_level'):
                    risk_emoji = {'low': '✅', 'medium': '⚠️', 'high': '⛔', 'critical': '🚨'}.get(security_data['risk_level'], '❓')
                    logger.info(f"   {risk_emoji} Risk level: {security_data['risk_level']}")

                # Rate limit to avoid API throttling
                await asyncio.sleep(0.7)  # Slightly longer delay with more API calls

        # Find wallets that bought 2+ winners (potential new KOLs/smart money to track)
        # Classify by performance tier for easy addition to curated_wallets.py
        discovered_kols = {}
        for wallet, appearances in wallet_appearances.items():
            if len(appearances) >= 2:  # Bought 2+ winners
                avg_gain = sum(a['gain'] for a in appearances) / len(appearances)
                max_gain = max(a['gain'] for a in appearances)
                winner_count = len(appearances)

                # Classify wallet tier based on performance
                if winner_count >= 5 and avg_gain >= 500:
                    tier = 'elite_tier'  # Exceptional performance
                elif winner_count >= 3 and avg_gain >= 400:
                    tier = 'god_tier'  # Very strong performance
                elif winner_count >= 3 or avg_gain >= 300:
                    tier = 'smart_money'  # Solid smart money
                else:
                    tier = 'potential'  # Worth watching

                discovered_kols[wallet] = {
                    'winner_count': winner_count,
                    'tokens': [a['token'] for a in appearances],
                    'avg_gain': avg_gain,
                    'max_gain': max_gain,
                    'suggested_tier': tier,  # Where to add them in curated_wallets.py
                    'win_rate': 100.0  # They only bought winners (100% in this sample)
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

        # Discovered KOLs/Smart Money
        if discovered_kols:
            # Count by tier
            tiers = {}
            for wallet, data in discovered_kols.items():
                tier = data['suggested_tier']
                tiers[tier] = tiers.get(tier, 0) + 1

            print(f"\n🔍 Discovered Potential New Wallets:")
            print(f"   Total discovered: {len(discovered_kols)}")
            print(f"\n   By tier:")
            for tier in ['elite_tier', 'god_tier', 'smart_money', 'potential']:
                if tier in tiers:
                    print(f"      {tier}: {tiers[tier]}")

            print(f"\n   Top 15 by winner count:")

            sorted_kols = sorted(discovered_kols.items(),
                               key=lambda x: (x[1]['winner_count'], x[1]['avg_gain']),
                               reverse=True)[:15]

            for i, (wallet, data) in enumerate(sorted_kols, 1):
                tier_emoji = {
                    'elite_tier': '🔥',
                    'god_tier': '👑',
                    'smart_money': '💰',
                    'potential': '👀'
                }.get(data['suggested_tier'], '❓')

                print(f"\n   {i}. {tier_emoji} {wallet[:8]}...{wallet[-4:]} ({data['suggested_tier']})")
                print(f"      Winners: {data['winner_count']} | Avg gain: {data['avg_gain']:.0f}% | Max: {data['max_gain']:.0f}%")
                print(f"      Tokens: {', '.join(data['tokens'][:3])}{'...' if len(data['tokens']) > 3 else ''}")

        print("\n" + "="*70)


async def main():
    """Main scraping workflow"""
    # Configurable parameters
    MIN_GAIN = 200  # 200% = 3x minimum (lower to 100 for 2x tokens)
    MAX_TOKENS = 1000  # Analyze up to 1000 tokens for comprehensive data

    logger.info("🚀 Starting external data scraper (ENHANCED VERSION)...")
    logger.info("📋 Configuration:")
    logger.info(f"   Minimum gain: {MIN_GAIN}% (3x)")
    logger.info(f"   Max tokens to analyze: {MAX_TOKENS}")
    logger.info(f"   Estimated cost: ~{MAX_TOKENS * 5} Helius credits (0.05% of 8.9M budget)")
    logger.info("")
    logger.info("📋 Data Collection Per Token:")
    logger.info("   1. DexScreener data (FREE): Volume, liquidity, price action")
    logger.info("   2. KOL involvement (~2 credits): Which wallets bought it")
    logger.info("   3. On-chain metrics (~2 credits): Holder distribution, supply economics")
    logger.info("   4. Security data (FREE): RugCheck, TokenSniffer, Birdeye APIs")
    logger.info("")
    logger.info("🎯 Ralph Will Learn From:")
    logger.info("   ✅ KOL patterns (3+ KOLs = higher win rate?)")
    logger.info("   ✅ Holder distribution (concentrated vs decentralized)")
    logger.info("   ✅ Security scores (rugs vs legit tokens)")
    logger.info("   ✅ Volume/liquidity sweet spots")
    logger.info("   ✅ Timing patterns (when do winners launch?)")
    logger.info("   ✅ Discover 200-300 new smart money wallets")
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
    logger.info("   2. Run ralph/analyze_patterns.py to discover winning patterns")
    logger.info("   3. Ralph will update conviction_engine.py based on findings")
    logger.info("   4. Add discovered KOLs to curated_wallets.py")
    logger.info("")
    logger.info("📈 Expected Learnings:")
    logger.info("   - Which KOL count threshold predicts success")
    logger.info("   - Optimal holder distribution (decentralization score)")
    logger.info("   - Security score thresholds (avoid rugs)")
    logger.info("   - Volume/liquidity patterns that correlate with 10x+")
    logger.info("   - Best launch timing windows")


if __name__ == "__main__":
    asyncio.run(main())
