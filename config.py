"""
Sentinel Signals v2 - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# TELEGRAM
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', 'true').lower() == 'true'

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be set")

# ============================================================================
# HELIUS
# ============================================================================

HELIUS_API_KEY = os.getenv('HELIUS_API_KEY')
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY must be set")

# ============================================================================
# CONVICTION SCORING
# ============================================================================

# Minimum conviction score to post signal (0-100)
MIN_CONVICTION_SCORE = int(os.getenv('MIN_CONVICTION_SCORE', 75))

# Score weights (updated with holder + volume velocity)
WEIGHTS = {
    # Smart Wallet Activity (max 40 points)
    'smart_wallet_elite': 15,      # Elite wallet bought (+15 per wallet)
    'smart_wallet_kol': 10,         # Top KOL bought (+10 per wallet)
    
    # Narrative Detection (max 25 points)
    'narrative_hot': 20,            # Hot/trending narrative
    'narrative_fresh': 10,          # Fresh narrative (< 48h)
    'narrative_multiple': 5,        # Multiple narratives
    
    # Holder Distribution (max 15 points) 🆕
    'holders_high': 15,             # 100+ holders
    'holders_medium': 10,           # 50-99 holders  
    'holders_low': 5,               # 30-49 holders
    
    # Volume Velocity (max 10 points) 🆕
    'volume_spiking': 10,           # Volume doubled in 5min
    'volume_growing': 5,            # Volume up 25%+ in 5min
    
    # Price Momentum (max 10 points)
    'momentum_very_strong': 10,     # +50% in 5min
    'momentum_strong': 5,           # +20% in 5min
}

# ============================================================================
# SIGNAL FILTERS
# ============================================================================

# Minimum requirements (basic quality filters)
MIN_LIQUIDITY = int(os.getenv('MIN_LIQUIDITY', 5000))
MIN_HOLDERS = int(os.getenv('MIN_HOLDERS', 30))  # Hard minimum
MAX_AGE_MINUTES = int(os.getenv('MAX_AGE_MINUTES', 120))  # Only signal tokens < 2h old

# ============================================================================
# NARRATIVE TRACKING
# ============================================================================

# Current hot narratives (update these periodically)
HOT_NARRATIVES = {
    'ai': {
        'keywords': ['ai', 'agent', 'artificial', 'gpt', 'llm', 'neural', 'bot', 'assistant'],
        'weight': 1.0,
        'active': True
    },
    'meme': {
        'keywords': ['pepe', 'doge', 'shib', 'wojak', 'chad', 'frog', 'cat', 'dog'],
        'weight': 0.8,
        'active': True
    },
    'gaming': {
        'keywords': ['game', 'gaming', 'play', 'metaverse', 'nft', 'pixel'],
        'weight': 0.7,
        'active': True
    },
    'defi': {
        'keywords': ['defi', 'yield', 'farm', 'stake', 'pool', 'swap'],
        'weight': 0.6,
        'active': True
    },
    'animals': {
        'keywords': ['cat', 'dog', 'frog', 'monkey', 'ape', 'penguin', 'bear', 'bull'],
        'weight': 0.5,
        'active': True
    }
}

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================

# Milestones to track (e.g., 1.5x, 2x, 3x, 5x, 10x)
MILESTONES = [1.5, 2, 3, 5, 10, 20, 50, 100]

# Daily report time (UTC)
DAILY_REPORT_HOUR = 0  # Midnight UTC
