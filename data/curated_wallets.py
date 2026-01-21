"""
Curated Wallets - High-PnL snipers and high win-rate KOLs
Data sourced from kolscan.io and GMGN.ai leaderboards (Jan 2026)

UPDATED: Now using expanded 50-wallet list from curated_wallets_top50.py
- 10 elite wallets (85%+ win rate, $125k+ PnL)
- 15 top KOLs (70-85% win rate, $40k-$125k PnL)
- 25 solid performers (65-70% win rate, $25k-$45k PnL)
Total: 50 tracked wallets (up from 20)
"""

# Import from the expanded 50-wallet list
from data.curated_wallets_top50 import (
    get_all_tracked_wallets,
    get_wallet_info,
    ELITE_WALLETS,
    TOP_KOL_WALLETS,
    SOLID_WALLETS
)

# Re-export for backwards compatibility
SMART_MONEY_WALLETS = ELITE_WALLETS
KOL_WALLETS = {**TOP_KOL_WALLETS, **SOLID_WALLETS}

def get_elite_wallets():
    """Get only elite tier wallets (85%+ win rate)"""
    return {k: v for k, v in ELITE_WALLETS.items() if v.get('win_rate', 0) >= 0.85}
