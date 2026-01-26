"""
Signal P&L Calculator
Calculates total P&L if you put $100 into each signal at peak performance

Usage:
  python calculate_signal_pnl.py --signals 50 --rug-rate 0.70 --include-shrimp
"""
import argparse
from typing import List, Dict


def calculate_pnl(
    total_signals: int,
    rug_rate: float,  # 0.0 to 1.0
    winners_distribution: Dict[str, float],  # e.g., {'2x': 0.5, '5x': 0.3, '10x': 0.2}
    investment_per_signal: float = 100,
    include_shrimp: bool = False
) -> Dict:
    """
    Calculate P&L for a set of signals

    Args:
        total_signals: Total number of signals sent
        rug_rate: Percentage of signals that rug (0.7 = 70%)
        winners_distribution: Distribution of winning multiples among non-rugs
        investment_per_signal: $ invested per signal
        include_shrimp: Whether to include a 100x winner like SHRIMP

    Returns:
        Dict with P&L breakdown
    """
    results = {
        'total_signals': total_signals,
        'total_invested': total_signals * investment_per_signal,
        'rug_count': 0,
        'winner_count': 0,
        'outcomes': {},
        'total_returned': 0,
        'net_pnl': 0,
        'roi_pct': 0
    }

    # Calculate rugs
    rug_count = int(total_signals * rug_rate)
    results['rug_count'] = rug_count

    # Rugs: assume -90% loss (some might recover partial)
    rug_loss_pct = -0.90
    rug_returned = rug_count * investment_per_signal * (1 + rug_loss_pct)
    results['outcomes']['rugs'] = {
        'count': rug_count,
        'invested': rug_count * investment_per_signal,
        'returned': rug_returned,
        'pnl': rug_returned - (rug_count * investment_per_signal)
    }
    results['total_returned'] += rug_returned

    # Calculate winners
    winner_count = total_signals - rug_count
    if include_shrimp and winner_count > 0:
        # Reserve 1 winner slot for SHRIMP
        winner_count -= 1
        shrimp_returned = investment_per_signal * 100  # 100x
        results['outcomes']['100x (SHRIMP)'] = {
            'count': 1,
            'invested': investment_per_signal,
            'returned': shrimp_returned,
            'pnl': shrimp_returned - investment_per_signal
        }
        results['total_returned'] += shrimp_returned

    results['winner_count'] = winner_count + (1 if include_shrimp else 0)

    # Distribute remaining winners
    for multiple_name, pct in winners_distribution.items():
        count = int(winner_count * pct)
        if count == 0:
            continue

        # Extract multiplier (e.g., '5x' -> 5)
        multiplier = float(multiple_name.replace('x', ''))

        invested = count * investment_per_signal
        returned = count * investment_per_signal * multiplier
        pnl = returned - invested

        results['outcomes'][multiple_name] = {
            'count': count,
            'invested': invested,
            'returned': returned,
            'pnl': pnl
        }
        results['total_returned'] += returned

    # Calculate totals
    results['net_pnl'] = results['total_returned'] - results['total_invested']
    results['roi_pct'] = (results['net_pnl'] / results['total_invested']) * 100

    return results


def print_results(results: Dict):
    """Pretty print P&L results"""
    print("\n" + "="*80)
    print("💰 SIGNAL P&L ANALYSIS (AT PEAK PERFORMANCE)")
    print("="*80)

    print(f"\n📊 OVERVIEW:")
    print(f"   Total Signals: {results['total_signals']}")
    print(f"   Total Invested: ${results['total_invested']:,.2f}")
    print(f"   Total Returned: ${results['total_returned']:,.2f}")
    print(f"   Net P&L: ${results['net_pnl']:,.2f}")
    print(f"   ROI: {results['roi_pct']:+.1f}%")

    print(f"\n🎯 BREAKDOWN:")
    print(f"   {'Outcome':<20} {'Count':<8} {'Invested':<12} {'Returned':<12} {'P&L':<12}")
    print(f"   {'-'*70}")

    for outcome, data in sorted(results['outcomes'].items(),
                               key=lambda x: x[1]['pnl'],
                               reverse=True):
        count = data['count']
        invested = data['invested']
        returned = data['returned']
        pnl = data['pnl']

        print(f"   {outcome:<20} {count:<8} ${invested:<11,.2f} ${returned:<11,.2f} "
              f"${pnl:+,.2f}")

    print(f"\n{'='*80}")

    # Win rate
    if results['total_signals'] > 0:
        win_rate = (results['winner_count'] / results['total_signals']) * 100
        rug_rate = (results['rug_count'] / results['total_signals']) * 100
        print(f"\n📈 METRICS:")
        print(f"   Win Rate: {win_rate:.1f}% ({results['winner_count']}/{results['total_signals']})")
        print(f"   Rug Rate: {rug_rate:.1f}% ({results['rug_count']}/{results['total_signals']})")

        if results['winner_count'] > 0:
            avg_winner_return = sum(
                d['returned'] for k, d in results['outcomes'].items() if k != 'rugs'
            ) / results['winner_count']
            print(f"   Avg Winner Return: ${avg_winner_return:,.2f} (per $100 invested)")


def main():
    parser = argparse.ArgumentParser(description='Calculate signal P&L')
    parser.add_argument('--signals', type=int, default=50,
                       help='Total number of signals (default: 50)')
    parser.add_argument('--rug-rate', type=float, default=0.70,
                       help='Rug rate as decimal (default: 0.70 = 70%%)')
    parser.add_argument('--include-shrimp', action='store_true',
                       help='Include a 100x winner like SHRIMP')
    parser.add_argument('--investment', type=float, default=100,
                       help='Investment per signal (default: $100)')

    args = parser.parse_args()

    # Typical pump.fun winners distribution (among non-rugs)
    # Based on meta: most winners do 2-5x, few do 10x+
    winners_dist = {
        '2x': 0.60,   # 60% of winners do 2x
        '3x': 0.20,   # 20% do 3x
        '5x': 0.15,   # 15% do 5x
        '10x': 0.05,  # 5% do 10x
    }

    print(f"\n🔍 SCENARIO: {args.signals} signals, {args.rug_rate*100:.0f}% rug rate")
    if args.include_shrimp:
        print(f"   📈 Including 1x 100x winner (SHRIMP-like)")

    results = calculate_pnl(
        total_signals=args.signals,
        rug_rate=args.rug_rate,
        winners_distribution=winners_dist,
        investment_per_signal=args.investment,
        include_shrimp=args.include_shrimp
    )

    print_results(results)

    # Show comparison scenarios
    print(f"\n\n{'='*80}")
    print("📊 COMPARISON: Current vs. Grok Target (30% rug rate)")
    print("="*80)

    # Current scenario (70% rug rate, no SHRIMP)
    print("\n🔴 CURRENT (70% rug rate, missed SHRIMP):")
    current = calculate_pnl(
        total_signals=args.signals,
        rug_rate=0.70,
        winners_distribution=winners_dist,
        investment_per_signal=args.investment,
        include_shrimp=False
    )
    print(f"   Net P&L: ${current['net_pnl']:+,.2f}")
    print(f"   ROI: {current['roi_pct']:+.1f}%")

    # Grok target (30% rug rate, caught SHRIMP)
    print("\n🟢 GROK TARGET (30% rug rate, caught SHRIMP):")
    target = calculate_pnl(
        total_signals=args.signals,
        rug_rate=0.30,
        winners_distribution=winners_dist,
        investment_per_signal=args.investment,
        include_shrimp=True
    )
    print(f"   Net P&L: ${target['net_pnl']:+,.2f}")
    print(f"   ROI: {target['roi_pct']:+.1f}%")

    # Improvement
    improvement = target['net_pnl'] - current['net_pnl']
    print(f"\n💰 IMPROVEMENT: ${improvement:+,.2f} ({((improvement/abs(current['net_pnl']))*100):+.0f}%)")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
