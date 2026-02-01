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
    - Telegram notifications for discovery results
    """

    APIFY_BASE_URL = "https://api.apify.com/v2"

    def __init__(self, on_wallets_added=None, on_discovery_complete=None):
        """
        Args:
            on_wallets_added: Callback when new wallets are added to tracking.
                             Called with list of wallet addresses.
            on_discovery_complete: Callback when discovery completes.
                                  Called with result dict including 'new_wallets' list.
        """
        self.running = False
        self.session = None
        self.on_wallets_added = on_wallets_added
        self.on_discovery_complete = on_discovery_complete
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

                    # Also run stale wallet cleanup after discovery
                    removed = await db.cleanup_stale_smart_money(days_inactive=30, min_signals=3)
                    if removed > 0:
                        logger.info(f"Cleaned up {removed} stale smart money wallets")

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
                # Note: Apify returns tokens, each with a 'wallets' array of smart money
                tokens = await self._fetch_smart_degens()

                if not tokens:
                    return {
                        'success': False,
                        'discovered': 0,
                        'added_to_tracking': 0,
                        'message': 'No tokens found from Apify'
                    }

                # Extract wallets from tokens (dedupe by address)
                wallet_addresses = set()
                for token in tokens:
                    token_wallets = token.get('wallets', [])
                    if isinstance(token_wallets, list):
                        for w in token_wallets:
                            if isinstance(w, dict):
                                addr = w.get('address') or w.get('wallet_address') or w.get('walletAddress')
                                if addr:
                                    wallet_addresses.add(addr)

                logger.info(f"Extracted {len(wallet_addresses)} unique wallet addresses from {len(tokens)} tokens")

                if not wallet_addresses:
                    return {
                        'success': False,
                        'discovered': 0,
                        'added_to_tracking': 0,
                        'message': 'No wallet addresses found in token data'
                    }

                # Fetch actual wallet stats from GMGN API for each address
                logger.info(f"Fetching wallet stats from GMGN for {len(wallet_addresses)} wallets...")
                wallets_with_stats = []
                for addr in list(wallet_addresses)[:config.DISCOVERY_LIMIT]:
                    stats = await self._fetch_wallet_stats(addr)
                    if stats:
                        wallets_with_stats.append(stats)
                    await asyncio.sleep(0.2)  # Rate limit

                logger.info(f"Got stats for {len(wallets_with_stats)} wallets")

                if not wallets_with_stats:
                    return {
                        'success': False,
                        'discovered': 0,
                        'added_to_tracking': 0,
                        'message': 'Could not fetch wallet stats from GMGN'
                    }

                # Log sample wallet stats
                sample = wallets_with_stats[0]
                logger.info(f"Sample wallet stats: addr={sample.get('address', 'N/A')[:8]}..., WR={sample.get('winrate', 'N/A')}, trades={sample.get('buy_30d', 'N/A')}, pnl={sample.get('realized_profit_30d', 'N/A')}")

                # Filter and store wallets
                stored = 0
                filter_reasons = {'no_address': 0, 'win_rate': 0, 'trades': 0, 'honeypot': 0, 'pnl': 0}
                for w in wallets_with_stats:
                    result = await self._store_wallet_with_reason(w)
                    if result == 'stored':
                        stored += 1
                    elif result in filter_reasons:
                        filter_reasons[result] += 1

                logger.info(f"Stored {stored}/{len(wallets_with_stats)} wallets")
                if stored < len(wallets_with_stats):
                    logger.info(f"Filtered out: {filter_reasons}")

                # Auto-enable tracking for top performers
                added, new_wallet_details = await db.auto_enable_top_smart_money_with_details(
                    max_wallets=config.DISCOVERY_AUTO_TRACK_TOP,
                    min_win_rate=config.DISCOVERY_MIN_WIN_RATE
                )

                if added > 0:
                    logger.info(f"Auto-enabled {added} wallets for tracking")

                    # Sync with Helius
                    await self._sync_helius()

                    # Callback for new wallets
                    if self.on_wallets_added:
                        all_wallets = await db.get_all_wallets()
                        addresses = [w['address'] for w in all_wallets]
                        await self.on_wallets_added(addresses)

                self.last_discovery = datetime.now()

                result = {
                    'success': True,
                    'discovered': stored,
                    'added_to_tracking': added,
                    'new_wallets': new_wallet_details,
                    'message': f'Discovered {stored} wallets, added {added} to tracking'
                }

                # Notify via callback (for Telegram)
                if self.on_discovery_complete:
                    await self.on_discovery_complete(result)

                return result

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

        actor_id = "muhammetakkurtt~gmgn-smart-degen-monitor-scraper"
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

            # Debug: Log sample data to see actual field names
            if results and len(results) > 0:
                sample = results[0]
                logger.debug(f"Sample wallet data keys: {list(sample.keys())}")
                logger.debug(f"Sample wallet data: {sample}")

            return results

    async def _fetch_wallet_stats(self, address: str) -> Optional[Dict]:
        """Fetch wallet stats from GMGN API."""
        url = f"https://gmgn.ai/defi/quotation/v1/smartmoney/sol/walletNew/{address}?period=30d"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://gmgn.ai/',
            'Origin': 'https://gmgn.ai',
        }

        try:
            async with self.session.get(url, headers=headers) as resp:
                # Log first response status
                if not hasattr(self, '_logged_first_status'):
                    self._logged_first_status = True
                    logger.info(f"GMGN API first response status: {resp.status}")

                if resp.status != 200:
                    if not hasattr(self, '_logged_error'):
                        self._logged_error = True
                        text = await resp.text()
                        logger.warning(f"GMGN API error: {resp.status} - {text[:200]}")
                    return None

                data = await resp.json()

                # Log first successful response
                if not hasattr(self, '_logged_sample'):
                    self._logged_sample = True
                    logger.info(f"GMGN API response: code={data.get('code')}, msg={data.get('msg')}")
                    if data.get('data'):
                        logger.info(f"GMGN data keys: {list(data.get('data', {}).keys())}")

                if data.get('code') != 0:
                    return None

                wallet_data = data.get('data', {})
                if not wallet_data:
                    return None

                # Add address to the data
                wallet_data['address'] = address
                return wallet_data

        except Exception as e:
            logger.warning(f"Failed to fetch stats for {address[:8]}: {e}")
            return None

    async def _store_wallet_with_reason(self, data: Dict) -> str:
        """Store a wallet in the smart_money table if it passes filters.

        Returns:
            'stored' if successful, or filter reason ('no_address', 'win_rate', 'trades', 'honeypot', 'pnl')
        """

        # Extract address (field names may vary)
        address = data.get('address') or data.get('wallet_address') or data.get('walletAddress')
        if not address:
            logger.debug(f"Wallet skipped: no address found in data")
            return 'no_address'

        # Extract metrics (GMGN uses: winrate, buy_30d, realized_profit_30d)
        win_rate = float(
            data.get('winrate') or data.get('winRate') or data.get('win_rate') or 0
        )
        # GMGN may return winrate as decimal (0.65) or percentage (65)
        if 0 < win_rate < 1:
            win_rate = win_rate * 100

        total_trades = int(
            data.get('buy_30d') or data.get('totalTrades') or
            data.get('total_trades') or data.get('trades') or 0
        )
        pnl_7d = float(
            data.get('realized_profit_7d') or data.get('pnl7d') or data.get('pnl_7d') or 0
        )
        pnl_30d = float(
            data.get('realized_profit_30d') or data.get('pnl30d') or
            data.get('pnl_30d') or data.get('pnl') or 0
        )
        honeypot_ratio = float(
            data.get('honeypotRatio') or data.get('honeypot_ratio') or 0
        )

        # Debug: Log extracted values
        logger.debug(f"Wallet {address[:8]}: WR={win_rate}, trades={total_trades}, pnl30d={pnl_30d}, honeypot={honeypot_ratio}")

        # Hard filters - must pass ALL (tightened for quality)
        if win_rate < config.DISCOVERY_MIN_WIN_RATE:
            logger.debug(f"Wallet {address[:8]} filtered: win_rate {win_rate} < {config.DISCOVERY_MIN_WIN_RATE}")
            return 'win_rate'
        if total_trades < config.DISCOVERY_MIN_TRADES:
            logger.debug(f"Wallet {address[:8]} filtered: trades {total_trades} < {config.DISCOVERY_MIN_TRADES}")
            return 'trades'
        if honeypot_ratio > config.DISCOVERY_MAX_HONEYPOT:
            logger.debug(f"Wallet {address[:8]} filtered: honeypot {honeypot_ratio} > {config.DISCOVERY_MAX_HONEYPOT}")
            return 'honeypot'

        # PNL filter - must be profitable
        min_pnl = getattr(config, 'DISCOVERY_MIN_PNL_30D', 5000)
        if pnl_30d < min_pnl:
            logger.debug(f"Wallet {address[:8]} filtered: pnl30d {pnl_30d} < {min_pnl}")
            return 'pnl'

        # Determine tier using config thresholds
        elite_wr = getattr(config, 'DISCOVERY_ELITE_WIN_RATE', 65.0)
        elite_pnl = getattr(config, 'DISCOVERY_ELITE_MIN_PNL', 15000)
        sm_wr = getattr(config, 'DISCOVERY_SMART_MONEY_WIN_RATE', 55.0)
        sm_pnl = getattr(config, 'DISCOVERY_SMART_MONEY_MIN_PNL', 7500)

        if win_rate >= elite_wr and pnl_30d >= elite_pnl:
            tier = 'elite'
        elif win_rate >= sm_wr and pnl_30d >= sm_pnl:
            tier = 'smart_money'
        else:
            tier = 'verified'

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

        return 'stored'

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
