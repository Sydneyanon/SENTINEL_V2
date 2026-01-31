"""
Curated Wallets - High-PnL snipers and high win-rate KOLs

DISABLED (2026-01-31): KOL tracking disabled
Analysis shows KOLs have 18% WR vs Organic 29% WR (-11% difference)
Going pure organic until we find consistently good wallets.

To re-enable:
1. Set ENABLE_KOL_TRACKING = True in config.py
2. Run /ralph to analyze wallet performance
3. Add wallets that show >40% win rate
4. Run /syncwebhook to register Helius webhooks
"""

# High-PnL Smart Money Wallets (Snipers, Consistent Winners)
# DISABLED - All wallets cleared until better performers found
SMART_MONEY_WALLETS = {
    # KOL TRACKING DISABLED
}

# High Win-Rate KOL Wallets (Known callers with proven track record)
# DISABLED - All wallets cleared until better performers found
KOL_WALLETS = {
    # KOL TRACKING DISABLED
    # Previous wallets archived in kol_blacklist.py if they had poor performance
    # Run /ralph to analyze wallet performance before re-adding
}


def get_all_tracked_wallets():
    """Get combined list of all tracked wallets"""
    return {**SMART_MONEY_WALLETS, **KOL_WALLETS}


def get_elite_wallets():
    """Get only elite tier wallets (85%+ win rate)"""
    return {k: v for k, v in SMART_MONEY_WALLETS.items() if v.get('win_rate', 0) >= 0.85}


def get_wallet_info(address: str):
    """Get info for a specific wallet"""
    all_wallets = get_all_tracked_wallets()
    return all_wallets.get(address)
