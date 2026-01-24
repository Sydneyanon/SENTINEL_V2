#!/usr/bin/env python3
"""
Win Rate Dashboard - Real-time performance tracking for Prometheus bot
Shows current win rate, ROI, and performance by category
"""
import os
import sys
import asyncio
import asyncpg
from datetime import datetime, timedelta
from collections import defaultdict

async def get_win_rate_stats(hours=24):
    """Get comprehensive win rate statistics"""

    # Connect to database
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return None

    conn = await asyncpg.connect(database_url)

    try:
        # Get signals from last N hours
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Query all signals with outcomes
        query = """
            SELECT
                mint_address,
                wallet_address,
                conviction_score,
                created_at,
                signal_outcome,
                max_roi,
                narrative_tags,
                kol_tier
            FROM signals
            WHERE created_at >= $1
            ORDER BY created_at DESC
        """

        signals = await conn.fetch(query, cutoff)

        if not signals:
            print(f"No signals found in last {hours} hours")
            return None

        # Calculate overall metrics
        total_signals = len(signals)
        wins = sum(1 for s in signals if s['signal_outcome'] in ['2x', '5x', '10x', '50x', '100x'])
        losses = sum(1 for s in signals if s['signal_outcome'] == 'rug')
        pending = sum(1 for s in signals if s['signal_outcome'] is None or s['signal_outcome'] == 'pending')

        win_rate = (wins / (total_signals - pending) * 100) if (total_signals - pending) > 0 else 0
        rug_rate = (losses / (total_signals - pending) * 100) if (total_signals - pending) > 0 else 0

        avg_roi = sum(s['max_roi'] or 0 for s in signals if s['max_roi']) / total_signals if total_signals > 0 else 0

        # Performance by KOL tier
        by_tier = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0})
        for s in signals:
            if s['signal_outcome'] and s['signal_outcome'] != 'pending':
                tier = s['kol_tier'] or 'unknown'
                by_tier[tier]['total'] += 1
                if s['signal_outcome'] in ['2x', '5x', '10x', '50x', '100x']:
                    by_tier[tier]['wins'] += 1
                elif s['signal_outcome'] == 'rug':
                    by_tier[tier]['losses'] += 1

        # Performance by narrative
        by_narrative = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0})
        for s in signals:
            if s['signal_outcome'] and s['signal_outcome'] != 'pending' and s['narrative_tags']:
                for narrative in (s['narrative_tags'] or []):
                    by_narrative[narrative]['total'] += 1
                    if s['signal_outcome'] in ['2x', '5x', '10x', '50x', '100x']:
                        by_narrative[narrative]['wins'] += 1
                    elif s['signal_outcome'] == 'rug':
                        by_narrative[narrative]['losses'] += 1

        # Performance by wallet
        by_wallet = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0, 'roi': []})
        for s in signals:
            if s['signal_outcome'] and s['signal_outcome'] != 'pending':
                wallet = s['wallet_address']
                by_wallet[wallet]['total'] += 1
                if s['max_roi']:
                    by_wallet[wallet]['roi'].append(s['max_roi'])
                if s['signal_outcome'] in ['2x', '5x', '10x', '50x', '100x']:
                    by_wallet[wallet]['wins'] += 1
                elif s['signal_outcome'] == 'rug':
                    by_wallet[wallet]['losses'] += 1

        return {
            'overview': {
                'total_signals': total_signals,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'win_rate': win_rate,
                'rug_rate': rug_rate,
                'avg_roi': avg_roi,
                'hours': hours
            },
            'by_tier': dict(by_tier),
            'by_narrative': dict(by_narrative),
            'by_wallet': dict(by_wallet)
        }

    finally:
        await conn.close()

def print_dashboard(stats):
    """Print formatted dashboard"""
    if not stats:
        return

    overview = stats['overview']

    print("\n" + "="*80)
    print(f"📊 PROMETHEUS WIN RATE DASHBOARD (Last {overview['hours']} hours)")
    print("="*80)

    print(f"\n🎯 OVERALL PERFORMANCE:")
    print(f"   Total Signals: {overview['total_signals']}")
    print(f"   Wins (2x+):    {overview['wins']} ({overview['win_rate']:.1f}%)")
    print(f"   Losses (rug):  {overview['losses']} ({overview['rug_rate']:.1f}%)")
    print(f"   Pending:       {overview['pending']}")
    print(f"   Avg ROI:       {overview['avg_roi']:.2f}x")

    # Win rate status
    if overview['win_rate'] >= 75:
        status = "🔥 EXCELLENT - Target achieved!"
    elif overview['win_rate'] >= 60:
        status = "✅ GOOD - Close to target"
    elif overview['win_rate'] >= 50:
        status = "⚠️  IMPROVING - Keep optimizing"
    else:
        status = "❌ NEEDS WORK - Aggressive optimization required"
    print(f"\n   Status: {status}")

    # By KOL tier
    print(f"\n📈 PERFORMANCE BY KOL TIER:")
    for tier, data in sorted(stats['by_tier'].items(), key=lambda x: x[1]['wins'] / max(x[1]['total'], 1), reverse=True):
        if data['total'] > 0:
            tier_win_rate = (data['wins'] / data['total'] * 100)
            print(f"   {tier:12s}: {tier_win_rate:5.1f}% win rate  ({data['wins']}/{data['total']} signals)")

    # By narrative
    print(f"\n🎭 TOP PERFORMING NARRATIVES:")
    sorted_narratives = sorted(
        [(n, d) for n, d in stats['by_narrative'].items() if d['total'] >= 2],
        key=lambda x: x[1]['wins'] / max(x[1]['total'], 1),
        reverse=True
    )[:5]

    for narrative, data in sorted_narratives:
        narrative_win_rate = (data['wins'] / data['total'] * 100)
        print(f"   {narrative:20s}: {narrative_win_rate:5.1f}% win rate  ({data['wins']}/{data['total']} signals)")

    # Top wallets
    print(f"\n🏆 TOP PERFORMING WALLETS:")
    sorted_wallets = sorted(
        [(w, d) for w, d in stats['by_wallet'].items() if d['total'] >= 3],
        key=lambda x: x[1]['wins'] / max(x[1]['total'], 1),
        reverse=True
    )[:5]

    for wallet, data in sorted_wallets:
        wallet_win_rate = (data['wins'] / data['total'] * 100)
        avg_roi = sum(data['roi']) / len(data['roi']) if data['roi'] else 0
        print(f"   {wallet[:12]}...: {wallet_win_rate:5.1f}% win rate | {avg_roi:.2f}x avg ROI | {data['total']} signals")

    # Bottom wallets (need improvement)
    print(f"\n⚠️  UNDERPERFORMING WALLETS (Consider blacklisting):")
    bottom_wallets = sorted(
        [(w, d) for w, d in stats['by_wallet'].items() if d['total'] >= 5],
        key=lambda x: x[1]['wins'] / max(x[1]['total'], 1)
    )[:3]

    for wallet, data in bottom_wallets:
        wallet_win_rate = (data['wins'] / data['total'] * 100)
        if wallet_win_rate < 40:  # Only show truly bad performers
            print(f"   {wallet[:12]}...: {wallet_win_rate:5.1f}% win rate | {data['total']} signals (BLACKLIST CANDIDATE)")

    print("\n" + "="*80 + "\n")

async def main():
    """Main entry point"""
    # Default to 24 hours, or use command line arg
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24

    print(f"Fetching stats for last {hours} hours...")
    stats = await get_win_rate_stats(hours)

    if stats:
        print_dashboard(stats)
    else:
        print("No data available")

if __name__ == "__main__":
    asyncio.run(main())
