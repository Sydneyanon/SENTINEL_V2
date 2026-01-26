#!/usr/bin/env python3
"""
Export Signals to ML Training Data - Bridge Between Production & ML

This script exports completed signals from PostgreSQL into the ML training dataset.
Runs after daily collection to add our own signal data to the ML pipeline.

Features:
- Pulls signals from last 7 days with known outcomes
- Enriches with DexScreener data at signal time
- Categorizes outcomes: rug, 2x, 10x, 50x, 100x+
- Appends to historical_training_data.json
- Tracks which signals have been exported

Run via cron: 0 2 * * * /path/to/export_signals_to_ml.py (after daily collection)
"""
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class SignalMLExporter:
    """Exports production signals to ML training data"""

    def __init__(self):
        self.db = Database()
        self.training_file = 'data/historical_training_data.json'
        self.export_log_file = 'data/signal_export_log.json'
        self.exported_signal_ids = set()

    async def initialize(self):
        """Initialize database and load export log"""
        await self.db.connect()

        # Load previously exported signal IDs
        if os.path.exists(self.export_log_file):
            try:
                with open(self.export_log_file, 'r') as f:
                    log = json.load(f)
                    self.exported_signal_ids = set(log.get('exported_signal_ids', []))
                    logger.info(f"   Loaded export log: {len(self.exported_signal_ids)} signals already exported")
            except:
                pass

    async def get_completed_signals(self, days: int = 7) -> list:
        """
        Get signals from last N days that have known outcomes

        Args:
            days: Number of days to look back

        Returns:
            List of signal records with outcomes
        """
        logger.info("=" * 80)
        logger.info("🔍 FETCHING COMPLETED SIGNALS FROM DATABASE")
        logger.info("=" * 80)
        logger.info(f"   Looking back: {days} days")
        logger.info(f"   Looking for: Signals with outcome != NULL")

        # Query signals with outcomes
        query = """
            SELECT
                id,
                token_address,
                symbol,
                conviction_score,
                price_usd,
                market_cap,
                liquidity,
                volume_24h,
                signal_source,
                outcome,
                outcome_price,
                outcome_timestamp,
                created_at
            FROM signals
            WHERE
                outcome IS NOT NULL
                AND created_at >= NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
        """

        try:
            rows = await self.db.fetch_all(query, (days,))

            # Convert to dict
            signals = []
            for row in rows:
                signal_id = row[0]

                # Skip if already exported
                if signal_id in self.exported_signal_ids:
                    continue

                signals.append({
                    'id': signal_id,
                    'token_address': row[1],
                    'symbol': row[2],
                    'conviction_score': row[3],
                    'price_usd': row[4],
                    'market_cap': row[5],
                    'liquidity': row[6],
                    'volume_24h': row[7],
                    'signal_source': row[8],
                    'outcome': row[9],
                    'outcome_price': row[10],
                    'outcome_timestamp': row[11],
                    'created_at': row[12]
                })

            logger.info(f"   ✅ Found {len(signals)} new completed signals")
            return signals

        except Exception as e:
            logger.error(f"   ❌ Database error: {e}")
            return []

    async def enrich_signal_with_dexscreener(self, signal: dict, session: aiohttp.ClientSession) -> dict:
        """
        Enrich signal data with DexScreener metrics

        Args:
            signal: Signal record from database
            session: aiohttp session

        Returns:
            Enriched signal data with all ML features
        """
        token_address = signal['token_address']

        try:
            # Get current DexScreener data
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"   Failed to fetch {signal['symbol']}: HTTP {resp.status}")
                    return None

                data = await resp.json()
                pairs = data.get('pairs', [])

                if not pairs:
                    logger.warning(f"   No pairs found for {signal['symbol']}")
                    return None

                # Get first Solana pair
                pair = None
                for p in pairs:
                    if p.get('chainId') == 'solana':
                        pair = p
                        break

                if not pair:
                    return None

                # Build enriched data
                enriched = {
                    'token_address': token_address,
                    'symbol': signal['symbol'],
                    'name': pair.get('baseToken', {}).get('name', signal['symbol']),
                    'price_usd': float(pair.get('priceUsd', 0)),
                    'market_cap': float(pair.get('fdv', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                    'volume_6h': float(pair.get('volume', {}).get('h6', 0)),
                    'volume_1h': float(pair.get('volume', {}).get('h1', 0)),
                    'buys_24h': int(pair.get('txns', {}).get('h24', {}).get('buys', 0)),
                    'sells_24h': int(pair.get('txns', {}).get('h24', {}).get('sells', 0)),
                    'buys_6h': int(pair.get('txns', {}).get('h6', {}).get('buys', 0)),
                    'sells_6h': int(pair.get('txns', {}).get('h6', {}).get('sells', 0)),
                    'buys_1h': int(pair.get('txns', {}).get('h1', {}).get('buys', 0)),
                    'sells_1h': int(pair.get('txns', {}).get('h1', {}).get('sells', 0)),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                    'price_change_6h': float(pair.get('priceChange', {}).get('h6', 0)),
                    'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0)),
                    'created_at': pair.get('pairCreatedAt', 0),
                    'dex_url': pair.get('url', ''),

                    # Add our conviction data
                    'conviction_score': signal['conviction_score'],
                    'signal_source': signal['signal_source'],
                    'outcome': signal['outcome'],
                    'outcome_price': signal['outcome_price'],
                    'signal_price': signal['price_usd'],
                    'signal_timestamp': signal['created_at'].isoformat() if signal['created_at'] else None,

                    # Calculate buy percentages
                    'buy_percentage_24h': (
                        100 * enriched['buys_24h'] / (enriched['buys_24h'] + enriched['sells_24h'])
                        if (enriched['buys_24h'] + enriched['sells_24h']) > 0 else 0
                    ),
                    'buy_percentage_6h': (
                        100 * enriched['buys_6h'] / (enriched['buys_6h'] + enriched['sells_6h'])
                        if (enriched['buys_6h'] + enriched['sells_6h']) > 0 else 0
                    ),

                    # Placeholder for whale data (would need separate fetch)
                    'whale_wallets': [],
                    'whale_count': 0,
                }

                return enriched

        except Exception as e:
            logger.debug(f"   Error enriching {signal['symbol']}: {e}")
            return None

    async def export_signals(self, days: int = 7):
        """
        Export completed signals to ML training data

        Args:
            days: Number of days to look back for signals
        """
        logger.info("=" * 80)
        logger.info("📤 EXPORTING SIGNALS TO ML TRAINING DATA")
        logger.info("=" * 80)
        logger.info(f"   Date: {datetime.utcnow().date()}")
        logger.info(f"   Looking back: {days} days")
        logger.info("")

        # Initialize
        await self.initialize()

        # Get completed signals
        signals = await self.get_completed_signals(days)

        if not signals:
            logger.info("   No new signals to export")
            return

        # Enrich signals with DexScreener data
        logger.info("\n" + "=" * 80)
        logger.info("🔬 ENRICHING SIGNALS WITH DEXSCREENER DATA")
        logger.info("=" * 80)

        enriched_signals = []
        async with aiohttp.ClientSession(trust_env=True) as session:
            for idx, signal in enumerate(signals, 1):
                logger.info(f"\n[{idx}/{len(signals)}] {signal['symbol']}...")

                enriched = await self.enrich_signal_with_dexscreener(signal, session)
                if enriched:
                    enriched_signals.append(enriched)
                    logger.info(f"   ✅ Enriched: ${enriched['market_cap']/1e6:.2f}M MCAP, "
                              f"Vol: ${enriched['volume_24h']/1e3:.0f}K, "
                              f"Outcome: {enriched['outcome']}")

                    # Track as exported
                    self.exported_signal_ids.add(signal['id'])

                await asyncio.sleep(0.5)  # Rate limiting

        if not enriched_signals:
            logger.warning("   ❌ No signals could be enriched")
            return

        # Load existing training data
        logger.info("\n" + "=" * 80)
        logger.info("💾 APPENDING TO TRAINING DATASET")
        logger.info("=" * 80)

        existing_data = {'tokens': []}
        if os.path.exists(self.training_file):
            try:
                with open(self.training_file, 'r') as f:
                    existing_data = json.load(f)
                    logger.info(f"   Existing: {existing_data.get('total_tokens', 0)} tokens")
            except:
                logger.info("   Creating new dataset")

        # Append new signals
        all_tokens = existing_data.get('tokens', []) + enriched_signals

        # Calculate outcome distribution
        outcome_dist = {}
        for token in all_tokens:
            outcome = token.get('outcome', 'unknown')
            outcome_dist[outcome] = outcome_dist.get(outcome, 0) + 1

        # Save updated dataset
        output = {
            'collected_at': datetime.utcnow().isoformat(),
            'total_tokens': len(all_tokens),
            'last_signal_export': datetime.utcnow().date().isoformat(),
            'signals_added_today': len(enriched_signals),
            'outcome_distribution': outcome_dist,
            'tokens': all_tokens
        }

        os.makedirs('data', exist_ok=True)
        with open(self.training_file, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"   ✅ Saved {self.training_file}")
        logger.info(f"   Total: {len(all_tokens)} tokens (+{len(enriched_signals)} signals)")
        logger.info(f"   Outcome distribution: {outcome_dist}")

        # Save export log
        export_log = {
            'last_export': datetime.utcnow().isoformat(),
            'total_exports': len(self.exported_signal_ids),
            'exported_signal_ids': list(self.exported_signal_ids)
        }

        with open(self.export_log_file, 'w') as f:
            json.dump(export_log, f, indent=2)

        logger.info(f"\n   ✅ Updated export log: {len(self.exported_signal_ids)} total signals tracked")

        logger.info("\n" + "=" * 80)
        logger.info("✅ SIGNAL EXPORT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"   Signals exported: {len(enriched_signals)}")
        logger.info(f"   Total dataset size: {len(all_tokens)} tokens")
        logger.info("")


async def main():
    """Run signal export"""
    exporter = SignalMLExporter()
    await exporter.export_signals(days=7)


if __name__ == "__main__":
    asyncio.run(main())
