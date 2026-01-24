#!/usr/bin/env python3
"""
Pattern Analyzer for Ralph
Analyzes external_data.json to discover NEW winning patterns and conditions

This discovers things like:
- "3+ KOLs = 78% win rate"
- "AI narrative + 2 elite KOLs = 65% 10x rate"
- "Tokens with <30% holder concentration = 82% success"
- etc.

OPT-044/057: Data mining to discover hidden criteria
"""
import json
import os
from collections import defaultdict
from typing import Dict, List
from loguru import logger


class PatternAnalyzer:
    """Discovers winning patterns from external data"""

    def __init__(self, data_file: str = 'ralph/external_data.json'):
        self.data_file = data_file
        self.tokens = []
        self.patterns = {}

    def load_data(self):
        """Load scraped external data"""
        if not os.path.exists(self.data_file):
            logger.error(f"❌ Data file not found: {self.data_file}")
            logger.error("   Run ralph/scrape_external_data.py first")
            return False

        with open(self.data_file, 'r') as f:
            data = json.load(f)

        self.tokens = data.get('tokens', [])
        logger.info(f"✅ Loaded {len(self.tokens)} tokens from {self.data_file}")
        return True

    def analyze_kol_patterns(self) -> Dict:
        """Discover: How many KOLs = what win rate?"""
        logger.info("\n🔍 Analyzing KOL count patterns...")

        kol_buckets = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            kol_count = token.get('our_kol_count', 0)
            outcome = token.get('outcome', 'unknown')

            # Bucket by KOL count
            if kol_count == 0:
                bucket = '0_kols'
            elif kol_count == 1:
                bucket = '1_kol'
            elif kol_count == 2:
                bucket = '2_kols'
            else:
                bucket = '3+_kols'

            kol_buckets[bucket]['total'] += 1
            kol_buckets[bucket]['outcomes'][outcome] += 1

        # Calculate win rates
        findings = {}
        for bucket, data in sorted(kol_buckets.items()):
            total = data['total']
            if total == 0:
                continue

            # Count successes (2x or better)
            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])

            win_rate = (successes / total) * 100

            # Count 10x+ rate
            big_wins = sum(count for outcome, count in data['outcomes'].items()
                         if outcome in ['10x', '50x', '100x'])
            big_win_rate = (big_wins / total) * 100

            findings[bucket] = {
                'total': total,
                'win_rate': win_rate,
                'big_win_rate': big_win_rate,
                'outcomes': dict(data['outcomes'])
            }

            logger.info(f"   {bucket}: {win_rate:.1f}% win rate, {big_win_rate:.1f}% 10x+ rate (n={total})")

        return findings

    def analyze_narrative_patterns(self) -> Dict:
        """Discover: Which narratives predict success?"""
        logger.info("\n🔍 Analyzing narrative patterns...")

        # Common narrative keywords to look for
        narrative_keywords = ['AI', 'cat', 'dog', 'pepe', 'meme', 'degen', 'wojak', 'chad',
                             'based', 'token', 'coin', 'sol', 'solana', 'meta', 'inu']

        narrative_stats = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            symbol = token.get('symbol', '').lower()
            name = token.get('name', '').lower()
            outcome = token.get('outcome', 'unknown')

            # Check for narrative keywords
            text = f"{symbol} {name}"

            for keyword in narrative_keywords:
                if keyword.lower() in text:
                    narrative_stats[keyword]['total'] += 1
                    narrative_stats[keyword]['outcomes'][outcome] += 1

        # Calculate win rates
        findings = {}
        for narrative, data in narrative_stats.items():
            total = data['total']
            if total < 5:  # Need at least 5 samples for significance
                continue

            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])

            win_rate = (successes / total) * 100

            findings[narrative] = {
                'total': total,
                'win_rate': win_rate,
                'outcomes': dict(data['outcomes'])
            }

        # Sort by win rate
        sorted_findings = sorted(findings.items(), key=lambda x: x[1]['win_rate'], reverse=True)

        logger.info("   Top narratives by win rate:")
        for narrative, data in sorted_findings[:10]:
            logger.info(f"      {narrative}: {data['win_rate']:.1f}% win rate (n={data['total']})")

        return dict(sorted_findings)

    def analyze_volume_patterns(self) -> Dict:
        """Discover: Does volume level predict success?"""
        logger.info("\n🔍 Analyzing volume patterns...")

        volume_buckets = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            volume = token.get('volume_24h', 0)
            outcome = token.get('outcome', 'unknown')

            # Bucket by volume
            if volume < 100_000:
                bucket = 'low_volume_<100k'
            elif volume < 500_000:
                bucket = 'medium_volume_100k-500k'
            elif volume < 1_000_000:
                bucket = 'high_volume_500k-1M'
            else:
                bucket = 'very_high_volume_>1M'

            volume_buckets[bucket]['total'] += 1
            volume_buckets[bucket]['outcomes'][outcome] += 1

        # Calculate win rates
        findings = {}
        for bucket, data in sorted(volume_buckets.items()):
            total = data['total']
            if total == 0:
                continue

            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])
            win_rate = (successes / total) * 100

            big_wins = sum(count for outcome, count in data['outcomes'].items()
                         if outcome in ['10x', '50x', '100x'])
            big_win_rate = (big_wins / total) * 100

            findings[bucket] = {
                'total': total,
                'win_rate': win_rate,
                'big_win_rate': big_win_rate
            }

            logger.info(f"   {bucket}: {win_rate:.1f}% win rate, {big_win_rate:.1f}% 10x+ (n={total})")

        return findings

    def analyze_liquidity_patterns(self) -> Dict:
        """Discover: Does liquidity level predict success?"""
        logger.info("\n🔍 Analyzing liquidity patterns...")

        liq_buckets = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            liquidity = token.get('liquidity_usd', 0)
            outcome = token.get('outcome', 'unknown')

            # Bucket by liquidity
            if liquidity < 10_000:
                bucket = 'thin_liq_<10k'
            elif liquidity < 50_000:
                bucket = 'low_liq_10k-50k'
            elif liquidity < 100_000:
                bucket = 'med_liq_50k-100k'
            else:
                bucket = 'high_liq_>100k'

            liq_buckets[bucket]['total'] += 1
            liq_buckets[bucket]['outcomes'][outcome] += 1

        # Calculate win rates
        findings = {}
        for bucket, data in sorted(liq_buckets.items()):
            total = data['total']
            if total == 0:
                continue

            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])
            win_rate = (successes / total) * 100

            findings[bucket] = {
                'total': total,
                'win_rate': win_rate
            }

            logger.info(f"   {bucket}: {win_rate:.1f}% win rate (n={total})")

        return findings

    def analyze_timing_patterns(self) -> Dict:
        """Discover: What time of day do winners launch?"""
        logger.info("\n🔍 Analyzing timing patterns (hour of day)...")

        from datetime import datetime

        hour_buckets = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            created_at = token.get('created_at')
            outcome = token.get('outcome', 'unknown')

            if not created_at:
                continue

            # Convert timestamp to hour (UTC)
            try:
                dt = datetime.fromtimestamp(created_at / 1000)  # ms to seconds
                hour = dt.hour

                # Bucket by time of day
                if 0 <= hour < 6:
                    bucket = 'night_0-6am_UTC'
                elif 6 <= hour < 12:
                    bucket = 'morning_6am-12pm_UTC'
                elif 12 <= hour < 18:
                    bucket = 'afternoon_12pm-6pm_UTC'
                else:
                    bucket = 'evening_6pm-12am_UTC'

                hour_buckets[bucket]['total'] += 1
                hour_buckets[bucket]['outcomes'][outcome] += 1
            except:
                continue

        # Calculate win rates
        findings = {}
        for bucket, data in sorted(hour_buckets.items()):
            total = data['total']
            if total < 5:  # Need minimum sample
                continue

            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])
            win_rate = (successes / total) * 100

            findings[bucket] = {
                'total': total,
                'win_rate': win_rate
            }

            logger.info(f"   {bucket}: {win_rate:.1f}% win rate (n={total})")

        return findings

    def analyze_price_momentum(self) -> Dict:
        """Discover: Short-term vs long-term gainers"""
        logger.info("\n🔍 Analyzing price momentum patterns...")

        momentum_buckets = defaultdict(lambda: {'total': 0, 'outcomes': defaultdict(int)})

        for token in self.tokens:
            gain_1h = token.get('price_change_1h', 0)
            gain_6h = token.get('price_change_6h', 0)
            gain_24h = token.get('price_change_24h', 0)
            outcome = token.get('outcome', 'unknown')

            # Classify momentum pattern
            if gain_1h > 100:  # Fast pump
                if gain_24h > gain_1h * 2:  # Sustained
                    bucket = 'fast_pump_sustained'
                else:
                    bucket = 'fast_pump_faded'
            elif gain_6h > gain_1h * 3:  # Slow builder
                bucket = 'slow_builder'
            else:
                bucket = 'steady_growth'

            momentum_buckets[bucket]['total'] += 1
            momentum_buckets[bucket]['outcomes'][outcome] += 1

        # Calculate win rates
        findings = {}
        for bucket, data in sorted(momentum_buckets.items()):
            total = data['total']
            if total < 3:
                continue

            successes = sum(count for outcome, count in data['outcomes'].items()
                          if outcome in ['2x', '5x', '10x', '50x', '100x'])
            win_rate = (successes / total) * 100

            findings[bucket] = {
                'total': total,
                'win_rate': win_rate
            }

            logger.info(f"   {bucket}: {win_rate:.1f}% win rate (n={total})")

        return findings
        """Discover: Complex patterns (KOLs + narratives)"""
        logger.info("\n🔍 Analyzing combined patterns (KOL count + narrative)...")

        # Focus on high-performing combos
        combos = defaultdict(lambda: {'total': 0, 'successes': 0, 'big_wins': 0})

        narrative_keywords = ['AI', 'cat', 'dog', 'pepe', 'meme']

        for token in self.tokens:
            kol_count = token.get('our_kol_count', 0)
            outcome = token.get('outcome', 'unknown')
            symbol = token.get('symbol', '').lower()
            name = token.get('name', '').lower()
            text = f"{symbol} {name}"

            # Create combo keys
            for keyword in narrative_keywords:
                if keyword.lower() in text:
                    if kol_count >= 2:
                        combo_key = f"2+_KOLs_{keyword}"
                    elif kol_count == 1:
                        combo_key = f"1_KOL_{keyword}"
                    else:
                        combo_key = f"0_KOLs_{keyword}"

                    combos[combo_key]['total'] += 1

                    if outcome in ['2x', '5x', '10x', '50x', '100x']:
                        combos[combo_key]['successes'] += 1

                    if outcome in ['10x', '50x', '100x']:
                        combos[combo_key]['big_wins'] += 1

        # Calculate and sort
        patterns = []
        for combo, data in combos.items():
            if data['total'] < 3:  # Need minimum sample size
                continue

            win_rate = (data['successes'] / data['total']) * 100
            big_win_rate = (data['big_wins'] / data['total']) * 100

            patterns.append({
                'pattern': combo,
                'total': data['total'],
                'win_rate': win_rate,
                'big_win_rate': big_win_rate
            })

        # Sort by win rate
        patterns.sort(key=lambda x: x['win_rate'], reverse=True)

        logger.info("   Top combined patterns:")
        for p in patterns[:15]:
            logger.info(f"      {p['pattern']}: {p['win_rate']:.1f}% win rate, "
                       f"{p['big_win_rate']:.1f}% 10x+ (n={p['total']})")

        return patterns

    def generate_conviction_recommendations(self, kol_patterns: Dict,
                                           narrative_patterns: Dict,
                                           combined_patterns: List[Dict]) -> List[str]:
        """Generate specific recommendations for conviction_engine.py"""
        logger.info("\n💡 Generating conviction score recommendations...")

        recommendations = []

        # KOL-based recommendations
        if '3+_kols' in kol_patterns:
            data = kol_patterns['3+_kols']
            if data['win_rate'] >= 70:
                recommendations.append(
                    f"INCREASE: 3+ KOLs detected → +15 bonus points "
                    f"(proven {data['win_rate']:.0f}% win rate)"
                )

        if '2_kols' in kol_patterns:
            data = kol_patterns['2_kols']
            recommendations.append(
                f"MAINTAIN: 2 KOLs → Current bonus appropriate "
                f"({data['win_rate']:.0f}% win rate)"
            )

        if '1_kol' in kol_patterns and '0_kols' in kol_patterns:
            with_kol = kol_patterns['1_kol']['win_rate']
            without = kol_patterns['0_kols']['win_rate']
            advantage = with_kol - without

            if advantage < 10:
                recommendations.append(
                    f"DECREASE: Single KOL advantage is only {advantage:.0f}% "
                    f"→ Consider reducing weight"
                )

        # Narrative-based recommendations
        hot_narratives = [(n, d) for n, d in narrative_patterns.items()
                         if d['win_rate'] >= 60 and d['total'] >= 10]

        cold_narratives = [(n, d) for n, d in narrative_patterns.items()
                          if d['win_rate'] <= 40 and d['total'] >= 10]

        for narrative, data in hot_narratives[:3]:
            recommendations.append(
                f"ADD HOT NARRATIVE: '{narrative}' → {data['win_rate']:.0f}% win rate "
                f"→ +10 bonus points"
            )

        for narrative, data in cold_narratives[:3]:
            recommendations.append(
                f"AVOID NARRATIVE: '{narrative}' → {data['win_rate']:.0f}% win rate "
                f"→ -5 penalty or skip"
            )

        # Combined pattern recommendations
        for pattern in combined_patterns[:5]:
            if pattern['win_rate'] >= 75:
                recommendations.append(
                    f"HIGH CONVICTION COMBO: {pattern['pattern']} → "
                    f"{pattern['win_rate']:.0f}% win rate → "
                    f"Set threshold to 60 (instead of 75) for these"
                )

        return recommendations

    def _generate_data_recommendations(self, volume_patterns, liquidity_patterns,
                                       timing_patterns, momentum_patterns) -> List[str]:
        """Generate recommendations from volume/liquidity/timing/momentum analysis"""
        recommendations = []

        # Volume recommendations
        best_volume = max(volume_patterns.items(), key=lambda x: x[1]['win_rate'], default=None)
        if best_volume:
            bucket, data = best_volume
            recommendations.append(
                f"VOLUME THRESHOLD: {bucket} has {data['win_rate']:.0f}% win rate "
                f"→ Require minimum volume level"
            )

        # Liquidity recommendations
        best_liq = max(liquidity_patterns.items(), key=lambda x: x[1]['win_rate'], default=None)
        if best_liq:
            bucket, data = best_liq
            recommendations.append(
                f"LIQUIDITY SWEET SPOT: {bucket} has {data['win_rate']:.0f}% win rate "
                f"→ Adjust liquidity scoring"
            )

        # Timing recommendations
        if timing_patterns:
            best_time = max(timing_patterns.items(), key=lambda x: x[1]['win_rate'])
            worst_time = min(timing_patterns.items(), key=lambda x: x[1]['win_rate'])

            best_bucket, best_data = best_time
            worst_bucket, worst_data = worst_time

            time_diff = best_data['win_rate'] - worst_data['win_rate']

            if time_diff > 15:  # Significant difference
                recommendations.append(
                    f"TIMING MATTERS: {best_bucket} = {best_data['win_rate']:.0f}% vs "
                    f"{worst_bucket} = {worst_data['win_rate']:.0f}% "
                    f"→ Lower threshold during hot hours"
                )

        # Momentum recommendations
        for pattern, data in momentum_patterns.items():
            if data['win_rate'] >= 70:
                recommendations.append(
                    f"MOMENTUM PATTERN: {pattern} = {data['win_rate']:.0f}% win rate "
                    f"→ Add momentum detection bonus"
                )

        return recommendations

    def save_analysis_report(self, kol_patterns, narrative_patterns,
                            combined_patterns, recommendations,
                            volume_patterns=None, liquidity_patterns=None,
                            timing_patterns=None, momentum_patterns=None):
                           combined_patterns, recommendations):
        """Save comprehensive analysis report"""
        report_path = os.path.join(os.path.dirname(self.data_file), 'pattern_analysis.json')

        report = {
            'analyzed_at': self._get_timestamp(),
            'token_count': len(self.tokens),
            'kol_patterns': kol_patterns,
            'narrative_patterns': narrative_patterns,
            'volume_patterns': volume_patterns or {},
            'liquidity_patterns': liquidity_patterns or {},
            'timing_patterns': timing_patterns or {},
            'momentum_patterns': momentum_patterns or {},
            'combined_patterns': combined_patterns,
            'recommendations': recommendations
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"\n💾 Analysis report saved to: {report_path}")

        # Also create human-readable version
        readme_path = os.path.join(os.path.dirname(self.data_file), 'PATTERN_FINDINGS.md')
        self._write_markdown_report(readme_path, kol_patterns, narrative_patterns,
                                    combined_patterns, recommendations,
                                    volume_patterns, liquidity_patterns,
                                    timing_patterns, momentum_patterns)

        logger.info(f"📄 Human-readable report saved to: {readme_path}")

    def _write_markdown_report(self, path, kol_patterns, narrative_patterns,
                               combined_patterns, recommendations,
                               volume_patterns=None, liquidity_patterns=None,
                               timing_patterns=None, momentum_patterns=None):
        """Write human-readable markdown report"""
        with open(path, 'w') as f:
            f.write("# Pattern Analysis Report\n\n")
            f.write(f"**Analyzed:** {self._get_timestamp()}\n")
            f.write(f"**Tokens:** {len(self.tokens)}\n\n")

            f.write("## 🎯 Key Findings\n\n")

            # KOL patterns
            f.write("### KOL Count Impact\n\n")
            f.write("| KOL Count | Win Rate | 10x+ Rate | Sample Size |\n")
            f.write("|-----------|----------|-----------|-------------|\n")
            for bucket, data in sorted(kol_patterns.items()):
                f.write(f"| {bucket} | {data['win_rate']:.1f}% | "
                       f"{data['big_win_rate']:.1f}% | {data['total']} |\n")

            # Narrative patterns
            f.write("\n### Narrative Performance\n\n")
            f.write("**Hot Narratives (>60% win rate):**\n\n")
            hot = [(n, d) for n, d in narrative_patterns if d['win_rate'] >= 60]
            for narrative, data in hot[:10]:
                f.write(f"- **{narrative}**: {data['win_rate']:.1f}% win rate (n={data['total']})\n")

            f.write("\n**Cold Narratives (<40% win rate):**\n\n")
            cold = [(n, d) for n, d in narrative_patterns if d['win_rate'] <= 40]
            for narrative, data in cold[:10]:
                f.write(f"- **{narrative}**: {data['win_rate']:.1f}% win rate (n={data['total']}) ⚠️\n")

            # Volume patterns
            if volume_patterns:
                f.write("\n### Volume Level Impact\n\n")
                f.write("| Volume Range | Win Rate | Sample Size |\n")
                f.write("|--------------|----------|-------------|\n")
                for bucket, data in sorted(volume_patterns.items()):
                    f.write(f"| {bucket} | {data['win_rate']:.1f}% | {data['total']} |\n")

            # Liquidity patterns
            if liquidity_patterns:
                f.write("\n### Liquidity Level Impact\n\n")
                f.write("| Liquidity Range | Win Rate | Sample Size |\n")
                f.write("|-----------------|----------|-------------|\n")
                for bucket, data in sorted(liquidity_patterns.items()):
                    f.write(f"| {bucket} | {data['win_rate']:.1f}% | {data['total']} |\n")

            # Timing patterns
            if timing_patterns:
                f.write("\n### Launch Timing Impact\n\n")
                f.write("| Time Window | Win Rate | Sample Size |\n")
                f.write("|-------------|----------|-------------|\n")
                for bucket, data in sorted(timing_patterns.items()):
                    f.write(f"| {bucket} | {data['win_rate']:.1f}% | {data['total']} |\n")

            # Momentum patterns
            if momentum_patterns:
                f.write("\n### Price Momentum Patterns\n\n")
                f.write("| Momentum Type | Win Rate | Sample Size |\n")
                f.write("|---------------|----------|-------------|\n")
                for bucket, data in sorted(momentum_patterns.items()):
                    f.write(f"| {bucket} | {data['win_rate']:.1f}% | {data['total']} |\n")

            # Combined patterns
            f.write("\n### High-Conviction Combinations\n\n")
            f.write("| Pattern | Win Rate | 10x+ Rate | Sample Size |\n")
            f.write("|---------|----------|-----------|-------------|\n")
            for p in combined_patterns[:15]:
                f.write(f"| {p['pattern']} | {p['win_rate']:.1f}% | "
                       f"{p['big_win_rate']:.1f}% | {p['total']} |\n")

            # Recommendations
            f.write("\n## 💡 Recommended Changes to conviction_engine.py\n\n")
            for i, rec in enumerate(recommendations, 1):
                f.write(f"{i}. {rec}\n")

            f.write("\n## 🔄 Next Steps\n\n")
            f.write("1. Review findings above\n")
            f.write("2. Update `scoring/conviction_engine.py` weights\n")
            f.write("3. Add hot narratives to `config.py`\n")
            f.write("4. Test new scoring on next batch of signals\n")
            f.write("5. Monitor conviction scores - should increase!\n")

    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def run_full_analysis(self):
        """Run complete pattern analysis"""
        logger.info("="*70)
        logger.info("🔬 PATTERN ANALYSIS - Discovering Winning Conditions")
        logger.info("="*70)

        # Load data
        if not self.load_data():
            return

        # Analyze ALL patterns
        kol_patterns = self.analyze_kol_patterns()
        narrative_patterns = self.analyze_narrative_patterns()
        volume_patterns = self.analyze_volume_patterns()
        liquidity_patterns = self.analyze_liquidity_patterns()
        timing_patterns = self.analyze_timing_patterns()
        momentum_patterns = self.analyze_price_momentum()
        combined_patterns = self.analyze_combined_patterns()

        # Generate recommendations
        recommendations = self.generate_conviction_recommendations(
            kol_patterns, narrative_patterns, combined_patterns
        )

        # Add volume/liquidity/timing recommendations
        recommendations.extend(self._generate_data_recommendations(
            volume_patterns, liquidity_patterns, timing_patterns, momentum_patterns
        ))

        # Print recommendations
        logger.info("\n" + "="*70)
        logger.info("💡 CONVICTION SCORE RECOMMENDATIONS")
        logger.info("="*70)
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. {rec}")

        # Save reports
        self.save_analysis_report(
            kol_patterns, narrative_patterns, combined_patterns, recommendations,
            volume_patterns, liquidity_patterns, timing_patterns, momentum_patterns
        )

        logger.info("\n" + "="*70)
        logger.info("✅ Analysis complete!")
        logger.info("="*70)


if __name__ == "__main__":
    analyzer = PatternAnalyzer()
    analyzer.run_full_analysis()
