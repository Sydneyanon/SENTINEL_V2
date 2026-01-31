"""
SENTINEL V3 - Scoring Engine
Simple 4-factor scoring: Wallet + Volume + Momentum + Holders
"""
from loguru import logger
from typing import Dict, Any, Tuple

from config import SCORING, MIN_SCORE, MIN_LIQUIDITY, MIN_HOLDERS, MAX_MCAP


def calculate_score(
    wallet_tier: str,
    volume_1h: float,
    liquidity: float,
    price_change_1h: float,
    holders: int,
    mcap: float
) -> Tuple[int, Dict[str, Any], bool, str]:
    """
    Calculate conviction score for a token.

    Returns:
        (score, breakdown, should_signal, skip_reason)
    """
    breakdown = {}
    skip_reason = None

    # ==========================================================================
    # PRE-CHECKS (hard filters)
    # ==========================================================================

    if mcap > MAX_MCAP:
        return 0, {}, False, f"MCAP ${mcap:,.0f} > ${MAX_MCAP:,.0f}"

    if liquidity < MIN_LIQUIDITY:
        return 0, {}, False, f"Liquidity ${liquidity:,.0f} < ${MIN_LIQUIDITY:,.0f}"

    if holders < MIN_HOLDERS:
        return 0, {}, False, f"Holders {holders} < {MIN_HOLDERS}"

    # ==========================================================================
    # FACTOR 1: Wallet Tier (0-40 points)
    # ==========================================================================

    wallet_score = SCORING['wallet'].get(wallet_tier, 0)
    breakdown['wallet'] = {
        'tier': wallet_tier,
        'score': wallet_score,
        'max': 40
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
    # FACTOR 3: Momentum (0-20 points)
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
        'max': 20
    }

    # ==========================================================================
    # FACTOR 4: Holders (0-20 points)
    # ==========================================================================

    if holders >= 100:
        holder_score = SCORING['holders']['high']
    elif holders >= 50:
        holder_score = SCORING['holders']['medium']
    elif holders >= 20:
        holder_score = SCORING['holders']['low']
    else:
        holder_score = 0

    breakdown['holders'] = {
        'count': holders,
        'score': holder_score,
        'max': 20
    }

    # ==========================================================================
    # TOTAL
    # ==========================================================================

    total_score = wallet_score + volume_score + momentum_score + holder_score
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

    if 'holders' in breakdown:
        h = breakdown['holders']
        lines.append(f"Holders ({h['count']}): {h['score']}/{h['max']}")

    if 'total' in breakdown:
        t = breakdown['total']
        lines.append(f"TOTAL: {t['score']}/{t['max']} (threshold: {t['threshold']})")

    return "\n".join(lines)
