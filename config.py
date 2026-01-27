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
TELEGRAM_BANNER_FILE_ID = os.getenv('TELEGRAM_BANNER_FILE_ID') or 'BAACAgUAAxkBAAEaX7ppd5NErIfPltGUXK9d1izb_B4CWwACJR0AAkpyuFdb23bR8TPhUjgE'  # Animated MP4 for signal announcements
ADMIN_TELEGRAM_USER_ID = int(os.getenv('ADMIN_TELEGRAM_USER_ID', 0)) if os.getenv('ADMIN_TELEGRAM_USER_ID') else None  # Your Telegram user ID for admin commands
ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')  # Optional: Admin channel for command responses (if not set, bot replies in DM)
ENABLE_TELEGRAM = True  # Enable Telegram posting

# Social Intelligence APIs
LUNARCRUSH_API_KEY = os.getenv('LUNARCRUSH_API_KEY')  # Social sentiment aggregator
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')  # Twitter API v2 (free tier)

# Moralis API (for historical data + whale tracking)
MORALIS_API_KEY = os.getenv('MORALIS_API_KEY')  # Free tier: 40K CU/day - Get at https://admin.moralis.io

# Automated Historical Data Collector (Background ML Training Dataset Builder - Weekly)
AUTO_COLLECTOR_ENABLED = os.getenv('AUTO_COLLECTOR_ENABLED', 'true').lower() == 'true'  # Enable/disable automated collection
AUTO_COLLECTOR_INTERVAL_HOURS = int(os.getenv('AUTO_COLLECTOR_INTERVAL_HOURS', '168'))  # Default: 168h = 7 days
AUTO_COLLECTOR_COUNT = int(os.getenv('AUTO_COLLECTOR_COUNT', '50'))  # Collect 50 new tokens per run
AUTO_COLLECTOR_MIN_MCAP = int(os.getenv('AUTO_COLLECTOR_MIN_MCAP', '1000000'))  # Min MCAP: $1M
AUTO_COLLECTOR_MAX_MCAP = int(os.getenv('AUTO_COLLECTOR_MAX_MCAP', '100000000'))  # Max MCAP: $100M

# Automated Daily Token Collector (Runs at Midnight UTC - Collects Yesterday's Winners)
DAILY_COLLECTOR_ENABLED = os.getenv('DAILY_COLLECTOR_ENABLED', 'true').lower() == 'true'  # Enable/disable daily collection
DAILY_COLLECTOR_COUNT = int(os.getenv('DAILY_COLLECTOR_COUNT', '50'))  # Collect 50 tokens per day

# Telegram Monitor (Built-in) - Alternative to solana-token-scraper
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')  # From https://my.telegram.org
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')  # From https://my.telegram.org
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')  # Your phone number (optional, for first-time auth)

# =============================================================================
# CREDIT OPTIMIZATION (CRITICAL!)
# =============================================================================

# STRICT MODE: Only track tokens bought by KOLs (saves massive API credits)
# When True: Only tracks tokens from /webhook/smart-wallet (KOL buys)
# When False: Also processes PumpPortal organic discoveries
STRICT_KOL_ONLY_MODE = False  # ← Disabled: now using organic scanner for discovery

# Disable PumpPortal entirely (saves CPU/memory)
# When True: Skip PumpPortal WebSocket entirely (Helius webhooks only)
# When False: Connect to PumpPortal for FREE unique buyers + KOL detection
DISABLE_PUMPPORTAL = False  # ← RE-ENABLED for unique buyers + KOL trade detection!

# Tiered polling optimization (saves credits while catching runners)
# Pre-grad: always polled (30s). Post-grad: <0 skipped, <20 slow (90s), >=20 normal (30s)
DISABLE_POLLING_BELOW_THRESHOLD = True

# =============================================================================
# CONVICTION SCORING THRESHOLDS
# =============================================================================

# Signal thresholds based on graduation status
# UPDATE 2026-01-27 (ON-CHAIN-FIRST SCORING):
# - Removed KOL smart wallet scoring (was 0-40 pts) - organic scanner replaces KOL-first discovery
# - Added buyer velocity scoring (0-25 pts) and bonding curve speed (0-15 pts)
# - Increased unique buyers (0-20), volume (0-15), reduced narrative (0-10), telegram (0-10)
# - Lowered post-grad threshold from 75 to 65 (no KOL boost available)
MIN_CONVICTION_SCORE = 50  # Pre-grad threshold (unchanged)
POST_GRAD_THRESHOLD = 65   # Lowered from 75 - no KOL boost, pure on-chain scoring

# Base score threshold for distribution checks
# Only check distribution if base score >= this value
DISTRIBUTION_CHECK_THRESHOLD = 50

# =============================================================================
# SCORING WEIGHTS (Total: 0-100 points possible)
# UPDATE 2026-01-27: On-chain-first scoring (KOL scoring disabled)
# =============================================================================

# Combined WEIGHTS dictionary (required by conviction engine)
WEIGHTS = {
    # Smart Wallet Activity - DISABLED (kept at 0 for structure, can re-enable)
    'smart_wallet_elite': 0,        # Elite wallet bought (disabled)
    'smart_wallet_kol': 0,          # Top KOL bought (disabled)

    # Narrative Detection (max 10 points - reduced from 25)
    'narrative_hot': 10,            # Hot/trending narrative
    'narrative_fresh': 5,           # Fresh narrative (< 48h)
    'narrative_multiple': 3,        # Multiple narratives

    # Holder Distribution (max 15 points)
    'holders_high': 15,             # 100+ holders
    'holders_medium': 10,           # 50-99 holders
    'holders_low': 5,               # 30-49 holders

    # Volume Velocity (max 15 points - increased from 10)
    'volume_spike': 15,             # Strong volume spike
    'volume_increasing': 10,        # Steady increase

    # Price Momentum (max 10 points)
    'momentum_strong': 10,          # Strong upward momentum
    'momentum_moderate': 5,         # Moderate momentum
}

# =============================================================================
# DETAILED SCORING WEIGHTS (for specific calculations)
# =============================================================================

# Smart Wallet Activity (DISABLED - kept for structure, can re-enable)
SMART_WALLET_WEIGHTS = {
    'per_kol': 0,            # Disabled (was 10)
    'max_score': 0,          # Disabled (was 40)
    'multi_kol_bonus': 0,    # Disabled (was 15)
    'kol_time_window': 300   # 5 minutes for multi-KOL bonus
}

# =============================================================================
# NEW: BUYER VELOCITY SCORING (0-25 points) - Replaces KOL scoring
# Measures how fast unique buyers are accumulating
# =============================================================================
BUYER_VELOCITY_WEIGHTS = {
    'explosive': 25,         # 100+ buyers in 5 min (viral organic demand)
    'very_fast': 20,         # 50-99 buyers in 5 min
    'fast': 15,              # 25-49 buyers in 5 min
    'moderate': 10,          # 15-24 buyers in 5 min
    'slow': 5,               # 5-14 buyers in 5 min
    'minimal': 0,            # <5 buyers in 5 min
    'window_seconds': 300,   # 5-minute window for velocity calculation
}

# =============================================================================
# NEW: BONDING CURVE SPEED SCORING (0-15 points)
# How fast the bonding curve is filling (organic demand indicator)
# =============================================================================
BONDING_SPEED_WEIGHTS = {
    'rocket': 15,            # >5%/min bonding velocity (explosive demand)
    'fast': 12,              # 2-5%/min bonding velocity
    'steady': 8,             # 1-2%/min bonding velocity
    'slow': 4,               # 0.5-1%/min bonding velocity
    'crawl': 0,              # <0.5%/min (weak demand)
}

# =============================================================================
# NEW: ORGANIC SCANNER CONFIG
# Filters for PumpPortal new tokens to identify organic activity
# =============================================================================
ORGANIC_SCANNER = {
    'enabled': True,
    'min_unique_buyers': 38,       # Lowered from 50 - catch mid-cycle tokens earlier
    'min_buy_ratio': 0.60,         # Lowered from 0.65 - allow slightly more balanced activity
    'max_bundle_ratio': 0.20,      # Max 20% of buys from same block (anti-bundle)
    'watch_window_seconds': 300,   # Watch tokens for 5 min before deciding
    'min_bonding_pct': 25,         # Lowered from 30 - catch earlier momentum
    'max_bonding_pct': 90,         # Raised from 85 - allow near-graduation catches
    'max_tracked_candidates': 100, # Max tokens to watch simultaneously
    'cooldown_seconds': 60,        # Wait 60s between scanner evaluations
    'velocity_bypass_multiplier': 2.0,  # If buyer velocity >2x in 5min, bypass buyer count
}

# =============================================================================
# NEW: GRADUATION SPEED BONUS (Post-grad only)
# Rewards fast graduations (strong demand) and penalizes slow ones
# =============================================================================
GRADUATION_SPEED_BONUS = {
    'fast_grad_minutes': 15,       # Graduated in <15 min = strong demand
    'fast_grad_bonus': 15,         # +15 pts for fast graduation
    'slow_grad_minutes': 30,       # Graduated in >30 min = weak demand
    'slow_grad_penalty': -10,      # -10 pts for slow graduation with low growth
    'slow_grad_min_buyers': 100,   # Below this buyer count = "low growth"
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

# Volume Velocity (0-15 points) - ON-CHAIN: Increased from 10 max
# POST-GRAD: Uses DexScreener volume/mcap ratio
VOLUME_WEIGHTS = {
    'spiking': 15,          # Volume 2x+ expected rate (raised from 10)
    'growing': 10,          # Volume 1.25x+ expected rate (raised from 7)
    'steady': 5             # Volume >1x expected rate (raised from 3)
}

# PRE-GRAD: Uses PumpPortal WebSocket rolling SOL volume (FREE)
# DexScreener has no data for pre-graduation tokens, so we track SOL
# volume from real-time trade events and calculate 5-min velocity ratios
PRE_GRAD_VOLUME_WEIGHTS = {
    'spiking': 15,          # velocity_ratio > 3.0 OR current_window > 50 SOL
    'growing': 10,          # velocity_ratio > 1.5 OR current_window > 20 SOL
    'steady': 5,            # velocity_ratio > 1.0 OR current_window > 5 SOL
    'window_seconds': 300,  # 5-minute rolling windows
}

# Price Momentum (0-10 points) - GROK ENHANCED: More graduated
MOMENTUM_WEIGHTS = {
    'very_strong': 10,      # +50% in 5 minutes
    'strong': 7,            # +30% in 5 minutes (raised from 5)
    'moderate': 3           # +10% in 5 minutes (new tier)
}

# Distribution Scoring (0-20 points) - ON-CHAIN: Increased from 15 max
# Pre-graduation: Based on unique buyers (FREE)
UNIQUE_BUYER_WEIGHTS = {
    'exceptional': 20,  # 100+ unique buyers (very strong organic, raised from 15)
    'high': 15,         # 50-99 unique buyers (raised from 12)
    'medium': 10,       # 25-49 unique buyers (raised from 8)
    'low': 5,           # 10-24 unique buyers
    'minimal': 0        # <10 unique buyers (too early/risky)
}

# Post-graduation: Based on real holders (10 credits)
HOLDER_WEIGHTS = {
    'high': 15,             # 100+ holders
    'medium': 10,           # 50-99 holders
    'low': 5                # 20-49 holders
}

# Twitter and LunarCrush scoring removed (no budget) - see lines 418-419

# Telegram Social Confirmation Scoring (FREE - 0-10 points) - Reduced from 15
# Applies to tracked tokens as social confirmation
TELEGRAM_CONFIRMATION_WEIGHTS = {
    'high_intensity': 10,   # 6+ mentions OR 3+ groups (reduced from 15)
    'medium_intensity': 7,  # 3-5 mentions OR growing buzz (reduced from 10)
    'low_intensity': 3,     # 1-2 mentions (reduced from 5)
    'age_decay': 0.5,       # 50% reduction if call >2 hours old
    'max_social_total': 15  # Cap total social score (reduced from 25)
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
MIN_LIQUIDITY = 8000        # Lowered to catch 40-60% bonding curve tokens (~$8K-$18K liquidity range)

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
        },
        'improvement_bonus': {
            'enabled': True,         # GROK: Reward improving distribution
            'bonus_points': 5,       # +5 pts if top 10 decreases
            'min_polls': 2,          # Need at least 2 polls to compare
            'min_improvement': 5     # Min 5% improvement to qualify
        }
    },
    
    # Pre-grad vs Post-grad differences
    'pre_grad_strict': True,         # Stricter for pre-graduation (riskier)
    'post_grad_forgive_bundles': True  # Forgive early bundles if distribution improved
}

# Anti-Rug Detection: Dev Sell Penalties (GROK ENHANCED)
DEV_SELL_DETECTION = {
    'enabled': True,   # GROK: Enabled for stricter rug detection
    'penalty_points': -20,  # GROK: -20 pts if dev sells >20%
    'dev_sell_threshold': 0.20,  # 20% dev sell threshold
    'early_window_minutes': 30  # Only apply in first 30 minutes
}

# Score Decay: Reduce conviction if metrics drop
SCORE_DECAY = {
    'enabled': True,
    'drop_threshold': 15,
    'block_signal': True
}

# =============================================================================
# TIMING & EXIT RULES (GROK RECOMMENDATIONS)
# =============================================================================

TIMING_RULES = {
    'early_trigger': {
        'enabled': True,              # Enable early trigger at 45% bonding
        'bonding_threshold': 45,      # Raised from 30% - too many rugs at 30% bonding
        'min_unique_buyers': 300,     # Raised from 200 - need more organic demand proof
        'min_conviction_boost': 0     # No extra conviction needed (already at threshold)
    },

    'mcap_cap': {
        'enabled': True,              # Cap signals at high MCAP (avoid tops)
        'max_mcap_pre_grad': 25000,   # Skip if MCAP >$25K on pre-grad call
        'max_mcap_post_grad': 50000,  # Skip if MCAP >$50K on post-grad call
        'log_skipped': True           # Log skipped signals for analysis
    },

    'post_call_monitoring': {
        'enabled': True,              # Monitor price after signal
        'exit_alert_threshold': -15,  # Alert if price drops -15% in 5min
        'monitoring_duration': 300,   # Monitor for 5 minutes (300 seconds)
        'check_interval': 30,         # Check every 30 seconds
        'send_telegram_alert': True   # Send exit alert to Telegram
    }
}

# Signal Quality Logging (for analysis & backtesting)
SIGNAL_LOGGING = {
    'log_why_no_signal': True,        # Log detailed breakdown when threshold missed
    'log_score_components': True,     # Log all scoring components
    'min_gap_to_log': 5,              # Only log if within 5 pts of threshold
    'save_to_database': True,         # Save missed signals to DB for analysis
    'include_recommendations': True   # Include what would push it over threshold
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

# Milestone multipliers for database tracking (all milestones recorded)
# Granular tracking:
# - 1-10x: every 1x
# - 10-100x: every 1x
# - 100-1000x: every 50x
# - 1000x+: every 1000x
MILESTONES = (
    # 2-10x (every 1x) - no 1x, that's just entry price
    [2, 3, 4, 5, 6, 7, 8, 9, 10] +
    # 11-100x (every 1x)
    list(range(11, 101)) +
    # 100-1000x (every 50x)
    [150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000] +
    # 1000x+ (every 1000x)
    [2000, 3000, 4000, 5000, 10000]
)

# Milestones that trigger a Telegram post (subset of MILESTONES)
# All milestones still recorded in database for analytics
MILESTONE_POST_THRESHOLDS = [
    2, 3, 4, 5,                             # LET IT BURN
    10, 20, 30, 40, 50,                     # SCORCHED EARTH
    100, 200, 300, 400, 500,                # HELL FIRE
    1000,                                    # INFERNO
]

# Milestone video banner tiers (set file_ids in env vars when videos are ready)
MILESTONE_BANNER_2X = os.getenv('MILESTONE_BANNER_2X')       # LET IT BURN (2-5x)
MILESTONE_BANNER_10X = os.getenv('MILESTONE_BANNER_10X')     # SCORCHED EARTH (10-50x)
MILESTONE_BANNER_100X = os.getenv('MILESTONE_BANNER_100X')   # HELL FIRE (100-500x)
MILESTONE_BANNER_1000X = os.getenv('MILESTONE_BANNER_1000X') # INFERNO (1000x)

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

# Maximum market cap for signal calls ($20K for testing)
# Tokens above this MCAP won't trigger new signals (already mooned)
MAX_MARKET_CAP_FILTER = int(os.getenv('MAX_MARKET_CAP_FILTER', '20000'))  # $20K default
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

ENABLE_NARRATIVES = True    # GROK: Enabled for early detection (+0-25 pts)
ENABLE_REALTIME_NARRATIVES = True  # RSS + BERTopic for emerging narratives (no API cost)
NARRATIVE_UPDATE_INTERVAL = 900  # Update narratives every 15 minutes (900s)
ENABLE_PERFORMANCE_TRACKING = True
ENABLE_MILESTONE_ALERTS = True
ENABLE_LUNARCRUSH = False   # LunarCrush disabled (no budget for API)
ENABLE_TWITTER = False      # Twitter disabled (no budget for API)
ENABLE_TELEGRAM_SCRAPER = True  # Telegram social confirmation - ENABLED!
ENABLE_BUILTIN_TELEGRAM_MONITOR = True  # Built-in Telegram monitor - ENABLED!

# =============================================================================
# NARRATIVE DETECTION (2026 HOT TRENDS)
# =============================================================================

# Hot narratives to watch for (updated for 2026 meta)
# Format: dict with narrative names as keys
HOT_NARRATIVES = {
    # AI / Agents (HOTTEST in 2026) - capped at 10 max
    'ai_agent': {
        'name': 'AI Agent',
        'keywords': ['ai', 'agent', 'autonomous', 'neural', 'gpt', 'bot', 'llm', 'cognition'],
        'weight': 10,  # Reduced from 25 (narrative max is now 10)
        'active': True
    },

    # DeSci (Growing trend)
    'desci': {
        'name': 'DeSci',
        'keywords': ['desci', 'science', 'research', 'biotech', 'lab', 'molecule', 'data'],
        'weight': 10,  # Reduced from 22
        'active': True
    },

    # RWA (Real World Assets - 2026 focus)
    'rwa': {
        'name': 'RWA',
        'keywords': ['rwa', 'real world', 'asset', 'tokenized', 'treasury', 'bond'],
        'weight': 8,   # Reduced from 20
        'active': True
    },

    # Privacy / ZK (Solana ZK compression)
    'privacy': {
        'name': 'Privacy',
        'keywords': ['privacy', 'zk', 'zero knowledge', 'anonymous', 'private', 'stealth'],
        'weight': 8,   # Reduced from 18
        'active': True
    },

    # DeFi (Always relevant)
    'defi': {
        'name': 'DeFi',
        'keywords': ['defi', 'yield', 'stake', 'farm', 'swap', 'liquidity', 'dex'],
        'weight': 7,   # Reduced from 15
        'active': True
    },

    # Mobile / Saga (Solana mobile push)
    'mobile': {
        'name': 'Mobile',
        'keywords': ['mobile', 'saga', 'phone', 'seeker', 'dapp'],
        'weight': 7,   # Reduced from 15
        'active': True
    },

    # GameFi
    'gamefi': {
        'name': 'GameFi',
        'keywords': ['game', 'play', 'nft', 'metaverse', 'gaming', 'p2e'],
        'weight': 6,   # Reduced from 12
        'active': True
    },

    # Meme (Classic)
    'meme': {
        'name': 'Meme',
        'keywords': ['meme', 'pepe', 'doge', 'shiba', 'wojak', 'frog', 'cat', 'dog'],
        'weight': 5,   # Reduced from 10
        'active': True
    }
}

# Narrative combo bonuses (when multiple narratives match) - Reduced proportionally
NARRATIVE_COMBOS = {
    ('ai_agent', 'desci'): +5,       # AI + DeSci = powerful combo (reduced from 10)
    ('ai_agent', 'defi'): +3,        # AI + DeFi = yield farming agents (reduced from 8)
    ('rwa', 'defi'): +3,             # RWA + DeFi = tokenized yields (reduced from 8)
}

# =============================================================================
# HELIUS ENHANCED FEATURES (Credit-efficient blockchain intelligence)
# =============================================================================

# Helius Pump.fun Program Webhook (organic discovery backbone)
# Monitors all Pump.fun program events for sub-second token creation detection
# Replaces flaky PumpPortal WS for initial discovery, PumpPortal still used for trades
HELIUS_PUMP_WEBHOOK = {
    'enabled': True,
    'program_id': '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P',  # Pump.fun program
    'webhook_type': 'enhanced',                # Enhanced = parsed data (costs credits)
    'transaction_types': ['ANY'],              # Catch all pump.fun txs (filter in handler)
    'endpoint_path': '/webhook/pump-program',  # Our FastAPI endpoint
    'auto_register': True,                     # Register webhook on startup
}

# Dev Sell Detection via Helius (rug prevention)
# Monitor creator wallet for large sells pre-graduation
# This is the #1 rug killer - early dev dumps happen before graduation
HELIUS_DEV_SELL_DETECTION = {
    'enabled': True,
    'sell_threshold_pct': 20,      # Flag if dev sells >20% of supply
    'early_window_minutes': 30,    # Only check in first 30 min
    'penalty_points': -30,         # Heavy penalty for dev selling
    'hard_block_pct': 50,          # Block signal if dev sold >50% supply
    'gate_mid_score': 40,          # Only check if mid_score >= 40 (save credits)
    'credit_cost': 5,              # ~5 credits per getSignaturesForAddress call
}

# Mint/Freeze Authority Check (rug protection)
# Verify if mint authority is revoked (safe) or still active (risky)
# Pump.fun tokens should have mint authority revoked after creation
HELIUS_AUTHORITY_CHECK = {
    'enabled': True,
    'check_mint_authority': True,   # Check if mint authority is revoked
    'check_freeze_authority': True, # Check if freeze authority is revoked
    'mint_active_penalty': -15,     # Penalty if mint authority still active
    'freeze_active_penalty': -20,   # Penalty if freeze authority still active (can freeze your tokens)
    'gate_mid_score': 30,           # Only check if mid_score >= 30
    'credit_cost': 1,               # ~1 credit per getAccountInfo call
}

# Parsed Transaction History (velocity & momentum enrichment)
# Use Helius getSignaturesForAddress for more accurate buyer velocity
# than PumpPortal trade events (Helius parses better, catches same-block bundles)
HELIUS_TX_HISTORY = {
    'enabled': True,
    'gate_mid_score': 50,          # Only fetch if mid_score >= 50 (expensive)
    'max_signatures': 100,         # Fetch last 100 txs
    'credit_cost': 5,              # ~5 credits per call
}

# =============================================================================
# CREDIT USAGE ESTIMATES (for monitoring)
# =============================================================================

CREDIT_COSTS = {
    'webhook': 1,
    'holder_check': 10,
    'account_info': 1,
    'metadata': 10,
    'tx_history': 5,
    'pump_webhook_event': 1,       # Enhanced webhook events
}

# Expected daily usage with optimizations
EXPECTED_DAILY_CREDITS = {
    'webhooks': 20000,      # 20 KOL wallets × ~1000 txs each
    'pump_program': 5000,   # Pump.fun program events (~500-1000/day filtered)
    'holder_checks': 3000,  # ~300 post-grad checks × 10 credits
    'authority_checks': 500,  # ~500 tokens × 1 credit each
    'dev_sell_checks': 1000,  # ~200 tokens × 5 credits each
    'other': 2000,          # Misc RPC calls
    'total': 31500          # ~945k/month (under 1M free tier)
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
