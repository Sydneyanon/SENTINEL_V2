"""
GMGN Wallet Metadata Fetcher
Fetches live wallet stats (win_rate, pnl_30d, name) from GMGN via Apify API
"""
import asyncio
import os
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from apify_client import ApifyClient

logger = logging.getLogger(__name__)


class GMGNWalletFetcher:
    """Fetches wallet metadata from GMGN.ai using Apify scrapers"""

    def __init__(self):
        self.apify_token = os.getenv('APIFY_API_TOKEN')
        if not self.apify_token:
            logger.warning("⚠️ APIFY_API_TOKEN not set - wallet metadata fetching disabled")
            self.client = None
        else:
            self.client = ApifyClient(token=self.apify_token)

        # Cache wallet metadata for 6 hours to avoid excessive API calls
        self.cache = {}
        self.cache_ttl_hours = 6

    async def get_wallet_metadata(self, wallet_address: str, chain: str = 'sol') -> Optional[Dict]:
        """
        Fetch wallet metadata from GMGN via Apify

        Args:
            wallet_address: Solana wallet address
            chain: Blockchain (sol, eth, base, bsc, tron)

        Returns:
            Dict with keys: name, win_rate, pnl_30d, pnl_7d, total_trades, etc.
        """
        if not self.client:
            logger.debug("Apify client not initialized - skipping metadata fetch")
            return None

        # Check cache first
        cache_key = f"{chain}:{wallet_address}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_age = datetime.now() - cached_data['timestamp']
            if cache_age < timedelta(hours=self.cache_ttl_hours):
                logger.debug(f"💾 Using cached wallet metadata for {wallet_address[:8]}...")
                return cached_data['data']

        try:
            logger.info(f"🔍 Fetching GMGN wallet metadata for {wallet_address[:8]}... via Apify")

            # Run the GMGN Wallet Stat Scraper actor
            # Note: The exact input schema may vary - adjust based on Apify actor docs
            run_input = {
                "walletAddress": wallet_address,
                "chain": chain,
                "timePeriod": "30d"  # Get 30-day stats
            }

            # Run actor and wait for completion
            run = await asyncio.to_thread(
                self.client.actor("muhammetakkurtt/gmgn-wallet-stat-scraper").call,
                run_input=run_input
            )

            # Fetch results from dataset
            dataset_items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                dataset_items.append(item)

            if not dataset_items:
                logger.warning(f"No data returned from Apify for wallet {wallet_address[:8]}...")
                return None

            # Parse the first result
            wallet_data = dataset_items[0]

            # Extract relevant fields (adjust based on actual Apify response)
            metadata = {
                'name': wallet_data.get('walletName') or wallet_data.get('name') or f"Wallet_{wallet_address[:4]}",
                'win_rate': self._parse_win_rate(wallet_data.get('winRate') or wallet_data.get('win_rate')),
                'pnl_30d': self._parse_pnl(wallet_data.get('pnl30d') or wallet_data.get('pnl_30d')),
                'pnl_7d': self._parse_pnl(wallet_data.get('pnl7d') or wallet_data.get('pnl_7d')),
                'total_trades': wallet_data.get('totalTrades') or wallet_data.get('total_trades') or 0,
                'realized_profit': self._parse_pnl(wallet_data.get('realizedProfit')),
                'unrealized_profit': self._parse_pnl(wallet_data.get('unrealizedProfit')),
            }

            # Cache the result
            self.cache[cache_key] = {
                'data': metadata,
                'timestamp': datetime.now()
            }

            logger.info(f"✅ Fetched metadata for {metadata['name']}: {metadata['win_rate']*100:.0f}% WR, ${metadata['pnl_30d']/1000:.0f}k PnL")

            return metadata

        except Exception as e:
            logger.error(f"❌ Error fetching wallet metadata from Apify: {e}")
            return None

    def _parse_win_rate(self, value) -> float:
        """Parse win rate to decimal (0.0 to 1.0)"""
        if value is None:
            return 0.0

        # Handle percentage string like "75%"
        if isinstance(value, str):
            value = value.strip().replace('%', '')
            try:
                value = float(value)
                # If it's already a percentage (>1), convert to decimal
                if value > 1:
                    return value / 100.0
                return value
            except ValueError:
                return 0.0

        # Handle float
        if isinstance(value, (int, float)):
            # If value > 1, assume it's percentage
            if value > 1:
                return value / 100.0
            return float(value)

        return 0.0

    def _parse_pnl(self, value) -> float:
        """Parse PnL value to USD float"""
        if value is None:
            return 0.0

        # Handle string like "$45,000" or "45k"
        if isinstance(value, str):
            value = value.strip().replace('$', '').replace(',', '')

            # Handle k/K suffix
            if value.endswith('k') or value.endswith('K'):
                try:
                    return float(value[:-1]) * 1000
                except ValueError:
                    return 0.0

            # Handle M/m suffix
            if value.endswith('M') or value.endswith('m'):
                try:
                    return float(value[:-1]) * 1000000
                except ValueError:
                    return 0.0

            # Regular number
            try:
                return float(value)
            except ValueError:
                return 0.0

        # Handle numeric
        if isinstance(value, (int, float)):
            return float(value)

        return 0.0


# Global instance
_gmgn_fetcher = None

def get_gmgn_fetcher() -> GMGNWalletFetcher:
    """Get global GMGN fetcher instance"""
    global _gmgn_fetcher
    if _gmgn_fetcher is None:
        _gmgn_fetcher = GMGNWalletFetcher()
    return _gmgn_fetcher


# Example usage
if __name__ == "__main__":
    async def test():
        fetcher = GMGNWalletFetcher()

        # Test with a wallet address
        metadata = await fetcher.get_wallet_metadata("57rXqaQsvgyBKwebP2StfqQeCBjBS4jsrZFJN5aU2V9b")

        if metadata:
            print(f"Name: {metadata['name']}")
            print(f"Win Rate: {metadata['win_rate']*100:.1f}%")
            print(f"30D PnL: ${metadata['pnl_30d']:,.0f}")
            print(f"7D PnL: ${metadata['pnl_7d']:,.0f}")
            print(f"Total Trades: {metadata['total_trades']}")
        else:
            print("Failed to fetch metadata")

    asyncio.run(test())
