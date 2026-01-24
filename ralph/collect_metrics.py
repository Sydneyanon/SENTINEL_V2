"""
Metrics Collection for Prometheus Bot Optimization
Collects performance data for Ralph optimization loop
"""
import asyncio
import asyncpg
import json
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Railway database connection
DATABASE_URL = os.getenv('DATABASE_URL',
    'postgresql://postgres:wCohdopAOCYQLiowDhqHOkHixWnOmbqp@switchyard.proxy.rlwy.net:14667/railway')

async def collect_metrics(duration_minutes: int = 120):
    """
    Collect performance metrics over a time window

    Args:
        duration_minutes: How far back to look (default: 2 hours)

    Returns:
        dict: Performance metrics
    """
    print(f"📊 Collecting metrics for last {duration_minutes} minutes...")

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to Railway database")

        cutoff_time = datetime.utcnow() - timedelta(minutes=duration_minutes)

        # Signal quality metrics
        signals_query = await conn.fetch('''
            SELECT
                COUNT(*) as total_signals,
                AVG(conviction_score) as avg_conviction
            FROM signals
            WHERE created_at > $1 AND signal_posted = TRUE
        ''', cutoff_time)

        signals_data = dict(signals_query[0]) if signals_query else {}

        # Performance metrics (would need actual ROI tracking - simplified for now)
        # In production, you'd track actual token performance
        performance_query = await conn.fetch('''
            SELECT
                COUNT(DISTINCT p.token_address) as tokens_tracked,
                AVG(p.milestone) as avg_milestone
            FROM performance p
            INNER JOIN signals s ON s.token_address = p.token_address
            WHERE s.created_at > $1
        ''', cutoff_time)

        performance_data = dict(performance_query[0]) if performance_query else {}

        # Credit usage (estimate from holder checks)
        # Assuming 10 credits per unique holder check
        holder_checks = await conn.fetchval('''
            SELECT COUNT(DISTINCT token_address)
            FROM smart_wallet_activity
            WHERE detected_at > $1
        ''', cutoff_time)

        estimated_credits = (holder_checks or 0) * 10

        # Smart wallet activity
        smart_wallet_stats = await conn.fetch('''
            SELECT
                COUNT(*) as total_kol_buys,
                COUNT(DISTINCT wallet_address) as unique_kols,
                COUNT(DISTINCT token_address) as tokens_with_kols
            FROM smart_wallet_activity
            WHERE detected_at > $1
        ''', cutoff_time)

        smart_data = dict(smart_wallet_stats[0]) if smart_wallet_stats else {}

        await conn.close()

        # Build metrics report
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'duration_minutes': duration_minutes,
            'signal_quality': {
                'signals_posted': int(signals_data.get('total_signals', 0)),
                'avg_conviction': float(signals_data.get('avg_conviction', 0) or 0),
                'tokens_tracked': int(performance_data.get('tokens_tracked', 0)),
                'avg_milestone': float(performance_data.get('avg_milestone', 0) or 0)
            },
            'credit_efficiency': {
                'estimated_helius_credits': estimated_credits,
                'holder_checks': holder_checks or 0,
                'credits_per_signal': (
                    estimated_credits / signals_data.get('total_signals', 1)
                    if signals_data.get('total_signals', 0) > 0 else 0
                )
            },
            'smart_wallet_activity': {
                'total_kol_buys': int(smart_data.get('total_kol_buys', 0)),
                'unique_kols': int(smart_data.get('unique_kols', 0)),
                'tokens_with_kols': int(smart_data.get('tokens_with_kols', 0))
            }
        }

        print("\n📈 Metrics Collected:")
        print(f"   Signals Posted: {metrics['signal_quality']['signals_posted']}")
        print(f"   Avg Conviction: {metrics['signal_quality']['avg_conviction']:.1f}")
        print(f"   Helius Credits: ~{metrics['credit_efficiency']['estimated_helius_credits']}")
        print(f"   KOL Buys: {metrics['smart_wallet_activity']['total_kol_buys']}")

        return metrics

    except Exception as e:
        print(f"❌ Error collecting metrics: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_baseline(opt_id: str, metrics: dict):
    """Save metrics as baseline for an optimization"""
    prd_path = Path(__file__).parent / 'prd.json'

    with open(prd_path, 'r') as f:
        prd = json.load(f)

    # Find the optimization and save baseline
    for story in prd['userStories']:
        if story['id'] == opt_id:
            story['baseline_metrics'] = metrics
            print(f"💾 Saved baseline for {opt_id}")
            break

    with open(prd_path, 'w') as f:
        json.dump(prd, f, indent=2)

def compare_metrics(baseline: dict, current: dict):
    """Compare current metrics to baseline"""
    print("\n📊 Metrics Comparison:")
    print("="*60)

    # Signal quality comparison
    baseline_signals = baseline['signal_quality']['signals_posted']
    current_signals = current['signal_quality']['signals_posted']
    signal_change = ((current_signals - baseline_signals) / baseline_signals * 100) if baseline_signals > 0 else 0

    print(f"\nSignal Quality:")
    print(f"  Signals: {baseline_signals} → {current_signals} ({signal_change:+.1f}%)")

    baseline_conv = baseline['signal_quality']['avg_conviction']
    current_conv = current['signal_quality']['avg_conviction']
    conv_change = ((current_conv - baseline_conv) / baseline_conv * 100) if baseline_conv > 0 else 0
    print(f"  Avg Conviction: {baseline_conv:.1f} → {current_conv:.1f} ({conv_change:+.1f}%)")

    # Credit efficiency
    baseline_credits = baseline['credit_efficiency']['estimated_helius_credits']
    current_credits = current['credit_efficiency']['estimated_helius_credits']
    credit_change = ((current_credits - baseline_credits) / baseline_credits * 100) if baseline_credits > 0 else 0

    print(f"\nCredit Efficiency:")
    print(f"  Credits Used: {baseline_credits} → {current_credits} ({credit_change:+.1f}%)")

    # Decision helper
    print(f"\n{'='*60}")
    print("Decision Factors:")

    if signal_change > 10:
        print(f"  ✅ Signals increased significantly (+{signal_change:.1f}%)")
    elif signal_change < -10:
        print(f"  ❌ Signals decreased significantly ({signal_change:.1f}%)")
    else:
        print(f"  ⚠️  Signals changed minimally ({signal_change:.1f}%)")

    if credit_change < -20:
        print(f"  ✅ Credits reduced significantly ({credit_change:.1f}%)")
    elif credit_change > 20:
        print(f"  ❌ Credits increased significantly (+{credit_change:.1f}%)")
    else:
        print(f"  ⚠️  Credits changed minimally ({credit_change:.1f}%)")

    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Collect Prometheus bot metrics')
    parser.add_argument('--duration', type=int, default=120, help='Minutes to look back (default: 120)')
    parser.add_argument('--save-baseline', type=str, help='Save as baseline for optimization ID')
    parser.add_argument('--compare', type=str, help='Compare to baseline for optimization ID')

    args = parser.parse_args()

    metrics = asyncio.run(collect_metrics(args.duration))

    if metrics:
        if args.save_baseline:
            save_baseline(args.save_baseline, metrics)
        elif args.compare:
            prd_path = Path(__file__).parent / 'prd.json'
            with open(prd_path, 'r') as f:
                prd = json.load(f)

            baseline = None
            for story in prd['userStories']:
                if story['id'] == args.compare:
                    baseline = story.get('baseline_metrics')
                    break

            if baseline:
                compare_metrics(baseline, metrics)
            else:
                print(f"❌ No baseline found for {args.compare}")
        else:
            # Just print metrics
            print("\n" + json.dumps(metrics, indent=2))
