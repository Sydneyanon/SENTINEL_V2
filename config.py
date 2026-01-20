"""
Configuration for PROMETHEUS
Autonomous memecoin signal system with tiered scoring and credit optimization
"""
import os

# =============================================================================
# API KEYS & DATABASE
# =============================================================================

# Helius API (for Solana blockchain data + webhooks)
HELIUS_API_KEY = os.getenv('HELIUS_API_KEY')

# Railway PostgreSQL Database (automatically provided by Railway)
DATABASE_URL = os.getenv('DATABASE_URL')

# Telegram Bot (PROMETHEUS)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')  # Should be like: -1001234567890
ENABLE_TELEGRAM = True  # Enable Telegram posting

# =============================================================================
# CONVICTION SCORING THRESHOLDS
# =============================================================================

# Signal thresholds based on graduation status
MIN_CONVICTION_SCORE = 80  # Pre-graduation threshold (40%+ bonding curve)
POST_GRAD_THRESHOLD = 75   # Post-graduation threshold (100% - on Raydium)

# Base score threshold for distribution checks
# Only check distribution if base score >= this value
DISTRIBUTION_CHECK_THRESHOLD = 50

# =============================================================================
# SCORING WEIGHTS (Total: 0-75 points possible)
# =============================================================================

# Smart Wallet Activity (0-40 points)
SMART_WALLET_WEIGHTS = {
    'per_kol': 10,           # 10 points per KOL wallet that bought
    'max_score': 40          # Cap at 4 KOLs (40 points max)
}

# Volume Velocity (0-10 points)
VOLUME_WEIGHTS = {
    'spiking': 10,          # Volume 2x+ expected rate
    'growing': 5            # Volume 1.25x+ expected rate
}

# Price Momentum (0-10 points)
MOMENTUM_WEIGHTS = {
    'very_strong': 10,      # +50% in 5 minutes
    'strong': 5             # +20% in 5 minutes
}

# Distribution Scoring (0-15 points)
# Pre-graduation: Based on unique buyers (FREE)
UNIQUE_BUYER_WEIGHTS = {
    'high': 15,             # 50+ unique buyers
    'medium': 10,           # 30-49 unique buyers
    'low': 5                # 15-29 unique buyers
}

# Post-graduation: Based on real holders (10 credits)
HOLDER_WEIGHTS = {
    'high': 15,             # 100+ holders
    'medium': 10,           # 50-99 holders
    'low': 5                # 20-49 holders
}

# =============================================================================
# SAFETY FILTERS
# =============================================================================

MIN_HOLDERS = 20            # Minimum holders for any signal
MIN_UNIQUE_BUYERS = 15      # Minimum unique buyers for pre-grad signals
MIN_LIQUIDITY = 5000        # Minimum liquidity in USD

# =============================================================================
# SMART WALLET TRACKING
# =============================================================================

# List of elite trader wallets to monitor
SMART_WALLETS = [
    # Add your KOL wallet addresses here
    # Example: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
]

# =============================================================================
# PERFORMANCE TRACKING
# =============================================================================

# Milestone multipliers for performance alerts
MILESTONES = [1.5, 2, 3, 5, 10, 20, 50, 100]

# How long to track token performance (hours)
TRACKING_DURATION = 24

# =============================================================================
# CREDIT OPTIMIZATION SETTINGS
# =============================================================================

# Cleanup settings
MAX_TRACKED_TOKENS = 1000   # Maximum tokens to track in memory
CLEANUP_THRESHOLD = 500     # How many to remove when limit hit

# Buyer tracking duration
BUYER_TRACKING_WINDOW = 15  # Minutes to track unique buyers

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"          # Options: DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = True
LOG_FILE = "sentinel_signals.log"

# =============================================================================
# FEATURE FLAGS
# =============================================================================

ENABLE_NARRATIVES = False   # Narrative detection (disabled for now)
ENABLE_PERFORMANCE_TRACKING = True
ENABLE_MILESTONE_ALERTS = True

# =============================================================================
# CREDIT USAGE ESTIMATES (for monitoring)
# =============================================================================

CREDIT_COSTS = {
    'webhook': 1,
    'holder_check': 10,
    'account_info': 1,
    'metadata': 10
}

# Expected daily usage with optimizations
EXPECTED_DAILY_CREDITS = {
    'webhooks': 20000,      # 20 KOL wallets × ~1000 txs each
    'holder_checks': 3000,  # ~300 post-grad checks × 10 credits
    'other': 2000,          # Misc RPC calls
    'total': 25000          # ~750k/month (well under 1M free tier)
}
