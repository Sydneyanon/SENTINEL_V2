#!/usr/bin/env python3
"""
Historical Data Collector - ML Training Dataset Builder

Finds 150 tokens that:
- Graduated from pump.fun (40-60% bonding → 100%)
- Reached 6-7-8 figure market caps ($1M-$100M+)
- Extracts whale wallets who bought early

Output:
- data/historical_training_data.json - Token metrics for ML training
- data/successful_whale_wallets.json - Whales who bought winners

Cost: ~3,000 CU (40K/day free tier = plenty of headroom)
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from loguru import logger
from collections import defaultdict

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import Database


class HistoricalDataCollector:
    """Collects historical data for ML training"""

    def __init__(self):
        self.moralis_api_key = config.MORALIS_API_KEY
        if not self.moralis_api_key:
            logger.warning("⚠️  MORALIS_API_KEY not set - whale extraction will be limited")
            logger.info("   Get free API key at: https://admin.moralis.io")

        self.moralis_base_url = "https://solana-gateway.moralis.io"
        self.moralis_headers = {
            "accept": "application/json",
            "X-API-Key": self.moralis_api_key
        } if self.moralis_api_key else {}

        self.db = None
        self.collected_tokens = []
        self.whale_wallets = defaultdict(lambda: {"tokens_bought": [], "win_count": 0, "total_invested": 0})
        self.total_cu_used = 0

    async def initialize(self):
        """Initialize database"""
        self.db = Database()
        await self.db.connect()
        logger.info("✅ Database connected")

    async def scan_moralis_for_pumpfun_graduates(self, min_mcap: int = 1000000, max_mcap: int = 100000000, limit: int = 150) -> list:
        """
        Use Moralis to find pump.fun bonding curve tokens that graduated to high MCaps

        Args:
            min_mcap: Minimum market cap ($1M = 6 figures)
            max_mcap: Maximum market cap ($100M = 8 figures)
            limit: How many tokens to collect

        Returns:
            List of token data
        """
        if not self.moralis_api_key:
            logger.warning("⚠️  No Moralis API key - falling back to DexScreener only")
            return await self.scan_dexscreener_for_runners(min_mcap, max_mcap, limit)

        logger.info("=" * 80)
        logger.info(f"🔍 USING MORALIS TO FIND {limit} PUMP.FUN GRADUATES")
        logger.info("=" * 80)
        logger.info(f"   MCAP Range: ${min_mcap:,} - ${max_mcap:,}")
        logger.info(f"   Target: Bonding curve tokens → High MCaps\n")

        collected_tokens = []

        # Strategy: Use Moralis to get top tokens by market cap, then filter for pump.fun graduates
        async with aiohttp.ClientSession() as session:
            try:
                # Moralis endpoint for top tokens by market cap
                url = f"{self.moralis_base_url}/token/mainnet/top-tokens"
                params = {
                    'limit': 500  # Get large batch to filter
                }

                logger.info("📊 Fetching top Solana tokens from Moralis...")

                async with session.get(url, headers=self.moralis_headers, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tokens = data.get('result', [])
                        self.total_cu_used += 10  # Estimate

                        logger.info(f"   Got {len(tokens)} tokens from Moralis")
                        logger.info("   Filtering for pump.fun graduates in MCAP range...\n")

                        # Process each token
                        for token_info in tokens:
                            if len(collected_tokens) >= limit:
                                break

                            token_address = token_info.get('token_address')
                            if not token_address:
                                continue

                            # Get full data from DexScreener (has more metrics)
                            token_data = await self.get_dexscreener_data(token_address, session)
                            if not token_data:
                                continue

                            mcap = token_data.get('market_cap', 0)

                            # Filter by MCAP range
                            if min_mcap <= mcap <= max_mcap:
                                collected_tokens.append(token_data)
                                logger.info(f"   ✅ {token_data['symbol']}: ${mcap:,.0f} MCAP")

                            await asyncio.sleep(0.5)  # Rate limit

                    else:
                        logger.warning(f"   Moralis failed: HTTP {resp.status}")

            except Exception as e:
                logger.error(f"   Moralis error: {e}")

        # If we didn't get enough from Moralis, fall back to DexScreener + known tokens
        if len(collected_tokens) < limit:
            logger.info(f"\n📝 Got {len(collected_tokens)} from Moralis, using DexScreener for remainder...")
            dex_tokens = await self.scan_dexscreener_for_runners(min_mcap, max_mcap, limit - len(collected_tokens))

            # Add unique tokens from DexScreener
            existing_addresses = {t['token_address'] for t in collected_tokens}
            for token in dex_tokens:
                if token['token_address'] not in existing_addresses:
                    collected_tokens.append(token)

        logger.info(f"\n✅ Collected {len(collected_tokens)} tokens total")
        return collected_tokens

    async def scan_dexscreener_for_runners(self, min_mcap: int = 1000000, max_mcap: int = 100000000, limit: int = 150) -> list:
        """
        Fallback: Scan DexScreener for pump.fun graduates that reached high MCaps

        Args:
            min_mcap: Minimum market cap ($1M = 6 figures)
            max_mcap: Maximum market cap ($100M = 8 figures)
            limit: How many tokens to collect

        Returns:
            List of token data
        """
        logger.info("=" * 80)
        logger.info(f"🔍 SCANNING DEXSCREENER FOR {limit} PUMP.FUN GRADUATES")
        logger.info("=" * 80)
        logger.info(f"   MCAP Range: ${min_mcap:,} - ${max_mcap:,}")
        logger.info(f"   Target: Tokens that graduated from 40-60% bonding\n")

        # DexScreener API endpoints to try
        search_strategies = [
            # Strategy 1: Use token boosts (recently promoted tokens)
            "https://api.dexscreener.com/token-boosts/latest/v1",

            # Strategy 2: Use token profiles (tracked tokens)
            "https://api.dexscreener.com/token-profiles/latest/v1",
        ]

        collected_addresses = set()
        tokens_data = []

        async with aiohttp.ClientSession() as session:
            # Try each strategy
            for idx, url in enumerate(search_strategies, 1):
                if len(collected_addresses) >= limit:
                    break

                logger.info(f"📊 Strategy {idx}: Fetching from DexScreener...")

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            logger.warning(f"   Failed: HTTP {resp.status}")
                            continue

                        data = await resp.json()

                        # Extract tokens from response
                        if isinstance(data, list):
                            tokens = data
                        else:
                            tokens = data.get('tokens', [])

                        logger.info(f"   Got {len(tokens)} tokens from API")

                        # Filter for pump.fun graduates in our MCAP range
                        for token in tokens:
                            if len(collected_addresses) >= limit:
                                break

                            # Get token address
                            token_address = token.get('tokenAddress') or token.get('address')
                            if not token_address or token_address in collected_addresses:
                                continue

                            # Check if it's from pump.fun / Raydium
                            chain_id = token.get('chainId', '')
                            if chain_id != 'solana':
                                continue

                            # Get MCAP from DexScreener full data
                            token_data = await self.get_dexscreener_data(token_address, session)
                            if not token_data:
                                continue

                            mcap = token_data.get('market_cap', 0)

                            # Filter by MCAP range
                            if min_mcap <= mcap <= max_mcap:
                                collected_addresses.add(token_address)
                                tokens_data.append(token_data)
                                logger.info(f"   ✅ {token_data['symbol']}: ${mcap:,.0f} MCAP")

                        await asyncio.sleep(2)  # Rate limit

                except Exception as e:
                    logger.error(f"   Error with strategy {idx}: {e}")

            # If we still need more, manually add known successful tokens
            if len(collected_addresses) < limit:
                logger.info(f"\n📝 Adding known successful tokens to reach {limit}...")
                known_tokens = await self.load_known_tokens()

                for token in known_tokens:
                    if len(collected_addresses) >= limit:
                        break

                    if token['address'] not in collected_addresses:
                        token_data = await self.get_dexscreener_data(token['address'], session)
                        if token_data:
                            collected_addresses.add(token['address'])
                            tokens_data.append(token_data)
                            logger.info(f"   ✅ {token['symbol']}: Known runner")

        logger.info(f"\n✅ Collected {len(tokens_data)} tokens for analysis")
        return tokens_data

    async def load_known_tokens(self) -> list:
        """Load manually curated known successful tokens"""
        try:
            with open('data/known_runner_tokens.json', 'r') as f:
                data = json.load(f)
                return data['tokens'][0]['tokens']  # Mega runners
        except:
            return []

    async def get_dexscreener_data(self, token_address: str, session=None) -> dict:
        """Get comprehensive token data from DexScreener (FREE!)"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

            if session:
                resp_ctx = session.get(url, timeout=aiohttp.ClientTimeout(total=15))
            else:
                resp_ctx = aiohttp.ClientSession().get(url, timeout=aiohttp.ClientTimeout(total=15))

            async with resp_ctx as resp:
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

                # Calculate buy percentages
                total_txs_24h = txns_24h.get('buys', 0) + txns_24h.get('sells', 0)
                total_txs_6h = txns_6h.get('buys', 0) + txns_6h.get('sells', 0)

                buy_pct_24h = (txns_24h.get('buys', 0) / total_txs_24h * 100) if total_txs_24h > 0 else 0
                buy_pct_6h = (txns_6h.get('buys', 0) / total_txs_6h * 100) if total_txs_6h > 0 else 0

                # Classify outcome based on MCAP
                mcap = float(pair.get('fdv', 0))
                outcome = self._classify_outcome_by_mcap(mcap)

                return {
                    'token_address': token_address,
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'price_usd': float(pair.get('priceUsd', 0)),
                    'market_cap': mcap,
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                    'volume_6h': float(pair.get('volume', {}).get('h6', 0)),
                    'buys_24h': txns_24h.get('buys', 0),
                    'sells_24h': txns_24h.get('sells', 0),
                    'buys_6h': txns_6h.get('buys', 0),
                    'sells_6h': txns_6h.get('sells', 0),
                    'buy_percentage_24h': buy_pct_24h,
                    'buy_percentage_6h': buy_pct_6h,
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                    'price_change_6h': float(pair.get('priceChange', {}).get('h6', 0)),
                    'created_at': pair.get('pairCreatedAt', 0),
                    'outcome': outcome,
                    'dex_url': pair.get('url', '')
                }

        except Exception as e:
            logger.debug(f"  DexScreener error for {token_address[:8]}: {e}")
            return None

    def _classify_outcome_by_mcap(self, mcap: float) -> str:
        """Classify token outcome based on MCAP achieved"""
        if mcap >= 100000000:  # $100M+
            return "100x+"
        elif mcap >= 50000000:  # $50M+
            return "50x"
        elif mcap >= 10000000:  # $10M+
            return "10x"
        elif mcap >= 2000000:  # $2M+
            return "2x"
        else:
            return "small"

    async def extract_whale_wallets(self, token_address: str, token_symbol: str, token_price: float = 0) -> list:
        """
        Extract whale wallets (>$50K positions) using Moralis

        Combines:
        1. Current top holders (Moralis)
        2. Early holders from transfers (Moralis) - identifies whales who bought early

        Cost: ~10 CU per token (5 for holders + 5 for transfers)
        """
        if not self.moralis_api_key:
            logger.debug(f"   Skipping whale extraction for {token_symbol} (no Moralis key)")
            return []

        whale_addresses = []

        try:
            async with aiohttp.ClientSession() as session:
                # Strategy 1: Get current top holders
                url = f"{self.moralis_base_url}/token/mainnet/{token_address}/top-holders"

                async with session.get(url, headers=self.moralis_headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.total_cu_used += 5

                        holders = data.get('result', [])

                        for holder in holders[:30]:  # Top 30 holders
                            balance = float(holder.get('balance', 0) or 0)
                            address = holder.get('owner_address', '')

                            # Skip contract addresses (very high balances)
                            if balance > 1000000000000:
                                continue

                            # Estimate USD value if we have price
                            if token_price > 0:
                                usd_value = (balance / 1e9) * token_price  # Assuming 9 decimals
                                if usd_value < 50000:  # Not a whale
                                    continue

                            if address and address not in whale_addresses:
                                whale_addresses.append(address)

                                # Track this whale
                                self.whale_wallets[address]['tokens_bought'].append({
                                    'token': token_symbol,
                                    'address': token_address
                                })

                        logger.debug(f"   Current holders: {len(whale_addresses)} whales")

                    else:
                        logger.debug(f"   Top holders failed: HTTP {resp.status}")

                # Strategy 2: Get early transfers to find early whales
                # This identifies wallets that bought in early (more predictive!)
                transfers_url = f"{self.moralis_base_url}/token/mainnet/{token_address}/transfers"
                params = {
                    'limit': 100,  # Get first 100 transfers
                    'order': 'ASC'  # Oldest first = earliest buyers
                }

                async with session.get(transfers_url, headers=self.moralis_headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.total_cu_used += 5

                        transfers = data.get('result', [])
                        early_buyers = defaultdict(float)

                        # Aggregate early buyers
                        for transfer in transfers:
                            to_address = transfer.get('to_address', '')
                            value = float(transfer.get('value', 0) or 0)

                            if to_address and value > 0:
                                early_buyers[to_address] += value

                        # Identify early whales (bought >$50K equivalent early)
                        for address, total_bought in early_buyers.items():
                            if token_price > 0:
                                usd_value = (total_bought / 1e9) * token_price
                                if usd_value >= 50000 and address not in whale_addresses:
                                    whale_addresses.append(address)

                                    # Track early whale
                                    self.whale_wallets[address]['tokens_bought'].append({
                                        'token': token_symbol,
                                        'address': token_address,
                                        'early_buyer': True  # Mark as early buyer
                                    })

                        logger.debug(f"   Early buyers: +{len([a for a in early_buyers if a in whale_addresses])} early whales")

                    else:
                        logger.debug(f"   Transfers failed: HTTP {resp.status}")

                logger.info(f"   🐋 Total whales found: {len(whale_addresses)}")
                return whale_addresses

        except Exception as e:
            logger.debug(f"   Whale extraction error: {e}")
            return []

    async def collect_all(self, target_count: int = 150):
        """Collect historical data for target number of tokens"""
        logger.info("=" * 80)
        logger.info("🚀 HISTORICAL DATA COLLECTION - MORALIS + DEXSCREENER")
        logger.info("=" * 80)

        # Step 1: Find successful pump.fun graduates using Moralis
        tokens_data = await self.scan_moralis_for_pumpfun_graduates(limit=target_count)

        if not tokens_data:
            logger.error("❌ No tokens found!")
            return

        # Step 2: Extract whales from each token (if Moralis key available)
        if self.moralis_api_key:
            logger.info("\n" + "=" * 80)
            logger.info("🐋 EXTRACTING WHALE WALLETS (CURRENT + EARLY HOLDERS)")
            logger.info("=" * 80)

            for idx, token in enumerate(tokens_data, 1):
                logger.info(f"\n[{idx}/{len(tokens_data)}] {token['symbol']}...")

                # Extract whales with price for USD value calculation
                whales = await self.extract_whale_wallets(
                    token['token_address'],
                    token['symbol'],
                    token.get('price_usd', 0)
                )
                token['whale_wallets'] = whales
                token['whale_count'] = len(whales)

                # Update whale win tracking
                if token['outcome'] in ['100x+', '50x', '10x']:
                    for whale in whales:
                        self.whale_wallets[whale]['win_count'] += 1

                await asyncio.sleep(1.5)  # Rate limit for Moralis

        # Step 3: Analyze whale success rates
        successful_whales = []
        if self.whale_wallets:
            logger.info("\n" + "=" * 80)
            logger.info("📊 WHALE ANALYSIS")
            logger.info("=" * 80)

            for wallet, data in self.whale_wallets.items():
                token_count = len(data['tokens_bought'])
                if token_count >= 2:  # Whale bought 2+ of our successful tokens
                    win_rate = (data['win_count'] / token_count) if token_count > 0 else 0
                    if win_rate >= 0.5:  # 50%+ win rate
                        successful_whales.append({
                            'address': wallet,
                            'tokens_bought_count': token_count,
                            'wins': data['win_count'],
                            'win_rate': win_rate,
                            'tokens': data['tokens_bought']
                        })

            successful_whales.sort(key=lambda x: x['win_rate'], reverse=True)
            logger.info(f"   Found {len(successful_whales)} successful whales (50%+ win rate)")

            for idx, whale in enumerate(successful_whales[:10], 1):
                logger.info(f"   {idx}. {whale['address'][:12]}... - {whale['win_rate']*100:.0f}% WR ({whale['wins']}/{whale['tokens_bought_count']})")

        # Step 4: Save results
        logger.info("\n" + "=" * 80)
        logger.info("💾 SAVING RESULTS")
        logger.info("=" * 80)

        # Save token data
        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_tokens': len(tokens_data),
            'cu_used_estimate': self.total_cu_used,
            'outcome_distribution': self._get_outcome_distribution(tokens_data),
            'tokens': tokens_data
        }

        with open('data/historical_training_data.json', 'w') as f:
            json.dump(output, f, indent=2)
        logger.info("   ✅ Saved data/historical_training_data.json")

        # Save successful whales
        if successful_whales:
            whale_output = {
                'collected_at': datetime.utcnow().isoformat(),
                'total_whales': len(successful_whales),
                'whales': successful_whales
            }

            with open('data/successful_whale_wallets.json', 'w') as f:
                json.dump(whale_output, f, indent=2)
            logger.info("   ✅ Saved data/successful_whale_wallets.json")

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n📊 Collected {len(tokens_data)} tokens:")
        for outcome, count in self._get_outcome_distribution(tokens_data).items():
            logger.info(f"   {outcome}: {count}")

        if successful_whales:
            logger.info(f"\n🐋 Identified {len(successful_whales)} successful whales")
            logger.info("   Can use these for whale-copy strategy!")

        logger.info(f"\n💰 Estimated Moralis CU used: {self.total_cu_used}")
        logger.info(f"   Daily free tier: 40,000 CU")
        logger.info(f"   Usage: {(self.total_cu_used/40000)*100:.1f}%")

        logger.info(f"\n🚀 Ready for ML training!")

    def _get_outcome_distribution(self, tokens_data: list) -> dict:
        """Get distribution of outcomes"""
        dist = defaultdict(int)
        for token in tokens_data:
            dist[token.get('outcome', 'unknown')] += 1
        return dict(dist)


async def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Collect historical token data for ML training')
    parser.add_argument('--count', type=int, default=150, help='Number of tokens to collect (default: 150)')
    parser.add_argument('--min-mcap', type=int, default=1000000, help='Minimum MCAP (default: 1M)')
    parser.add_argument('--max-mcap', type=int, default=100000000, help='Maximum MCAP (default: 100M)')
    args = parser.parse_args()

    collector = HistoricalDataCollector()
    await collector.initialize()
    await collector.collect_all(target_count=args.count)


if __name__ == "__main__":
    asyncio.run(main())
