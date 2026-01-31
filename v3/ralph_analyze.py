"""
RALPH - Signal Performance Analyzer for V3
Run: python v3/ralph_analyze.py

Analyzes V2 signal data to find optimal V3 config settings.
"""
import asyncio
import asyncpg
import os


async def main():
    # Connect directly to v2 database
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)

    print("=" * 60)
    print("RALPH - V3 Configuration Analysis")
    print("=" * 60)

    # Get total signals with outcomes
    total = await conn.fetchval('''
        SELECT COUNT(*) FROM signals
        WHERE outcome IS NOT NULL
        AND signal_posted = TRUE
    ''')

    if total == 0:
        print("\n❌ No signals with outcomes yet. Need more data.")
        await conn.close()
        return

    print(f"\nAnalyzing {total} signals with outcomes...\n")

    # =====================================================================
    # 1. OVERALL WIN RATE
    # =====================================================================
    print("=" * 60)
    print("1. OVERALL PERFORMANCE")
    print("=" * 60)

    stats = await conn.fetchrow('''
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins,
            COUNT(*) FILTER (WHERE outcome = 'rug') as rugs,
            AVG(max_roi) as avg_max_mult,
            MAX(max_roi) as best_mult
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE
    ''')

    wr = (stats['wins'] / stats['total'] * 100) if stats['total'] else 0
    print(f"Total Signals: {stats['total']}")
    print(f"Wins: {stats['wins']} | Rugs: {stats['rugs']}")
    print(f"Win Rate: {wr:.1f}%")
    if stats['avg_max_mult']:
        print(f"Avg Max Multiplier: {stats['avg_max_mult']:.2f}x")
    if stats['best_mult']:
        print(f"Best Performer: {stats['best_mult']:.2f}x")

    # =====================================================================
    # 2. BY WALLET/KOL
    # =====================================================================
    print("\n" + "=" * 60)
    print("2. WIN RATE BY KOL")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            COALESCE(
                (SELECT wallet_name FROM smart_wallet_activity swa
                 WHERE swa.token_address = s.token_address LIMIT 1),
                'Organic'
            ) as source,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins,
            AVG(max_roi) as avg_mult
        FROM signals s
        WHERE outcome IS NOT NULL AND signal_posted = TRUE
        GROUP BY source
        HAVING COUNT(*) >= 3
        ORDER BY (COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')))::float / NULLIF(COUNT(*), 0) DESC
        LIMIT 15
    ''')

    print(f"{'Source':<20} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
    print("-" * 60)
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        mult = r['avg_mult'] or 1.0
        marker = " ★" if wr >= 40 else ""
        print(f"{r['source'][:20]:<20} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {mult:<10.2f}x{marker}")

    # =====================================================================
    # 3. BY MCAP RANGE (Critical for MAX_MCAP setting)
    # =====================================================================
    print("\n" + "=" * 60)
    print("3. WIN RATE BY ENTRY MCAP → Determines MAX_MCAP setting")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            CASE
                WHEN market_cap < 5000 THEN '< $5K'
                WHEN market_cap < 10000 THEN '$5K-10K'
                WHEN market_cap < 15000 THEN '$10K-15K'
                WHEN market_cap < 20000 THEN '$15K-20K'
                WHEN market_cap < 30000 THEN '$20K-30K'
                WHEN market_cap < 50000 THEN '$30K-50K'
                WHEN market_cap < 75000 THEN '$50K-75K'
                ELSE '$75K+'
            END as mcap_range,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins,
            AVG(max_roi) as avg_mult
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE AND market_cap IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(market_cap)
    ''')

    print(f"{'MCAP Range':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
    print("-" * 55)
    best_mcap_wr = 0
    best_mcap_range = None
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        mult = r['avg_mult'] or 1.0
        marker = " ★ BEST" if r['signals'] >= 5 and wr > best_mcap_wr else ""
        if r['signals'] >= 5 and wr > best_mcap_wr:
            best_mcap_wr = wr
            best_mcap_range = r['mcap_range']
        print(f"{r['mcap_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {mult:<10.2f}x{marker}")

    # =====================================================================
    # 4. BY LIQUIDITY RANGE (Critical for MIN_LIQUIDITY setting)
    # =====================================================================
    print("\n" + "=" * 60)
    print("4. WIN RATE BY ENTRY LIQUIDITY → Determines MIN_LIQUIDITY setting")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            CASE
                WHEN liquidity < 5000 THEN '< $5K'
                WHEN liquidity < 10000 THEN '$5K-10K'
                WHEN liquidity < 15000 THEN '$10K-15K'
                WHEN liquidity < 20000 THEN '$15K-20K'
                WHEN liquidity < 30000 THEN '$20K-30K'
                WHEN liquidity < 50000 THEN '$30K-50K'
                ELSE '$50K+'
            END as liq_range,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins,
            AVG(max_roi) as avg_mult
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE AND liquidity IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(liquidity)
    ''')

    print(f"{'Liquidity':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
    print("-" * 55)
    best_liq_wr = 0
    best_liq_range = None
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        mult = r['avg_mult'] or 1.0
        marker = " ★ BEST" if r['signals'] >= 5 and wr > best_liq_wr else ""
        if r['signals'] >= 5 and wr > best_liq_wr:
            best_liq_wr = wr
            best_liq_range = r['liq_range']
        print(f"{r['liq_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {mult:<10.2f}x{marker}")

    # =====================================================================
    # 5. BY CONVICTION SCORE (Critical for MIN_SCORE setting)
    # =====================================================================
    print("\n" + "=" * 60)
    print("5. WIN RATE BY CONVICTION SCORE → Determines MIN_SCORE setting")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            CASE
                WHEN conviction_score < 30 THEN '< 30'
                WHEN conviction_score < 40 THEN '30-40'
                WHEN conviction_score < 50 THEN '40-50'
                WHEN conviction_score < 60 THEN '50-60'
                WHEN conviction_score < 70 THEN '60-70'
                WHEN conviction_score < 80 THEN '70-80'
                ELSE '80+'
            END as score_range,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins,
            AVG(max_roi) as avg_mult
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE AND conviction_score IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(conviction_score)
    ''')

    print(f"{'Score':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
    print("-" * 55)
    best_score_wr = 0
    best_score_range = None
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        mult = r['avg_mult'] or 1.0
        marker = " ★ BEST" if r['signals'] >= 5 and wr > best_score_wr else ""
        if r['signals'] >= 5 and wr > best_score_wr:
            best_score_wr = wr
            best_score_range = r['score_range']
        print(f"{r['score_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {mult:<10.2f}x{marker}")

    # =====================================================================
    # 6. BY HOUR OF DAY (UTC)
    # =====================================================================
    print("\n" + "=" * 60)
    print("6. WIN RATE BY HOUR (UTC)")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            EXTRACT(HOUR FROM created_at) as hour,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE AND created_at IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    ''')

    overall_wr = (stats['wins'] / stats['total'] * 100) if stats['total'] else 0
    print(f"{'Hour':<10} {'Signals':<10} {'WR%':<10} {'Bar'}")
    print("-" * 50)
    best_hours = []
    worst_hours = []
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        bar_len = int(wr / 5)
        bar = "█" * bar_len
        marker = ""
        if r['signals'] >= 5:
            if wr >= overall_wr + 15:
                marker = " ★ BEST"
                best_hours.append(int(r['hour']))
            elif wr <= overall_wr - 15:
                marker = " ✗ AVOID"
                worst_hours.append(int(r['hour']))
        print(f"{int(r['hour']):02d}:00     {r['signals']:<10} {wr:<10.0f} {bar}{marker}")

    # =====================================================================
    # 7. BY DAY OF WEEK
    # =====================================================================
    print("\n" + "=" * 60)
    print("7. WIN RATE BY DAY OF WEEK")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            EXTRACT(DOW FROM created_at) as dow,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome IN ('2x','5x','10x','50x','100x')) as wins
        FROM signals
        WHERE outcome IS NOT NULL AND signal_posted = TRUE AND created_at IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    ''')

    days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    print(f"{'Day':<10} {'Signals':<10} {'WR%':<10} {'Bar'}")
    print("-" * 50)
    for r in rows:
        wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
        bar_len = int(wr / 5)
        bar = "█" * bar_len
        marker = ""
        if r['signals'] >= 5:
            if wr >= overall_wr + 10:
                marker = " ★"
            elif wr <= overall_wr - 10:
                marker = " ✗"
        day_name = days[int(r['dow'])]
        print(f"{day_name:<10} {r['signals']:<10} {wr:<10.0f} {bar}{marker}")

    # =====================================================================
    # 8. TOP PERFORMING TOKENS (for validation)
    # =====================================================================
    print("\n" + "=" * 60)
    print("8. TOP PERFORMERS (10x+)")
    print("=" * 60)

    rows = await conn.fetch('''
        SELECT
            token_symbol,
            market_cap,
            liquidity,
            conviction_score,
            max_roi,
            outcome
        FROM signals
        WHERE outcome IN ('10x','50x','100x') AND signal_posted = TRUE
        ORDER BY max_roi DESC
        LIMIT 10
    ''')

    print(f"{'Symbol':<12} {'MCAP':<12} {'Liq':<12} {'Score':<8} {'ROI':<10}")
    print("-" * 55)
    for r in rows:
        mcap = f"${r['market_cap']/1000:.0f}K" if r['market_cap'] else "-"
        liq = f"${r['liquidity']/1000:.0f}K" if r['liquidity'] else "-"
        roi = f"{r['max_roi']:.1f}x" if r['max_roi'] else "-"
        print(f"{r['token_symbol'] or 'UNKNOWN':<12} {mcap:<12} {liq:<12} {r['conviction_score'] or 0:<8} {roi:<10}")

    # =====================================================================
    # 9. RECOMMENDATIONS FOR V3 CONFIG
    # =====================================================================
    print("\n" + "=" * 60)
    print("9. V3 CONFIG RECOMMENDATIONS")
    print("=" * 60)

    print("\nBased on your data:\n")

    # Current v3 defaults
    print("Current V3 defaults:")
    print("  MIN_SCORE = 60")
    print("  MIN_LIQUIDITY = 20000")
    print("  MAX_MCAP = 50000")
    print()

    print("Data-driven recommendations:")
    if best_mcap_range:
        print(f"  ✓ Best MCAP range: {best_mcap_range} ({best_mcap_wr:.0f}% WR)")
    if best_liq_range:
        print(f"  ✓ Best liquidity range: {best_liq_range} ({best_liq_wr:.0f}% WR)")
    if best_score_range:
        print(f"  ✓ Best score range: {best_score_range} ({best_score_wr:.0f}% WR)")
    if best_hours:
        print(f"  ✓ Best hours (UTC): {', '.join(f'{h}:00' for h in best_hours[:3])}")
    if worst_hours:
        print(f"  ✗ Avoid hours (UTC): {', '.join(f'{h}:00' for h in worst_hours[:3])}")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
