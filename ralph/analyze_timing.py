#!/usr/bin/env python3
"""
OPT-034: Analyze optimal hours/days for signal posting

Analyzes historical signal performance by time of day and day of week
to identify HOT ZONES (high win rate) and COLD ZONES (low win rate).

Usage:
    python ralph/analyze_timing.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database


async def analyze_timing():
    """Analyze signal performance by time of day and day of week"""

    db = Database()
    await db.connect()

    try:
        # Get all signals with outcomes
        signals = await db.get_signals_with_outcomes()

        if not signals:
            print("❌ No signals with outcomes found in database")
            print("   Outcome tracking needs more data before OPT-034 can be implemented")
            return None

        print(f"✅ Found {len(signals)} signals with outcomes\n")

        # Group by hour of day (UTC)
        by_hour = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'rugs': 0,
            'roi_sum': 0.0,
            'signals': []
        })

        # Group by day of week (0=Monday, 6=Sunday)
        by_day = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'rugs': 0,
            'roi_sum': 0.0,
            'signals': []
        })

        # Process each signal
        for signal in signals:
            created_at = signal.get('created_at')
            outcome = signal.get('outcome')
            max_roi = signal.get('max_roi', 0) or 0

            if not created_at:
                continue

            # Ensure timezone aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            hour = created_at.hour  # 0-23 UTC
            day = created_at.weekday()  # 0=Monday, 6=Sunday

            # Categorize outcome
            is_win = outcome in ('2x', '5x', '10x', '50x', '100x')
            is_rug = outcome == 'rug'
            is_loss = outcome in ('loss', 'rug')

            # Update hour stats
            by_hour[hour]['total'] += 1
            by_hour[hour]['signals'].append(signal)
            by_hour[hour]['roi_sum'] += max_roi
            if is_win:
                by_hour[hour]['wins'] += 1
            if is_loss:
                by_hour[hour]['losses'] += 1
            if is_rug:
                by_hour[hour]['rugs'] += 1

            # Update day stats
            by_day[day]['total'] += 1
            by_day[day]['signals'].append(signal)
            by_day[day]['roi_sum'] += max_roi
            if is_win:
                by_day[day]['wins'] += 1
            if is_loss:
                by_day[day]['losses'] += 1
            if is_rug:
                by_day[day]['rugs'] += 1

        # Calculate metrics and identify zones
        print("=" * 80)
        print("ANALYSIS BY HOUR OF DAY (UTC)")
        print("=" * 80)

        hot_hours = []
        cold_hours = []

        hour_results = []
        for hour in range(24):
            stats = by_hour[hour]
            if stats['total'] == 0:
                continue

            win_rate = (stats['wins'] / stats['total']) * 100
            rug_rate = (stats['rugs'] / stats['total']) * 100
            avg_roi = stats['roi_sum'] / stats['total']

            zone = "🔥 HOT" if win_rate >= 65 else ("❄️ COLD" if win_rate < 45 else "🌡️ WARM")

            print(f"{hour:02d}:00 UTC: {stats['total']:3d} signals | "
                  f"WR: {win_rate:5.1f}% | RR: {rug_rate:5.1f}% | "
                  f"Avg ROI: {avg_roi:5.2f}x | {zone}")

            if win_rate >= 65:
                hot_hours.append(hour)
            elif win_rate < 45:
                cold_hours.append(hour)

            hour_results.append({
                'hour': hour,
                'total': stats['total'],
                'win_rate': win_rate,
                'rug_rate': rug_rate,
                'avg_roi': avg_roi,
                'zone': zone
            })

        print("\n" + "=" * 80)
        print("ANALYSIS BY DAY OF WEEK")
        print("=" * 80)

        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hot_days = []
        cold_days = []

        day_results = []
        for day in range(7):
            stats = by_day[day]
            if stats['total'] == 0:
                continue

            win_rate = (stats['wins'] / stats['total']) * 100
            rug_rate = (stats['rugs'] / stats['total']) * 100
            avg_roi = stats['roi_sum'] / stats['total']

            zone = "🔥 HOT" if win_rate >= 65 else ("❄️ COLD" if win_rate < 45 else "🌡️ WARM")

            print(f"{day_names[day]:9s}: {stats['total']:3d} signals | "
                  f"WR: {win_rate:5.1f}% | RR: {rug_rate:5.1f}% | "
                  f"Avg ROI: {avg_roi:5.2f}x | {zone}")

            if win_rate >= 65:
                hot_days.append(day)
            elif win_rate < 45:
                cold_days.append(day)

            day_results.append({
                'day': day,
                'day_name': day_names[day],
                'total': stats['total'],
                'win_rate': win_rate,
                'rug_rate': rug_rate,
                'avg_roi': avg_roi,
                'zone': zone
            })

        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)

        if hot_hours:
            print(f"\n🔥 HOT HOURS (Win Rate >= 65%): {[f'{h:02d}:00' for h in hot_hours]}")
            print("   → PUSH HARD: Keep conviction threshold at normal level (75)")
        else:
            print("\n⚠️ No HOT HOURS found (need win rate >= 65%)")

        if cold_hours:
            print(f"\n❄️ COLD HOURS (Win Rate < 45%): {[f'{h:02d}:00' for h in cold_hours]}")
            print("   → EASE OFF: Raise conviction threshold by +10 pts (to 85)")
        else:
            print("\n✅ No COLD HOURS found (all hours >= 45% win rate)")

        if hot_days:
            hot_day_names = [day_names[d] for d in hot_days]
            print(f"\n🔥 HOT DAYS (Win Rate >= 65%): {hot_day_names}")
            print("   → PUSH HARD: Normal conviction threshold on these days")
        else:
            print("\n⚠️ No HOT DAYS found (need win rate >= 65%)")

        if cold_days:
            cold_day_names = [day_names[d] for d in cold_days]
            print(f"\n❄️ COLD DAYS (Win Rate < 45%): {cold_day_names}")
            print("   → EASE OFF: Raise conviction threshold on these days")
        else:
            print("\n✅ No COLD DAYS found (all days >= 45% win rate)")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total signals analyzed: {len(signals)}")
        print(f"Hot hours identified: {len(hot_hours)}")
        print(f"Cold hours identified: {len(cold_hours)}")
        print(f"Hot days identified: {len(hot_days)}")
        print(f"Cold days identified: {len(cold_days)}")

        # Return results for OPT-034 implementation
        return {
            'total_signals': len(signals),
            'by_hour': hour_results,
            'by_day': day_results,
            'hot_hours': hot_hours,
            'cold_hours': cold_hours,
            'hot_days': hot_days,
            'cold_days': cold_days
        }

    finally:
        await db.close()


if __name__ == '__main__':
    results = asyncio.run(analyze_timing())

    if results:
        # Save results to file for time_optimizer.py to use
        output_path = '/app/ralph/timing_analysis_results.json'
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results saved to {output_path}")

        # Check if we have enough data to proceed
        if results['total_signals'] < 30:
            print(f"\n⚠️ WARNING: Only {results['total_signals']} signals with outcomes")
            print("   Recommend waiting for at least 50 signals before implementing OPT-034")
            sys.exit(1)
        else:
            print(f"\n✅ Sufficient data ({results['total_signals']} signals) to proceed with OPT-034")
            sys.exit(0)
    else:
        print("\n❌ Cannot proceed with OPT-034 - insufficient data")
        sys.exit(1)
