"""
RALPH - Signal Performance Analyzer
Run: python v3/ralph_analyze.py

Analyzes all signal data to find what actually works.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    import database as db

    print("=" * 60)
    print("RALPH - Signal Performance Analysis")
    print("=" * 60)

    await db.init_db()
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        # Total signals
        total = await conn.fetchval('''
            SELECT COUNT(*) FROM signals WHERE outcome IS NOT NULL
        ''')

        if total == 0:
            print("\n❌ No signals with outcomes yet. Need more data.")
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
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                COUNT(*) FILTER (WHERE outcome = 'rug') as rugs,
                AVG(max_multiplier) as avg_max_mult,
                MAX(max_multiplier) as best_mult
            FROM signals
            WHERE outcome IS NOT NULL
        ''')

        wr = (stats['wins'] / stats['total'] * 100) if stats['total'] else 0
        print(f"Total Signals: {stats['total']}")
        print(f"Wins: {stats['wins']} | Rugs: {stats['rugs']}")
        print(f"Win Rate: {wr:.1f}%")
        print(f"Avg Max Multiplier: {stats['avg_max_mult']:.2f}x")
        print(f"Best Performer: {stats['best_mult']:.2f}x")

        # =====================================================================
        # 2. BY WALLET TIER
        # =====================================================================
        print("\n" + "=" * 60)
        print("2. WIN RATE BY WALLET TIER")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                wallet_tier,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                AVG(max_multiplier) as avg_mult
            FROM signals
            WHERE outcome IS NOT NULL AND wallet_tier IS NOT NULL
            GROUP BY wallet_tier
            ORDER BY (COUNT(*) FILTER (WHERE outcome = 'win'))::float / NULLIF(COUNT(*), 0) DESC
        ''')

        print(f"{'Tier':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
        print("-" * 55)
        for r in rows:
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            print(f"{r['wallet_tier'] or 'unknown':<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {r['avg_mult'] or 0:<10.2f}x")

        # =====================================================================
        # 3. BY MCAP RANGE
        # =====================================================================
        print("\n" + "=" * 60)
        print("3. WIN RATE BY ENTRY MCAP")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                CASE
                    WHEN entry_mcap < 5000 THEN '< $5K'
                    WHEN entry_mcap < 10000 THEN '$5K-10K'
                    WHEN entry_mcap < 15000 THEN '$10K-15K'
                    WHEN entry_mcap < 20000 THEN '$15K-20K'
                    WHEN entry_mcap < 30000 THEN '$20K-30K'
                    WHEN entry_mcap < 50000 THEN '$30K-50K'
                    ELSE '$50K+'
                END as mcap_range,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                AVG(max_multiplier) as avg_mult
            FROM signals
            WHERE outcome IS NOT NULL AND entry_mcap IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(entry_mcap)
        ''')

        print(f"{'MCAP Range':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
        print("-" * 55)
        for r in rows:
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            marker = " ★" if wr >= 40 else ""
            print(f"{r['mcap_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {r['avg_mult'] or 0:<10.2f}x{marker}")

        # =====================================================================
        # 4. BY LIQUIDITY RANGE
        # =====================================================================
        print("\n" + "=" * 60)
        print("4. WIN RATE BY ENTRY LIQUIDITY")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                CASE
                    WHEN entry_liquidity < 5000 THEN '< $5K'
                    WHEN entry_liquidity < 10000 THEN '$5K-10K'
                    WHEN entry_liquidity < 20000 THEN '$10K-20K'
                    WHEN entry_liquidity < 30000 THEN '$20K-30K'
                    WHEN entry_liquidity < 50000 THEN '$30K-50K'
                    ELSE '$50K+'
                END as liq_range,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                AVG(max_multiplier) as avg_mult
            FROM signals
            WHERE outcome IS NOT NULL AND entry_liquidity IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(entry_liquidity)
        ''')

        print(f"{'Liquidity':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
        print("-" * 55)
        for r in rows:
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            marker = " ★" if wr >= 40 else ""
            print(f"{r['liq_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {r['avg_mult'] or 0:<10.2f}x{marker}")

        # =====================================================================
        # 5. BY SCORE RANGE
        # =====================================================================
        print("\n" + "=" * 60)
        print("5. WIN RATE BY CONVICTION SCORE")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                CASE
                    WHEN score < 30 THEN '< 30'
                    WHEN score < 40 THEN '30-40'
                    WHEN score < 50 THEN '40-50'
                    WHEN score < 60 THEN '50-60'
                    WHEN score < 70 THEN '60-70'
                    WHEN score < 80 THEN '70-80'
                    ELSE '80+'
                END as score_range,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                AVG(max_multiplier) as avg_mult
            FROM signals
            WHERE outcome IS NOT NULL AND score IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(score)
        ''')

        print(f"{'Score':<15} {'Signals':<10} {'Wins':<8} {'WR%':<8} {'Avg Mult':<10}")
        print("-" * 55)
        for r in rows:
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            marker = " ★" if wr >= 40 else ""
            print(f"{r['score_range']:<15} {r['signals']:<10} {r['wins']:<8} {wr:<8.1f} {r['avg_mult'] or 0:<10.2f}x{marker}")

        # =====================================================================
        # 6. BY HOUR OF DAY (UTC)
        # =====================================================================
        print("\n" + "=" * 60)
        print("6. WIN RATE BY HOUR (UTC)")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                EXTRACT(HOUR FROM posted_at) as hour,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins
            FROM signals
            WHERE outcome IS NOT NULL AND posted_at IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        ''')

        print(f"{'Hour':<10} {'Signals':<10} {'WR%':<10} {'Bar'}")
        print("-" * 50)
        for r in rows:
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            bar = "█" * int(wr / 5)
            marker = " ★ BEST" if wr >= 50 else (" ✗ AVOID" if wr < 20 else "")
            print(f"{int(r['hour']):02d}:00     {r['signals']:<10} {wr:<10.0f} {bar}{marker}")

        # =====================================================================
        # 7. TOP PERFORMING WALLETS
        # =====================================================================
        print("\n" + "=" * 60)
        print("7. TOP PERFORMING WALLETS")
        print("=" * 60)

        rows = await conn.fetch('''
            SELECT
                w.name,
                w.address,
                w.tier,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE s.outcome = 'win') as wins,
                AVG(s.max_multiplier) as avg_mult
            FROM wallets w
            JOIN signals s ON s.wallet_address = w.address
            WHERE s.outcome IS NOT NULL
            GROUP BY w.address, w.name, w.tier
            HAVING COUNT(*) >= 3
            ORDER BY (COUNT(*) FILTER (WHERE s.outcome = 'win'))::float / COUNT(*) DESC
            LIMIT 10
        ''')

        print(f"{'Wallet':<20} {'Tier':<12} {'Signals':<10} {'WR%':<8}")
        print("-" * 55)
        for r in rows:
            name = r['name'] or r['address'][:8]
            wr = (r['wins'] / r['signals'] * 100) if r['signals'] else 0
            print(f"{name:<20} {r['tier']:<12} {r['signals']:<10} {wr:.0f}%")

        # =====================================================================
        # 8. RECOMMENDATIONS
        # =====================================================================
        print("\n" + "=" * 60)
        print("8. RALPH'S RECOMMENDATIONS")
        print("=" * 60)

        # Find best mcap range
        best_mcap = await conn.fetchrow('''
            SELECT
                CASE
                    WHEN entry_mcap < 10000 THEN '< $10K'
                    WHEN entry_mcap < 20000 THEN '$10K-20K'
                    WHEN entry_mcap < 30000 THEN '$20K-30K'
                    ELSE '$30K+'
                END as range,
                COUNT(*) FILTER (WHERE outcome = 'win')::float / NULLIF(COUNT(*), 0) * 100 as wr
            FROM signals
            WHERE outcome IS NOT NULL AND entry_mcap IS NOT NULL
            GROUP BY 1
            HAVING COUNT(*) >= 5
            ORDER BY 2 DESC
            LIMIT 1
        ''')

        # Find best score threshold
        best_score = await conn.fetchrow('''
            SELECT
                score as threshold,
                COUNT(*) FILTER (WHERE outcome = 'win')::float / NULLIF(COUNT(*), 0) * 100 as wr,
                COUNT(*) as total
            FROM signals
            WHERE outcome IS NOT NULL AND score IS NOT NULL
            GROUP BY score
            HAVING COUNT(*) >= 3
            ORDER BY 2 DESC
            LIMIT 1
        ''')

        # Find worst hours
        worst_hours = await conn.fetch('''
            SELECT
                EXTRACT(HOUR FROM posted_at)::int as hour,
                COUNT(*) FILTER (WHERE outcome = 'win')::float / NULLIF(COUNT(*), 0) * 100 as wr
            FROM signals
            WHERE outcome IS NOT NULL
            GROUP BY 1
            HAVING COUNT(*) >= 3
            ORDER BY 2 ASC
            LIMIT 3
        ''')

        print("\nBased on your data:")
        print()
        if best_mcap:
            print(f"  ✓ Best MCAP range: {best_mcap['range']} ({best_mcap['wr']:.0f}% WR)")
        if best_score:
            print(f"  ✓ Best score threshold: {best_score['threshold']}+ ({best_score['wr']:.0f}% WR)")
        if worst_hours:
            hours = [str(int(h['hour'])) for h in worst_hours]
            print(f"  ✗ Avoid hours (UTC): {', '.join(hours)}:00")

        print("\n" + "=" * 60)
        print("Analysis complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
