"""
Rug Source Analysis - Identify where rugs are coming from

Analyzes signal outcomes by source to determine if rugs are coming from:
- KOL buys
- Telegram calls
- Other sources

Usage:
    python analyze_rug_sources.py [--days 7]
"""
import asyncio
import os
import sys
from database import Database
from datetime import datetime, timedelta
from typing import Dict, List


async def analyze_rug_sources(days: int = 7):
    """
    Analyze signal outcomes by source to identify rug patterns

    Args:
        days: Number of days to analyze (default: 7)
    """
    db = Database()
    await db.connect()

    print("=" * 100)
    print(f"🔍 RUG SOURCE ANALYSIS - Last {days} Days")
    print("=" * 100)

    async with db.pool.acquire() as conn:
        # =================================================================
        # SECTION 1: OVERALL SIGNAL BREAKDOWN BY SOURCE
        # =================================================================
        print(f"\n{'='*100}")
        print("📊 SIGNAL BREAKDOWN BY SOURCE")
        print("=" * 100)

        source_breakdown = await conn.fetch('''
            SELECT
                signal_source,
                COUNT(*) as total_signals,
                SUM(CASE WHEN signal_posted = TRUE THEN 1 ELSE 0 END) as posted_count,
                SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) as has_outcome,
                AVG(conviction_score) as avg_conviction
            FROM signals
            WHERE created_at >= NOW() - INTERVAL '{} days'
            GROUP BY signal_source
            ORDER BY total_signals DESC
        '''.format(days))

        if source_breakdown:
            print(f"\n{'Source':<20} | {'Total':<8} | {'Posted':<8} | {'Has Outcome':<12} | {'Avg Conviction':<15}")
            print("-" * 100)
            for row in source_breakdown:
                source = row['signal_source'] or 'unknown'
                total = row['total_signals']
                posted = row['posted_count']
                has_outcome = row['has_outcome']
                avg_conv = row['avg_conviction'] or 0

                print(f"{source:<20} | {total:<8} | {posted:<8} | {has_outcome:<12} | {avg_conv:<15.1f}")
        else:
            print("  No signals found in this time period")

        # =================================================================
        # SECTION 2: OUTCOME BREAKDOWN BY SOURCE
        # =================================================================
        print(f"\n{'='*100}")
        print("💰 OUTCOME BREAKDOWN BY SOURCE")
        print("=" * 100)

        outcome_breakdown = await conn.fetch('''
            SELECT
                signal_source,
                outcome,
                COUNT(*) as count,
                AVG(max_roi) as avg_roi
            FROM signals
            WHERE created_at >= NOW() - INTERVAL '{} days'
            AND outcome IS NOT NULL
            GROUP BY signal_source, outcome
            ORDER BY signal_source, outcome
        '''.format(days))

        if outcome_breakdown:
            current_source = None
            for row in outcome_breakdown:
                source = row['signal_source'] or 'unknown'
                outcome = row['outcome']
                count = row['count']
                avg_roi = row['avg_roi'] or 0

                if source != current_source:
                    print(f"\n{source.upper()}:")
                    current_source = source

                print(f"  {outcome:<15}: {count:>3} signals (avg ROI: {avg_roi:>6.1f}%)")
        else:
            print("  No outcome data available")

        # =================================================================
        # SECTION 3: RUG RATE BY SOURCE
        # =================================================================
        print(f"\n{'='*100}")
        print("🚨 RUG RATE ANALYSIS BY SOURCE")
        print("=" * 100)

        rug_analysis = await conn.fetch('''
            SELECT
                signal_source,
                COUNT(*) as total_with_outcome,
                SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rug_count,
                SUM(CASE WHEN outcome IN ('2x', '5x', '10x', '50x', '100x') THEN 1 ELSE 0 END) as win_count,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as loss_count,
                ROUND(
                    100.0 * SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(*), 0),
                    2
                ) as rug_rate_pct,
                ROUND(
                    100.0 * SUM(CASE WHEN outcome IN ('2x', '5x', '10x', '50x', '100x') THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(*), 0),
                    2
                ) as win_rate_pct
            FROM signals
            WHERE created_at >= NOW() - INTERVAL '{} days'
            AND outcome IS NOT NULL
            GROUP BY signal_source
            ORDER BY rug_rate_pct DESC
        '''.format(days))

        if rug_analysis:
            print(f"\n{'Source':<20} | {'Total':<7} | {'Rugs':<6} | {'Wins':<6} | {'Losses':<7} | {'Rug Rate':<10} | {'Win Rate':<10}")
            print("-" * 100)

            total_rugs = 0
            total_signals = 0
            worst_source = None
            best_source = None

            for row in rug_analysis:
                source = row['signal_source'] or 'unknown'
                total = row['total_with_outcome']
                rugs = row['rug_count']
                wins = row['win_count']
                losses = row['loss_count']
                rug_rate = row['rug_rate_pct'] or 0
                win_rate = row['win_rate_pct'] or 0

                total_rugs += rugs
                total_signals += total

                if worst_source is None or rug_rate > worst_source['rate']:
                    worst_source = {'source': source, 'rate': rug_rate, 'count': rugs}

                if best_source is None or rug_rate < best_source['rate']:
                    best_source = {'source': source, 'rate': rug_rate, 'count': rugs}

                # Add warning emoji for high rug rates
                warning = "🚨" if rug_rate > 50 else ("⚠️" if rug_rate > 30 else "")

                print(f"{source:<20} | {total:<7} | {rugs:<6} | {wins:<6} | {losses:<7} | {rug_rate:<9.1f}% | {win_rate:<9.1f}% {warning}")

            # Summary
            overall_rug_rate = (total_rugs / total_signals * 100) if total_signals > 0 else 0
            print("\n" + "=" * 100)
            print(f"📈 OVERALL: {total_rugs} rugs out of {total_signals} signals ({overall_rug_rate:.1f}% rug rate)")

            if worst_source:
                print(f"🚨 WORST SOURCE: {worst_source['source']} ({worst_source['rate']:.1f}% rug rate, {worst_source['count']} rugs)")
            if best_source:
                print(f"✅ BEST SOURCE: {best_source['source']} ({best_source['rate']:.1f}% rug rate, {best_source['count']} rugs)")
        else:
            print("  No outcome data available for rug analysis")

        # =================================================================
        # SECTION 4: RECENT RUGS BY SOURCE
        # =================================================================
        print(f"\n{'='*100}")
        print("📋 RECENT RUGS (Last 20)")
        print("=" * 100)

        recent_rugs = await conn.fetch('''
            SELECT
                signal_source,
                token_symbol,
                token_address,
                conviction_score,
                created_at,
                outcome_timestamp,
                max_roi
            FROM signals
            WHERE created_at >= NOW() - INTERVAL '{} days'
            AND outcome = 'rug'
            ORDER BY created_at DESC
            LIMIT 20
        '''.format(days))

        if recent_rugs:
            print(f"\n{'Date':<12} | {'Source':<15} | {'Symbol':<10} | {'Conv':<5} | {'Max ROI':<8} | {'Address':<20}")
            print("-" * 100)

            for rug in recent_rugs:
                source = rug['signal_source'] or 'unknown'
                symbol = rug['token_symbol'] or 'UNKNOWN'
                conv = rug['conviction_score']
                max_roi = rug['max_roi'] or 0
                created = rug['created_at'].strftime('%Y-%m-%d') if rug['created_at'] else 'N/A'
                address = rug['token_address'][:20] if rug['token_address'] else 'N/A'

                print(f"{created:<12} | {source:<15} | {symbol:<10} | {conv:<5} | {max_roi:<7.1f}% | {address:<20}")
        else:
            print("  No recent rugs found")

        # =================================================================
        # SECTION 5: CORRELATION ANALYSIS
        # =================================================================
        print(f"\n{'='*100}")
        print("🔗 CORRELATION: Telegram Calls + KOL Buys")
        print("=" * 100)

        # Find tokens that had BOTH telegram calls AND were tracked (implying KOL activity)
        correlation = await conn.fetch('''
            SELECT
                s.token_address,
                s.token_symbol,
                s.signal_source,
                s.outcome,
                s.conviction_score,
                COUNT(DISTINCT tc.group_name) as tg_group_count,
                COUNT(tc.id) as tg_call_count
            FROM signals s
            LEFT JOIN telegram_calls tc ON s.token_address = tc.token_address
            WHERE s.created_at >= NOW() - INTERVAL '{} days'
            AND s.outcome IS NOT NULL
            GROUP BY s.token_address, s.token_symbol, s.signal_source, s.outcome, s.conviction_score
            HAVING COUNT(tc.id) > 0
            ORDER BY s.outcome, s.created_at DESC
            LIMIT 20
        '''.format(days))

        if correlation:
            print(f"\n{'Symbol':<10} | {'Source':<15} | {'Outcome':<10} | {'TG Groups':<10} | {'TG Calls':<10} | {'Conviction':<11}")
            print("-" * 100)

            for row in correlation:
                symbol = row['token_symbol'] or 'UNKNOWN'
                source = row['signal_source'] or 'unknown'
                outcome = row['outcome']
                tg_groups = row['tg_group_count']
                tg_calls = row['tg_call_count']
                conv = row['conviction_score']

                print(f"{symbol:<10} | {source:<15} | {outcome:<10} | {tg_groups:<10} | {tg_calls:<10} | {conv:<11}")
        else:
            print("  No correlation data available (telegram_calls table may be empty)")

        # =================================================================
        # SECTION 6: ACTIONABLE INSIGHTS
        # =================================================================
        print(f"\n{'='*100}")
        print("💡 ACTIONABLE INSIGHTS")
        print("=" * 100)

        if rug_analysis:
            for row in rug_analysis:
                source = row['signal_source'] or 'unknown'
                rug_rate = row['rug_rate_pct'] or 0
                win_rate = row['win_rate_pct'] or 0
                total = row['total_with_outcome']

                if rug_rate > 50:
                    print(f"\n🚨 CRITICAL: '{source}' source has {rug_rate:.1f}% rug rate!")
                    print(f"   Recommendation: Consider disabling or reducing weight for this source")
                    print(f"   Or add stricter rug detection filters for {source} signals")

                elif rug_rate > 30:
                    print(f"\n⚠️  WARNING: '{source}' source has {rug_rate:.1f}% rug rate")
                    print(f"   Recommendation: Add additional filters or reduce conviction bonus")

                elif rug_rate < 20 and win_rate > 40:
                    print(f"\n✅ EXCELLENT: '{source}' source has only {rug_rate:.1f}% rug rate with {win_rate:.1f}% win rate")
                    print(f"   Recommendation: Consider increasing weight or conviction bonus for this source")

        print("\n" + "=" * 100)

    await db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Analyze rug sources')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')
    args = parser.parse_args()

    asyncio.run(analyze_rug_sources(days=args.days))
