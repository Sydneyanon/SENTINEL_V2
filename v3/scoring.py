"""
SENTINEL V3 - Scoring Engine
Data-driven scoring: Wallet + Volume + Momentum + Buy/Sell Ratio
Based on Ralph analysis of 323 signals.
"""
from datetime import datetime, timezone
from loguru import logger
from typing import Dict, Any, Tuple, Optional

from config import (
    SCORING, MIN_SCORE, MIN_LIQUIDITY, MAX_MCAP,
    AVOID_HOURS_UTC
)


def calculate_score(
    wallet_tier: str,
    volume_1h: float,
    liquidity: float,
    price_change_1h: float,
    holders: int,
    mcap: float,
    buys_1h: int = 0,
    sells_1h: int = 0,
    graduated: bool = True
) -> Tuple[int, Dict[str, Any], bool, str]:
    """
    Calculate conviction score for a token.

    Returns:
        (score, breakdown, should_signal, skip_reason)
    """
    breakdown = {}
    skip_reason = None

    # ==========================================================================
    # PRE-CHECKS (hard filters - based on Ralph data analysis)
    # ==========================================================================

    # MCAP filter - only apply to GRADUATED tokens (pre-grad MCAP is unreliable)
    # Pre-grad tokens use bonding curve math which doesn't reflect true MCAP
    if graduated and mcap > MAX_MCAP:
        return 0, {}, False, f"MCAP ${mcap:,.0f} > ${MAX_MCAP:,.0f}"

    # Liquidity filter - lower threshold for pre-grad (bonding curve starts at ~$1-2K)
    # Graduated tokens: $8K min | Pre-grad: $1K min (5 SOL * $200)
    min_liq = MIN_LIQUIDITY if graduated else 1000
    if liquidity < min_liq:
        return 0, {}, False, f"Liquidity ${liquidity:,.0f} < ${min_liq:,.0f}"

    # Holders - NO HARD FILTER (V2 uses unique_buyers scoring instead)
    # DexScreener often returns 0, pre-grad is just an estimate
    # Let scoring decide based on unique_buyers from WebSocket

    # Buy/Sell ratio - NO HARD FILTER (was blocking all pre-grad with 0/0 data)
    # Use scoring instead (lines 117-137)
    buy_sell_ratio = buys_1h / max(sells_1h, 1)

    # Time filter - avoid worst hours (optional)
    if AVOID_HOURS_UTC:
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in AVOID_HOURS_UTC:
            return 0, {}, False, f"Avoided hour {current_hour}:00 UTC (<15% WR)"

    # ==========================================================================
    # FACTOR 1: Wallet Tier (0-30 points)
    # ==========================================================================
    # Note: Ralph showed KOL (25%) vs Organic (29%) similar - reduced weight

    wallet_score = SCORING['wallet'].get(wallet_tier, SCORING['wallet']['new'])
    breakdown['wallet'] = {
        'tier': wallet_tier,
        'score': wallet_score,
        'max': 30
    }

    # ==========================================================================
    # FACTOR 2: Volume (0-20 points)
    # ==========================================================================

    if liquidity > 0:
        vol_ratio = volume_1h / liquidity
        if vol_ratio >= 2.0:
            volume_score = SCORING['volume']['high']
        elif vol_ratio >= 1.0:
            volume_score = SCORING['volume']['medium']
        elif vol_ratio >= 0.5:
            volume_score = SCORING['volume']['low']
        else:
            volume_score = 0
    else:
        vol_ratio = 0
        volume_score = 0

    breakdown['volume'] = {
        'ratio': round(vol_ratio, 2),
        'score': volume_score,
        'max': 20
    }

    # ==========================================================================
    # FACTOR 3: Momentum (0-25 points) - increased weight
    # ==========================================================================

    if price_change_1h >= 30:
        momentum_score = SCORING['momentum']['strong']
    elif price_change_1h >= 15:
        momentum_score = SCORING['momentum']['moderate']
    elif price_change_1h >= 5:
        momentum_score = SCORING['momentum']['weak']
    else:
        momentum_score = 0

    breakdown['momentum'] = {
        'price_change_1h': round(price_change_1h, 1),
        'score': momentum_score,
        'max': 25
    }

    # ==========================================================================
    # FACTOR 4: Buy/Sell Ratio (0-25 points) - NEW strong predictor
    # ==========================================================================
    # Ralph: Wins avg 1.1 vs Rugs avg 0.5 - strong predictor

    if buy_sell_ratio >= 2.0:
        bs_score = SCORING['buy_sell_ratio']['strong']
    elif buy_sell_ratio >= 1.5:
        bs_score = SCORING['buy_sell_ratio']['good']
    elif buy_sell_ratio >= 1.0:
        bs_score = SCORING['buy_sell_ratio']['weak']
    else:
        bs_score = 0

    breakdown['buy_sell_ratio'] = {
        'ratio': round(buy_sell_ratio, 2),
        'buys': buys_1h,
        'sells': sells_1h,
        'score': bs_score,
        'max': 25
    }

    # ==========================================================================
    # TOTAL (max 100)
    # ==========================================================================

    total_score = wallet_score + volume_score + momentum_score + bs_score
    breakdown['total'] = {
        'score': total_score,
        'max': 100,
        'threshold': MIN_SCORE
    }

    should_signal = total_score >= MIN_SCORE

    if not should_signal:
        skip_reason = f"Score {total_score} < {MIN_SCORE}"

    return total_score, breakdown, should_signal, skip_reason


# =============================================================================
# V2-STYLE SCORING (for ActiveTokenTracker continuous analysis)
# =============================================================================
# STABLE MODE: Jan 22 config with 53% WR - Quality > Quantity
# Uses accumulated WebSocket data - EXACT V2 weights

# Thresholds
V2_MIN_SCORE = 60  # Pre-grad threshold
V2_POST_GRAD_THRESHOLD = 75  # Post-grad threshold (stricter)
V2_MIN_UNIQUE_BUYERS = 15  # Minimum unique buyers
V2_MIN_LIQUIDITY = 20000  # Minimum liquidity for graduated

# Smart Wallet Weights (0-40 pts max)
SMART_WALLET_WEIGHTS = {
    'per_kol': 10,           # +10 per KOL buy
    'max_score': 40,         # max 40 pts from smart wallets
    'multi_kol_bonus': 15,   # bonus for multiple KOLs (2+)
}

# Buyer Velocity Weights (0-18 pts) - buyers in 5 min window
BUYER_VELOCITY_WEIGHTS = {
    'explosive': 18,         # 100+ buyers in 5 min
    'very_fast': 14,         # 50-99 buyers in 5 min
    'fast': 10,              # 25-49 buyers in 5 min
    'moderate': 6,           # 15-24 buyers in 5 min
    'slow': 3,               # 5-14 buyers in 5 min
    'minimal': 0,            # <5 buyers in 5 min
}

# Bonding Speed Weights (0-15 pts) - bonding velocity %/min
BONDING_SPEED_WEIGHTS = {
    'hyper': 15,             # >7%/min
    'rocket': 12,            # >5%/min
    'fast': 8,               # 2-5%/min
    'steady': 5,             # 1-2%/min
    'slow': 2,               # 0.5-1%/min
    'crawl': 0,              # <0.5%/min
}

# Unique Buyer Weights (0-10 pts)
UNIQUE_BUYER_WEIGHTS = {
    'exceptional': 10,       # 100+ unique buyers
    'high': 7,               # 50-99 unique buyers
    'medium': 5,             # 25-49 unique buyers
    'low': 3,                # 10-24 unique buyers
    'minimal': 0,            # <10 unique buyers
}

# Buy/Sell Ratio Weights (0-10 pts)
BUY_SELL_WEIGHTS = {
    'strong': 10,            # ratio >= 2.0
    'good': 7,               # ratio >= 1.5
    'weak': 3,               # ratio >= 1.0
    'negative': 0,           # ratio < 1.0
}


def calculate_score_v2(
    wallet_tier: str,
    liquidity: float,
    mcap: float,
    holders: int,
    graduated: bool,
    buys: int,
    sells: int,
    unique_buyers: int,
    kol_count: int,
    bonding_pct: float,
    tracking_seconds: float
) -> Tuple[int, Dict[str, Any], bool, str]:
    """
    V2-style scoring with STABLE MODE weights (Jan 22 config, 53% WR).

    Scoring factors (0-100):
    PRE-GRAD:
    - Smart Wallet: 0-40 pts (per KOL + multi-KOL bonus)
    - Buyer Velocity: 0-18 pts (buyers in 5 min window)
    - Bonding Speed: 0-15 pts (bonding velocity %/min)
    - Unique Buyers: 0-10 pts
    - Buy/Sell Ratio: 0-10 pts
    - Acceleration Bonus: 0-15 pts (reserved for future)

    POST-GRAD:
    - Smart Wallet: 0-40 pts
    - Buyer Velocity: 0-18 pts
    - Unique Buyers: 0-10 pts
    - Buy/Sell Ratio: 0-10 pts
    - Volume: 0-12 pts (reserved for future)
    - Graduation Speed: 0-10 pts (reserved for future)

    Returns:
        (score, breakdown, should_signal, skip_reason)
    """
    breakdown = {}
    skip_reason = None

    # ==========================================================================
    # PRE-CHECKS
    # ==========================================================================

    # Liquidity check for graduated tokens only
    if graduated and liquidity < V2_MIN_LIQUIDITY:
        return 0, {}, False, f"Liquidity ${liquidity:,.0f} < ${V2_MIN_LIQUIDITY:,.0f}"

    # Unique buyers check with gradual ramp-up
    if tracking_seconds < 60:
        min_buyers_required = 3  # Warming up
    elif tracking_seconds < 120:
        min_buyers_required = 8  # Building momentum
    else:
        min_buyers_required = V2_MIN_UNIQUE_BUYERS  # Full threshold (15)

    if unique_buyers < min_buyers_required:
        return 0, {}, False, f"Unique buyers {unique_buyers} < {min_buyers_required}"

    # ==========================================================================
    # FACTOR 1: Smart Wallet Score (0-40 pts) - STABLE MODE
    # ==========================================================================
    # +10 per KOL, max 40, +15 bonus for multiple KOLs

    wallet_base = min(kol_count * SMART_WALLET_WEIGHTS['per_kol'], SMART_WALLET_WEIGHTS['max_score'])

    # Multi-KOL bonus (2+ KOLs buying same token)
    multi_kol_bonus = SMART_WALLET_WEIGHTS['multi_kol_bonus'] if kol_count >= 2 else 0

    # Tier bonus (on top of count)
    tier_bonus = {'elite': 5, 'top_kol': 3, 'verified': 2, 'smart_money': 3, 'new': 0}
    wallet_tier_bonus = tier_bonus.get(wallet_tier, 0)

    wallet_score = min(wallet_base + multi_kol_bonus + wallet_tier_bonus, SMART_WALLET_WEIGHTS['max_score'])

    breakdown['smart_wallet'] = {
        'kol_count': kol_count,
        'tier': wallet_tier,
        'base': wallet_base,
        'multi_kol_bonus': multi_kol_bonus,
        'tier_bonus': wallet_tier_bonus,
        'score': wallet_score,
        'max': 40
    }

    # ==========================================================================
    # FACTOR 2: Buyer Velocity (0-18 pts) - buyers in 5 min window
    # ==========================================================================

    # Scale to 5 min window (300 seconds)
    window_seconds = 300
    if tracking_seconds > 0:
        buyers_scaled = unique_buyers * (window_seconds / min(tracking_seconds, window_seconds))
    else:
        buyers_scaled = unique_buyers

    if buyers_scaled >= 100:
        velocity_score = BUYER_VELOCITY_WEIGHTS['explosive']
    elif buyers_scaled >= 50:
        velocity_score = BUYER_VELOCITY_WEIGHTS['very_fast']
    elif buyers_scaled >= 25:
        velocity_score = BUYER_VELOCITY_WEIGHTS['fast']
    elif buyers_scaled >= 15:
        velocity_score = BUYER_VELOCITY_WEIGHTS['moderate']
    elif buyers_scaled >= 5:
        velocity_score = BUYER_VELOCITY_WEIGHTS['slow']
    else:
        velocity_score = BUYER_VELOCITY_WEIGHTS['minimal']

    breakdown['buyer_velocity'] = {
        'unique_buyers': unique_buyers,
        'tracking_seconds': round(tracking_seconds, 0),
        'buyers_scaled_5min': round(buyers_scaled, 1),
        'score': velocity_score,
        'max': 18
    }

    # ==========================================================================
    # FACTOR 3: Bonding Speed (0-15 pts) - PRE-GRAD ONLY
    # ==========================================================================

    bonding_score = 0
    bonding_velocity = 0

    if not graduated and tracking_seconds > 0:
        # Calculate bonding velocity (%/min)
        tracking_minutes = tracking_seconds / 60
        if tracking_minutes > 0:
            bonding_velocity = bonding_pct / tracking_minutes

            if bonding_velocity > 7:
                bonding_score = BONDING_SPEED_WEIGHTS['hyper']
            elif bonding_velocity > 5:
                bonding_score = BONDING_SPEED_WEIGHTS['rocket']
            elif bonding_velocity >= 2:
                bonding_score = BONDING_SPEED_WEIGHTS['fast']
            elif bonding_velocity >= 1:
                bonding_score = BONDING_SPEED_WEIGHTS['steady']
            elif bonding_velocity >= 0.5:
                bonding_score = BONDING_SPEED_WEIGHTS['slow']
            else:
                bonding_score = BONDING_SPEED_WEIGHTS['crawl']

    breakdown['bonding_speed'] = {
        'bonding_pct': round(bonding_pct, 1),
        'velocity_pct_per_min': round(bonding_velocity, 2),
        'graduated': graduated,
        'score': bonding_score,
        'max': 15
    }

    # ==========================================================================
    # FACTOR 4: Unique Buyers (0-10 pts)
    # ==========================================================================

    if unique_buyers >= 100:
        unique_score = UNIQUE_BUYER_WEIGHTS['exceptional']
    elif unique_buyers >= 50:
        unique_score = UNIQUE_BUYER_WEIGHTS['high']
    elif unique_buyers >= 25:
        unique_score = UNIQUE_BUYER_WEIGHTS['medium']
    elif unique_buyers >= 10:
        unique_score = UNIQUE_BUYER_WEIGHTS['low']
    else:
        unique_score = UNIQUE_BUYER_WEIGHTS['minimal']

    breakdown['unique_buyers'] = {
        'count': unique_buyers,
        'score': unique_score,
        'max': 10
    }

    # ==========================================================================
    # FACTOR 5: Buy/Sell Ratio (0-10 pts)
    # ==========================================================================

    buy_sell_ratio = buys / max(sells, 1)

    if buy_sell_ratio >= 2.0:
        bs_score = BUY_SELL_WEIGHTS['strong']
    elif buy_sell_ratio >= 1.5:
        bs_score = BUY_SELL_WEIGHTS['good']
    elif buy_sell_ratio >= 1.0:
        bs_score = BUY_SELL_WEIGHTS['weak']
    else:
        bs_score = BUY_SELL_WEIGHTS['negative']

    breakdown['buy_sell_ratio'] = {
        'buys': buys,
        'sells': sells,
        'ratio': round(buy_sell_ratio, 2),
        'score': bs_score,
        'max': 10
    }

    # ==========================================================================
    # TOTAL
    # ==========================================================================

    total_score = (
        wallet_score +      # 0-40
        velocity_score +    # 0-18
        bonding_score +     # 0-15 (pre-grad only)
        unique_score +      # 0-10
        bs_score            # 0-10
    )
    # Max: 93 pre-grad, 78 post-grad

    # Use different threshold for pre-grad vs post-grad
    threshold = V2_POST_GRAD_THRESHOLD if graduated else V2_MIN_SCORE

    breakdown['total'] = {
        'score': total_score,
        'max': 93 if not graduated else 78,
        'threshold': threshold,
        'graduated': graduated
    }

    should_signal = total_score >= threshold

    if not should_signal:
        skip_reason = f"Score {total_score} < {threshold}"

    return total_score, breakdown, should_signal, skip_reason


def format_breakdown(breakdown: Dict) -> str:
    """Format score breakdown for logging/display."""
    lines = []

    if 'wallet' in breakdown:
        w = breakdown['wallet']
        lines.append(f"Wallet ({w['tier']}): {w['score']}/{w['max']}")

    if 'volume' in breakdown:
        v = breakdown['volume']
        lines.append(f"Volume ({v['ratio']}x liq): {v['score']}/{v['max']}")

    if 'momentum' in breakdown:
        m = breakdown['momentum']
        lines.append(f"Momentum ({m['price_change_1h']:+.1f}%): {m['score']}/{m['max']}")

    if 'buy_sell_ratio' in breakdown:
        bs = breakdown['buy_sell_ratio']
        lines.append(f"Buy/Sell ({bs['buys']}/{bs['sells']}={bs['ratio']}): {bs['score']}/{bs['max']}")

    if 'total' in breakdown:
        t = breakdown['total']
        lines.append(f"TOTAL: {t['score']}/{t['max']} (threshold: {t['threshold']})")

    return "\n".join(lines)
