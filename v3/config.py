"""
SENTINEL V3 - Clean Configuration
Only what's proven to work. No experimental features.
"""
import os

# =============================================================================
# API KEYS (from environment)
# =============================================================================
HELIUS_API_KEY = os.getenv('HELIUS_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
ADMIN_USER_ID = int(os.getenv('ADMIN_TELEGRAM_USER_ID', 0)) or None
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Your Railway URL (e.g., https://xxx.railway.app)

# =============================================================================
# SIGNAL THRESHOLDS
# =============================================================================
MIN_SCORE = 60              # Minimum conviction score to post signal
MIN_LIQUIDITY = 20000       # Minimum liquidity ($20K)
MIN_HOLDERS = 20            # Minimum holders
MAX_MCAP = 50000            # Maximum MCAP for signal ($50K)

# =============================================================================
# SCORING WEIGHTS (100 points max)
# =============================================================================
# Simple 4-factor scoring that works:
SCORING = {
    # Wallet tier (0-40 points) - the main signal
    'wallet': {
        'elite': 40,        # 90%+ win rate wallets
        'top_kol': 30,      # 70%+ win rate KOLs
        'verified': 20,     # 50%+ win rate
        'new': 10,          # Unproven but tracked
    },

    # Volume (0-20 points)
    'volume': {
        'high': 20,         # Volume > 2x liquidity
        'medium': 12,       # Volume > 1x liquidity
        'low': 5,           # Volume > 0.5x liquidity
    },

    # Momentum (0-20 points)
    'momentum': {
        'strong': 20,       # +30% in last hour
        'moderate': 12,     # +15% in last hour
        'weak': 5,          # +5% in last hour
    },

    # Holders (0-20 points)
    'holders': {
        'high': 20,         # 100+ holders
        'medium': 12,       # 50+ holders
        'low': 5,           # 20+ holders
    },
}

# =============================================================================
# TRACKING
# =============================================================================
TRACKING_DURATION_HOURS = 24    # How long to track each token
POLL_INTERVAL_SECONDS = 30      # How often to check prices

# Milestones to post
MILESTONES = [2, 3, 5, 10, 20, 50, 100]

# =============================================================================
# TELEGRAM BANNERS (file_ids - set in Railway env vars)
# =============================================================================
BANNER_SIGNAL = os.getenv('TELEGRAM_BANNER_FILE_ID')
BANNER_2X = os.getenv('MILESTONE_BANNER_2X')
BANNER_10X = os.getenv('MILESTONE_BANNER_10X')
BANNER_100X = os.getenv('MILESTONE_BANNER_100X')

# =============================================================================
# WALLET TIERS (loaded from database, seeded here)
# =============================================================================
# These are starting wallets - the system will auto-adjust tiers based on performance
SEED_WALLETS = {
    # Named KOLs with known track records
    'FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke': {'name': 'Radiance', 'tier': 'top_kol'},
    'G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC': {'name': 'Clukz', 'tier': 'top_kol'},
    'Be24Gbf5KisDk1LcWWZsBn8dvB816By7YzYF5zWZnRR6': {'name': 'CHAIRMAN', 'tier': 'top_kol'},
    'GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65': {'name': 'Latuche', 'tier': 'top_kol'},
    'DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt': {'name': 'The Doc', 'tier': 'top_kol'},

    # Anonymous wallets (will be named by address prefix)
    '3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV': {'tier': 'verified'},
    'Bi4rd5FH5bYEN8scZ7wevxNZyNmKHdaBcvewdPFxYdLt': {'tier': 'verified'},
    'F5jWYuiDLTiaLYa54D88YbpXgEsA6NKHzWy4SN4bMYjt': {'tier': 'verified'},
    '4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9': {'tier': 'verified'},
    'CA4keXLtGJWBcsWivjtMFBghQ8pFsGRWFxLrRCtirzu5': {'tier': 'verified'},
    'JAmx4Wsh7cWXRzQuVt3TCKAyDfRm9HA7ztJa4f7RM8h9': {'tier': 'verified'},
    '2net6etAtTe3Rbq2gKECmQwnzcKVXRaLcHy2Zy1iCiWz': {'tier': 'verified'},
    'gangJEP5geDHjPVRhDS5dTF5e6GtRvtNogMEEVs91RV': {'tier': 'verified'},
    '5sNnKuWKUtZkdC1eFNyqz3XHpNoCRQ1D1DfHcNHMV7gn': {'tier': 'verified'},
    '39q2g5tTQn9n7KnuapzwS2smSx3NGYqBoea11tBjsGEt': {'tier': 'verified'},
}

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
