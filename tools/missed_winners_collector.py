#!/usr/bin/env python3
"""
Missed Winners Collector - Find yesterday's pump.fun winners we didn't signal

This is the MOST valuable training data:
- Tokens that pumped 10x+ yesterday
- That Ralph didn't catch
- Learn WHY we missed them → improve future detection

Usage:
    python tools/missed_winners_collector.py

Called by /collect command in admin bot.
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from loguru import logger

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class MissedWinnersCollector:
    """
    Collects yesterday's pump.fun winners that we missed signaling.

    Pipeline:
    1. Fetch top gainers from DexScreener (pump.fun tokens, 24h)
    2. Filter for significant gains (10x+, 50x+, 100x+)
    3. Check against our signals database
    4. Collect features for MISSED winners
    5. Save to training data with 'missed_winner' flag
    """

    def __init__(self, database=None):
        self.database = database
        self.data_file = 'data/historical_training_data.json'
        self.stats = {
            'total_winners_found': 0,
            'already_signaled': 0,
            'missed_winners': 0,
            'collected': 0,
            'errors': 0
        }
        # Minimum gain to consider (10x = 900% gain)
        self.min_gain_percent = 200  # 3x minimum
        self.target_gains = {
            '100x': 9900,   # 100x = 9900% gain
            '50x': 4900,
            '10x': 900,
            '5x': 400,
            '3x': 200,
            '2x': 100
        }

    async def fetch_top_gainers(self) -> List[Dict]:
        """Fetch top pump.fun gainers from DexScreener"""
        logger.info("🔍 Fetching top pump.fun gainers from DexScreener...")

        gainers = []

        try:
            async with aiohttp.ClientSession() as session:
                # DexScreener token boosted/trending endpoint (includes top movers)
                # We'll use the search endpoint filtered for pump.fun
                url = "https://api.dexscreener.com/token-boosts/top/v1"

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        for token in data:
                            # Filter for Solana pump.fun tokens
                            if token.get('chainId') == 'solana':
                                address = token.get('tokenAddress', '')
                                # pump.fun tokens end with 'pump'
                                if address.endswith('pump'):
                                    gainers.append({
                                        'address': address,
                                        'source': 'boosted'
                                    })

                        logger.info(f"   Found {len(gainers)} pump.fun tokens from boosted")

                # Also check trending/new pairs
                url2 = "https://api.dexscreener.com/latest/dex/tokens/trending"
                try:
                    async with session.get(url2, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for token in data.get('tokens', data) if isinstance(data, dict) else data:
                                if isinstance(token, dict):
                                    address = token.get('address', token.get('tokenAddress', ''))
                                    if address.endswith('pump'):
                                        if not any(g['address'] == address for g in gainers):
                                            gainers.append({
                                                'address': address,
                                                'source': 'trending'
                                            })
                except:
                    pass

                # Search for recent pump.fun tokens with high gains
                # Use pairs search with solana + raydium filter
                search_url = "https://api.dexscreener.com/latest/dex/search?q=pump"
                try:
                    async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = data.get('pairs', [])

                            for pair in pairs[:100]:  # Check top 100
                                if pair.get('chainId') != 'solana':
                                    continue

                                address = pair.get('baseToken', {}).get('address', '')
                                if not address.endswith('pump'):
                                    continue

                                # Check 24h price change
                                price_change = pair.get('priceChange', {}).get('h24', 0) or 0

                                if price_change >= self.min_gain_percent:
                                    if not any(g['address'] == address for g in gainers):
                                        gainers.append({
                                            'address': address,
                                            'symbol': pair.get('baseToken', {}).get('symbol', ''),
                                            'price_change_24h': price_change,
                                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                                            'liquidity': pair.get('liquidity', {}).get('usd', 0),
                                            'fdv': pair.get('fdv', 0),
                                            'source': 'search',
                                            'pair_data': pair
                                        })

                            logger.info(f"   Found {len([g for g in gainers if g.get('source') == 'search'])} high-gain tokens from search")
                except Exception as e:
                    logger.warning(f"   Search endpoint error: {e}")

        except Exception as e:
            logger.error(f"❌ Error fetching gainers: {e}")

        self.stats['total_winners_found'] = len(gainers)
        logger.info(f"✅ Total potential winners found: {len(gainers)}")

        return gainers

    async def get_token_details(self, address: str) -> Optional[Dict]:
        """Get detailed token data from DexScreener"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            # Get the main Raydium pair
                            for pair in pairs:
                                if pair.get('dexId') in ['raydium', 'orca']:
                                    return {
                                        'address': address,
                                        'symbol': pair.get('baseToken', {}).get('symbol', ''),
                                        'name': pair.get('baseToken', {}).get('name', ''),
                                        'price_usd': float(pair.get('priceUsd', 0) or 0),
                                        'price_change_24h': pair.get('priceChange', {}).get('h24', 0) or 0,
                                        'price_change_6h': pair.get('priceChange', {}).get('h6', 0) or 0,
                                        'price_change_1h': pair.get('priceChange', {}).get('h1', 0) or 0,
                                        'volume_24h': pair.get('volume', {}).get('h24', 0) or 0,
                                        'volume_6h': pair.get('volume', {}).get('h6', 0) or 0,
                                        'liquidity_usd': pair.get('liquidity', {}).get('usd', 0) or 0,
                                        'fdv': pair.get('fdv', 0) or 0,
                                        'market_cap': pair.get('marketCap', 0) or 0,
                                        'pair_created_at': pair.get('pairCreatedAt', 0),
                                        'txns_24h_buys': pair.get('txns', {}).get('h24', {}).get('buys', 0),
                                        'txns_24h_sells': pair.get('txns', {}).get('h24', {}).get('sells', 0),
                                    }
                            # Fallback to first pair
                            pair = pairs[0]
                            return {
                                'address': address,
                                'symbol': pair.get('baseToken', {}).get('symbol', ''),
                                'name': pair.get('baseToken', {}).get('name', ''),
                                'price_usd': float(pair.get('priceUsd', 0) or 0),
                                'price_change_24h': pair.get('priceChange', {}).get('h24', 0) or 0,
                                'volume_24h': pair.get('volume', {}).get('h24', 0) or 0,
                                'liquidity_usd': pair.get('liquidity', {}).get('usd', 0) or 0,
                                'fdv': pair.get('fdv', 0) or 0,
                            }
        except Exception as e:
            logger.debug(f"Error getting details for {address[:8]}...: {e}")
        return None

    async def check_if_signaled(self, address: str) -> bool:
        """Check if we already signaled this token"""
        if not self.database:
            return False

        try:
            signal = await self.database.get_signal(address)
            return signal is not None and signal.get('signal_posted', False)
        except Exception as e:
            logger.debug(f"Error checking signal: {e}")
            return False

    def classify_outcome(self, price_change_pct: float) -> str:
        """Classify outcome based on price change percentage"""
        if price_change_pct >= 9900:
            return '100x+'
        elif price_change_pct >= 4900:
            return '50x'
        elif price_change_pct >= 900:
            return '10x'
        elif price_change_pct >= 400:
            return '5x'
        elif price_change_pct >= 200:
            return '3x'
        elif price_change_pct >= 100:
            return '2x'
        elif price_change_pct >= 0:
            return 'small'
        else:
            return 'loss'

    async def collect_missed_winners(self) -> List[Dict]:
        """Main collection pipeline"""
        logger.info("=" * 70)
        logger.info("🎯 MISSED WINNERS COLLECTOR")
        logger.info("=" * 70)
        logger.info("Finding yesterday's pump.fun winners we didn't signal...")

        # Step 1: Fetch top gainers
        gainers = await self.fetch_top_gainers()

        if not gainers:
            logger.warning("No gainers found")
            return []

        missed_winners = []

        # Step 2: Check each one against our signals
        logger.info(f"\n🔎 Checking {len(gainers)} tokens against our signals...")

        for i, gainer in enumerate(gainers):
            address = gainer.get('address', '')
            if not address:
                continue

            # Check if we signaled it
            was_signaled = await self.check_if_signaled(address)

            if was_signaled:
                self.stats['already_signaled'] += 1
                continue

            # This is a missed winner - get full details
            details = gainer.get('pair_data')
            if not details:
                details = await self.get_token_details(address)
                await asyncio.sleep(0.2)  # Rate limit

            if not details:
                continue

            price_change = details.get('price_change_24h', gainer.get('price_change_24h', 0)) or 0

            # Only include if it's a significant gainer
            if price_change < self.min_gain_percent:
                continue

            outcome = self.classify_outcome(price_change)

            # Calculate buy/sell ratio
            buys = details.get('txns_24h_buys', 0) or 0
            sells = details.get('txns_24h_sells', 0) or 0
            total_txns = buys + sells
            buy_percentage = (buys / total_txns * 100) if total_txns > 0 else 50

            missed_winner = {
                'address': address,
                'symbol': details.get('symbol', gainer.get('symbol', '')),
                'name': details.get('name', ''),
                'outcome': outcome,
                'price_change_24h': price_change,
                'roi': 1 + (price_change / 100),  # Convert % to multiplier
                'volume_24h': details.get('volume_24h', 0),
                'liquidity_usd': details.get('liquidity_usd', 0),
                'market_cap': details.get('market_cap', details.get('fdv', 0)),
                'buy_percentage': buy_percentage,
                'buys_24h': buys,
                'sells_24h': sells,
                'is_missed_winner': True,
                'collected_at': datetime.utcnow().isoformat(),
                'source': gainer.get('source', 'dexscreener')
            }

            missed_winners.append(missed_winner)
            self.stats['missed_winners'] += 1

            logger.info(f"   🎯 MISSED: ${missed_winner['symbol']} → {outcome} ({price_change:.0f}%)")

        logger.info(f"\n📊 Results:")
        logger.info(f"   Total winners checked: {len(gainers)}")
        logger.info(f"   Already signaled: {self.stats['already_signaled']}")
        logger.info(f"   MISSED WINNERS: {self.stats['missed_winners']}")

        return missed_winners

    async def save_to_training_data(self, missed_winners: List[Dict]) -> int:
        """Save missed winners to training data file"""
        if not missed_winners:
            return 0

        # Load existing data
        existing_data = {'tokens': [], 'total_tokens': 0}
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    existing_data = json.load(f)
        except:
            pass

        existing_tokens = existing_data.get('tokens', [])
        existing_addresses = {t.get('address') for t in existing_tokens}

        # Add new missed winners
        added = 0
        for winner in missed_winners:
            if winner['address'] not in existing_addresses:
                existing_tokens.append(winner)
                existing_addresses.add(winner['address'])
                added += 1

        # Update outcome distribution
        outcome_dist = existing_data.get('outcome_distribution', {})
        for winner in missed_winners:
            outcome = winner.get('outcome', 'unknown')
            outcome_dist[outcome] = outcome_dist.get(outcome, 0) + 1

        # Save
        updated_data = {
            'total_tokens': len(existing_tokens),
            'tokens': existing_tokens,
            'outcome_distribution': outcome_dist,
            'last_collection': datetime.utcnow().isoformat(),
            'last_missed_winners_count': len(missed_winners),
            'discovery_method': 'dexscreener_missed_winners'
        }

        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(updated_data, f, indent=2)

        self.stats['collected'] = added
        logger.info(f"✅ Added {added} new missed winners to training data")
        logger.info(f"   Total training tokens: {len(existing_tokens)}")

        return added

    async def run(self) -> Dict:
        """Run the full collection pipeline"""
        try:
            # Collect missed winners
            missed_winners = await self.collect_missed_winners()

            # Save to training data
            if missed_winners:
                await self.save_to_training_data(missed_winners)

            return {
                'action': 'completed',
                'missed_winners': len(missed_winners),
                'already_signaled': self.stats['already_signaled'],
                'collected': self.stats['collected'],
                'total_checked': self.stats['total_winners_found']
            }

        except Exception as e:
            logger.error(f"❌ Collection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'action': 'failed',
                'reason': str(e)
            }


async def main():
    """CLI entry point"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from database import Database

    db = Database()
    await db.connect()

    collector = MissedWinnersCollector(database=db)
    result = await collector.run()

    print(f"\n{'='*70}")
    print("COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(json.dumps(result, indent=2))

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
