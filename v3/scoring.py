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
