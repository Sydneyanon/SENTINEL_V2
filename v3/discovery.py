"""
SENTINEL V3 - Smart Money Discovery Scheduler
Automatically discovers and tracks high-performing wallets via GMGN/Apify.
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from typing import List, Dict, Optional

import config
import database as db
import helius


class SmartMoneyDiscovery:
    """
    Automated smart money wallet discovery using Apify GMGN scrapers.

    Features:
    - Weekly discovery runs (configurable)
    - Stores wallets in database with performance metrics
    - Auto-enables tracking for top performers
    - Syncs with Helius webhooks
    """

    APIFY_BASE_URL = "https://api.apify.com/v2"

    def __init__(self, on_wallets_added=None):
        """
        Args:
            on_wallets_added: Callback when new wallets are added to tracking.
                             Called with list of wallet addresses.
        """
        self.running = False
        self.session = None
        self.on_wallets_added = on_wallets_added
        self.last_discovery = None
        self._task = None

    async def start(self):
        """Start the discovery scheduler."""
        if not config.APIFY_API_TOKEN:
            logger.warning("Smart Money Discovery disabled (no APIFY_API_TOKEN)")
            return

        self.running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Smart Money Discovery started (interval: {config.DISCOVERY_INTERVAL_HOURS}h)")

    async def stop(self):
        """Stop the discovery scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("Smart Money Discovery stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop - runs discovery periodically."""
        import aiohttp

        # Wait 60 seconds on startup to let other services initialize
        await asyncio.sleep(60)

        while self.running:
            try:
                # Check if enough time has passed since last discovery
                should_run = False

                if self.last_discovery is None:
                    # First run - check database for last discovery time
                    stats = await db.get_smart_money_stats()
                    if stats['total_discovered'] == 0:
                        should_run = True
                        logger.info("No smart money wallets found - running initial discovery")
                else:
                    hours_since = (datetime.now() - self.last_discovery).total_seconds() / 3600
                    if hours_since >= config.DISCOVERY_INTERVAL_HOURS:
                        should_run = True

                if should_run:
                    await self.run_discovery()

                # Sleep for 1 hour then check again
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery scheduler error: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retrying

    async def run_discovery(self) -> Dict:
        """
        Run a discovery cycle.

        Returns:
            {
                'success': bool,
                'discovered': int,
                'added_to_tracking': int,
                'message': str
            }
        """
        import aiohttp

        if not config.APIFY_API_TOKEN:
            return {
                'success': False,
                'discovered': 0,
                'added_to_tracking': 0,
                'message': 'APIFY_API_TOKEN not set'
            }

        logger.info("Starting smart money discovery...")

        try:
            async with aiohttp.ClientSession() as session:
                self.session = session

                # Fetch smart degens from GMGN
                wallets = await self._fetch_smart_degens()

                if not wallets:
                    return {
                        'success': False,
                        'discovered': 0,
                        'added_to_tracking': 0,
                        'message': 'No wallets found from Apify'
                    }

                # Filter and store wallets
                stored = 0
                for w in wallets:
                    if await self._store_wallet(w):
                        stored += 1

                logger.info(f"Stored {stored} smart money wallets")

                # Auto-enable tracking for top performers
                added = await db.auto_enable_top_smart_money(
                    max_wallets=config.DISCOVERY_AUTO_TRACK_TOP,
                    min_win_rate=config.DISCOVERY_MIN_WIN_RATE
                )

                if added > 0:
                    logger.info(f"Auto-enabled {added} wallets for tracking")

                    # Sync with Helius
                    await self._sync_helius()

                    # Callback for new wallets
                    if self.on_wallets_added:
                        new_wallets = await db.get_smart_money_wallets(tracking_only=True)
                        addresses = [w['address'] for w in new_wallets]
                        await self.on_wallets_added(addresses)

                self.last_discovery = datetime.now()

                return {
                    'success': True,
                    'discovered': stored,
                    'added_to_tracking': added,
                    'message': f'Discovered {stored} wallets, added {added} to tracking'
                }

        except Exception as e:
            logger.error(f"Discovery error: {e}")
            return {
                'success': False,
                'discovered': 0,
                'added_to_tracking': 0,
                'message': str(e)
            }

    async def _fetch_smart_degens(self) -> List[Dict]:
        """Fetch smart money wallets from Apify GMGN scraper."""

        actor_id = "muhammetakkurtt/gmgn-smart-degen-monitor-scraper"
        url = f"{self.APIFY_BASE_URL}/acts/{actor_id}/runs?token={config.APIFY_API_TOKEN}"

        input_data = {
            "chain": "sol",
            "limit": config.DISCOVERY_LIMIT,
        }

        logger.info(f"Starting Apify actor: {actor_id}")

        # Start the actor run
        async with self.session.post(url, json=input_data, timeout=30) as resp:
            if resp.status not in (200, 201):
                error = await resp.text()
                logger.error(f"Failed to start actor: {resp.status} - {error}")
                return []

            run_data = await resp.json()
            run_id = run_data['data']['id']

        logger.info(f"Actor run started: {run_id}")

        # Poll for completion (max 2 minutes)
        status_url = f"{self.APIFY_BASE_URL}/actor-runs/{run_id}?token={config.APIFY_API_TOKEN}"

        for i in range(24):  # 24 * 5 seconds = 2 minutes
            await asyncio.sleep(5)

            async with self.session.get(status_url) as resp:
                if resp.status != 200:
                    continue

                status_data = await resp.json()
                status = status_data['data']['status']

                if status == 'SUCCEEDED':
                    logger.info("Actor run completed")
                    break
                elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                    logger.error(f"Actor run failed: {status}")
                    return []
        else:
            logger.error("Actor run timed out")
            return []

        # Get results from dataset
        dataset_id = status_data['data']['defaultDatasetId']
        dataset_url = f"{self.APIFY_BASE_URL}/datasets/{dataset_id}/items?token={config.APIFY_API_TOKEN}"

        async with self.session.get(dataset_url) as resp:
            if resp.status != 200:
                return []

            results = await resp.json()
            logger.info(f"Got {len(results)} wallets from Apify")
            return results

    async def _store_wallet(self, data: Dict) -> bool:
        """Store a wallet in the smart_money table if it passes filters."""

        # Extract address (field names may vary)
        address = data.get('address') or data.get('wallet_address') or data.get('walletAddress')
        if not address:
            return False

        # Extract metrics
        win_rate = float(data.get('winRate') or data.get('win_rate') or 0)
        total_trades = int(data.get('totalTrades') or data.get('total_trades') or data.get('trades') or 0)
        pnl_7d = float(data.get('pnl7d') or data.get('pnl_7d') or 0)
        pnl_30d = float(data.get('pnl30d') or data.get('pnl_30d') or data.get('pnl') or 0)
        honeypot_ratio = float(data.get('honeypotRatio') or data.get('honeypot_ratio') or 0)

        # Apply filters
        if win_rate < config.DISCOVERY_MIN_WIN_RATE:
            return False
        if total_trades < config.DISCOVERY_MIN_TRADES:
            return False
        if honeypot_ratio > config.DISCOVERY_MAX_HONEYPOT:
            return False
        if pnl_30d <= 0:
            return False

        # Determine tier
        if win_rate >= 60 and pnl_30d > 10000:
            tier = 'elite'
        elif win_rate >= 50 and pnl_30d > 5000:
            tier = 'smart_money'
        elif win_rate >= 40:
            tier = 'verified'
        else:
            tier = 'new'

        # Store in database
        await db.add_smart_money(
            address=address,
            source='smart_degen',
            win_rate=win_rate,
            total_trades=total_trades,
            pnl_7d=pnl_7d,
            pnl_30d=pnl_30d,
            honeypot_ratio=honeypot_ratio,
            tier=tier
        )

        return True

    async def _sync_helius(self):
        """Sync all tracked wallets with Helius."""
        if not config.WEBHOOK_URL:
            logger.warning("Cannot sync Helius - WEBHOOK_URL not set")
            return

        wallets = await db.get_all_wallets()
        if not wallets:
            return

        webhook_url = f"{config.WEBHOOK_URL.strip().rstrip('/')}/webhook/wallet"
        addresses = [w['address'] for w in wallets]

        result = await helius.sync_wallets(addresses, webhook_url)

        if result['success']:
            logger.info(f"Helius synced: {result['wallets_synced']} wallets")
        else:
            logger.error(f"Helius sync failed: {result['message']}")


# Singleton instance
_discovery: Optional[SmartMoneyDiscovery] = None


def get_discovery() -> SmartMoneyDiscovery:
    """Get the discovery instance."""
    global _discovery
    if _discovery is None:
        _discovery = SmartMoneyDiscovery()
    return _discovery
