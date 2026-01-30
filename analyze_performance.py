#!/usr/bin/env python3
"""
Performance Analysis Script - Analyze signal data to find optimal conviction thresholds
and identify what's causing low win rates.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '/home/user/SENTINEL_V2')

from database import Database

async def analyze():
    db = Database()
    await db.connect()

    print("=" * 70)
    print("SENTINEL PERFORMANCE ANALYSIS")
    print("=" * 70)

    # Get all signals with performance data - use last 7 days
    signals = await db.get_signals_in_last_hours(168)  # 7 days

    print(f"\nTotal signals analyzed (7 days): {len(signals)}")

    if not signals:
        print("No signals found!")
        return

    # ===== CONVICTION SCORE ANALYSIS =====
    print("\n" + "=" * 70)
    print("CONVICTION SCORE ANALYSIS")
    print("=" * 70)

    conviction_buckets = {
        "90-100": {"wins": 0, "total": 0, "rois": []},
        "80-89": {"wins": 0, "total": 0, "rois": []},
        "70-79": {"wins": 0, "total": 0, "rois": []},
        "60-69": {"wins": 0, "total": 0, "rois": []},
        "50-59": {"wins": 0, "total": 0, "rois": []},
        "40-49": {"wins": 0, "total": 0, "rois": []},
        "<40": {"wins": 0, "total": 0, "rois": []},
    }

    for s in signals:
        score = s.get('conviction_score') or 0
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0

        if entry > 0 and peak > 0:
            roi = peak / entry
        else:
            roi = 0

        # Determine bucket
        if score >= 90:
            bucket = "90-100"
        elif score >= 80:
            bucket = "80-89"
        elif score >= 70:
            bucket = "70-79"
        elif score >= 60:
            bucket = "60-69"
        elif score >= 50:
            bucket = "50-59"
        elif score >= 40:
            bucket = "40-49"
        else:
            bucket = "<40"

        conviction_buckets[bucket]["total"] += 1
        conviction_buckets[bucket]["rois"].append(roi)
        if roi >= 2.0:
            conviction_buckets[bucket]["wins"] += 1

    print(f"\n{'Score Range':<12} {'Signals':<10} {'2x+ Wins':<10} {'Win Rate':<12} {'Avg Peak ROI':<12}")
    print("-" * 60)

    for bucket, data in conviction_buckets.items():
        if data["total"] > 0:
            wr = (data["wins"] / data["total"]) * 100
            avg_roi = sum(data["rois"]) / len(data["rois"]) if data["rois"] else 0
            print(f"{bucket:<12} {data['total']:<10} {data['wins']:<10} {wr:<11.1f}% {avg_roi:<.2f}x")

    # ===== KOL vs NON-KOL ANALYSIS =====
    print("\n" + "=" * 70)
    print("KOL vs NON-KOL ANALYSIS")
    print("=" * 70)

    kol_data = {"wins": 0, "total": 0, "rois": []}
    non_kol_data = {"wins": 0, "total": 0, "rois": []}

    for s in signals:
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0
        kol_wallets = s.get('kol_wallets') or []

        if entry > 0 and peak > 0:
            roi = peak / entry
        else:
            roi = 0

        if kol_wallets and len(kol_wallets) > 0:
            kol_data["total"] += 1
            kol_data["rois"].append(roi)
            if roi >= 2.0:
                kol_data["wins"] += 1
        else:
            non_kol_data["total"] += 1
            non_kol_data["rois"].append(roi)
            if roi >= 2.0:
                non_kol_data["wins"] += 1

    print(f"\n{'Type':<15} {'Signals':<10} {'2x+ Wins':<10} {'Win Rate':<12} {'Avg Peak ROI':<12}")
    print("-" * 60)

    if kol_data["total"] > 0:
        wr = (kol_data["wins"] / kol_data["total"]) * 100
        avg_roi = sum(kol_data["rois"]) / len(kol_data["rois"]) if kol_data["rois"] else 0
        print(f"{'KOL-backed':<15} {kol_data['total']:<10} {kol_data['wins']:<10} {wr:<11.1f}% {avg_roi:<.2f}x")

    if non_kol_data["total"] > 0:
        wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100
        avg_roi = sum(non_kol_data["rois"]) / len(non_kol_data["rois"]) if non_kol_data["rois"] else 0
        print(f"{'Pure Organic':<15} {non_kol_data['total']:<10} {non_kol_data['wins']:<10} {wr:<11.1f}% {avg_roi:<.2f}x")

    # ===== BONDING CURVE ANALYSIS =====
    print("\n" + "=" * 70)
    print("BONDING CURVE % AT ENTRY ANALYSIS")
    print("=" * 70)

    bc_buckets = {
        "0-20%": {"wins": 0, "total": 0, "rois": []},
        "20-40%": {"wins": 0, "total": 0, "rois": []},
        "40-60%": {"wins": 0, "total": 0, "rois": []},
        "60-80%": {"wins": 0, "total": 0, "rois": []},
        "80-100%": {"wins": 0, "total": 0, "rois": []},
    }

    for s in signals:
        bc = s.get('bonding_curve_pct') or 0
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0

        if entry > 0 and peak > 0:
            roi = peak / entry
        else:
            roi = 0

        if bc <= 20:
            bucket = "0-20%"
        elif bc <= 40:
            bucket = "20-40%"
        elif bc <= 60:
            bucket = "40-60%"
        elif bc <= 80:
            bucket = "60-80%"
        else:
            bucket = "80-100%"

        bc_buckets[bucket]["total"] += 1
        bc_buckets[bucket]["rois"].append(roi)
        if roi >= 2.0:
            bc_buckets[bucket]["wins"] += 1

    print(f"\n{'BC Range':<12} {'Signals':<10} {'2x+ Wins':<10} {'Win Rate':<12} {'Avg Peak ROI':<12}")
    print("-" * 60)

    for bucket, data in bc_buckets.items():
        if data["total"] > 0:
            wr = (data["wins"] / data["total"]) * 100
            avg_roi = sum(data["rois"]) / len(data["rois"]) if data["rois"] else 0
            print(f"{bucket:<12} {data['total']:<10} {data['wins']:<10} {wr:<11.1f}% {avg_roi:<.2f}x")

    # ===== BUY/SELL RATIO ANALYSIS =====
    print("\n" + "=" * 70)
    print("BUY PERCENTAGE ANALYSIS")
    print("=" * 70)

    bs_buckets = {
        "90-100%": {"wins": 0, "total": 0, "rois": []},
        "80-89%": {"wins": 0, "total": 0, "rois": []},
        "70-79%": {"wins": 0, "total": 0, "rois": []},
        "60-69%": {"wins": 0, "total": 0, "rois": []},
        "<60%": {"wins": 0, "total": 0, "rois": []},
    }

    for s in signals:
        buy_pct = s.get('buy_percentage') or 0
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0

        if entry > 0 and peak > 0:
            roi = peak / entry
        else:
            roi = 0

        if buy_pct >= 90:
            bucket = "90-100%"
        elif buy_pct >= 80:
            bucket = "80-89%"
        elif buy_pct >= 70:
            bucket = "70-79%"
        elif buy_pct >= 60:
            bucket = "60-69%"
        else:
            bucket = "<60%"

        bs_buckets[bucket]["total"] += 1
        bs_buckets[bucket]["rois"].append(roi)
        if roi >= 2.0:
            bs_buckets[bucket]["wins"] += 1

    print(f"\n{'Buy %':<12} {'Signals':<10} {'2x+ Wins':<10} {'Win Rate':<12} {'Avg Peak ROI':<12}")
    print("-" * 60)

    for bucket, data in bs_buckets.items():
        if data["total"] > 0:
            wr = (data["wins"] / data["total"]) * 100
            avg_roi = sum(data["rois"]) / len(data["rois"]) if data["rois"] else 0
            print(f"{bucket:<12} {data['total']:<10} {data['wins']:<10} {wr:<11.1f}% {avg_roi:<.2f}x")

    # ===== WORST PERFORMERS (RUGS) =====
    print("\n" + "=" * 70)
    print("WORST PERFORMERS (Never hit 1.5x)")
    print("=" * 70)

    rugs = []
    for s in signals:
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0

        if entry > 0 and peak > 0:
            roi = peak / entry
            if roi < 1.5:
                rugs.append({
                    'symbol': s.get('token_symbol', '???'),
                    'score': s.get('conviction_score', 0),
                    'roi': roi,
                    'kol': bool(s.get('kol_wallets')),
                    'bc': s.get('bonding_curve_pct'),
                    'buy_pct': s.get('buy_percentage')
                })

    rugs.sort(key=lambda x: x['roi'])

    print(f"\n{'Symbol':<12} {'Score':<8} {'Peak ROI':<10} {'KOL?':<6} {'BC%':<8} {'Buy%':<8}")
    print("-" * 60)

    for r in rugs[:20]:  # Show worst 20
        kol_str = "Yes" if r['kol'] else "No"
        bc_str = f"{r['bc']:.0f}%" if r['bc'] else "N/A"
        buy_str = f"{r['buy_pct']:.0f}%" if r['buy_pct'] else "N/A"
        print(f"${r['symbol']:<11} {r['score']:<8} {r['roi']:<9.2f}x {kol_str:<6} {bc_str:<8} {buy_str:<8}")

    # ===== BEST PERFORMERS =====
    print("\n" + "=" * 70)
    print("BEST PERFORMERS (5x+)")
    print("=" * 70)

    winners = []
    for s in signals:
        entry = s.get('entry_price') or 0
        peak = s.get('max_price_reached') or 0

        if entry > 0 and peak > 0:
            roi = peak / entry
            if roi >= 5.0:
                winners.append({
                    'symbol': s.get('token_symbol', '???'),
                    'score': s.get('conviction_score', 0),
                    'roi': roi,
                    'kol': bool(s.get('kol_wallets')),
                    'bc': s.get('bonding_curve_pct'),
                    'buy_pct': s.get('buy_percentage')
                })

    winners.sort(key=lambda x: x['roi'], reverse=True)

    print(f"\n{'Symbol':<12} {'Score':<8} {'Peak ROI':<10} {'KOL?':<6} {'BC%':<8} {'Buy%':<8}")
    print("-" * 60)

    for w in winners[:20]:  # Show top 20
        kol_str = "Yes" if w['kol'] else "No"
        bc_str = f"{w['bc']:.0f}%" if w['bc'] else "N/A"
        buy_str = f"{w['buy_pct']:.0f}%" if w['buy_pct'] else "N/A"
        print(f"${w['symbol']:<11} {w['score']:<8} {w['roi']:<9.1f}x {kol_str:<6} {bc_str:<8} {buy_str:<8}")

    # ===== RECOMMENDATIONS =====
    print("\n" + "=" * 70)
    print("OPTIMAL CONVICTION THRESHOLD ANALYSIS")
    print("=" * 70)

    print(f"\n{'Threshold':<12} {'Signals':<10} {'Wins':<10} {'Win Rate':<12} {'Avg ROI':<12}")
    print("-" * 60)

    best_threshold = 0
    best_wr = 0
    for threshold in range(40, 95, 5):
        wins = 0
        total = 0
        rois = []
        for s in signals:
            if (s.get('conviction_score') or 0) >= threshold:
                entry = s.get('entry_price') or 0
                peak = s.get('max_price_reached') or 0
                if entry > 0 and peak > 0:
                    total += 1
                    roi = peak / entry
                    rois.append(roi)
                    if roi >= 2.0:
                        wins += 1
        if total >= 5:  # Need at least 5 signals
            wr = (wins / total) * 100
            avg_roi = sum(rois) / len(rois) if rois else 0
            print(f"{threshold}+          {total:<10} {wins:<10} {wr:<11.1f}% {avg_roi:<.2f}x")
            if wr > best_wr:
                best_wr = wr
                best_threshold = threshold

    # ===== TIME OF DAY ANALYSIS =====
    print("\n" + "=" * 70)
    print("TIME OF DAY ANALYSIS (UTC)")
    print("=" * 70)

    hour_buckets = defaultdict(lambda: {"wins": 0, "total": 0, "rois": []})

    for s in signals:
        created = s.get('created_at')
        if created:
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                except:
                    continue
            hour = created.hour
            entry = s.get('entry_price') or 0
            peak = s.get('max_price_reached') or 0

            if entry > 0:
                roi = peak / entry if peak > 0 else 0
                hour_buckets[hour]["total"] += 1
                hour_buckets[hour]["rois"].append(roi)
                if roi >= 2.0:
                    hour_buckets[hour]["wins"] += 1

    print(f"\n{'Hour (UTC)':<12} {'Signals':<10} {'Wins':<10} {'Win Rate':<12}")
    print("-" * 45)

    for hour in sorted(hour_buckets.keys()):
        data = hour_buckets[hour]
        if data["total"] > 0:
            wr = (data["wins"] / data["total"]) * 100
            print(f"{hour:02d}:00        {data['total']:<10} {data['wins']:<10} {wr:.1f}%")

    # ===== FINAL RECOMMENDATIONS =====
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)

    print(f"\n1. OPTIMAL CONVICTION THRESHOLD: {best_threshold}+ (achieves {best_wr:.1f}% win rate)")

    if kol_data["total"] > 0 and non_kol_data["total"] > 0:
        kol_wr = (kol_data["wins"] / kol_data["total"]) * 100 if kol_data["total"] > 0 else 0
        non_kol_wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100 if non_kol_data["total"] > 0 else 0
        kol_avg = sum(kol_data["rois"]) / len(kol_data["rois"]) if kol_data["rois"] else 0
        non_kol_avg = sum(non_kol_data["rois"]) / len(non_kol_data["rois"]) if non_kol_data["rois"] else 0

        print(f"\n2. KOL IMPACT:")
        print(f"   - KOL-backed: {kol_wr:.1f}% win rate, {kol_avg:.2f}x avg ROI")
        print(f"   - Pure Organic: {non_kol_wr:.1f}% win rate, {non_kol_avg:.2f}x avg ROI")

        if kol_wr > non_kol_wr:
            print(f"   - KOL signals are {(kol_wr/non_kol_wr - 1)*100:.0f}% more likely to win")

    await db.close()

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(analyze())
