"""
Direct GMGN.ai Wallet Fetcher (No Apify)
Fetches wallet stats by scraping GMGN.ai HTML pages
Free but may be rate-limited
"""
import aiohttp
import asyncio
import re
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger


class GMGNDirectFetcher:
    """Fetches wallet metadata from GMGN.ai via direct HTTP requests"""

    def __init__(self):
        # Cache wallet metadata for 6 hours to avoid rate limits
        self.cache = {}
        self.cache_ttl_hours = 6

        # User agent to avoid bot detection
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def get_wallet_metadata(self, wallet_address: str, chain: str = 'sol') -> Optional[Dict]:
        """
        Fetch wallet metadata from GMGN.ai

        Args:
            wallet_address: Solana wallet address
            chain: Blockchain (sol, eth, base, bsc)

        Returns:
            Dict with keys: name, win_rate, pnl_30d, total_trades, etc.
        """
        # Validate address
        if wallet_address.startswith('0x') or len(wallet_address) < 32:
            logger.warning(f"⚠️ Invalid Solana address: {wallet_address[:10]}...")
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
            logger.info(f"🔍 Fetching GMGN wallet metadata for {wallet_address[:8]}... (direct)")

            # GMGN wallet page URL
            url = f"https://gmgn.ai/{chain}/address/{wallet_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ GMGN returned status {resp.status} for {wallet_address[:8]}")
                        return None

                    html = await resp.text()

                    # Parse HTML for wallet stats
                    metadata = self._parse_wallet_page(html, wallet_address)

                    if not metadata:
                        logger.warning(f"⚠️ Could not parse wallet data for {wallet_address[:8]}")
                        return None

                    # Cache the result
                    self.cache[cache_key] = {
                        'data': metadata,
                        'timestamp': datetime.now()
                    }

                    logger.info(f"✅ Fetched metadata: {metadata['name']} ({metadata['win_rate']*100:.0f}% WR, ${metadata['pnl_30d']/1000:.0f}k PnL)")

                    return metadata

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout fetching GMGN data for {wallet_address[:8]}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching GMGN data: {e}")
            return None

    def _parse_wallet_page(self, html: str, wallet_address: str) -> Optional[Dict]:
        """
        Parse GMGN wallet page HTML to extract stats

        Note: This is fragile and may break if GMGN changes their HTML structure
        """
        try:
            # Extract wallet name/label (if any)
            name_match = re.search(r'<title>([^<]+)</title>', html)
            name = name_match.group(1).strip() if name_match else f"KOL_{wallet_address[:6]}"

            # Clean up name (remove "| GMGN" suffix)
            name = re.sub(r'\s*\|\s*GMGN.*$', '', name).strip()
            if not name or name == wallet_address or len(name) < 2:
                name = f"KOL_{wallet_address[:6]}"

            # Try to extract win rate (look for percentage near "Win Rate" text)
            win_rate = 0.0
            win_rate_patterns = [
                r'Win\s*Rate[:\s]*(\d+\.?\d*)%',
                r'winRate["\']?\s*:\s*["\']?(\d+\.?\d*)',
                r'win_rate["\']?\s*:\s*["\']?(\d+\.?\d*)',
            ]
            for pattern in win_rate_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    win_rate = float(match.group(1))
                    if win_rate > 1:  # If it's a percentage
                        win_rate = win_rate / 100.0
                    break

            # Try to extract 30D PnL
            pnl_30d = 0.0
            pnl_patterns = [
                r'30D\s*PnL[:\s]*\$?([\d,]+\.?\d*)[kKmM]?',
                r'pnl_30d["\']?\s*:\s*["\']?([\d,]+\.?\d*)',
                r'realized.*?profit.*?(\d+\.?\d*)[kKmM]',
            ]
            for pattern in pnl_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    pnl_str = match.group(1).replace(',', '')
                    pnl_30d = float(pnl_str)

                    # Check for k/K/m/M suffix
                    if 'k' in match.group(0).lower():
                        pnl_30d *= 1000
                    elif 'm' in match.group(0).lower():
                        pnl_30d *= 1000000
                    break

            # Try to extract total trades
            total_trades = 0
            trades_patterns = [
                r'Total\s*Trades[:\s]*(\d+)',
                r'totalTrades["\']?\s*:\s*["\']?(\d+)',
                r'total_trades["\']?\s*:\s*["\']?(\d+)',
            ]
            for pattern in trades_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    total_trades = int(match.group(1))
                    break

            metadata = {
                'name': name,
                'win_rate': win_rate,
                'pnl_30d': pnl_30d,
                'pnl_7d': 0.0,  # Not easily extractable
                'total_trades': total_trades,
                'realized_profit': pnl_30d,  # Approximation
                'unrealized_profit': 0.0,
            }

            logger.debug(f"📊 Parsed: name={name}, WR={win_rate*100:.0f}%, PnL=${pnl_30d:,.0f}")

            return metadata

        except Exception as e:
            logger.error(f"❌ Error parsing GMGN HTML: {e}")
            return None


# Global instance
_gmgn_direct_fetcher = None

def get_gmgn_direct_fetcher() -> GMGNDirectFetcher:
    """Get global GMGN direct fetcher instance"""
    global _gmgn_direct_fetcher
    if _gmgn_direct_fetcher is None:
        _gmgn_direct_fetcher = GMGNDirectFetcher()
    return _gmgn_direct_fetcher


# Test script
if __name__ == "__main__":
    async def test():
        fetcher = GMGNDirectFetcher()

        # Test with a wallet address
        metadata = await fetcher.get_wallet_metadata("57rXqaQsvgyBKwebP2StfqQeCBjBS4jsrZFJN5aU2V9b")

        if metadata:
            print(f"Name: {metadata['name']}")
            print(f"Win Rate: {metadata['win_rate']*100:.1f}%")
            print(f"30D PnL: ${metadata['pnl_30d']:,.0f}")
            print(f"Total Trades: {metadata['total_trades']}")
        else:
            print("Failed to fetch metadata")

    asyncio.run(test())
