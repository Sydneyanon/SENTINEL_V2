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
TELEGRAM_BANNER_FILE_ID = os.getenv('TELEGRAM_BANNER_FILE_ID')  # Animated GIF/MP4 for signal announcements
ADMIN_TELEGRAM_USER_ID = int(os.getenv('ADMIN_TELEGRAM_USER_ID', 0)) if os.getenv('ADMIN_TELEGRAM_USER_ID') else None  # Your Telegram user ID for admin commands
ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')  # Optional: Admin channel for command responses (if not set, bot replies in DM)
ENABLE_TELEGRAM = True  # Enable Telegram posting

# Social Intelligence APIs
LUNARCRUSH_API_KEY = os.getenv('LUNARCRUSH_API_KEY')  # Social sentiment aggregator
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')  # Twitter API v2 (free tier)

# Telegram Monitor (Built-in) - Alternative to solana-token-scraper
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')  # From https://my.telegram.org
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')  # From https://my.telegram.org
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')  # Your phone number (optional, for first-time auth)

# =============================================================================
# CREDIT OPTIMIZATION (CRITICAL!)
# =============================================================================

# STRICT MODE: Only track tokens bought by KOLs (saves massive API credits)
# When True: Only tracks tokens from /webhook/smart-wallet (KOL buys)
# When False: Also processes PumpPortal graduations (burns credits fast!)
STRICT_KOL_ONLY_MODE = True  # ← SET TO TRUE TO SAVE CREDITS!

# Disable PumpPortal entirely (saves CPU/memory)
# When True: Skip PumpPortal WebSocket entirely (Helius webhooks only)
# When False: Connect to PumpPortal for FREE unique buyers + KOL detection
DISABLE_PUMPPORTAL = False  # ← RE-ENABLED for unique buyers + KOL trade detection!

# Disable polling for tokens below threshold (saves credits)
DISABLE_POLLING_BELOW_THRESHOLD = True  # Only poll tokens >= 50 conviction

# =============================================================================
# CONVICTION SCORING THRESHOLDS
# =============================================================================

# Signal thresholds based on graduation status
MIN_CONVICTION_SCORE = 70  # Pre-graduation threshold (40%+ bonding curve) - RESTORED: Was 67% WR at this level
POST_GRAD_THRESHOLD = 70   # Post-graduation threshold (100% - on Raydium) - RESTORED: Quality over quantity

# Base score threshold for distribution checks
# Only check distribution if base score >= this value
DISTRIBUTION_CHECK_THRESHOLD = 50

# =============================================================================
# SCORING WEIGHTS (Total: 0-100 points possible)
# =============================================================================

# Combined WEIGHTS dictionary (required by conviction engine)
WEIGHTS = {
    # Smart Wallet Activity (max 40 points)
    'smart_wallet_elite': 15,      # Elite wallet bought (+15 per wallet)
    'smart_wallet_kol': 10,         # Top KOL bought (+10 per wallet)
    
    # Narrative Detection (max 25 points)
    'narrative_hot': 20,            # Hot/trending narrative
    'narrative_fresh': 10,          # Fresh narrative (< 48h)
    'narrative_multiple': 5,        # Multiple narratives
    
    # Holder Distribution (max 15 points)
    'holders_high': 15,             # 100+ holders
    'holders_medium': 10,           # 50-99 holders  
    'holders_low': 5,               # 30-49 holders
    
    # Volume Velocity (max 10 points)
    'volume_spike': 10,             # Strong volume spike
    'volume_increasing': 5,         # Steady increase
    
    # Price Momentum (max 10 points)
    'momentum_strong': 10,          # Strong upward momentum
    'momentum_moderate': 5,         # Moderate momentum
}

# =============================================================================
# DETAILED SCORING WEIGHTS (for specific calculations)
# =============================================================================

# Smart Wallet Activity (0-40 points)
SMART_WALLET_WEIGHTS = {
    'per_kol': 10,           # 10 points per KOL wallet that bought
    'max_score': 40,         # Cap at 4 KOLs (40 points max)
    'multi_kol_bonus': 15,   # Extra bonus if 2+ KOLs buy within 5 min
    'kol_time_window': 300   # 5 minutes for multi-KOL bonus
}

# Phase 3: Smart Polling Intervals (adaptive based on stage)
POLLING_INTERVALS = {
    'initial': 5,            # First 2 minutes: every 5 seconds
    'initial_duration': 120, # 2 minutes at fast polling
    'normal': 15,            # Normal: every 15 seconds
    'slow': 30,              # If stuck: every 30 seconds
    'stuck_threshold': 3,    # Consider "stuck" after 3 polls with no progress
    'max_age': 1800          # Stop polling after 30 minutes
}

# Credit-Saving Gating: Only fetch holders if these conditions met
HOLDER_FETCH_GATES = {
    'min_unique_buyers': 50,     # Need at least 50 unique buyers
    'min_base_score': 60,        # Need at least 60 pts from other factors
    'always_fetch_post_grad': True  # Always check holders post-graduation
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
# LOWERED: Catch early KOL plays before they get crowded
UNIQUE_BUYER_WEIGHTS = {
    'exceptional': 15,  # 50+ unique buyers (strong organic interest)
    'high': 12,         # 30-49 unique buyers
    'medium': 8,        # 15-29 unique buyers
    'low': 5,           # 5-14 unique buyers (early stage)
    'minimal': 0        # <5 unique buyers (too early/risky)
}

# Post-graduation: Based on real holders (10 credits)
HOLDER_WEIGHTS = {
    'high': 15,             # 100+ holders
    'medium': 10,           # 50-99 holders
    'low': 5                # 20-49 holders
}

# Social Sentiment Scoring (LunarCrush - 0-20 points)
LUNARCRUSH_WEIGHTS = {
    'trending_top20': 10,   # Trending in top 20
    'trending_top50': 7,    # Trending in top 50
    'trending_top100': 3,   # Trending in top 100
    'sentiment_high': 5,    # Sentiment >= 4.0
    'sentiment_medium': 3,  # Sentiment >= 3.5
    'volume_spike': 5,      # Social volume +100%
    'volume_growth': 3      # Social volume +50%
}

# Twitter Buzz Scoring (Free Tier - 0-15 points)
TWITTER_WEIGHTS = {
    'high_buzz': 15,        # 5+ mentions, 10+ avg engagement
    'medium_buzz': 10,      # 3+ mentions
    'low_buzz': 5,          # 1+ mentions
    'viral_tweet': 12       # Single tweet with 100+ likes (minimum)
}

# Telegram Social Confirmation Scoring (FREE - 0-15 points)
# Only applies to tokens already tracked by KOLs (social confirmation)
TELEGRAM_CONFIRMATION_WEIGHTS = {
    'high_intensity': 15,   # 6+ mentions OR 3+ groups
    'medium_intensity': 10, # 3-5 mentions OR growing buzz
    'low_intensity': 5,     # 1-2 mentions
    'age_decay': 0.5,       # 50% reduction if call >2 hours old
    'max_social_total': 25  # Cap total social score (Twitter + Telegram)
}

# Telegram Call-Triggered Tracking (Optional)
TELEGRAM_CALL_TRIGGER_ENABLED = False  # Start tracking based on calls alone (disabled by default)
TELEGRAM_CALL_TRIGGER_SETTINGS = {
    'min_groups': 2,              # Minimum groups mentioning token
    'time_window_seconds': 300,   # Mentions must occur within 5 min
    'base_score': 15,             # Initial score for call-triggered tokens (lower than KOL)
    'require_kol_confirmation': True,  # Auto-kill if no KOL buy within X min
    'kol_confirmation_window': 300,    # 5 minutes to get KOL confirmation
    'signal_threshold': 85        # Higher threshold for call-only triggers (vs 80 for KOL)
}

# Phase 1 Refinements: Early Kill Switch
EARLY_KILL_SWITCH = {
    'enabled': True,
    'min_new_buyers': 5,        # Minimum new buyers in check window
    'check_window_seconds': 120, # Check every 2 minutes
    'trigger_at_bonding_pct': 50 # Only apply at 50%+ bonding curve
}

# =============================================================================
# SAFETY FILTERS & RUG DETECTION
# =============================================================================

MIN_HOLDERS = 20            # Minimum holders for any signal
MIN_UNIQUE_BUYERS = 15      # Minimum unique buyers for pre-grad signals
MIN_LIQUIDITY = 5000        # Minimum liquidity in USD

# =============================================================================
# RUG DETECTION SETTINGS (Grok's Anti-Scam System)
# =============================================================================

RUG_DETECTION = {
    'enabled': True,
    
    # Bundle Detection (coordinated buys in same block)
    'bundles': {
        'detect': True,
        'penalties': {
            'minor': -10,      # 4-10 same-block txs
            'medium': -25,     # 11-20 same-block txs
            'massive': -40     # 21+ same-block txs (likely sniper bundle)
        },
        'overrides': {
            'unique_buyers_high': 100,    # If >100 unique buyers, cut penalty in half
            'unique_buyers_medium': 50    # If >50 buyers, reduce penalty by 10
        }
    },
    
    # Holder Concentration (top holder control)
    'holder_concentration': {
        'check': True,
        'credit_cost': 10,           # Helius credits per check
        'thresholds': {
            'check_pre_grad': 65,    # Only check if base score >= 65 (pre-grad)
            'check_post_grad': 0,    # ALWAYS check graduated tokens (mandatory rug protection)
        },
        'penalties': {
            'extreme': -999,         # Top 10 hold >80% = HARD DROP
            'severe': -35,           # Top 10 hold >70%
            'high': -20,             # Top 10 hold >50%
            'medium': -10            # Top 10 hold >40%
        },
        'concentration_limits': {
            'hard_drop': 80,         # Auto-kill if top 10 > 80%
            'severe': 70,
            'high': 50,
            'medium': 40
        },
        'kol_bonus': {
            'enabled': True,
            'per_kol': 10,           # +10 pts per KOL in top 10
            'penalty_reduction': 5    # Reduce penalty by 5 per KOL
        }
    },
    
    # Pre-grad vs Post-grad differences
    'pre_grad_strict': True,         # Stricter for pre-graduation (riskier)
    'post_grad_forgive_bundles': True  # Forgive early bundles if distribution improved
}

# Anti-Rug Detection: Dev Sell Penalties (Future enhancement)
DEV_SELL_DETECTION = {
    'enabled': False,  # Not implemented yet
    'penalty_points': -25,
    'dev_sell_threshold': 0.20,
    'early_window_minutes': 30
}

# Score Decay: Reduce conviction if metrics drop
SCORE_DECAY = {
    'enabled': True,
    'drop_threshold': 15,
    'block_signal': True
}

# =============================================================================
# SMART WALLET TRACKING (ELITE KOLs)
# =============================================================================

# Option 1: Simple list (just addresses)
# SMART_WALLETS = [
#     "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
#     "8BnEgHoWFysVcuFFX7QztDmzuH8r5ZFvyP3sYwn1XTh6",
# ]

# Option 2: Detailed tracking (RECOMMENDED) - addresses + metadata
SMART_WALLETS = [
    # Top 10 KOL wallets from gmgn.ai
    # Bot will auto-discover: names, win rates, tiers, specialties on startup!
    
    "CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o",
    "5zCkbcD74hFPeBHwYdwJLJAoLVgHX45AFeR7RzC8vFiD",
    "5TcyQLh8ojBf81DKeRC4vocTbNKJpJCsR9Kei16kLqDM",
    "2wHHnAmdhFaAAsayWAeqKe3snK3KkbRQkRgLwTtz7iCi",
    "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm",
    "4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk",
    "DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt",
    "DP7G43VPwR5Ab5rcjrCnvJ8UgvRXRHTWscMjRD1eSdGC",
    "EvGpkcSBfhp5K9SNP48wVtfNXdKYRBiK3kvMkB66kU3Q",
    "7uyGRgoCRKfynPbB35kWQwEGz9pmRvUyNFunV939mXpN",
    
    # Add 10-20 more for optimal coverage!
]

# If using simple list format, convert to detailed internally
# This happens automatically in smart_wallet_tracker.py

# Wallet tiers for scoring
WALLET_TIERS = {
    'elite': {
        'boost_multiplier': 1.2,    # 20% boost to conviction
        'min_win_rate': 0.75
    },
    'top_kol': {
        'boost_multiplier': 1.1,    # 10% boost
        'min_win_rate': 0.65
    },
    'verified': {
        'boost_multiplier': 1.0,    # Standard
        'min_win_rate': 0.55
    }
}

# Wallet scoring thresholds for auto-discovery (future feature)
WALLET_SCORE_THRESHOLDS = {
    'elite': 80,        # Auto-add if score >=80
    'demote': 60,       # Auto-remove if score drops <60
    'min_trades': 10,   # Minimum trades to be eligible
}

# =============================================================================
# PERFORMANCE TRACKING & ROI ANALYSIS
# =============================================================================

# Milestone multipliers for performance alerts
# Granular tracking:
# - 1-10x: every 1x
# - 10-100x: every 1x
# - 100-1000x: every 50x
# - 1000x+: every 1000x
MILESTONES = (
    # 1-10x (every 1x)
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] +
    # 11-100x (every 1x)
    list(range(11, 101)) +
    # 100-1000x (every 50x)
    [150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000] +
    # 1000x+ (every 1000x)
    [2000, 3000, 4000, 5000, 10000]
)

# How long to track token performance (hours)
TRACKING_DURATION = 24

# ROI tracking intervals for refinement (log at these intervals)
ROI_TRACKING_INTERVALS = [
    5,      # 5 minutes
    15,     # 15 minutes
    60,     # 1 hour
    360,    # 6 hours
    1440    # 24 hours
]

# Performance metrics to track
TRACK_METRICS = {
    'price_change': True,
    'holder_growth': True,
    'volume_24h': True,
    'liquidity_change': True,
    'unique_buyer_growth': True
}

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
LOG_FILE = "prometheus.log"

# =============================================================================
# FEATURE FLAGS
# =============================================================================

ENABLE_NARRATIVES = False   # Narrative detection (disabled - narratives are static)
ENABLE_PERFORMANCE_TRACKING = True
ENABLE_MILESTONE_ALERTS = True
ENABLE_LUNARCRUSH = False   # LunarCrush disabled (use Twitter only)
ENABLE_TWITTER = True       # Twitter buzz detection (free tier - ENABLED)
ENABLE_TELEGRAM_SCRAPER = True  # Telegram social confirmation - ENABLED!
ENABLE_BUILTIN_TELEGRAM_MONITOR = True  # Built-in Telegram monitor - ENABLED!

# =============================================================================
# NARRATIVE DETECTION (2026 HOT TRENDS)
# =============================================================================

# Hot narratives to watch for (updated for 2026 meta)
# Format: dict with narrative names as keys
HOT_NARRATIVES = {
    # AI / Agents (HOTTEST in 2026)
    'ai_agent': {
        'name': 'AI Agent',
        'keywords': ['ai', 'agent', 'autonomous', 'neural', 'gpt', 'bot', 'llm', 'cognition'],
        'weight': 25,  # Maximum weight
        'active': True
    },
    
    # DeSci (Growing trend)
    'desci': {
        'name': 'DeSci',
        'keywords': ['desci', 'science', 'research', 'biotech', 'lab', 'molecule', 'data'],
        'weight': 22,
        'active': True
    },
    
    # RWA (Real World Assets - 2026 focus)
    'rwa': {
        'name': 'RWA',
        'keywords': ['rwa', 'real world', 'asset', 'tokenized', 'treasury', 'bond'],
        'weight': 20,
        'active': True
    },
    
    # Privacy / ZK (Solana ZK compression)
    'privacy': {
        'name': 'Privacy',
        'keywords': ['privacy', 'zk', 'zero knowledge', 'anonymous', 'private', 'stealth'],
        'weight': 18,
        'active': True
    },
    
    # DeFi (Always relevant)
    'defi': {
        'name': 'DeFi',
        'keywords': ['defi', 'yield', 'stake', 'farm', 'swap', 'liquidity', 'dex'],
        'weight': 15,
        'active': True
    },
    
    # Mobile / Saga (Solana mobile push)
    'mobile': {
        'name': 'Mobile',
        'keywords': ['mobile', 'saga', 'phone', 'seeker', 'dapp'],
        'weight': 15,
        'active': True
    },
    
    # GameFi
    'gamefi': {
        'name': 'GameFi',
        'keywords': ['game', 'play', 'nft', 'metaverse', 'gaming', 'p2e'],
        'weight': 12,
        'active': True
    },
    
    # Meme (Classic)
    'meme': {
        'name': 'Meme',
        'keywords': ['meme', 'pepe', 'doge', 'shiba', 'wojak', 'frog', 'cat', 'dog'],
        'weight': 10,
        'active': True
    }
}

# Narrative combo bonuses (when multiple narratives match)
NARRATIVE_COMBOS = {
    ('ai_agent', 'desci'): +10,      # AI + DeSci = powerful combo
    ('ai_agent', 'defi'): +8,        # AI + DeFi = yield farming agents
    ('rwa', 'defi'): +8,             # RWA + DeFi = tokenized yields
}

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

# =============================================================================
# TELEGRAM GROUPS TO MONITOR (Built-in Monitor)
# =============================================================================

# Run: python telegram_monitor.py to auto-generate this list from your groups
# Then edit to keep only groups you want to monitor

TELEGRAM_GROUPS = {
    -1001758611100: 'mad_apes',  # Mad Apes (gambles)
    -1001419575394: 'alpha_group_22',  # Alpha Group 22
    -1002064849541: 'alpha_group_23',  # Alpha Group 23 (NEW)
    -1002380594298: 'alpha_group_24',  # Alpha Group 24 (NEW)
    -1001490374084: 'alpha_group_1',  # Alpha Group 1
    -1001860996162: 'alpha_group_2',  # Alpha Group 2
    -1002139128702: 'alpha_group_3',  # Alpha Group 3
    -1002432801514: 'alpha_group_4',  # Alpha Group 4
    -1001324535284: 'alpha_group_5',  # Alpha Group 5
    -1001508785153: 'alpha_group_6',  # Alpha Group 6
    -1001523240618: 'alpha_group_7',  # Alpha Group 7
    -1001879023403: 'alpha_group_8',  # Alpha Group 8
    -1002152633628: 'alpha_group_9',  # Alpha Group 9
    -1002697838664: 'alpha_group_10',  # Alpha Group 10
    -1002552682611: 'alpha_group_11',  # Alpha Group 11
    -1002824908745: 'alpha_group_12',  # Alpha Group 12
    -1002661048397: 'alpha_group_13',  # Alpha Group 13
    -1001812989440: 'alpha_group_14',  # Alpha Group 14
    -1002402275750: 'alpha_group_15',  # Alpha Group 15
    -1001727197121: 'alpha_group_16',  # Alpha Group 16
    -1001885421444: 'alpha_group_17',  # Alpha Group 17
    -1001267600694: 'alpha_group_18',  # Alpha Group 18
    -1001572364341: 'alpha_group_19',  # Alpha Group 19
    -1002654543409: 'alpha_group_20',  # Alpha Group 20
    -1001510769567: 'alpha_group_21',  # Alpha Group 21
}

# Alternative: If using external solana-token-scraper (webhook mode)
# You don't need to configure TELEGRAM_GROUPS
# Just set ENABLE_BUILTIN_TELEGRAM_MONITOR = False
