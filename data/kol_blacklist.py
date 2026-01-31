"""
KOL Blacklist - Wallets flagged by Ralph for poor performance
DO NOT re-add these wallets without reviewing their recent performance

Each entry includes:
- Wallet address
- Reason for removal
- Date flagged
- Rug rate at time of removal
"""

# Blacklisted KOL wallets - DO NOT ADD TO TRACKING
KOL_BLACKLIST = {
    '57rXqaQsvgyBKwebP2StfqQeCBjBS4jsrZFJN5aU2V9b': {
        'name': 'Ram',
        'reason': 'Flagged by Ralph - 100% rug rate',
        'date_removed': '2026-01-31',
        'rug_rate': 1.0,
    },
    'sAdNbe1cKNMDqDsa4npB3TfL62T14uAo2MsUQfLvzLT': {
        'name': 'KOL_sAdNbe1c',
        'reason': 'Flagged by Ralph - 92% rug rate',
        'date_removed': '2026-01-31',
        'rug_rate': 0.92,
    },
    '8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs': {
        'name': 'KOL_8oQoMh',
        'reason': 'Flagged by Ralph - 65% rug rate',
        'date_removed': '2026-01-31',
        'rug_rate': 0.65,
    },
}


def is_blacklisted(wallet_address: str) -> dict:
    """
    Check if a wallet is blacklisted.

    Returns:
        None if not blacklisted, or dict with blacklist info if blacklisted
    """
    return KOL_BLACKLIST.get(wallet_address)


def get_blacklist_warning(wallet_address: str) -> str:
    """
    Get a warning message for a blacklisted wallet.

    Returns:
        Warning string if blacklisted, empty string if not
    """
    info = KOL_BLACKLIST.get(wallet_address)
    if info:
        return (
            f"⚠️ BLACKLISTED WALLET: {info.get('name', wallet_address[:8])}\n"
            f"   Reason: {info['reason']}\n"
            f"   Removed: {info['date_removed']}\n"
            f"   Rug Rate: {info['rug_rate']*100:.0f}%"
        )
    return ""
