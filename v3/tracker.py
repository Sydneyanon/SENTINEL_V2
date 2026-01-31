"""
SENTINEL V3 - Token Tracker
Monitors active signals, checks milestones, determines outcomes.
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional, Dict, List

from config import MILESTONES, TRACKING_DURATION_HOURS, POLL_INTERVAL_SECONDS
import database as db


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

        # Fetch current price from DexScreener
        data = await self._fetch_dexscreener(token_address)
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

    async def _fetch_dexscreener(self, token_address: str) -> Optional[Dict]:
        """Fetch token data from DexScreener."""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    pairs = data.get('pairs', [])

                    if not pairs:
                        return None

                    # Get the pair with highest liquidity
                    pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))

                    return {
                        'price': float(pair.get('priceUsd', 0) or 0),
                        'mcap': float(pair.get('marketCap', 0) or 0),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                        'volume_1h': float(pair.get('volume', {}).get('h1', 0) or 0),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                        'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0) or 0),
                        'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                    }

        except Exception as e:
            logger.warning(f"DexScreener fetch error for {token_address[:8]}: {e}")
            return None


async def fetch_token_data(token_address: str) -> Optional[Dict]:
    """Standalone function to fetch token data from DexScreener."""
    tracker = TokenTracker()
    data = await tracker._fetch_dexscreener(token_address)

    if not data:
        return None

    # Also try to get symbol/name
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    pairs = result.get('pairs', [])
                    if pairs:
                        pair = pairs[0]
                        data['symbol'] = pair.get('baseToken', {}).get('symbol', 'UNKNOWN')
                        data['name'] = pair.get('baseToken', {}).get('name', 'Unknown')
                        data['holders'] = 0  # DexScreener doesn't provide this
    except Exception:
        pass

    return data
