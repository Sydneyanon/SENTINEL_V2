"""
Automated Historical Data Collector - Background Scheduler

Uses Helius searchAssets + program TX scanning to discover pump.fun tokens
and build ML training data on a weekly schedule.

Features:
- Runs weekly by default (configurable)
- Discovers tokens via Helius DAS API (on-chain, not DexScreener discovery)
- Incremental updates (deduplicates against existing dataset)
- Collects 30+ ML features per token with Helius authority/holder enrichment
- Configurable via environment variables
- Runs in background without blocking main bot
"""
import asyncio
import os
import json
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional

import config


class AutomatedCollector:
    """Background scheduler for historical data collection"""

    def __init__(self):
        # Configuration from environment
        self.enabled = os.getenv('AUTO_COLLECTOR_ENABLED', 'true').lower() == 'true'
        self.interval_hours = int(os.getenv('AUTO_COLLECTOR_INTERVAL_HOURS', '168'))  # Default: 7 days
        self.tokens_per_run = int(os.getenv('AUTO_COLLECTOR_COUNT', '50'))  # Collect 50 new tokens per week
        self.min_mcap = int(os.getenv('AUTO_COLLECTOR_MIN_MCAP', '1000000'))
        self.max_mcap = int(os.getenv('AUTO_COLLECTOR_MAX_MCAP', '100000000'))

        self.task = None
        self.last_run = None
        self.next_run = None

    async def start(self):
        """Start the background collector"""
        if not self.enabled:
            logger.info("🤖 Automated collector: DISABLED (set AUTO_COLLECTOR_ENABLED=true to enable)")
            return

        logger.info("=" * 80)
        logger.info("🤖 AUTOMATED HISTORICAL COLLECTOR (Helius Backfill)")
        logger.info("=" * 80)
        logger.info(f"   Status: ENABLED")
        logger.info(f"   Strategy: Helius searchAssets + DexScreener enrichment")
        logger.info(f"   Schedule: Every {self.interval_hours} hours ({self.interval_hours/24:.0f} days)")
        logger.info(f"   Tokens per run: {self.tokens_per_run}")
        logger.info(f"   MCAP range: ${self.min_mcap:,} - ${self.max_mcap:,}")

        # Check when we last ran
        self.last_run = self._get_last_run_time()

        if self.last_run:
            hours_since = (datetime.utcnow() - self.last_run).total_seconds() / 3600
            logger.info(f"   Last run: {self.last_run.isoformat()} ({hours_since:.1f}h ago)")

            # Calculate next run
            self.next_run = self.last_run + timedelta(hours=self.interval_hours)
            time_until = (self.next_run - datetime.utcnow()).total_seconds() / 3600

            if time_until > 0:
                logger.info(f"   Next run: {self.next_run.isoformat()} (in {time_until:.1f}h)")
            else:
                logger.info(f"   Next run: NOW (overdue by {abs(time_until):.1f}h)")
                self.next_run = datetime.utcnow()
        else:
            logger.info(f"   First run: Starting in 1 hour (giving bot time to stabilize)")
            self.next_run = datetime.utcnow() + timedelta(hours=1)

        logger.info("=" * 80)

        # Start background task
        self.task = asyncio.create_task(self._run_scheduled())

    async def stop(self):
        """Stop the background collector"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run_scheduled(self):
        """Background task that runs collector on schedule"""
        while True:
            try:
                # Wait until next scheduled run
                now = datetime.utcnow()
                if self.next_run > now:
                    wait_seconds = (self.next_run - now).total_seconds()
                    logger.info(f"🤖 Collector scheduled to run in {wait_seconds/3600:.1f}h at {self.next_run.isoformat()}")
                    await asyncio.sleep(wait_seconds)

                # Run collector
                logger.info("=" * 80)
                logger.info("🤖 AUTOMATED COLLECTOR: STARTING SCHEDULED RUN")
                logger.info("=" * 80)

                await self._run_collector()

                # Update last run time
                self.last_run = datetime.utcnow()
                self._save_last_run_time(self.last_run)

                # Calculate next run
                self.next_run = self.last_run + timedelta(hours=self.interval_hours)

                logger.info("=" * 80)
                logger.info("🤖 AUTOMATED COLLECTOR: RUN COMPLETE")
                logger.info(f"   Next run: {self.next_run.isoformat()}")
                logger.info("=" * 80)

            except asyncio.CancelledError:
                logger.info("🤖 Automated collector stopped")
                break
            except Exception as e:
                logger.error(f"🤖 Automated collector error: {e}")
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)

    async def _run_collector(self):
        """Run the Helius backfill collector for ML training data"""
        try:
            from tools.helius_backfill_collector import HeliusBackfillCollector

            existing_tokens = self._get_existing_tokens()
            logger.info(f"   Found {len(existing_tokens)} already collected tokens")
            logger.info(f"   Target: Collect {self.tokens_per_run} NEW tokens via Helius backfill")

            collector = HeliusBackfillCollector()
            await collector.run(max_tokens=self.tokens_per_run)

            stats = collector.stats
            logger.info(f"✅ Automated Helius backfill complete: "
                         f"+{stats.get('enriched', 0)} tokens "
                         f"(~{stats.get('credits_used_estimate', 0)} credits)")

        except Exception as e:
            logger.error(f"❌ Collector error: {e}")
            raise

    def _get_existing_tokens(self) -> set:
        """Get set of already collected token addresses"""
        try:
            with open('data/historical_training_data.json', 'r') as f:
                data = json.load(f)
                return set(token['token_address'] for token in data.get('tokens', []))
        except FileNotFoundError:
            return set()
        except Exception as e:
            logger.warning(f"Error reading existing tokens: {e}")
            return set()

    def _get_last_run_time(self) -> Optional[datetime]:
        """Get timestamp of last collector run"""
        try:
            with open('data/historical_training_data.json', 'r') as f:
                data = json.load(f)
                collected_at = data.get('collected_at')
                if collected_at:
                    return datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
        except:
            pass
        return None

    def _save_last_run_time(self, timestamp: datetime):
        """Update the collected_at timestamp in output file"""
        try:
            with open('data/historical_training_data.json', 'r+') as f:
                data = json.load(f)
                data['collected_at'] = timestamp.isoformat()
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        except Exception as e:
            logger.warning(f"Could not update last run time: {e}")

    async def trigger_manual_run(self):
        """Trigger an immediate collector run (for admin commands)"""
        logger.info("🤖 Manual collector run triggered by admin")
        await self._run_collector()
        self.last_run = datetime.utcnow()
        self._save_last_run_time(self.last_run)
        self.next_run = self.last_run + timedelta(hours=self.interval_hours)
        logger.info(f"✅ Manual run complete. Next scheduled run: {self.next_run.isoformat()}")


# Global instance
automated_collector = None


async def start_automated_collector():
    """Initialize and start the automated collector"""
    global automated_collector
    automated_collector = AutomatedCollector()
    await automated_collector.start()
    return automated_collector


async def stop_automated_collector():
    """Stop the automated collector"""
    global automated_collector
    if automated_collector:
        await automated_collector.stop()
