"""
Automated Daily Token Collector - Runs at Midnight UTC

Uses Helius searchAssets + program TX scanning to discover pump.fun tokens,
then collects comprehensive ML features via DexScreener + Helius enrichment.

Features:
- Runs at MIDNIGHT UTC every day
- Discovers pump.fun tokens via Helius DAS searchAssets API (on-chain)
- Collects 30+ ML features per token (DexScreener market data + Helius authority/holders)
- Classifies outcomes by market cap for labeled training data
- Deduplicates against existing dataset
- Triggers ML retraining when 200+ tokens accumulated

Schedule: 00:00 UTC daily
"""
import asyncio
import os
from datetime import datetime, timedelta, time
from loguru import logger
from typing import Optional

import config


class AutomatedDailyCollector:
    """Background scheduler that runs daily token collection at midnight UTC"""

    def __init__(self):
        # Configuration from environment
        self.enabled = os.getenv('DAILY_COLLECTOR_ENABLED', 'true').lower() == 'true'
        self.tokens_per_day = int(os.getenv('DAILY_COLLECTOR_COUNT', '50'))
        self.run_time_utc = time(0, 0)  # Midnight UTC

        self.task = None
        self.last_run = None
        self.next_run = None

    async def start(self):
        """Start the daily collector scheduler"""
        if not self.enabled:
            logger.info("📅 Daily collector: DISABLED (set DAILY_COLLECTOR_ENABLED=true to enable)")
            return

        logger.info("=" * 80)
        logger.info("📅 AUTOMATED DAILY TOKEN COLLECTOR")
        logger.info("=" * 80)
        logger.info(f"   Status: ENABLED")
        logger.info(f"   Schedule: Daily at {self.run_time_utc.strftime('%H:%M')} UTC (midnight)")
        logger.info(f"   Tokens per day: {self.tokens_per_day}")
        logger.info(f"   Strategy: Helius searchAssets + DexScreener enrichment")
        logger.info(f"   Goal: Build labeled ML training data (on-chain discovery)")

        # Calculate next run time
        self.next_run = self._calculate_next_run()
        time_until = (self.next_run - datetime.utcnow()).total_seconds() / 3600

        logger.info(f"   Next run: {self.next_run.isoformat()} (in {time_until:.1f}h)")
        logger.info("=" * 80)

        # Start background task
        self.task = asyncio.create_task(self._run_scheduled())

    async def stop(self):
        """Stop the daily collector"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _calculate_next_run(self) -> datetime:
        """
        Calculate next midnight UTC run time

        If it's currently before midnight today, run at midnight today.
        If it's after midnight, run at midnight tomorrow.
        """
        now = datetime.utcnow()
        today_midnight = datetime.combine(now.date(), self.run_time_utc)

        if now < today_midnight:
            # Haven't hit midnight yet today
            return today_midnight
        else:
            # Already past midnight, run tomorrow
            return today_midnight + timedelta(days=1)

    async def _run_scheduled(self):
        """Background task that runs daily collection at midnight UTC"""
        while True:
            try:
                # Wait until next scheduled run (midnight UTC)
                now = datetime.utcnow()
                if self.next_run > now:
                    wait_seconds = (self.next_run - now).total_seconds()
                    logger.info(f"📅 Daily collector scheduled for {self.next_run.strftime('%Y-%m-%d %H:%M UTC')} "
                               f"(in {wait_seconds/3600:.1f}h)")
                    await asyncio.sleep(wait_seconds)

                # Run collector at midnight UTC
                logger.info("=" * 80)
                logger.info("📅 DAILY COLLECTION: STARTING MIDNIGHT RUN")
                logger.info("=" * 80)
                logger.info(f"   Date: {datetime.utcnow().date()}")
                logger.info(f"   Goal: Collect yesterday's top performers")

                await self._run_daily_collection()

                # Update last run time
                self.last_run = datetime.utcnow()

                # Calculate next run (tomorrow midnight)
                self.next_run = self._calculate_next_run()

                logger.info("=" * 80)
                logger.info("📅 DAILY COLLECTION: COMPLETE")
                logger.info(f"   Next run: {self.next_run.strftime('%Y-%m-%d %H:%M UTC')}")
                logger.info("=" * 80)

            except asyncio.CancelledError:
                logger.info("📅 Daily collector stopped")
                break
            except Exception as e:
                logger.error(f"📅 Daily collector error: {e}")
                logger.exception(e)
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)

    async def _run_daily_collection(self):
        """Run Helius backfill + ML retraining pipeline"""
        try:
            # STEP 1: Discover pump.fun tokens via Helius and collect ML features
            logger.info("📊 STEP 1: Running Helius backfill (searchAssets + DexScreener)...")
            from tools.helius_backfill_collector import HeliusBackfillCollector

            collector = HeliusBackfillCollector()
            await collector.run(max_tokens=self.tokens_per_day)

            stats = collector.stats
            logger.info(f"✅ Helius backfill complete: +{stats.get('enriched', 0)} tokens "
                         f"(~{stats.get('credits_used_estimate', 0)} credits)")
            logger.info("")

            # STEP 2: ML model retraining (if enough new data)
            logger.info("🎓 STEP 2: Checking if ML retraining needed...")
            from tools.automated_ml_retrain import AutomatedMLRetrainer

            retrainer = AutomatedMLRetrainer()
            await retrainer.run()

            logger.info("✅ ML retraining check complete")

        except Exception as e:
            logger.error(f"❌ Daily collection error: {e}")
            logger.exception(e)
            raise

    async def trigger_manual_run(self):
        """Trigger an immediate collection run (for admin commands)"""
        logger.info("📅 Manual daily collection triggered by admin")
        await self._run_daily_collection()
        self.last_run = datetime.utcnow()
        self.next_run = self._calculate_next_run()
        logger.info(f"✅ Manual run complete. Next scheduled run: {self.next_run.isoformat()}")


# Global instance
automated_daily_collector = None


async def start_automated_daily_collector():
    """Initialize and start the automated daily collector"""
    global automated_daily_collector
    automated_daily_collector = AutomatedDailyCollector()
    await automated_daily_collector.start()
    return automated_daily_collector


async def stop_automated_daily_collector():
    """Stop the automated daily collector"""
    global automated_daily_collector
    if automated_daily_collector:
        await automated_daily_collector.stop()
