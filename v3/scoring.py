"""
SENTINEL V3 - Scoring Engine
Data-driven scoring: Wallet + Volume + Momentum + Buy/Sell Ratio
Based on Ralph analysis of 323 signals.
"""
from datetime import datetime, timezone
from loguru import logger
from typing import Dict, Any, Tuple, Optional

from config import (
    SCORING, MIN_SCORE, MIN_LIQUIDITY, MIN_HOLDERS, MAX_MCAP,
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

    # Holders filter - lower for pre-grad (estimated from bonding curve)
    # Graduated: 20 min | Pre-grad: 10 min (estimated)
    min_holders = MIN_HOLDERS if graduated else 10
    if holders < min_holders:
        return 0, {}, False, f"Holders {holders} < {min_holders}"

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
# Uses accumulated WebSocket data instead of one-shot REST API data

V2_MIN_SCORE = 45  # Threshold for V2 scoring (accumulates over time)


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
    V2-style scoring with accumulated WebSocket data.

    Scoring factors (0-100):
    - Wallet Tier: 0-25 pts
    - Buyer Velocity: 0-20 pts (buys per minute)
    - Unique Buyers: 0-15 pts
    - Buy/Sell Ratio: 0-15 pts
    - Bonding Progress: 0-15 pts (pre-grad only)
    - Multi-KOL Bonus: 0-10 pts

    Returns:
        (score, breakdown, should_signal, skip_reason)
    """
    breakdown = {}
    skip_reason = None

    # ==========================================================================
    # PRE-CHECKS (minimal - let scoring decide)
    # ==========================================================================

    # Only check liquidity for pre-grad (graduated checked elsewhere)
    min_liq = 1000 if not graduated else MIN_LIQUIDITY
    if liquidity < min_liq:
        return 0, {}, False, f"Liquidity ${liquidity:,.0f} < ${min_liq:,.0f}"

    # ==========================================================================
    # FACTOR 1: Wallet Tier (0-25 points)
    # ==========================================================================

    tier_scores = {'elite': 25, 'top_kol': 20, 'verified': 15, 'new': 10, 'smart_money': 20}
    wallet_score = tier_scores.get(wallet_tier, 10)
    breakdown['wallet'] = {'tier': wallet_tier, 'score': wallet_score, 'max': 25}

    # ==========================================================================
    # FACTOR 2: Buyer Velocity (0-20 points)
    # ==========================================================================
    # Buys per minute - indicates FOMO/momentum

    tracking_minutes = max(tracking_seconds / 60, 0.5)  # Min 30 seconds
    buys_per_minute = buys / tracking_minutes

    if buys_per_minute >= 5:
        velocity_score = 20  # Very high velocity
    elif buys_per_minute >= 3:
        velocity_score = 15
    elif buys_per_minute >= 1.5:
        velocity_score = 10
    elif buys_per_minute >= 0.5:
        velocity_score = 5
    else:
        velocity_score = 0

    breakdown['buyer_velocity'] = {
        'buys': buys,
        'minutes': round(tracking_minutes, 1),
        'per_minute': round(buys_per_minute, 2),
        'score': velocity_score,
        'max': 20
    }

    # ==========================================================================
    # FACTOR 3: Unique Buyers (0-15 points)
    # ==========================================================================
    # More unique buyers = more organic interest

    if unique_buyers >= 20:
        unique_score = 15
    elif unique_buyers >= 12:
        unique_score = 12
    elif unique_buyers >= 8:
        unique_score = 8
    elif unique_buyers >= 5:
        unique_score = 5
    else:
        unique_score = 0

    breakdown['unique_buyers'] = {
        'count': unique_buyers,
        'score': unique_score,
        'max': 15
    }

    # ==========================================================================
    # FACTOR 4: Buy/Sell Ratio (0-15 points)
    # ==========================================================================

    buy_sell_ratio = buys / max(sells, 1)

    if buy_sell_ratio >= 5.0:
        bs_score = 15  # Very bullish
    elif buy_sell_ratio >= 3.0:
        bs_score = 12
    elif buy_sell_ratio >= 2.0:
        bs_score = 8
    elif buy_sell_ratio >= 1.0:
        bs_score = 4
    else:
        bs_score = 0

    breakdown['buy_sell_ratio'] = {
        'buys': buys,
        'sells': sells,
        'ratio': round(buy_sell_ratio, 2),
        'score': bs_score,
        'max': 15
    }

    # ==========================================================================
    # FACTOR 5: Bonding Progress (0-15 points) - Pre-grad only
    # ==========================================================================

    bonding_score = 0
    if not graduated and bonding_pct > 0:
        if bonding_pct >= 80:
            bonding_score = 15  # Near graduation!
        elif bonding_pct >= 60:
            bonding_score = 12
        elif bonding_pct >= 40:
            bonding_score = 8
        elif bonding_pct >= 20:
            bonding_score = 4

    breakdown['bonding'] = {
        'pct': round(bonding_pct, 1),
        'graduated': graduated,
        'score': bonding_score,
        'max': 15
    }

    # ==========================================================================
    # FACTOR 6: Multi-KOL Bonus (0-10 points)
    # ==========================================================================
    # Multiple KOLs buying = strong signal

    if kol_count >= 3:
        kol_bonus = 10
    elif kol_count >= 2:
        kol_bonus = 6
    else:
        kol_bonus = 0

    breakdown['multi_kol'] = {
        'count': kol_count,
        'score': kol_bonus,
        'max': 10
    }

    # ==========================================================================
    # TOTAL (max 100)
    # ==========================================================================

    total_score = (
        wallet_score +
        velocity_score +
        unique_score +
        bs_score +
        bonding_score +
        kol_bonus
    )

    breakdown['total'] = {
        'score': total_score,
        'max': 100,
        'threshold': V2_MIN_SCORE
    }

    should_signal = total_score >= V2_MIN_SCORE

    if not should_signal:
        skip_reason = f"Score {total_score} < {V2_MIN_SCORE}"

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
