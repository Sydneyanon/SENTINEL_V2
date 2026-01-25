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
import ssl
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import Database
from tools.historical_data_collector import HistoricalDataCollector
from tools.enhanced_token_analyzer import EnhancedTokenAnalyzer


class DailyTokenCollector:
    """Collects top tokens daily for continuous ML dataset building"""

    def __init__(self):
        self.collector = HistoricalDataCollector()
        self.tokens_per_day = int(os.getenv('DAILY_COLLECTOR_COUNT', '50'))  # Default: 50 tokens/day

        # Enhanced analyzer for maximum data extraction
        self.analyzer = EnhancedTokenAnalyzer(
            helius_rpc_url=self.collector.helius_rpc_url,
            moralis_headers=self.collector.moralis_headers
        ) if self.collector.helius_rpc_url else None

    async def get_daily_top_tokens(self, limit: int = 100) -> list:
        """
        Get tokens that ALREADY RAN in the last 24 hours (yesterday's winners)

        This is HISTORICAL data collection:
        - Tokens that already pumped (we know the outcome)
        - Extract conditions BEFORE they ran
        - Extract whale wallets that bought EARLY
        - Perfect for ML: "These early signals → This outcome"

        Strategies:
        1. Moralis: Get recently graduated pump.fun tokens (last 24-48h)
        2. Check each token's price performance
        3. Filter for: Minimum 2x gain, $100K+ volume
        4. Outcome categorization: 2x, 10x, 50x, 100x+

        Args:
            limit: Number of tokens to collect (default: 100)

        Returns:
            List of token data with completed outcomes
        """
        logger.info("=" * 80)
        logger.info("📈 FETCHING YESTERDAY'S TOP PERFORMERS (MORALIS)")
        logger.info("=" * 80)
        logger.info(f"   Target: {limit} tokens that ALREADY RAN in last 24h")
        logger.info(f"   Source: Moralis graduated pump.fun tokens")
        logger.info(f"   Goal: Historical data with known outcomes for ML\n")

        if not self.collector.moralis_api_key:
            logger.error("❌ MORALIS_API_KEY not set - cannot fetch tokens")
            logger.error("   Get free API key at: https://admin.moralis.io")
            return []

        token_addresses = set()
        tokens_data = []

        # Create SSL context that doesn't verify certificates (for Railway/Docker environments)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
            # Strategy: Use Moralis to get recently graduated pump.fun tokens
            logger.info("📊 Fetching graduated tokens from Moralis...")

            url = "https://solana-gateway.moralis.io/token/mainnet/exchange/pumpfun/graduated?limit=100"
            headers = {'x-api-key': self.collector.moralis_api_key}

            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Extract tokens - Moralis returns list directly or in 'result' key
                        graduated_tokens = data if isinstance(data, list) else data.get('result', [])
                        logger.info(f"   Got {len(graduated_tokens)} graduated pump.fun tokens")

                        # Process each graduated token
                        for token in graduated_tokens:
                            if len(tokens_data) >= limit:
                                break

                            # Get token address from Moralis response
                            token_addr = token.get('tokenAddress') or token.get('address') or token.get('mint')
                            if not token_addr or token_addr in token_addresses:
                                continue

                            # ENHANCED: Get MAXIMUM data using enhanced analyzer
                            if self.analyzer:
                                token_data = await self.analyzer.analyze_token_complete(token_addr, session)
                            else:
                                # Fallback to basic DexScreener data
                                token_data = await self.collector.get_dexscreener_data(token_addr, session)

                            if not token_data:
                                continue

                            # CRITICAL FILTER: Only tokens that ALREADY RAN in last 24h
                            price_change_24h = token_data.get('price_change_24h', 0)
                            volume_24h = token_data.get('volume_24h', 0)
                            market_cap = token_data.get('market_cap', 0)

                            # Filters for "yesterday's winners":
                            # ADJUSTED: More realistic thresholds for graduated pump.fun tokens
                            # 1. Minimum 100% gain (2x) in 24h - they already ran
                            # 2. Minimum $50K volume - real activity (lowered from $100K)
                            # 3. Minimum $100K MCAP - not too small (lowered from $500K)
                            if price_change_24h < 100:  # Less than 2x = skip
                                continue

                            if volume_24h < 50000:  # Less than $50K volume = skip
                                continue

                            if market_cap < 100000:  # Less than $100K MCAP = too small
                                continue

                            # This is a winner! Add it
                            token_addresses.add(token_addr)
                            tokens_data.append(token_data)

                            # Log comprehensive data collected
                            logger.info(f"   ✅ {token_data.get('symbol')}: +{price_change_24h:.0f}% "
                                       f"(${market_cap/1e6:.1f}M MCAP, "
                                       f"Vol: ${volume_24h/1e3:.0f}K, "
                                       f"Top10: {token_data.get('top_10_holder_pct', 0):.1f}%)")

                            await asyncio.sleep(0.5)  # Rate limiting

                    elif resp.status == 401:
                        error_text = await resp.text()
                        logger.error(f"   ❌ Authentication failed (401): {error_text}")
                        logger.error(f"   Check MORALIS_API_KEY is set correctly")
                        logger.error(f"   Key preview: {self.collector.moralis_api_key[:8]}..." if self.collector.moralis_api_key else "   Key is None/empty!")
                    elif resp.status == 429:
                        logger.error(f"   ❌ Rate limited (429) - hit daily CU limit or too many requests")
                        logger.error(f"   Free tier: 40K CU/day, resets at midnight UTC")
                    else:
                        error_text = await resp.text()
                        logger.warning(f"   Failed: HTTP {resp.status} - {error_text}")

            except Exception as e:
                logger.error(f"   Error fetching from Moralis: {e}")
                import traceback
                logger.debug(traceback.format_exc())

            # Sort by 24h gain (highest first)
            tokens_data.sort(key=lambda x: x.get('price_change_24h', 0), reverse=True)

        logger.info(f"\n✅ Collected {len(tokens_data)} tokens that ALREADY RAN")
        if tokens_data:
            logger.info(f"   Top gainer: {tokens_data[0]['symbol']} (+{tokens_data[0]['price_change_24h']:.0f}%)")
            logger.info(f"   Median gain: +{tokens_data[len(tokens_data)//2]['price_change_24h']:.0f}%")

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

        # Extract EARLY whale activity (who bought BEFORE it pumped)
        if self.collector.helius_rpc_url:
            logger.info("\n" + "=" * 80)
            logger.info("🐋 EXTRACTING EARLY WHALE ACTIVITY")
            logger.info("=" * 80)
            logger.info("   Goal: Find wallets that bought BEFORE the pump")
            logger.info("   Method: Get transaction history, identify large early buys\n")

            for idx, token in enumerate(tokens_data, 1):
                logger.info(f"\n[{idx}/{len(tokens_data)}] {token['symbol']} (+{token.get('price_change_24h', 0):.0f}%)...")

                # Extract early whales (bought in first 20% of bonding curve or early post-grad)
                whales = await self._extract_early_whales(
                    token['token_address'],
                    token['symbol'],
                    token.get('price_usd', 0),
                    token.get('created_at', 0)
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

    async def _extract_early_whales(self, token_address: str, token_symbol: str,
                                    current_price: float, created_at: int) -> list:
        """
        Extract wallets that bought EARLY (before the pump)

        Strategy:
        1. Get token's transaction history (first 100-200 transfers)
        2. Identify large buys in the early phase
        3. "Early" = first 2 hours after creation OR before 30% bonding curve

        This is MUCH more valuable than current holders because:
        - These wallets spotted it early
        - They're the ones we want to follow in real-time
        """
        if not self.collector.helius_rpc_url:
            return []

        early_whales = []

        try:
            # Use Helius to get transaction signatures for this token
            # Then parse transfers to find early large buyers

            # For now, fall back to current large holders
            # TODO: Implement full transaction history parsing via Helius
            whales = await self.collector.extract_whale_wallets(
                token_address,
                token_symbol,
                current_price
            )

            # Mark all as "early_whale" since we're looking at tokens post-pump
            # These holders likely bought early since they're still holding
            for whale in whales:
                if whale not in self.collector.whale_wallets:
                    self.collector.whale_wallets[whale] = {
                        'tokens_bought': [],
                        'win_count': 0,
                        'total_invested': 0
                    }

                self.collector.whale_wallets[whale]['tokens_bought'].append({
                    'token': token_symbol,
                    'address': token_address,
                    'early_buyer': True,  # Assume early since still holding after pump
                    'detected_after_pump': True  # Historical data collection
                })

            return whales

        except Exception as e:
            logger.debug(f"   Error extracting early whales: {e}")
            return []

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
