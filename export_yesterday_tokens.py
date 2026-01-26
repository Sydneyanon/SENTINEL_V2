#!/usr/bin/env python3
"""
Export Yesterday's Top Tokens from DexScreener

Manually runs the daily collector to pull yesterday's top performers
and exports to JSON for review.

Usage:
    python export_yesterday_tokens.py [--limit 50]
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from loguru import logger

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.daily_token_collector import DailyTokenCollector


async def export_yesterday_tokens(limit: int = 50):
    """
    Pull yesterday's top tokens from DexScreener and export to JSON

    Args:
        limit: Number of tokens to collect (default: 50)
    """
    logger.info("=" * 80)
    logger.info("📊 EXPORTING YESTERDAY'S TOP TOKENS FROM DEXSCREENER")
    logger.info("=" * 80)
    logger.info(f"   Target: {limit} tokens")
    logger.info(f"   Filters:")
    logger.info(f"     - Minimum 2x gain (100%+) in 24h")
    logger.info(f"     - Minimum $50K volume")
    logger.info(f"     - Minimum $20K market cap")
    logger.info(f"   Source: DexScreener (token-boosts + token-profiles)")
    logger.info("=" * 80)
    logger.info("")

    # Initialize collector
    collector = DailyTokenCollector()

    # Get yesterday's top tokens
    tokens = await collector.get_daily_top_tokens(limit=limit)

    if not tokens:
        logger.error("❌ No tokens found matching criteria!")
        logger.info("\nPossible reasons:")
        logger.info("  1. DexScreener API is down")
        logger.info("  2. No tokens met the filters (2x, $50K vol, $20K mcap)")
        logger.info("  3. Rate limiting")
        return

    # Prepare export data
    export_data = {
        'collection_date': datetime.utcnow().isoformat(),
        'collection_type': 'yesterday_winners',
        'filters': {
            'min_gain_pct': 100,
            'min_volume_24h': 50000,
            'min_market_cap': 20000
        },
        'total_tokens': len(tokens),
        'tokens': tokens
    }

    # Calculate summary stats
    if tokens:
        gains = [t['price_change_24h'] for t in tokens if 'price_change_24h' in t]
        volumes = [t['volume_24h'] for t in tokens if 'volume_24h' in t]
        mcaps = [t['market_cap'] for t in tokens if 'market_cap' in t]

        export_data['summary'] = {
            'avg_gain_pct': sum(gains) / len(gains) if gains else 0,
            'max_gain_pct': max(gains) if gains else 0,
            'min_gain_pct': min(gains) if gains else 0,
            'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
            'avg_mcap': sum(mcaps) / len(mcaps) if mcaps else 0,
            'top_gainer': tokens[0]['symbol'] if tokens else None,
            'top_gainer_pct': tokens[0]['price_change_24h'] if tokens else 0
        }

    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)

    # Export to JSON
    filename = f"data/yesterday_tokens_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ EXPORT COMPLETE")
    logger.info("=" * 80)
    logger.info(f"   Tokens collected: {len(tokens)}")

    if 'summary' in export_data:
        summary = export_data['summary']
        logger.info(f"   Average gain: +{summary['avg_gain_pct']:.0f}%")
        logger.info(f"   Top gainer: {summary['top_gainer']} (+{summary['top_gainer_pct']:.0f}%)")
        logger.info(f"   Max gain: +{summary['max_gain_pct']:.0f}%")
        logger.info(f"   Avg volume: ${summary['avg_volume']/1e3:.0f}K")
        logger.info(f"   Avg mcap: ${summary['avg_mcap']/1e6:.2f}M")

    logger.info(f"\n   📁 Exported to: {filename}")
    logger.info("=" * 80)

    # Print top 10 tokens
    logger.info("\n🔥 TOP 10 TOKENS:")
    logger.info("-" * 80)
    logger.info(f"{'Symbol':<12} {'Gain':<10} {'Volume':<12} {'MCAP':<12} {'Top10%':<8}")
    logger.info("-" * 80)

    for i, token in enumerate(tokens[:10]):
        symbol = token.get('symbol', 'UNKNOWN')[:12]
        gain = token.get('price_change_24h', 0)
        volume = token.get('volume_24h', 0)
        mcap = token.get('market_cap', 0)
        top10 = token.get('top_10_holder_pct', 0)

        logger.info(f"{symbol:<12} +{gain:<9.0f}% ${volume/1e3:<11.0f}K ${mcap/1e6:<11.2f}M {top10:<7.1f}%")

    logger.info("-" * 80)
    logger.info(f"\nFull data saved to: {filename}")
    logger.info("You can now review the JSON file for all token details.")

    return tokens


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Export yesterday\'s top tokens from DexScreener')
    parser.add_argument('--limit', type=int, default=50, help='Number of tokens to collect (default: 50)')
    args = parser.parse_args()

    asyncio.run(export_yesterday_tokens(limit=args.limit))
