"""
GMGN Smart Money Discovery via Apify
Finds high-performing wallets to add to V3 tracking.
"""
import asyncio
import aiohttp
import json
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class WalletCandidate:
    address: str
    pnl_7d: float
    pnl_30d: float
    win_rate: float
    total_trades: int
    avg_holding_time: str
    honeypot_ratio: float  # % of honeypot tokens bought
    source: str  # 'smart_degen', 'copytrade', etc.

    def is_quality(self) -> bool:
        """Filter out scammers and bots."""
        # Minimum requirements
        if self.win_rate < 35:  # Below 35% = likely losing money
            return False
        if self.total_trades < 20:  # Too few trades = not enough data
            return False
        if self.honeypot_ratio > 30:  # >30% honeypots = likely scammer/bot
            return False
        if self.pnl_30d < 0:  # Losing money overall
            return False
        return True

    def get_tier(self) -> str:
        """Assign tier based on performance."""
        if self.win_rate >= 60 and self.pnl_30d > 10000:
            return 'elite'
        elif self.win_rate >= 50 and self.pnl_30d > 5000:
            return 'smart_money'
        elif self.win_rate >= 40:
            return 'verified'
        else:
            return 'new'


class ApifyGMGNScraper:
    """
    Apify client for GMGN scrapers.

    Required scrapers:
    - muhammetakkurtt/gmgn-smart-degen-monitor-scraper
    - muhammetakkurtt/gmgn-wallet-stat-scraper
    """

    BASE_URL = "https://api.apify.com/v2"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def run_actor(self, actor_id: str, input_data: dict, timeout: int = 120) -> List[dict]:
        """
        Run an Apify actor and wait for results.

        Args:
            actor_id: Actor ID (e.g., "muhammetakkurtt/gmgn-smart-degen-monitor-scraper")
            input_data: Input parameters for the actor
            timeout: Max wait time in seconds

        Returns:
            List of result items
        """
        await self._ensure_session()

        # Start the actor run
        url = f"{self.BASE_URL}/acts/{actor_id}/runs?token={self.api_token}"

        async with self.session.post(url, json=input_data, timeout=30) as resp:
            if resp.status != 201:
                error = await resp.text()
                raise Exception(f"Failed to start actor: {resp.status} - {error}")

            run_data = await resp.json()
            run_id = run_data['data']['id']

        # Poll for completion
        status_url = f"{self.BASE_URL}/actor-runs/{run_id}?token={self.api_token}"

        for _ in range(timeout // 5):  # Check every 5 seconds
            await asyncio.sleep(5)

            async with self.session.get(status_url) as resp:
                if resp.status != 200:
                    continue

                status_data = await resp.json()
                status = status_data['data']['status']

                if status == 'SUCCEEDED':
                    break
                elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                    raise Exception(f"Actor run failed with status: {status}")
        else:
            raise Exception(f"Actor run timed out after {timeout}s")

        # Get results from dataset
        dataset_id = status_data['data']['defaultDatasetId']
        dataset_url = f"{self.BASE_URL}/datasets/{dataset_id}/items?token={self.api_token}"

        async with self.session.get(dataset_url) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def get_smart_degens(self, chain: str = "sol", limit: int = 50) -> List[dict]:
        """
        Get smart money wallets from GMGN Smart Degen Monitor.

        Args:
            chain: Blockchain (sol, eth, bsc, base)
            limit: Max wallets to fetch
        """
        input_data = {
            "chain": chain,
            "limit": limit,
        }

        return await self.run_actor(
            "muhammetakkurtt/gmgn-smart-degen-monitor-scraper",
            input_data
        )

    async def get_wallet_stats(self, wallet_address: str, chain: str = "sol") -> dict:
        """
        Get detailed stats for a specific wallet.

        Args:
            wallet_address: Wallet address to check
            chain: Blockchain
        """
        input_data = {
            "walletAddress": wallet_address,
            "chain": chain,
        }

        results = await self.run_actor(
            "muhammetakkurtt/gmgn-wallet-stat-scraper",
            input_data,
            timeout=60
        )

        return results[0] if results else {}

    async def get_copytrade_wallets(self, chain: str = "sol", limit: int = 50) -> List[dict]:
        """
        Get profitable wallets from GMGN CopyTrade.

        Args:
            chain: Blockchain
            limit: Max wallets
        """
        input_data = {
            "chain": chain,
            "limit": limit,
        }

        return await self.run_actor(
            "muhammetakkurtt/gmgn-copytrade-wallet-scraper",
            input_data
        )


async def discover_smart_money(
    api_token: str,
    chain: str = "sol",
    min_win_rate: float = 40.0,
    min_trades: int = 20,
    max_honeypot_ratio: float = 30.0,
    source: str = "smart_degen",  # 'smart_degen', 'copytrade', or 'both'
    limit: int = 50  # Reduce default to save API calls
) -> List[WalletCandidate]:
    """
    Discover smart money wallets using Apify GMGN scrapers.

    Cost optimization: Use source='smart_degen' (1 API call) instead of 'both' (2 calls)

    Args:
        api_token: Apify API token
        chain: Blockchain to scan
        min_win_rate: Minimum win rate %
        min_trades: Minimum trade count
        max_honeypot_ratio: Maximum honeypot %
        source: Which scraper to use ('smart_degen', 'copytrade', or 'both')
        limit: Max wallets to fetch (lower = fewer credits)

    Returns:
        List of quality wallet candidates
    """
    scraper = ApifyGMGNScraper(api_token)
    candidates = []

    try:
        smart_degens = []
        copytrade = []

        # Only call the scrapers we need (saves API credits)
        if source in ('smart_degen', 'both'):
            print(f"[1/2] Fetching smart degens from GMGN (limit={limit})...")
            smart_degens = await scraper.get_smart_degens(chain=chain, limit=limit)
            print(f"      Found {len(smart_degens)} wallets")

        if source in ('copytrade', 'both'):
            print(f"[{'2' if source == 'both' else '1'}/2] Fetching copytrade wallets...")
            copytrade = await scraper.get_copytrade_wallets(chain=chain, limit=limit)
            print(f"      Found {len(copytrade)} wallets")

        # Combine and dedupe
        all_wallets = {}

        for w in smart_degens:
            addr = w.get('address') or w.get('wallet_address') or w.get('walletAddress')
            if addr:
                all_wallets[addr] = {'source': 'smart_degen', **w}

        for w in copytrade:
            addr = w.get('address') or w.get('wallet_address') or w.get('walletAddress')
            if addr and addr not in all_wallets:
                all_wallets[addr] = {'source': 'copytrade', **w}

        print(f"[3/3] Filtering {len(all_wallets)} unique wallets...")

        for addr, data in all_wallets.items():
            # Extract stats (field names may vary)
            win_rate = float(data.get('winRate') or data.get('win_rate') or 0)
            total_trades = int(data.get('totalTrades') or data.get('total_trades') or data.get('trades') or 0)
            pnl_7d = float(data.get('pnl7d') or data.get('pnl_7d') or 0)
            pnl_30d = float(data.get('pnl30d') or data.get('pnl_30d') or data.get('pnl') or 0)
            honeypot_ratio = float(data.get('honeypotRatio') or data.get('honeypot_ratio') or 0)
            avg_holding = data.get('avgHoldingTime') or data.get('avg_holding_time') or 'unknown'

            candidate = WalletCandidate(
                address=addr,
                pnl_7d=pnl_7d,
                pnl_30d=pnl_30d,
                win_rate=win_rate,
                total_trades=total_trades,
                avg_holding_time=str(avg_holding),
                honeypot_ratio=honeypot_ratio,
                source=data['source']
            )

            # Apply filters
            if candidate.win_rate < min_win_rate:
                continue
            if candidate.total_trades < min_trades:
                continue
            if candidate.honeypot_ratio > max_honeypot_ratio:
                continue
            if candidate.pnl_30d <= 0:
                continue

            candidates.append(candidate)

        # Sort by win rate * PNL
        candidates.sort(key=lambda c: c.win_rate * c.pnl_30d, reverse=True)

        print(f"\n✅ Found {len(candidates)} quality wallets\n")

    finally:
        await scraper.close()

    return candidates


def format_for_v3(candidates: List[WalletCandidate]) -> str:
    """Format candidates as V3 SEED_WALLETS config."""
    lines = ["# Smart Money Wallets (discovered via GMGN/Apify)"]
    lines.append("# Add to v3/config.py SEED_WALLETS\n")

    for c in candidates[:30]:  # Top 30
        tier = c.get_tier()
        lines.append(f"    '{c.address}': {{'tier': '{tier}'}},  # WR:{c.win_rate:.0f}% PNL:${c.pnl_30d:.0f}")

    return "\n".join(lines)


def format_as_commands(candidates: List[WalletCandidate]) -> str:
    """Format candidates as /addwallet commands."""
    lines = ["# Run these in Telegram to add wallets:\n"]

    for i, c in enumerate(candidates[:30], 1):
        tier = c.get_tier()
        name = f"SM_{c.address[:6]}"  # SM = Smart Money
        lines.append(f"/addwallet {c.address} {name}")

    lines.append(f"\n# Then run /syncwebhook to update Helius")
    return "\n".join(lines)


# CLI usage
if __name__ == "__main__":
    import sys
    import os
    import argparse
    from datetime import datetime
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Discover smart money wallets via GMGN/Apify")
    parser.add_argument("--source", choices=["smart_degen", "copytrade", "both"], default="smart_degen",
                        help="Which scraper to use (default: smart_degen = 1 API call)")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max wallets to fetch (default: 50)")
    parser.add_argument("--min-wr", type=float, default=40.0,
                        help="Minimum win rate %% (default: 40)")
    parser.add_argument("--min-trades", type=int, default=20,
                        help="Minimum trades (default: 20)")
    args = parser.parse_args()

    api_token = os.environ.get("APIFY_API_TOKEN")

    if not api_token:
        print("❌ Set APIFY_API_TOKEN environment variable")
        print("   Get your token from: https://console.apify.com/account/integrations")
        sys.exit(1)

    print("=" * 50)
    print("GMGN Smart Money Discovery")
    print("=" * 50)
    print(f"Source: {args.source} | Limit: {args.limit} | Min WR: {args.min_wr}%")
    print(f"Estimated cost: {'~$0.05' if args.source != 'both' else '~$0.10'}")
    print()

    candidates = asyncio.run(discover_smart_money(
        api_token=api_token,
        chain="sol",
        source=args.source,
        limit=args.limit,
        min_win_rate=args.min_wr,
        min_trades=args.min_trades,
        max_honeypot_ratio=30.0
    ))

    if not candidates:
        print("No quality wallets found. Try adjusting filters.")
        sys.exit(0)

    print("Top 10 Smart Money Wallets:")
    print("-" * 80)

    for i, c in enumerate(candidates[:10], 1):
        print(f"{i:2}. {c.address[:8]}...{c.address[-4:]}")
        print(f"    Win Rate: {c.win_rate:.1f}% | PNL 30d: ${c.pnl_30d:,.0f} | Trades: {c.total_trades}")
        print(f"    Tier: {c.get_tier()} | Source: {c.source}")
        print()

    # Save outputs
    with open("smart_money_config.txt", "w") as f:
        f.write(format_for_v3(candidates))

    with open("smart_money_commands.txt", "w") as f:
        f.write(format_as_commands(candidates))

    print("-" * 80)
    print("✅ Saved to:")
    print("   - smart_money_config.txt (for config.py)")
    print("   - smart_money_commands.txt (Telegram commands)")
