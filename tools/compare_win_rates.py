#!/usr/bin/env python3
"""
Win Rate Comparison: KOL-Based vs On-Chain-First Scoring

Compares signal performance before and after the scoring transition.
Transition: PR #131 merged ~2026-01-27 06:17 UTC (on-chain-first scoring)

Run on Railway or locally with DATABASE_URL set:
  python tools/compare_win_rates.py
"""

import asyncio
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from datetime import datetime, timezone

DATABASE_URL = os.getenv('DATABASE_URL')
TRANSITION_DATE = '2026-01-27 06:17:00+00'  # PR #131 merge = on-chain-first deployed


async def run():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set. Run on Railway or export DATABASE_URL first.")
        sys.exit(1)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

    async with pool.acquire() as conn:
        # ================================================================
        # 1. OVERALL STATS
        # ================================================================
        total = await conn.fetchval("SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE")
        print(f"\n{'='*70}")
        print(f"  SENTINEL V2 — WIN RATE COMPARISON: KOL vs ON-CHAIN")
        print(f"{'='*70}")
        print(f"\nTotal posted signals in DB: {total}")
        print(f"Transition date: {TRANSITION_DATE}")
        print()

        # ================================================================
        # 2. KOL ERA (before transition)
        # ================================================================
        kol_signals = await conn.fetch(f"""
            SELECT
                token_symbol, conviction_score, entry_price,
                max_price_reached, max_roi, outcome,
                signal_source, created_at, narrative_tags
            FROM signals
            WHERE signal_posted = TRUE
              AND created_at < '{TRANSITION_DATE}'::timestamptz
            ORDER BY created_at DESC
        """)

        print(f"{'─'*70}")
        print(f"  ERA 1: KOL-BASED SCORING (before {TRANSITION_DATE[:10]})")
        print(f"{'─'*70}")
        _print_era_stats(kol_signals, "KOL")

        # ================================================================
        # 3. ON-CHAIN ERA (after transition)
        # ================================================================
        onchain_signals = await conn.fetch(f"""
            SELECT
                token_symbol, conviction_score, entry_price,
                max_price_reached, max_roi, outcome,
                signal_source, created_at, narrative_tags
            FROM signals
            WHERE signal_posted = TRUE
              AND created_at >= '{TRANSITION_DATE}'::timestamptz
            ORDER BY created_at DESC
        """)

        print(f"\n{'─'*70}")
        print(f"  ERA 2: ON-CHAIN-FIRST SCORING (after {TRANSITION_DATE[:10]})")
        print(f"{'─'*70}")
        _print_era_stats(onchain_signals, "ON-CHAIN")

        # ================================================================
        # 4. BY SIGNAL SOURCE (all time)
        # ================================================================
        source_stats = await conn.fetch("""
            SELECT
                COALESCE(signal_source, 'unknown') as source,
                COUNT(*) as total,
                SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                ROUND(AVG(max_roi)::numeric, 2) as avg_roi,
                ROUND(MAX(max_roi)::numeric, 2) as best_roi
            FROM signals
            WHERE signal_posted = TRUE
            GROUP BY COALESCE(signal_source, 'unknown')
            ORDER BY total DESC
        """)

        print(f"\n{'─'*70}")
        print(f"  BY SIGNAL SOURCE (all time)")
        print(f"{'─'*70}")
        print(f"\n  {'Source':<20} {'Total':>6} {'Wins':>6} {'Rugs':>6} {'Loss':>6} {'Pend':>6} {'WR%':>7} {'AvgROI':>8} {'Best':>8}")
        print(f"  {'─'*20} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*8} {'─'*8}")
        for row in source_stats:
            decided = row['total'] - row['pending']
            wr = (row['wins'] / decided * 100) if decided > 0 else 0
            print(f"  {row['source']:<20} {row['total']:>6} {row['wins']:>6} {row['rugs']:>6} "
                  f"{row['losses']:>6} {row['pending']:>6} {wr:>6.1f}% "
                  f"{row['avg_roi'] or 0:>7.2f}x {row['best_roi'] or 0:>7.1f}x")

        # ================================================================
        # 5. BY CONVICTION SCORE BAND
        # ================================================================
        score_stats = await conn.fetch("""
            SELECT
                CASE
                    WHEN conviction_score >= 80 THEN '80-100'
                    WHEN conviction_score >= 70 THEN '70-79'
                    WHEN conviction_score >= 60 THEN '60-69'
                    WHEN conviction_score >= 50 THEN '50-59'
                    ELSE '<50'
                END as band,
                COUNT(*) as total,
                SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                ROUND(AVG(max_roi)::numeric, 2) as avg_roi
            FROM signals
            WHERE signal_posted = TRUE
            GROUP BY band
            ORDER BY band DESC
        """)

        print(f"\n{'─'*70}")
        print(f"  BY CONVICTION SCORE BAND")
        print(f"{'─'*70}")
        print(f"\n  {'Band':<10} {'Total':>6} {'Wins':>6} {'Rugs':>6} {'Pend':>6} {'WR%':>7} {'AvgROI':>8}")
        print(f"  {'─'*10} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*8}")
        for row in score_stats:
            decided = row['total'] - row['pending']
            wr = (row['wins'] / decided * 100) if decided > 0 else 0
            print(f"  {row['band']:<10} {row['total']:>6} {row['wins']:>6} {row['rugs']:>6} "
                  f"{row['pending']:>6} {wr:>6.1f}% {row['avg_roi'] or 0:>7.2f}x")

        # ================================================================
        # 6. RECENT ON-CHAIN SIGNALS (last 48h detail)
        # ================================================================
        recent = await conn.fetch(f"""
            SELECT
                token_symbol, conviction_score, entry_price,
                max_price_reached, outcome, signal_source, created_at
            FROM signals
            WHERE signal_posted = TRUE
              AND created_at >= '{TRANSITION_DATE}'::timestamptz
            ORDER BY created_at DESC
            LIMIT 30
        """)

        if recent:
            print(f"\n{'─'*70}")
            print(f"  RECENT ON-CHAIN SIGNALS (detail)")
            print(f"{'─'*70}")
            print(f"\n  {'Symbol':<12} {'Score':>5} {'Entry':>14} {'Peak':>8} {'Outcome':<10} {'Source':<15} {'Age'}")
            print(f"  {'─'*12} {'─'*5} {'─'*14} {'─'*8} {'─'*10} {'─'*15} {'─'*10}")
            now = datetime.now(timezone.utc)
            for row in recent:
                sym = (row['token_symbol'] or '?')[:11]
                score = row['conviction_score'] or 0
                entry = row['entry_price'] or 0
                peak = row['max_price_reached'] or 0
                peak_x = f"{peak/entry:.1f}x" if entry > 0 and peak > 0 else "?"
                outcome = row['outcome'] or 'pending'
                source = (row['signal_source'] or 'unknown')[:14]
                age_h = (now - row['created_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
                print(f"  {sym:<12} {score:>5} ${entry:>13.8f} {peak_x:>8} {outcome:<10} {source:<15} {age_h:.1f}h")

        # ================================================================
        # 7. DAILY WIN RATE TREND (last 7 days)
        # ================================================================
        daily = await conn.fetch("""
            SELECT
                DATE(created_at) as day,
                COUNT(*) as total,
                SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                ROUND(AVG(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 2) as avg_roi
            FROM signals
            WHERE signal_posted = TRUE
              AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """)

        if daily:
            print(f"\n{'─'*70}")
            print(f"  DAILY TREND (last 7 days)")
            print(f"{'─'*70}")
            print(f"\n  {'Date':<12} {'Total':>6} {'Wins':>6} {'Rugs':>6} {'Pend':>6} {'WR%':>7} {'AvgROI':>8}")
            print(f"  {'─'*12} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*8}")
            for row in daily:
                decided = row['total'] - row['pending']
                wr = (row['wins'] / decided * 100) if decided > 0 else 0
                day_str = row['day'].strftime('%Y-%m-%d')
                # Mark transition day
                marker = " <-- ON-CHAIN" if day_str == '2026-01-27' else ""
                print(f"  {day_str:<12} {row['total']:>6} {row['wins']:>6} {row['rugs']:>6} "
                      f"{row['pending']:>6} {wr:>6.1f}% {row['avg_roi'] or 0:>7.2f}x{marker}")

        print(f"\n{'='*70}")
        print(f"  NOTE: On-chain era started ~{TRANSITION_DATE[:16]} UTC")
        print(f"  Outcomes take 24-48h to determine — recent signals may show 'pending'")
        print(f"{'='*70}\n")

    await pool.close()


def _print_era_stats(signals, era_name):
    if not signals:
        print(f"\n  No signals in {era_name} era.\n")
        return

    total = len(signals)
    outcomes = [s for s in signals if s['outcome']]
    pending = total - len(outcomes)

    wins = len([s for s in outcomes if s['outcome'] in ('2x', '5x', '10x', '50x', '100x')])
    rugs = len([s for s in outcomes if s['outcome'] == 'rug'])
    losses = len([s for s in outcomes if s['outcome'] == 'loss'])

    # Outcome breakdown
    outcome_counts = {}
    for s in outcomes:
        oc = s['outcome']
        outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

    decided = len(outcomes)
    win_rate = (wins / decided * 100) if decided > 0 else 0
    rug_rate = (rugs / decided * 100) if decided > 0 else 0

    # ROI stats
    rois = [s['max_roi'] for s in signals if s['max_roi'] is not None and s['max_roi'] > 0]
    avg_roi = sum(rois) / len(rois) if rois else 0
    best_roi = max(rois) if rois else 0
    median_roi = sorted(rois)[len(rois)//2] if rois else 0

    # Score stats
    scores = [s['conviction_score'] for s in signals if s['conviction_score']]
    avg_score = sum(scores) / len(scores) if scores else 0

    print(f"\n  Signals: {total} ({pending} pending outcome)")
    print(f"  Decided: {decided}")
    print()
    print(f"  WIN RATE:  {win_rate:.1f}%  ({wins} wins / {decided} decided)")
    print(f"  RUG RATE:  {rug_rate:.1f}%  ({rugs} rugs)")
    print(f"  LOSS RATE: {(losses/decided*100) if decided else 0:.1f}%  ({losses} losses)")
    print()
    print(f"  Outcome breakdown:")
    for oc in ['100x', '50x', '10x', '5x', '2x', 'loss', 'rug']:
        count = outcome_counts.get(oc, 0)
        bar = '#' * count
        if count > 0:
            print(f"    {oc:>5}: {count:>4}  {bar}")
    print()
    print(f"  Avg ROI:    {avg_roi:.2f}x")
    print(f"  Median ROI: {median_roi:.2f}x")
    print(f"  Best ROI:   {best_roi:.1f}x")
    print(f"  Avg Score:  {avg_score:.0f}/100")

    # Source breakdown for this era
    sources = {}
    for s in signals:
        src = s['signal_source'] or 'unknown'
        if src not in sources:
            sources[src] = 0
        sources[src] += 1
    if sources:
        print(f"\n  Signal sources:")
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"    {src}: {count}")


if __name__ == '__main__':
    asyncio.run(run())
