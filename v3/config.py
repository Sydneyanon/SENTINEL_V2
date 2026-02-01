"""
SENTINEL V3 - Data-Driven Configuration
Based on Ralph analysis of 323 signals over 30 days (28% baseline WR).
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
APIFY_API_TOKEN = os.getenv('APIFY_API_TOKEN')  # For GMGN smart money discovery

# =============================================================================
# SIGNAL THRESHOLDS (Data-driven from Ralph analysis)
# =============================================================================
# Score: 27% WR at all levels 30-50, doesn't predict wins
MIN_SCORE = 30

# Liquidity: Wins avg $10K vs Rugs avg $20K. Best ≤$10K = 29% WR
MIN_LIQUIDITY = 8000

# MCAP: Increased to $100K to see more smart money trades
MAX_MCAP = 100000

# Holders: Disabled - DexScreener/PumpPortal don't provide holder count
MIN_HOLDERS = 0

# Buy/Sell Ratio: Wins avg 1.1 vs Rugs avg 0.5. Best ≥2.0 = 29% WR
MIN_BUY_SELL_RATIO = 2.0

# =============================================================================
# TIME FILTERS (Optional - based on hourly analysis)
# =============================================================================
# Best hours (UTC): 08:00 (60%), 16:00 (60%), 23:00 (50%)
# Worst hours (UTC): 01:00 (14%), 11:00 (14%), 14:00 (11%)
# Set to None to disable time filtering
BEST_HOURS_UTC = [8, 16, 23]  # 60%+ win rate
AVOID_HOURS_UTC = [1, 11, 14]  # <15% win rate

# =============================================================================
# SCORING WEIGHTS (100 points max)
# =============================================================================
# Note: Ralph showed KOL (25%) vs Organic (29%) similar performance.
# Wallet tier matters less than entry timing (MCAP, liquidity).
SCORING = {
    # Wallet tier (0-30 points) - reduced weight since KOL ~= Organic
    'wallet': {
        'elite': 30,        # 70%+ win rate wallets
        'top_kol': 25,      # 50%+ win rate KOLs
        'verified': 15,     # 40%+ win rate
        'new': 10,          # Unproven but tracked
    },

    # Volume (0-20 points)
    'volume': {
        'high': 20,         # Volume > 2x liquidity
        'medium': 12,       # Volume > 1x liquidity
        'low': 5,           # Volume > 0.5x liquidity
    },

    # Momentum (0-25 points) - increased weight
    'momentum': {
        'strong': 25,       # +30% in last hour
        'moderate': 15,     # +15% in last hour
        'weak': 5,          # +5% in last hour
    },

    # Buy/Sell Ratio (0-25 points) - NEW, strong predictor
    'buy_sell_ratio': {
        'strong': 25,       # Ratio >= 2.0
        'good': 15,         # Ratio >= 1.5
        'weak': 5,          # Ratio >= 1.0
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
# Starting wallets - system auto-adjusts tiers based on performance
# NOTE: Remove underperformers identified by Ralph:
#   - Ram (100% rug rate)
#   - KOL_sAdNbe1c (92% rug rate)
#   - KOL_8oQoMh (65% rug rate)
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
# SMART MONEY DISCOVERY (via GMGN/Apify)
# =============================================================================
DISCOVERY_INTERVAL_HOURS = 168  # Run weekly (7 days) to save Apify credits

# Hard filters - must pass all
# NOTE: Loosened for initial testing - tighten after first week of data
DISCOVERY_MIN_WIN_RATE = 45.0   # 45%+ WR (tighten to 55% later)
DISCOVERY_MIN_TRADES = 25       # 25+ trades (tighten to 35 later)
DISCOVERY_MAX_HONEYPOT = 25.0   # 25% max (tighten to 20% later)
DISCOVERY_MIN_PNL_30D = 2000    # $2k min (tighten to $5k later)

# Tier thresholds (for classification)
DISCOVERY_ELITE_WIN_RATE = 65.0      # Elite tier: 65%+ WR
DISCOVERY_ELITE_MIN_PNL = 15000      # Elite tier: $15k+ PNL
DISCOVERY_SMART_MONEY_WIN_RATE = 55.0  # Smart money: 55%+ WR
DISCOVERY_SMART_MONEY_MIN_PNL = 7500   # Smart money: $7.5k+ PNL

# Limits
DISCOVERY_LIMIT = 100           # Fetch more for initial testing
DISCOVERY_AUTO_TRACK_TOP = 15   # Track more initially to gather data

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
