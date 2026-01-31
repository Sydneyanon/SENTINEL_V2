"""
SENTINEL V3 - Token Tracker
Monitors active signals, checks milestones, determines outcomes.
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional, Dict, List

from config import MILESTONES, TRACKING_DURATION_HOURS, POLL_INTERVAL_SECONDS
import database as db
from fetchers import fetch_token_data


class TokenTracker:
    """Tracks active signals and checks for milestones."""

    def __init__(self, telegram_poster=None):
        self.telegram = telegram_poster
        self.running = False
        self._task = None

    async def start(self):
        """Start the tracking loop."""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._tracking_loop())
        logger.info("Token tracker started")

    async def stop(self):
        """Stop the tracking loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Token tracker stopped")

    async def _tracking_loop(self):
        """Main tracking loop."""
        while self.running:
            try:
                await self._check_all_signals()
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Tracking loop error: {e}")
                await asyncio.sleep(60)

    async def _check_all_signals(self):
        """Check all active signals for price updates and milestones."""
        signals = await db.get_active_signals()

        if not signals:
            return

        logger.debug(f"Checking {len(signals)} active signals")

        for signal in signals:
            try:
                await self._check_signal(signal)
            except Exception as e:
                logger.error(f"Error checking signal {signal['id']}: {e}")

    async def _check_signal(self, signal: Dict):
        """Check a single signal for updates."""
        token_address = signal['token_address']

        # Fetch current price (DexScreener for post-grad, PumpPortal for pre-grad)
        data = await fetch_token_data(token_address)
        if not data:
            return

        current_price = data.get('price', 0)
        if not current_price or not signal['entry_price']:
            return

        # Update price in database
        await db.update_signal_price(signal['id'], current_price)

        # Calculate multiplier
        multiplier = current_price / signal['entry_price']

        # Check for milestones
        reached_milestones = await db.get_signal_milestones(signal['id'])

        for milestone in MILESTONES:
            if milestone in reached_milestones:
                continue

            if multiplier >= milestone:
                # New milestone reached!
                is_new = await db.record_milestone(
                    signal['id'],
                    token_address,
                    milestone,
                    current_price
                )

                if is_new:
                    logger.info(f"{signal['symbol']} reached {milestone}x!")

                    # Post to Telegram
                    if self.telegram:
                        await self.telegram.post_milestone(signal, milestone, current_price)

        # Check if tracking period is over
        if signal['posted_at']:
            age = datetime.utcnow() - signal['posted_at']
            if age > timedelta(hours=TRACKING_DURATION_HOURS):
                await self._finalize_signal(signal, multiplier)

    async def _finalize_signal(self, signal: Dict, final_multiplier: float):
        """Finalize signal outcome after tracking period."""
        # Determine outcome
        if final_multiplier >= 2.0:
            outcome = 'win'
        elif final_multiplier < 0.5:
            outcome = 'rug'
        else:
            outcome = 'neutral'

        await db.set_signal_outcome(signal['id'], outcome, final_multiplier)

        logger.info(
            f"Signal {signal['symbol']} finalized: {outcome} "
            f"(final: {final_multiplier:.2f}x, max: {signal['max_multiplier']:.2f}x)"
        )

