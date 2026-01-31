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

# KOL TRACKING - DISABLED (2026-01-31)
# Analysis shows KOLs have 18% WR vs Organic 29% WR (-11% difference)
# Going pure organic until we can find consistently good wallets
ENABLE_KOL_TRACKING = False  # ← DISABLED: KOLs underperforming organic by 11%

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
# - Added buyer velocity scoring (0-18 pts) and bonding curve speed (0-15 pts)
# - Unique buyers (0-10), volume (0-12), narrative (0-7 RSS+BERTopic), telegram (0-5)
# - Lowered post-grad threshold from 75 to 65 (no KOL boost available)
# UPDATE 2026-01-31 (RALPH OPTIMIZATION):
# - Lowered MIN_CONVICTION_SCORE from 50 to 30 (same WR, more signals)
# - Data shows threshold doesn't significantly impact WR (26% at all levels)
MIN_CONVICTION_SCORE = 30  # Pre-grad threshold (Ralph: same WR at 30 vs 50, more signals)
POST_GRAD_THRESHOLD = 55   # Post-grad threshold (lowered from 65 to catch runners - 2026-01-31)

# Base score threshold for distribution checks
# Only check distribution if base score >= this value
DISTRIBUTION_CHECK_THRESHOLD = 30

# =============================================================================
# SCORING WEIGHTS (Total: 0-100 points max — clean budget)
# UPDATE 2026-01-28: Normalized to 100-point max for both pre-grad and post-grad
#
# PRE-GRAD BUDGET (100 max):
#   Buyer Velocity: 18 | Bonding Speed: 15 | Acceleration: 15
#   Buy/Sell Ratio: 10 | Unique Buyers: 10 | Volume: 8
#   Vol/Liq Vel: 6 | Momentum: 6 | Narrative: 7 | TG Calls: 5
#
# POST-GRAD BUDGET (100 max):
#   Buyer Velocity: 18 | Volume: 12 | Buy/Sell: 10 | Unique Buyers: 10
#   Social Verification: 14 | Graduation Speed: 10 | Vol/Liq: 6
#   Momentum: 8 | Narrative: 7 | TG Calls: 5
# =============================================================================

# Combined WEIGHTS dictionary (required by conviction engine)
WEIGHTS = {
    # Smart Wallet Activity - DISABLED (2026-01-31: KOLs underperform organic by 11%)
    'smart_wallet_elite': 0,        # DISABLED - was 15
    'smart_wallet_kol': 0,          # DISABLED - was 10
    'smart_wallet_verified': 0,     # DISABLED - was 7
    'smart_wallet_emerging': 0,     # DISABLED - was 4

    # Narrative Detection (max 7 points — RSS+BERTopic matching)
    'narrative_hot': 5,             # Hot/trending narrative (RSS+BERTopic cluster match)
    'narrative_fresh': 2,           # Fresh narrative (< 48h)
    'narrative_multiple': 2,        # Multiple narratives

    # Holder Distribution (max 10 points)
    'holders_high': 10,             # 100+ holders
    'holders_medium': 7,            # 50-99 holders
    'holders_low': 4,               # 30-49 holders

    # Volume Velocity (max 8 points pre-grad, 12 post-grad)
    'volume_spike': 8,              # Strong volume spike
    'volume_increasing': 5,         # Steady increase

    # Price Momentum (max 6 points pre-grad, 8 post-grad)
    'momentum_strong': 6,           # Strong upward momentum
    'momentum_moderate': 3,         # Moderate momentum
}

# =============================================================================
# DETAILED SCORING WEIGHTS (for specific calculations)
# =============================================================================

# Smart Wallet Activity - DISABLED (2026-01-31: KOLs underperform organic by 11%)
SMART_WALLET_WEIGHTS = {
    'per_kol': 0,            # DISABLED - was 10
    'max_score': 0,          # DISABLED - was 40 (this is the key flag)
    'multi_kol_bonus': 0,    # DISABLED - was 15
    'kol_time_window': 300   # 5 minutes for multi-KOL bonus (kept for reference)
}

# =============================================================================
# BUYER VELOCITY SCORING (0-18 points) - Replaces KOL scoring
# Measures how fast unique buyers are accumulating
# =============================================================================
BUYER_VELOCITY_WEIGHTS = {
    'explosive': 18,         # 100+ buyers in 5 min (viral organic demand)
    'very_fast': 14,         # 50-99 buyers in 5 min
    'fast': 10,              # 25-49 buyers in 5 min
    'moderate': 6,           # 15-24 buyers in 5 min
    'slow': 3,               # 5-14 buyers in 5 min
    'minimal': 0,            # <5 buyers in 5 min
    'window_seconds': 300,   # 5-minute window for velocity calculation
}

# =============================================================================
# NEW: BONDING CURVE SPEED SCORING (0-15 points)
# How fast the bonding curve is filling (organic demand indicator)
# =============================================================================
BONDING_SPEED_WEIGHTS = {
    'hyper': 15,             # >7%/min bonding velocity (insane demand)
    'rocket': 12,            # >5%/min bonding velocity (explosive demand)
    'fast': 8,               # 2-5%/min bonding velocity
    'steady': 5,             # 1-2%/min bonding velocity
    'slow': 2,               # 0.5-1%/min bonding velocity
    'crawl': 0,              # <0.5%/min (weak demand)
}

# =============================================================================
# PRICE ACCELERATION BONUS (pre-grad only)
# Rewards rapid price increase — early FOMO indicator
# =============================================================================
ACCELERATION_BONUS = {
    'enabled': True,
    'thresholds': [
        {'pct': 50, 'points': 15},   # +50% in ≤10 min → +15 pts
        {'pct': 30, 'points': 8},    # +30% in ≤10 min → +8 pts
    ],
    'max_age_minutes': 10,            # Only apply if token age ≤10 min
}

# =============================================================================
# EARLY PUMP ALERT — force signal at low scores if momentum criteria met
# Overrides threshold: price +30% in <10min + buyers >40 + bonding >40%
# =============================================================================
EARLY_PUMP_ALERT = {
    'enabled': True,
    'min_price_change_pct': 30,       # +30% price change required
    'max_age_minutes': 10,            # Within 10 minutes of creation
    'min_unique_buyers': 40,          # At least 40 unique buyers
    'min_bonding_pct': 40,            # At least 40% bonding
    'min_score': 20,                  # Must have at least score 20 (100-point budget)
    'max_score': 30,                  # Only triggers below normal threshold (30)
}

# =============================================================================
# NEW: ORGANIC SCANNER CONFIG
# Filters for PumpPortal new tokens to identify organic activity
# UPDATE 2026-01-31 (RALPH OPTIMIZATION):
# - Added min_buy_sell_ratio: 2.0 (≥2.0 gives 32% WR vs 27% baseline)
# - Raised min_bonding_pct: 20 → 40 (data shows ≥40% bonding wins more)
# =============================================================================
ORGANIC_SCANNER = {
    'enabled': True,
    'min_unique_buyers': 50,       # Raised from 30 to reduce rugs (2026-01-31)
    'min_buy_ratio': 0.65,         # Raised from 0.55 to filter weak momentum (2026-01-31)
    'min_buy_sell_ratio': 2.0,     # NEW: Ralph shows ≥2.0 B/S ratio gives +5% WR
    'max_bundle_ratio': 0.20,      # Max 20% of buys from same block (anti-bundle)
    'watch_window_seconds': 300,   # Watch tokens for 5 min before deciding
    'min_bonding_pct': 40,         # Raised from 20 → 40 (Ralph: higher bonding wins more)
    'max_bonding_pct': 90,         # Raised from 85 — allow near-graduation entries
    'max_tracked_candidates': 100, # Max tokens to watch simultaneously
    'cooldown_seconds': 60,        # Wait 60s between scanner evaluations
    'velocity_bypass_multiplier': 2.5,  # If velocity > 2.5x in 5 min → qualify regardless of buyer count
}

# =============================================================================
# NEW: GRADUATION SPEED BONUS (Post-grad only)
# Rewards fast graduations (strong demand) and penalizes slow ones
# =============================================================================
GRADUATION_SPEED_BONUS = {
    'fast_grad_minutes': 15,       # Graduated in <15 min = strong demand
    'fast_grad_bonus': 10,         # +10 pts for fast graduation
    'slow_grad_minutes': 30,       # Graduated in >30 min = weak demand
    'slow_grad_penalty': -6,       # -6 pts for slow graduation with low growth
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
    'min_base_score': 35,        # Need at least 35 pts from other factors
    'always_fetch_post_grad': True  # Always check holders post-graduation
}

# Volume Velocity (0-8 pre-grad, 0-12 post-grad)
# POST-GRAD: Uses DexScreener volume/mcap ratio (higher weight — key post-grad signal)
VOLUME_WEIGHTS = {
    'spiking': 12,          # Volume 2x+ expected rate (post-grad)
    'growing': 8,           # Volume 1.25x+ expected rate
    'steady': 4             # Volume >1x expected rate
}

# PRE-GRAD: Uses PumpPortal WebSocket rolling SOL volume (FREE)
PRE_GRAD_VOLUME_WEIGHTS = {
    'spiking': 8,           # velocity_ratio > 3.0 OR current_window > 50 SOL
    'growing': 5,           # velocity_ratio > 1.5 OR current_window > 20 SOL
    'steady': 3,            # velocity_ratio > 1.0 OR current_window > 5 SOL
    'window_seconds': 300,  # 5-minute rolling windows
}

# Price Momentum (0-6 pre-grad, 0-8 post-grad with multi-timeframe)
MOMENTUM_WEIGHTS = {
    'very_strong': 6,       # +50% in 5 minutes
    'strong': 4,            # +30% in 5 minutes
    'moderate': 2           # +10% in 5 minutes
}

# Distribution Scoring (0-10 points)
# Pre-graduation: Based on unique buyers (FREE)
UNIQUE_BUYER_WEIGHTS = {
    'exceptional': 10,  # 100+ unique buyers (very strong organic)
    'high': 7,          # 50-99 unique buyers
    'medium': 5,        # 25-49 unique buyers
    'low': 3,           # 10-24 unique buyers
    'minimal': 0        # <10 unique buyers (too early/risky)
}

# Post-graduation: Based on real holders (10 credits)
HOLDER_WEIGHTS = {
    'high': 10,             # 100+ holders
    'medium': 7,            # 50-99 holders
    'low': 4                # 20-49 holders
}

# Twitter and LunarCrush scoring removed (no budget) - see lines 418-419

# Telegram Social Confirmation Scoring - DISABLED
# TG calls removed from scoring - too easily gamed (2026-01-31)
TELEGRAM_CONFIRMATION_WEIGHTS = {
    'high_intensity': 0,    # DISABLED
    'medium_intensity': 0,  # DISABLED
    'low_intensity': 0,     # DISABLED
    'age_decay': 0,         # DISABLED
    'max_social_total': 0   # DISABLED
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
            'check_pre_grad': 40,    # Only check if base score >= 40 (100-point budget)
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
            'enabled': False,         # DISABLED (2026-01-31: KOLs underperform organic)
            'per_kol': 0,             # DISABLED - was 10
            'penalty_reduction': 0    # DISABLED - was 5
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
        'max_mcap_post_grad': 200000, # Skip if MCAP >$200K on post-grad call (raised from $50K)
        'log_skipped': True           # Log skipped signals for analysis
    },

    # NEW: Tiered Post-Grad Strategy (Grok recommendation 2026-01-29)
    # Catches $100-150K entries that run to $500-600K
    # Pump.fun graduation is ~$69K, so we tier based on distance from grad
    #
    # LOGIC: Score boosts are ADDITIVE (reward proven runners)
    # - Threshold stays at 65 across all tiers
    # - Higher MCAP = token proved itself = gets bonus points
    # - Still need gates to avoid dead cats
    'post_grad_tiers': {
        'enabled': True,

        # Tier 1: Fresh graduates ($70K-$100K) - track only, no boost
        # Need full 65 score from base factors (hardest tier)
        'tier_1': {
            'max_mcap': 100000,           # Up to $100K MCAP
            'score_boost': 0,             # No boost - fresh grad needs to prove itself
            'min_grad_speed_minutes': 30, # Must have graduated in <30 min (quality filter)
            'description': 'Fresh graduate'
        },

        # Tier 2: Confirmed runners ($100K-$150K) - proven momentum
        # Token climbed from $69K grad → $100K+, reward with +5 pts
        'tier_2': {
            'max_mcap': 150000,           # $100K-$150K MCAP
            'score_boost': +5,            # +5 for proving it can climb (effective threshold 60)
            'min_volume_velocity': 1.5,   # Volume must be 1.5x+ liquidity (active trading)
            'min_price_change_1h': 10,    # Must be up 10%+ in 1h (momentum)
            'max_retrace_pct': 30,        # Can't be in >30% retrace (not dead cat)
            'retrace_soft_penalty': -5,   # Soft penalty if 20-30% retrace
            'retrace_soft_threshold': 20, # Apply soft penalty above this retrace %
            'description': 'Confirmed runner'
        },

        # Tier 3: Extended runners ($150K-$200K) - major validation
        # Token went $69K → $150K+, strong signal, cumulative +10 pts
        'tier_3': {
            'max_mcap': 200000,           # $150K-$200K MCAP
            'score_boost': +10,           # +10 cumulative for major climb (effective threshold 55)
            'min_volume_velocity': 2.0,   # Volume must be 2x+ liquidity (very active)
            'min_price_change_1h': 20,    # Must be up 20%+ in 1h (strong momentum)
            'max_retrace_pct': 20,        # Can't be in >20% retrace (fresh breakout only)
            'require_smart_wallet': True, # Require smart wallet activity (validation)
            'no_smart_wallet_penalty': -10,  # Penalty if no smart wallet at this MCAP
            'smart_wallet_recency_minutes': 60,  # Smart wallet buy must be within 60 min
            'multi_wallet_bonus': 10,     # +10 bonus if 2+ smart wallets bought
            'description': 'Extended runner'
        },

        # Acceleration bonus: +15 pts for explosive moves
        'acceleration_bonus': {
            'enabled': True,
            'min_price_change_30m': 30,   # +30% in 30 min
            'bonus_points': 15,           # +15 pts for acceleration
        }
    },

    'signal_maturity_gate': {
        'enabled': True,              # Gate signals on minimum maturity
        'min_mcap_pre_grad': 12000,   # Pre-grad: skip if MCAP < $12K (lowered from $15K)
        'min_age_minutes_pre_grad': 12,  # Pre-grad: skip if age < 12 min (default)
        'min_age_minutes_fast_track': 5,  # Fast-track: high conviction OR high velocity → only 5 min
        'fast_track_min_score': 55,   # Score threshold for fast-track maturity (100-point budget)
        'fast_track_min_velocity_score': 15,  # Buyer velocity score threshold (25+ buyers/5min = "fast")
        'min_age_minutes_ultra_fast': 2,  # Ultra fast-track: explosive velocity + bonding → 2 min
        'ultra_fast_min_velocity_score': 22,  # Ultra: need "very_fast" velocity (50+ buyers/5min)
        'ultra_fast_min_bonding_pct': 50,  # Ultra: need 50%+ bonding (real organic demand)
        'hard_block_age_minutes': 2,  # Hard block: NO signal before 2 min (filters bot pumps)
        'min_mcap_post_grad': 0,      # Post-grad: no min MCAP (already graduated)
        'min_age_minutes_post_grad': 0,  # Post-grad: no min age
        'log_skipped': True           # Log skipped signals
    },

    'dump_detection': {
        'enabled': True,              # Detect tokens that already pumped & dumped
        'min_peak_mcap': 30000,       # Only apply if peak MCAP was meaningful ($30K+)
        # Dynamic retrace tiers (Grok calibration):
        'hard_block_retrace_pct': 60, # >60% retrace from peak → hard block (deep dump)
        'penalty_retrace_pct': 40,    # 40-60% retrace → score penalty (partial retrace)
        'penalty_min': -20,           # Penalty at 40% retrace
        'penalty_max': -30,           # Penalty at 60% retrace (scales linearly)
        'log_skipped': True           # Log blocked/penalized dump signals
    },

    'post_call_monitoring': {
        'enabled': True,              # Monitor price after signal
        'exit_alert_threshold': -15,  # Alert if price drops -15%
        'monitoring_duration': 600,   # Monitor for 10 minutes (raised from 300s/5min)
        'check_interval': 30,         # Check every 30 seconds
        'send_telegram_alert': True,  # Send exit alert to Telegram
        'buyer_fade_enabled': True,   # Also check buyer velocity fade
        'buyer_fade_threshold': 5,    # Fade alert if < 5 new buyers in window
        'buyer_fade_window_seconds': 120,  # 2-minute window for buyer check
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

# Option 2: Detailed tracking - DISABLED (2026-01-31)
# KOLs have 18% WR vs Organic 29% WR (-11% difference)
# Cleared until we find consistently good wallets
SMART_WALLETS = [
    # KOL TRACKING DISABLED
    # Previous wallets archived - can be re-added after finding better performers
    # Run /ralph to analyze wallet performance before re-enabling
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
MILESTONE_BANNER_10X = os.getenv('MILESTONE_BANNER_10X')     # HELL FIRE (10-50x)
MILESTONE_BANNER_100X = os.getenv('MILESTONE_BANNER_100X')   # SCORCHED EARTH (100-500x)
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

# Maximum market cap for signal calls
# Tokens above this MCAP won't trigger new signals (already mooned)
# UPDATE 2026-01-31 (RALPH): Lowered from $20K to $15K (≤$15K gives 34% WR vs 27% baseline)
MAX_MARKET_CAP_FILTER = int(os.getenv('MAX_MARKET_CAP_FILTER', '15000'))  # $15K (Ralph optimized)
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

ENABLE_NARRATIVES = True    # Enabled for early detection (+0-7 pts, 100-point budget)
ENABLE_STATIC_NARRATIVES = False  # Static keyword matching - DISABLED (too noisy, not useful)
ENABLE_REALTIME_NARRATIVES = True  # RSS + BERTopic for emerging narratives (no API cost)
NARRATIVE_UPDATE_INTERVAL = 900  # Update narratives every 15 minutes (900s)
ENABLE_PERFORMANCE_TRACKING = True
ENABLE_MILESTONE_ALERTS = True
ENABLE_LUNARCRUSH = False   # LunarCrush disabled (no budget for API)
ENABLE_TWITTER = False      # Twitter disabled (no budget for API)
ENABLE_TELEGRAM_SCRAPER = False  # DISABLED - TG calls too easily gamed (2026-01-31)
ENABLE_BUILTIN_TELEGRAM_MONITOR = False  # DISABLED - not using TG for scoring anymore

# =============================================================================
# NARRATIVE DETECTION (2026 HOT TRENDS)
# =============================================================================

# Hot narratives to watch for (updated for 2026 meta)
# Format: dict with narrative names as keys
HOT_NARRATIVES = {
    # AI / Agents (HOTTEST in 2026) - narrative cap raised to 15
    'ai_agent': {
        'name': 'AI Agent',
        'keywords': ['ai', 'agent', 'autonomous', 'neural', 'gpt', 'bot', 'llm', 'cognition'],
        'weight': 15,  # Raised from 10 - hottest narrative, max points
        'active': True
    },

    # DeSci (Growing trend)
    'desci': {
        'name': 'DeSci',
        'keywords': ['desci', 'science', 'research', 'biotech', 'lab', 'molecule', 'data'],
        'weight': 12,  # Raised from 10 - strong 2026 narrative
        'active': True
    },

    # RWA (Real World Assets - 2026 focus)
    'rwa': {
        'name': 'RWA',
        'keywords': ['rwa', 'real world', 'asset', 'tokenized', 'treasury', 'bond'],
        'weight': 10,  # Raised from 8
        'active': True
    },

    # Privacy / ZK (Solana ZK compression)
    'privacy': {
        'name': 'Privacy',
        'keywords': ['privacy', 'zk', 'zero knowledge', 'anonymous', 'private', 'stealth'],
        'weight': 10,  # Raised from 8
        'active': True
    },

    # DeFi (Always relevant)
    'defi': {
        'name': 'DeFi',
        'keywords': ['defi', 'yield', 'stake', 'farm', 'swap', 'liquidity', 'dex'],
        'weight': 8,   # Raised from 7
        'active': True
    },

    # Mobile / Saga (Solana mobile push)
    'mobile': {
        'name': 'Mobile',
        'keywords': ['mobile', 'saga', 'phone', 'seeker', 'dapp'],
        'weight': 8,   # Raised from 7
        'active': True
    },

    # GameFi
    'gamefi': {
        'name': 'GameFi',
        'keywords': ['game', 'play', 'nft', 'metaverse', 'gaming', 'p2e'],
        'weight': 7,   # Raised from 6
        'active': True
    },

    # Meme (Classic)
    'meme': {
        'name': 'Meme',
        'keywords': ['meme', 'pepe', 'doge', 'shiba', 'wojak', 'frog', 'cat', 'dog'],
        'weight': 5,   # Unchanged - meme is default, not a narrative edge
        'active': True
    }
}

# Narrative combo bonuses (when multiple narratives match) - Raised for narrative importance
NARRATIVE_COMBOS = {
    ('ai_agent', 'desci'): +7,       # AI + DeSci = powerful combo (raised from 5)
    ('ai_agent', 'defi'): +5,        # AI + DeFi = yield farming agents (raised from 3)
    ('rwa', 'defi'): +5,             # RWA + DeFi = tokenized yields (raised from 3)
}

# =============================================================================
# HELIUS ENHANCED FEATURES (Credit-efficient blockchain intelligence)
# =============================================================================

# Helius Pump.fun Program Webhook (organic discovery backbone)
# Monitors all Pump.fun program events for sub-second token creation detection
# Replaces flaky PumpPortal WS for initial discovery, PumpPortal still used for trades
HELIUS_PUMP_WEBHOOK = {
    'enabled': False,  # DISABLED: Enhanced webhooks burn ~10M credits/month watching ALL pump.fun txs
                       # PumpPortal WebSocket provides same organic discovery data for FREE
                       # Helius credits should be reserved for enrichment (authority, holders, tx patterns)
    'program_id': '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P',  # Pump.fun program
    'webhook_type': 'enhanced',                # Enhanced = parsed data (costs credits)
    'transaction_types': ['ANY'],              # Catch all pump.fun txs (filter in handler)
    'endpoint_path': '/webhook/pump-program',  # Our FastAPI endpoint
    'auto_register': False,                    # Don't auto-register (saves credits)
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
    'gate_mid_score': 25,          # Only check if mid_score >= 25 (100-point budget)
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
    'gate_mid_score': 35,          # Only fetch if mid_score >= 35 (100-point budget)
    'max_signatures': 100,         # Fetch last 100 txs
    'credit_cost': 5,              # ~5 credits per call
}

# =============================================================================
# HELIUS BACKFILL (Historical ML Training Data via searchAssets)
# Uses Helius DAS API to find pump.fun graduates for Ralph's ML pipeline
# =============================================================================

HELIUS_BACKFILL = {
    'enabled': True,
    'use_dexscreener_discovery': True,  # Primary: DexScreener endpoints (FREE, guaranteed pairs)
    'use_search_assets': False,         # OFF: finds un-graduated tokens (pump.fun still authority)
    'use_program_scan': False,          # OFF: mostly un-graduated tokens, wastes DexScreener lookups
    'search_pages': 5,                  # Pages to fetch from searchAssets (200 tokens/page)
    'program_scan_tx_limit': 500,       # Max program TXs to scan in fallback mode
    'max_tokens_per_run': 200,          # Cap tokens per backfill run
    'min_mcap_graduated': 5000,         # Min MCAP ($5K - catch early graduates + dumps)
    'max_mcap': 500_000_000,            # Max MCAP ($500M = mega cap, still useful data)
    'min_liquidity': 1000,              # Min liquidity ($1K - include small pools for ML diversity)
    'min_volume_24h': 100,              # Min 24h volume ($100 - include quiet tokens for ML diversity)
    'require_raydium_pair': True,       # Only tokens with Raydium DEX pair (graduated)
    'enrich_with_helius': True,         # Add authority + holder data from Helius
    'helius_enrich_gate_score': 0,      # Enrich all tokens (backfill = comprehensive data)
    'dexscreener_rate_limit': 0.4,      # Seconds between DexScreener calls
    'helius_rate_limit': 0.3,           # Seconds between Helius calls
    'estimated_credits_per_run': 2200,  # ~11 credits/token (authority+holders) for enrichment only

    # =========================================================================
    # RUNNER DISCOVERY (2026-01-29): Focus on PROVEN RUNNERS for ML training
    # Instead of random tokens, collect tokens that have ALREADY shown they can run
    # =========================================================================
    'runner_discovery': {
        'enabled': True,                    # Use runner-focused discovery
        'min_price_change_24h': 50,         # Min +50% in 24h (1.5x minimum)
        'min_price_change_6h': 30,          # OR min +30% in 6h (faster movers)
        'min_mcap': 50_000,                 # Min $50K MCAP (graduated, not dust)
        'max_mcap': 10_000_000,             # Max $10M MCAP (catch before mega run)
        'min_volume_24h': 10_000,           # Min $10K volume (real trading activity)
        'min_liquidity': 5_000,             # Min $5K liquidity (can actually trade)
        'prefer_raydium': True,             # Prefer Raydium pairs (graduated from pump)
        'max_age_hours': 48,                # Max 48h old (recent launches)
        'fallback_to_generic': True,        # Fall back to generic discovery if no runners
    },
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
    'backfill': 500,        # Weekly backfill run (~500 credits per run)
    'other': 2000,          # Misc RPC calls
    'total': 32000          # ~960k/month (under 1M free tier)
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
