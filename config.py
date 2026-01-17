"""
Configuration - Centralized settings for Sentinel Signals
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CORE SETTINGS
# ============================================================================

# Database
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# API Keys
HELIUS_API_KEY = os.getenv('HELIUS_API_KEY', '')
HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
DEXSCREENER_API_KEY = os.getenv('DEXSCREENER_API_KEY', '')

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')

# ============================================================================
# CONVICTION SCORING
# ============================================================================

# Minimum conviction score to post signal (0-100)
MIN_CONVICTION_SCORE = int(os.getenv('MIN_CONVICTION_SCORE', 75))

# Score weights
WEIGHTS = {
    'smart_wallet_elite': 15,      # Elite wallet bought (+15 per wallet)
    'smart_wallet_kol': 10,         # Top KOL bought (+10 per wallet)
    'narrative_hot': 20,            # Hot/trending narrative
    'narrative_fresh': 10,          # Fresh narrative (< 48h)
    'narrative_multiple': 5,        # Multiple narratives
    'timing_very_early': 10,        # < 30 min old
    'timing_early': 5,              # 30-60 min old
}

# ============================================================================
# SIGNAL FILTERS
# ============================================================================

# Minimum requirements (basic quality filters)
MIN_LIQUIDITY = int(os.getenv('MIN_LIQUIDITY', 5000))
MIN_HOLDERS = int(os.getenv('MIN_HOLDERS', 30))
MAX_AGE_MINUTES = int(os.getenv('MAX_AGE_MINUTES', 120))  # Only signal tokens < 2h old

# ============================================================================
# NARRATIVE TRACKING
# ============================================================================

# Current hot narratives (update these periodically)
HOT_NARRATIVES = {
    'ai': {
        'keywords': ['ai', 'agent', 'artificial', 'gpt', 'llm', 'neural'],
        'weight': 1.0,
        'active': True
    },
    'meme': {
        'keywords': ['pepe', 'doge', 'shib', 'wojak', 'chad'],
        'weight': 0.8,
        'active': True
    },
    'gaming': {
        'keywords': ['game', 'gaming', 'play', 'metaverse', 'nft'],
        'weight': 0.7,
        'active': True
    },
    'defi': {
        'keywords': ['defi', 'yield', 'farm', 'stake', 'pool'],
        'weight': 0.6,
        'active': True
    },
    'animals': {
        'keywords': ['cat', 'dog', 'frog', 'monkey', 'bear', 'bull'],
        'weight': 0.9,
        'active': True
    }
}

# ============================================================================
# FEATURE FLAGS
# ============================================================================

ENABLE_SMART_WALLETS = os.getenv('ENABLE_SMART_WALLETS', 'true').lower() == 'true'
ENABLE_NARRATIVES = os.getenv('ENABLE_NARRATIVES', 'true').lower() == 'true'
ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', 'true').lower() == 'true'

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
