#!/usr/bin/env python3
"""
Helius Backfill Collector - On-Chain ML Training Dataset Builder

Uses Helius DAS searchAssets API to discover pump.fun tokens (graduated),
then collects comprehensive features for Ralph's ML pipeline.

Advantages over DexScreener-only collection:
- Discovers ALL pump.fun tokens (not just boosted/promoted ones)
- Includes on-chain security data (authority checks, holder concentration)
- More diverse outcome distribution (captures rugs, small caps, mega runners)
- Rapidly fills dataset toward 200+ token threshold for auto-retraining

Cost: ~500 Helius credits per run (well within daily free tier)

Usage:
    python tools/helius_backfill_collector.py
    python tools/helius_backfill_collector.py --max-tokens 300
    python tools/helius_backfill_collector.py --program-scan-only
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
from loguru import logger

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from helius_fetcher import HeliusDataFetcher, PUMP_PROGRAM_ID, TOTAL_SUPPLY


class HeliusBackfillCollector:
    """
    Collects historical pump.fun token data using Helius for ML training.

    Discovery pipeline:
    1. Helius DAS searchAssets (finds tokens by program authority)
    2. Fallback: Helius program TX scanning (parses recent program interactions)
    3. DexScreener validation + comprehensive market data (FREE)
    4. Helius enrichment: authority check, holder concentration (gated)
    5. Outcome classification and deduplication
    6. Append to historical_training_data.json
    """

    def __init__(self, database=None):
        self.helius = HeliusDataFetcher()
        self.backfill_cfg = config.HELIUS_BACKFILL
        self.data_file = 'data/historical_training_data.json'
        self.database = database  # Persistent storage across Railway deploys
        self.existing_addresses = set()
        self.runner_data = {}  # Stores runner discovery data for classification
        self.stats = {
            'discovered': 0,
            'graduated': 0,
            'enriched': 0,
            'skipped_existing': 0,
            'skipped_no_dex': 0,
            'skipped_filters': 0,
            'credits_used_estimate': 0,
        }

    async def _load_existing_data(self) -> dict:
        """Load existing training data from DB first, fall back to file"""
        tokens = []

        # Primary: load from database (survives Railway deploys)
        if self.database:
            try:
                tokens = await self.database.load_training_tokens()
                if tokens:
                    logger.info(f"   📂 Loaded {len(tokens)} tokens from database (persistent)")
            except Exception as e:
                logger.warning(f"   ⚠️ DB load failed, falling back to file: {e}")
                tokens = []

        # Fallback: load from file
        if not tokens:
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    tokens = data.get('tokens', [])
                    logger.info(f"   📁 Loaded {len(tokens)} tokens from file (fallback)")
            except FileNotFoundError:
                logger.info("   No existing dataset found, creating new one")
            except Exception as e:
                logger.error(f"   Error loading existing data: {e}")

        # Build dedup set
        for token in tokens:
            addr = token.get('token_address', '')
            if addr:
                self.existing_addresses.add(addr)

        return {'tokens': tokens, 'total_tokens': len(tokens)}

    async def discover_runners_from_dexscreener(self) -> List[Dict]:
        """
        Discover PROVEN RUNNERS from DexScreener - tokens with high price gains.

        This method specifically targets tokens that have ALREADY shown they can run,
        which provides much better ML training data than random tokens.

        Filters:
        - Min +50% price change in 24h OR +30% in 6h
        - Min $50K MCAP (graduated, not dust)
        - Max $10M MCAP (catch before mega run)
        - Min $10K volume (real trading)
        - Prefers Raydium pairs (graduated from pump.fun)

        Returns:
            List of dicts with token address and performance data
        """
        runner_cfg = self.backfill_cfg.get('runner_discovery', {})
        if not runner_cfg.get('enabled', True):
            return []

        min_change_24h = runner_cfg.get('min_price_change_24h', 50)
        min_change_6h = runner_cfg.get('min_price_change_6h', 30)
        min_mcap = runner_cfg.get('min_mcap', 50_000)
        max_mcap = runner_cfg.get('max_mcap', 10_000_000)
        min_volume = runner_cfg.get('min_volume_24h', 10_000)
        min_liq = runner_cfg.get('min_liquidity', 5_000)
        prefer_raydium = runner_cfg.get('prefer_raydium', True)
        max_age_hours = runner_cfg.get('max_age_hours', 48)

        runners = []
        seen_addresses = set()

        logger.info(f"   Runner filters: +{min_change_24h}% 24h OR +{min_change_6h}% 6h, "
                    f"MCAP ${min_mcap/1000:.0f}K-${max_mcap/1000000:.0f}M, Vol ${min_volume/1000:.0f}K+")

        async with aiohttp.ClientSession() as session:
            # Search multiple queries to find Solana gainers
            search_queries = [
                "solana",
                "pump",
                "sol",
                "raydium",
            ]

            for query in search_queries:
                try:
                    search_url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
                    async with session.get(
                        search_url, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                        for pair in data.get('pairs', []):
                            # Only Solana
                            if pair.get('chainId') != 'solana':
                                continue

                            addr = pair.get('baseToken', {}).get('address', '')
                            if not addr or addr in seen_addresses:
                                continue

                            # Get metrics
                            mcap = pair.get('marketCap') or pair.get('fdv') or 0
                            liquidity = pair.get('liquidity', {}).get('usd', 0) or 0
                            volume_24h = pair.get('volume', {}).get('h24', 0) or 0
                            price_change_24h = pair.get('priceChange', {}).get('h24', 0) or 0
                            price_change_6h = pair.get('priceChange', {}).get('h6', 0) or 0
                            dex_id = pair.get('dexId', '').lower()

                            # Apply filters
                            if mcap < min_mcap or mcap > max_mcap:
                                continue
                            if liquidity < min_liq:
                                continue
                            if volume_24h < min_volume:
                                continue

                            # Check if it's a runner (high price gain)
                            is_runner = (price_change_24h >= min_change_24h or
                                         price_change_6h >= min_change_6h)
                            if not is_runner:
                                continue

                            # Prefer Raydium (graduated from pump.fun)
                            if prefer_raydium and 'raydium' not in dex_id:
                                # Still include but mark as non-raydium
                                pass

                            # Check age if available
                            pair_created = pair.get('pairCreatedAt', 0)
                            if pair_created and max_age_hours:
                                age_hours = (datetime.utcnow().timestamp() * 1000 - pair_created) / (1000 * 3600)
                                if age_hours > max_age_hours:
                                    continue

                            seen_addresses.add(addr)
                            runners.append({
                                'address': addr,
                                'symbol': pair.get('baseToken', {}).get('symbol', '?'),
                                'mcap': mcap,
                                'price_change_24h': price_change_24h,
                                'price_change_6h': price_change_6h,
                                'volume_24h': volume_24h,
                                'liquidity': liquidity,
                                'dex_id': dex_id,
                                'is_raydium': 'raydium' in dex_id,
                            })

                except Exception as e:
                    logger.debug(f"   DexScreener search '{query}' error: {e}")
                await asyncio.sleep(0.5)

            # Also check recent Solana pairs for runners
            try:
                pairs_url = "https://api.dexscreener.com/latest/dex/pairs/solana"
                async with session.get(
                    pairs_url, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pair in data.get('pairs', []):
                            addr = pair.get('baseToken', {}).get('address', '')
                            if not addr or addr in seen_addresses:
                                continue

                            mcap = pair.get('marketCap') or pair.get('fdv') or 0
                            liquidity = pair.get('liquidity', {}).get('usd', 0) or 0
                            volume_24h = pair.get('volume', {}).get('h24', 0) or 0
                            price_change_24h = pair.get('priceChange', {}).get('h24', 0) or 0
                            price_change_6h = pair.get('priceChange', {}).get('h6', 0) or 0
                            dex_id = pair.get('dexId', '').lower()

                            if mcap < min_mcap or mcap > max_mcap:
                                continue
                            if liquidity < min_liq:
                                continue
                            if volume_24h < min_volume:
                                continue

                            is_runner = (price_change_24h >= min_change_24h or
                                         price_change_6h >= min_change_6h)
                            if not is_runner:
                                continue

                            seen_addresses.add(addr)
                            runners.append({
                                'address': addr,
                                'symbol': pair.get('baseToken', {}).get('symbol', '?'),
                                'mcap': mcap,
                                'price_change_24h': price_change_24h,
                                'price_change_6h': price_change_6h,
                                'volume_24h': volume_24h,
                                'liquidity': liquidity,
                                'dex_id': dex_id,
                                'is_raydium': 'raydium' in dex_id,
                            })
            except Exception as e:
                logger.debug(f"   DexScreener pairs error: {e}")

        # Sort by best performance (highest 24h gain)
        runners.sort(key=lambda x: x.get('price_change_24h', 0), reverse=True)

        logger.info(f"   🏃 Runner discovery: {len(runners)} tokens with {min_change_24h}%+ gains")

        # Log top 5 runners
        for r in runners[:5]:
            logger.info(f"      {r['symbol']}: +{r['price_change_24h']:.0f}% 24h, "
                        f"${r['mcap']/1000:.0f}K MCAP, ${r['volume_24h']/1000:.0f}K vol")

        return runners

    async def discover_from_dexscreener(self) -> List[str]:
        """
        Discover Solana tokens from DexScreener endpoints (FREE, no credits).

        Uses multiple DexScreener APIs to find tokens that definitely have
        trading pairs (solving the problem where searchAssets finds un-graduated
        pump.fun tokens that aren't on any DEX yet).

        Sources:
        - token-boosts/latest/v1: Recently boosted tokens
        - token-profiles/latest/v1: Recently updated profiles
        - search?q=pump.fun: Pump.fun token search results
        - latest/dex/pairs/solana: Recent Solana pairs

        Returns:
            List of Solana token mint addresses
        """
        mints = set()

        endpoints = [
            ("boosted tokens", "https://api.dexscreener.com/token-boosts/latest/v1"),
            ("token profiles", "https://api.dexscreener.com/token-profiles/latest/v1"),
        ]

        async with aiohttp.ClientSession() as session:
            # Fetch boosted + profiles endpoints
            for label, url in endpoints:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status != 200:
                            logger.debug(f"   DexScreener {label}: HTTP {resp.status}")
                            continue
                        data = await resp.json()
                        for item in data:
                            if item.get('chainId') == 'solana':
                                addr = item.get('tokenAddress', '')
                                if addr:
                                    mints.add(addr)
                        logger.info(f"   {label}: {len(mints)} Solana tokens so far")
                except Exception as e:
                    logger.debug(f"   DexScreener {label} error: {e}")
                await asyncio.sleep(0.5)

            # Search for pump.fun tokens
            try:
                search_url = "https://api.dexscreener.com/latest/dex/search?q=pump.fun"
                async with session.get(
                    search_url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pair in data.get('pairs', []):
                            if pair.get('chainId') == 'solana':
                                addr = pair.get('baseToken', {}).get('address', '')
                                if addr:
                                    mints.add(addr)
                        logger.info(f"   pump.fun search: {len(mints)} Solana tokens so far")
            except Exception as e:
                logger.debug(f"   DexScreener search error: {e}")
            await asyncio.sleep(0.5)

            # Recent Solana pairs
            try:
                pairs_url = "https://api.dexscreener.com/latest/dex/pairs/solana"
                async with session.get(
                    pairs_url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pair in data.get('pairs', []):
                            addr = pair.get('baseToken', {}).get('address', '')
                            if addr:
                                mints.add(addr)
                        logger.info(f"   recent pairs: {len(mints)} Solana tokens so far")
            except Exception as e:
                logger.debug(f"   DexScreener pairs error: {e}")

        logger.info(f"   DexScreener discovery total: {len(mints)} unique Solana tokens")
        return list(mints)

    async def discover_tokens(self) -> List[str]:
        """
        Discover pump.fun token mints using Helius APIs + DexScreener endpoints.

        Pipeline (NEW - Runner-First):
        0. RUNNER DISCOVERY (primary) - finds tokens that have ALREADY proven they can run
        1. DexScreener discovery (fallback) - finds tokens WITH trading pairs
        2. Helius searchAssets (DAS) - broader on-chain discovery
        3. Helius program TX scanning - finds recent program activity

        Deduplicates against existing dataset.

        Returns:
            List of new token mint addresses to process
        """
        all_mints = set()
        runner_mints = []
        step = 1

        # Calculate total steps
        # NOTE: Helius searchAssets and program scan find PRE-BOND tokens (still on pump.fun curve)
        # These are useless for runner discovery - only use DexScreener which finds GRADUATED tokens
        runner_cfg = self.backfill_cfg.get('runner_discovery', {})
        use_runner_discovery = runner_cfg.get('enabled', True)
        use_dexscreener = self.backfill_cfg.get('use_dexscreener_discovery', True)
        # Default FALSE for Helius - it finds pre-bond tokens which pollutes runner data
        use_helius_search = self.backfill_cfg.get('use_search_assets', False)
        use_helius_scan = self.backfill_cfg.get('use_program_scan', False)

        total_steps = sum([
            use_runner_discovery,
            use_dexscreener,
            use_helius_search,
            use_helius_scan,
        ])

        # =====================================================================
        # PRIMARY: Runner Discovery (tokens that have ALREADY shown they can run)
        # =====================================================================
        if use_runner_discovery:
            logger.info(f"\n   [{step}/{total_steps}] 🏃 RUNNER DISCOVERY (proven gainers)...")
            runners = await self.discover_runners_from_dexscreener()

            # Store runner data for later use (classification)
            self.runner_data = {r['address']: r for r in runners}

            # Extract just the addresses
            runner_mints = [r['address'] for r in runners if r['address'] not in self.existing_addresses]
            all_mints.update(runner_mints)

            logger.info(f"   Runners found: {len(runners)}, new to process: {len(runner_mints)}")
            step += 1

            # If we found enough runners, skip generic discovery
            max_tokens = self.backfill_cfg.get('max_tokens_per_run', 200)
            if len(runner_mints) >= max_tokens:
                logger.info(f"   ✅ Found {len(runner_mints)} runners - skipping generic discovery")
                new_mints = runner_mints[:max_tokens]
                self.stats['discovered'] = len(all_mints)
                self.stats['skipped_existing'] = len(runners) - len(runner_mints)
                return new_mints

        # =====================================================================
        # FALLBACK: Generic DexScreener Discovery (only if not enough runners)
        # NOTE: We do NOT use Helius for fallback - it finds PRE-BOND tokens
        # =====================================================================
        need_fallback = runner_cfg.get('fallback_to_generic', True) and len(runner_mints) < 20
        if need_fallback:
            logger.info(f"\n   📢 Only {len(runner_mints)} runners found, using DexScreener fallback...")

            # Generic DexScreener endpoints (FREE - finds GRADUATED tokens with pairs)
            if use_dexscreener:
                logger.info(f"\n   [{step}/{total_steps}] Discovering tokens via DexScreener endpoints (FREE)...")
                dex_mints = await self.discover_from_dexscreener()
                all_mints.update(dex_mints)
                logger.info(f"   DexScreener found: {len(dex_mints)} mints")
                step += 1

            # DISABLED: Helius searchAssets finds PRE-BOND tokens (pump.fun still authority)
            # These pollute runner data with tokens that haven't graduated yet
            if use_helius_search:
                logger.info(f"\n   [{step}/{total_steps}] Discovering tokens via Helius DAS searchAssets...")
                logger.warning("   ⚠️ Helius searchAssets finds PRE-BOND tokens - consider disabling")
                pages = self.backfill_cfg.get('search_pages', 5)
                search_mints = await self.helius.search_pump_graduates(
                    limit_per_page=200,
                    pages=pages
                )
                new_from_search = len(set(search_mints) - all_mints)
                all_mints.update(search_mints)
                self.stats['credits_used_estimate'] += pages
                logger.info(f"   searchAssets found: {len(search_mints)} mints ({new_from_search} new)")
                step += 1

            # DISABLED: Program TX scanning also finds PRE-BOND tokens
            if use_helius_scan:
                logger.info(f"\n   [{step}/{total_steps}] Discovering tokens via program TX scanning...")
                logger.warning("   ⚠️ Program scan finds PRE-BOND tokens - consider disabling")
                tx_limit = self.backfill_cfg.get('program_scan_tx_limit', 500)
                program_mints = await self.helius.scan_program_graduates(tx_limit=tx_limit)
                new_from_scan = len(set(program_mints) - all_mints)
                all_mints.update(program_mints)
                self.stats['credits_used_estimate'] += 10
                logger.info(f"   Program scan found: {len(program_mints)} mints ({new_from_scan} new)")

        # Deduplicate against existing dataset
        new_mints = [m for m in all_mints if m not in self.existing_addresses]
        self.stats['discovered'] = len(all_mints)
        self.stats['skipped_existing'] = len(all_mints) - len(new_mints)

        # Cap at max tokens per run
        max_tokens = self.backfill_cfg.get('max_tokens_per_run', 200)
        if len(new_mints) > max_tokens:
            new_mints = new_mints[:max_tokens]

        logger.info(f"\n   Discovery complete: {len(all_mints)} total, "
                     f"{self.stats['skipped_existing']} existing, "
                     f"{len(new_mints)} new to process")

        return new_mints

    async def collect_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Collect comprehensive data for a single token.

        Pipeline:
        1. DexScreener: market data, volume, price changes, social, transactions
        2. Helius: authority check (mint/freeze revocation)
        3. Helius: holder concentration (top 10 holders)
        4. Classify outcome based on market cap

        Returns:
            Dict with comprehensive token features or None if filtered out
        """
        try:
            # Step 1: DexScreener comprehensive data (FREE)
            dex_data = await self.helius.get_dexscreener_data(token_address)

            if not dex_data:
                self.stats['skipped_no_dex'] += 1
                return None

            market_cap = dex_data.get('market_cap', 0)
            liquidity = dex_data.get('liquidity', 0)
            volume_24h = dex_data.get('volume_24h', 0)

            # Apply filters (relaxed for ML training diversity)
            min_mcap = self.backfill_cfg.get('min_mcap_graduated', 5000)
            max_mcap = self.backfill_cfg.get('max_mcap', 500_000_000)
            min_liq = self.backfill_cfg.get('min_liquidity', 1000)
            min_vol = self.backfill_cfg.get('min_volume_24h', 100)

            if market_cap < min_mcap or market_cap > max_mcap:
                self.stats['skipped_filters'] += 1
                logger.debug(f"   Filter: {token_address[:8]} MCAP ${market_cap:,.0f} outside range")
                return None

            if liquidity < min_liq:
                self.stats['skipped_filters'] += 1
                logger.debug(f"   Filter: {token_address[:8]} liquidity ${liquidity:,.0f} < ${min_liq:,}")
                return None

            if volume_24h < min_vol:
                self.stats['skipped_filters'] += 1
                logger.debug(f"   Filter: {token_address[:8]} volume ${volume_24h:,.0f} < ${min_vol:,}")
                return None

            # Build comprehensive token record
            token_data = {
                'token_address': token_address,
                'symbol': dex_data.get('token_symbol', 'UNKNOWN'),
                'name': dex_data.get('token_name', 'Unknown'),

                # Price & Market Cap
                'price_usd': dex_data.get('price_usd', 0),
                'market_cap': market_cap,

                # Liquidity
                'liquidity': liquidity,
                'liquidity_usd': liquidity,  # Alias for ML pipeline
                'liquidity_base': dex_data.get('liquidity_base', 0),
                'liquidity_quote': dex_data.get('liquidity_quote', 0),
                'reserve_ratio': dex_data.get('reserve_ratio', 0),

                # Volume (multi-timeframe)
                'volume_24h': volume_24h,
                'volume_6h': dex_data.get('volume_6h', 0),
                'volume_1h': dex_data.get('volume_1h', 0),

                # Price changes (multi-timeframe)
                'price_change_5m': dex_data.get('price_change_5m', 0),
                'price_change_1h': dex_data.get('price_change_1h', 0),
                'price_change_6h': dex_data.get('price_change_6h', 0),
                'price_change_24h': dex_data.get('price_change_24h', 0),

                # Transaction counts
                'buys_24h': dex_data.get('buys_24h', 0),
                'sells_24h': dex_data.get('sells_24h', 0),
                'buys_6h': dex_data.get('buys_6h', 0),
                'sells_6h': dex_data.get('sells_6h', 0),
                'buys_1h': dex_data.get('buys_1h', 0),
                'sells_1h': dex_data.get('sells_1h', 0),

                # Buy percentages (for legacy compatibility)
                'buy_percentage_24h': self._buy_pct(
                    dex_data.get('buys_24h', 0), dex_data.get('sells_24h', 0)
                ),
                'buy_percentage_6h': self._buy_pct(
                    dex_data.get('buys_6h', 0), dex_data.get('sells_6h', 0)
                ),

                # Derived metrics (for ML pipeline)
                'buy_pressure_1h': dex_data.get('buy_pressure_1h', 0),
                'buy_pressure_6h': dex_data.get('buy_pressure_6h', 0),
                'volume_velocity_1h': dex_data.get('volume_velocity_1h', 0),
                'momentum_score': dex_data.get('momentum_score', 0),

                # Social verification
                'has_website': dex_data.get('has_website', False),
                'has_twitter': dex_data.get('has_twitter', False),
                'has_telegram': dex_data.get('has_telegram', False),
                'has_discord': dex_data.get('has_discord', False),
                'social_count': dex_data.get('social_count', 0),

                # Risk signals
                'boost_active': dex_data.get('boost_active', 0),
                'pair_created_at': dex_data.get('pair_created_at', 0),

                # On-chain fields (populated by Helius enrichment)
                'holder_count': 0,
                'top_10_concentration_pct': 0,
                'top_3_concentration_pct': 0,
                'top_10_holder_pct': 0,
                'decentralization_score': 0,
                'mint_authority_revoked': True,
                'freeze_authority_revoked': True,
                'authority_risk_flags': [],

                # Transaction pattern fields (Helius parsed TX enrichment)
                'unique_buyers': 0,
                'unique_sellers': 0,
                'tx_buy_count': 0,
                'tx_sell_count': 0,
                'tx_buy_ratio': 0,
                'large_sell_count': 0,

                # Fields not available in backfill (set defaults)
                'our_kol_count': 0,
                'new_wallet_count': 0,
                'bonding_velocity': 0,

                # Security (defaults - can't check retroactively)
                'security': {
                    'rugcheck_score': 0,
                    'rugged': False,
                    'is_honeypot': False,
                    'risk_level': 'unknown',
                },

                # Metadata
                'collected_via': 'helius_backfill',
                'collected_at': datetime.utcnow().isoformat(),
                'created_at': dex_data.get('pair_created_at', 0),
            }

            # Step 2: Helius authority check (~1 credit)
            if self.backfill_cfg.get('enrich_with_helius', True):
                await self._enrich_authority(token_data, token_address)
                await asyncio.sleep(self.backfill_cfg.get('helius_rate_limit', 0.3))

            # Step 3: Helius holder concentration (~10 credits)
            if self.backfill_cfg.get('enrich_with_helius', True):
                await self._enrich_holders(token_data, token_address)
                await asyncio.sleep(self.backfill_cfg.get('helius_rate_limit', 0.3))

            # Step 4: Helius transaction patterns (~5 credits)
            if self.backfill_cfg.get('enrich_with_helius', True):
                await self._enrich_transactions(token_data, token_address)
                await asyncio.sleep(self.backfill_cfg.get('helius_rate_limit', 0.3))

            # Step 5: Classify outcome
            token_data['outcome'] = self._classify_outcome(token_data)

            # Calculate token age
            if token_data.get('created_at') and token_data['created_at'] > 0:
                try:
                    created = datetime.fromtimestamp(token_data['created_at'] / 1000)
                    age_hours = (datetime.utcnow() - created).total_seconds() / 3600
                    token_data['token_age_hours'] = age_hours
                except (ValueError, OSError):
                    token_data['token_age_hours'] = 0
            else:
                token_data['token_age_hours'] = 0

            self.stats['enriched'] += 1
            return token_data

        except Exception as e:
            logger.error(f"   Error collecting data for {token_address[:8]}: {e}")
            return None

    async def _enrich_authority(self, token_data: Dict, token_address: str):
        """Add mint/freeze authority data from Helius"""
        try:
            auth_result = await self.helius.check_token_authority(token_address)

            if auth_result.get('success'):
                token_data['mint_authority_revoked'] = auth_result.get('mint_revoked', True)
                token_data['freeze_authority_revoked'] = auth_result.get('freeze_revoked', True)
                token_data['authority_risk_flags'] = auth_result.get('risk_flags', [])

                # Update security risk level based on authority
                risk_flags = auth_result.get('risk_flags', [])
                if 'MINT_ACTIVE' in risk_flags and 'FREEZE_ACTIVE' in risk_flags:
                    token_data['security']['risk_level'] = 'critical'
                elif 'MINT_ACTIVE' in risk_flags or 'FREEZE_ACTIVE' in risk_flags:
                    token_data['security']['risk_level'] = 'high'
                else:
                    token_data['security']['risk_level'] = 'low'

                self.stats['credits_used_estimate'] += 1

        except Exception as e:
            logger.debug(f"   Authority check error: {e}")

    async def _enrich_holders(self, token_data: Dict, token_address: str):
        """Add holder concentration data from Helius"""
        try:
            holder_result = await self.helius.get_token_holders(token_address, limit=10)

            if holder_result and holder_result.get('holders'):
                holders = holder_result['holders']
                total_supply = holder_result.get('total_supply', 0)

                if total_supply > 0:
                    # Calculate concentration metrics
                    top_10_total = sum(h.get('amount', 0) for h in holders[:10])
                    top_3_total = sum(h.get('amount', 0) for h in holders[:3])

                    top_10_pct = (top_10_total / total_supply) * 100
                    top_3_pct = (top_3_total / total_supply) * 100

                    token_data['holder_count'] = len(holders)
                    token_data['top_10_concentration_pct'] = round(top_10_pct, 2)
                    token_data['top_3_concentration_pct'] = round(top_3_pct, 2)
                    token_data['top_10_holder_pct'] = round(top_10_pct, 2)

                    # Decentralization score: 100 = perfectly distributed, 0 = one holder
                    token_data['decentralization_score'] = round(
                        max(0, 100 - top_10_pct), 2
                    )

                    # Set onchain_metrics for ML pipeline compatibility
                    token_data['onchain_metrics'] = {
                        'holder_count': len(holders),
                        'top_10_concentration_pct': round(top_10_pct, 2),
                        'top_3_concentration_pct': round(top_3_pct, 2),
                        'decentralization_score': round(max(0, 100 - top_10_pct), 2),
                    }

                self.stats['credits_used_estimate'] += 10

        except Exception as e:
            logger.debug(f"   Holder enrichment error: {e}")

    async def _enrich_transactions(self, token_data: Dict, token_address: str):
        """Add transaction pattern data from Helius parsed transactions.

        Key runner signals:
        - unique_buyers: More distinct wallets buying = more organic demand
        - buy_ratio: High buy/total ratio = sustained buying pressure
        - large_sell_count: Insider dumps = rug signal
        """
        try:
            tx_result = await self.helius.get_recent_token_transactions(
                token_address, limit=100
            )

            if tx_result.get('success'):
                token_data['unique_buyers'] = tx_result.get('unique_buyers', 0)
                token_data['unique_sellers'] = tx_result.get('unique_sellers', 0)
                token_data['tx_buy_count'] = tx_result.get('buy_count', 0)
                token_data['tx_sell_count'] = tx_result.get('sell_count', 0)
                token_data['tx_buy_ratio'] = round(tx_result.get('buy_ratio', 0), 4)
                token_data['large_sell_count'] = len(tx_result.get('large_sells', []))

                self.stats['credits_used_estimate'] += 5

        except Exception as e:
            logger.debug(f"   Transaction enrichment error: {e}")

    def _classify_outcome(self, token_data: Dict) -> str:
        """
        Classify token outcome for ML training.

        NEW (2026-01-29): Uses PRICE PERFORMANCE as primary signal.
        This is more relevant for ML training because we want to learn
        what patterns lead to big price moves, not just absolute MCAP.

        Classification by price_change_24h:
        - mega_runner: +500%+ (5x in 24h - rare)
        - big_runner:  +200-500% (3-5x in 24h)
        - runner:      +100-200% (2-3x in 24h)
        - gainer:      +50-100% (1.5-2x in 24h)
        - flat:        0-50% (minimal movement)
        - dumper:      <0% (negative movement)

        Falls back to MCAP if discovered via non-runner method.
        """
        # Check if we have runner data from discovery
        token_address = token_data.get('token_address', '')
        runner_data = getattr(self, 'runner_data', {}).get(token_address)

        # Use price_change from runner data or token_data
        if runner_data:
            price_change_24h = runner_data.get('price_change_24h', 0)
        else:
            price_change_24h = token_data.get('price_change_24h', 0)

        # Also check security for potential rug classification
        risk_flags = token_data.get('authority_risk_flags', [])
        if 'MINT_ACTIVE' in risk_flags and 'FREEZE_ACTIVE' in risk_flags:
            return 'rug_risk'

        # PRIMARY: Classify by price performance (what we actually care about)
        if price_change_24h >= 500:
            return 'mega_runner'  # 5x+ in 24h
        elif price_change_24h >= 200:
            return 'big_runner'   # 3-5x in 24h
        elif price_change_24h >= 100:
            return 'runner'       # 2-3x in 24h
        elif price_change_24h >= 50:
            return 'gainer'       # 1.5-2x in 24h
        elif price_change_24h > 0:
            return 'flat'         # Minimal positive movement
        elif price_change_24h < -20:
            return 'dumper'       # Significant dump
        else:
            # FALLBACK: Use MCAP for tokens without price data
            mcap = token_data.get('market_cap', 0)
            if mcap >= 50_000_000:
                return 'big_runner'
            elif mcap >= 10_000_000:
                return 'runner'
            elif mcap >= 2_000_000:
                return 'gainer'
            else:
                return 'flat'

    def _buy_pct(self, buys: int, sells: int) -> float:
        """Calculate buy percentage"""
        total = buys + sells
        return (buys / total * 100) if total > 0 else 0

    async def run(self, max_tokens: int = None, program_scan_only: bool = False):
        """
        Execute the full backfill pipeline.

        Args:
            max_tokens: Override max tokens per run
            program_scan_only: Only use program TX scanning (skip searchAssets)
        """
        logger.info("=" * 80)
        logger.info("HELIUS BACKFILL COLLECTOR - ML Training Dataset Builder")
        logger.info("=" * 80)
        logger.info(f"   Date: {datetime.utcnow().date()}")
        logger.info(f"   Config: dexDiscovery={self.backfill_cfg.get('use_dexscreener_discovery', True)}, "
                     f"searchAssets={self.backfill_cfg.get('use_search_assets')}, "
                     f"programScan={self.backfill_cfg.get('use_program_scan')}")
        logger.info(f"   Filters: MCAP ${self.backfill_cfg.get('min_mcap_graduated', 5000):,}-"
                     f"${self.backfill_cfg.get('max_mcap', 500_000_000):,}, "
                     f"Liq ${self.backfill_cfg.get('min_liquidity', 1000):,}+, "
                     f"Vol ${self.backfill_cfg.get('min_volume_24h', 100):,}+")
        logger.info("")

        if max_tokens:
            self.backfill_cfg['max_tokens_per_run'] = max_tokens

        if program_scan_only:
            self.backfill_cfg['use_search_assets'] = False

        # Step 1: Load existing data for deduplication
        logger.info("[Step 1/4] Loading existing dataset...")
        existing_data = await self._load_existing_data()
        existing_tokens = existing_data.get('tokens', [])

        # Step 2: Discover new token mints
        logger.info("\n[Step 2/4] Discovering pump.fun tokens via Helius...")
        new_mints = await self.discover_tokens()

        if not new_mints:
            logger.info("\n   No new tokens to process. Dataset is up to date.")
            self._print_summary(0, existing_tokens)
            return

        # Step 3: Collect comprehensive data for each token
        logger.info(f"\n[Step 3/4] Collecting comprehensive data for {len(new_mints)} tokens...")
        new_tokens = []
        rate_limit = self.backfill_cfg.get('dexscreener_rate_limit', 0.4)

        for idx, mint in enumerate(new_mints, 1):
            if idx % 25 == 0 or idx == 1:
                logger.info(f"\n   Processing {idx}/{len(new_mints)}...")

            token_data = await self.collect_token_data(mint)

            if token_data:
                new_tokens.append(token_data)
                symbol = token_data.get('symbol', '?')
                mcap = token_data.get('market_cap', 0)
                outcome = token_data.get('outcome', '?')
                logger.info(f"   [{idx}] {symbol}: ${mcap:,.0f} MCAP ({outcome})")

            # Rate limit DexScreener
            await asyncio.sleep(rate_limit)

        self.stats['graduated'] = len(new_tokens)

        if not new_tokens:
            logger.info("\n   No tokens passed filters. Try adjusting config thresholds.")
            self._print_summary(0, existing_tokens)
            return

        # Step 4: Save results
        logger.info(f"\n[Step 4/4] Saving {len(new_tokens)} new tokens to dataset...")
        all_tokens = existing_tokens + new_tokens

        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_tokens': len(all_tokens),
            'last_backfill': datetime.utcnow().isoformat(),
            'tokens_added_this_run': len(new_tokens),
            'discovery_method': 'helius_backfill',
            'outcome_distribution': self._get_outcome_distribution(all_tokens),
            'tokens': all_tokens,
        }

        os.makedirs('data', exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(output, f, indent=2)
        logger.info(f"   📁 Saved to {self.data_file}")

        # Persist ALL tokens to database (survives Railway deploys)
        if self.database:
            try:
                await self.database.save_training_tokens(all_tokens, source='backfill')
                logger.info(f"   💾 Persisted {len(all_tokens)} tokens to database")
            except Exception as e:
                logger.error(f"   ⚠️ DB persist failed (file save OK): {e}")

        self._print_summary(len(new_tokens), all_tokens)

    def _get_outcome_distribution(self, tokens: list) -> dict:
        """Get distribution of outcomes"""
        dist = defaultdict(int)
        for token in tokens:
            dist[token.get('outcome', 'unknown')] += 1
        return dict(dist)

    def _print_summary(self, new_count: int, all_tokens: list):
        """Print collection summary"""
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)

        logger.info(f"\n   Discovery:")
        logger.info(f"      Tokens discovered:    {self.stats['discovered']}")
        logger.info(f"      Already in dataset:    {self.stats['skipped_existing']}")
        logger.info(f"      No DexScreener pair:   {self.stats['skipped_no_dex']}")
        logger.info(f"      Failed filters:        {self.stats['skipped_filters']}")
        logger.info(f"      Successfully enriched: {self.stats['enriched']}")

        logger.info(f"\n   Dataset:")
        logger.info(f"      New tokens added:     +{new_count}")
        logger.info(f"      Total tokens:          {len(all_tokens)}")

        dist = self._get_outcome_distribution(all_tokens)
        logger.info(f"\n   Outcome Distribution (by price performance):")
        # New performance-based categories
        for outcome in ['mega_runner', 'big_runner', 'runner', 'gainer', 'flat', 'dumper', 'rug_risk', 'unknown']:
            count = dist.get(outcome, 0)
            if count > 0:
                pct = count / len(all_tokens) * 100 if all_tokens else 0
                logger.info(f"      {outcome:12s}: {count:4d} ({pct:.1f}%)")
        # Legacy categories (for backwards compatibility)
        legacy_cats = ['100x+', '50x', '10x', '2x', 'small']
        legacy_count = sum(dist.get(c, 0) for c in legacy_cats)
        if legacy_count > 0:
            logger.info(f"\n   (Legacy MCAP categories: {legacy_count} tokens)")

        logger.info(f"\n   Credits:")
        logger.info(f"      Estimated used:        ~{self.stats['credits_used_estimate']}")
        logger.info(f"      Daily free tier:       1,000,000")

        # Check if ready for ML training
        min_for_training = 200
        if len(all_tokens) >= min_for_training:
            logger.info(f"\n   ML Status: READY FOR TRAINING ({len(all_tokens)}/{min_for_training} tokens)")
            logger.info(f"   Run: python tools/automated_ml_retrain.py")
        else:
            remaining = min_for_training - len(all_tokens)
            logger.info(f"\n   ML Status: Need {remaining} more tokens ({len(all_tokens)}/{min_for_training})")
            logger.info(f"   Run backfill again or wait for daily collector")

        logger.info("")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Helius Backfill Collector for ML Training Data')
    parser.add_argument('--max-tokens', type=int, default=None,
                        help='Max tokens to process per run (default: from config)')
    parser.add_argument('--program-scan-only', action='store_true',
                        help='Only use program TX scanning (skip searchAssets)')
    parser.add_argument('--no-helius-enrich', action='store_true',
                        help='Skip Helius enrichment (authority + holders)')
    args = parser.parse_args()

    collector = HeliusBackfillCollector()

    if args.no_helius_enrich:
        collector.backfill_cfg['enrich_with_helius'] = False

    await collector.run(
        max_tokens=args.max_tokens,
        program_scan_only=args.program_scan_only,
    )


if __name__ == "__main__":
    asyncio.run(main())
