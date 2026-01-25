#!/usr/bin/env python3
"""
One-time historical data collector runner
Run this manually via Railway shell or add to startup
"""
import asyncio
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.historical_data_collector import HistoricalDataCollector
from loguru import logger

async def main():
    """Run collector once"""
    logger.info("=" * 80)
    logger.info("MANUAL HISTORICAL DATA COLLECTION")
    logger.info("=" * 80)

    # Check if already run
    if os.path.exists('data/historical_training_data.json'):
        logger.info("⚠️  Data already collected!")
        logger.info("   Files found:")
        logger.info("   - data/historical_training_data.json")
        if os.path.exists('data/successful_whale_wallets.json'):
            logger.info("   - data/successful_whale_wallets.json")

        response = input("\nRun again anyway? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("❌ Cancelled - data already exists")
            return

    # Run collector
    collector = HistoricalDataCollector()
    await collector.initialize()
    await collector.collect_all(target_count=150)

    logger.info("\n" + "=" * 80)
    logger.info("✅ COMPLETE - Data ready for ML training!")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
