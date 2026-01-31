"""
Ralph Unified Analysis - All analysis in one place.

Combines:
- Win rate analysis
- Threshold optimization
- KOL performance
- ML accuracy
- Recommendations
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import config


class RalphAnalysis:
    """Unified analysis engine - one command to rule them all."""

    def __init__(self, db):
        self.db = db

    async def full_analysis(self, days: int = 7) -> Dict:
        """
        Run complete analysis and generate recommendations.
        This is the single /ralph command output.
        """
        logger.info("=" * 60)
        logger.info("🤖 RALPH UNIFIED ANALYSIS")
        logger.info("=" * 60)
        logger.info(f"   Analyzing last {days} days...")

        results = {
            'days': days,
            'timestamp': datetime.utcnow().isoformat(),
            'current_config': {
                'min_conviction_score': config.MIN_CONVICTION_SCORE,
                'post_grad_threshold': config.POST_GRAD_THRESHOLD,
                'min_unique_buyers': config.ORGANIC_SCANNER.get('min_unique_buyers', 50),
                'min_buy_ratio': config.ORGANIC_SCANNER.get('min_buy_ratio', 0.65),
            },
            'recommendations': []
        }

        try:
            # Get data
            from ralph.data_manager import DataManager
            dm = DataManager(self.db)
            data = await dm.get_training_data(days=days)

            if len(data) < 10:
                logger.warning(f"   ⚠️ Only {len(data)} signals - need more data")
                results['error'] = 'insufficient_data'
                results['signal_count'] = len(data)
                return results

            results['signal_count'] = len(data)
            logger.info(f"   📊 Analyzing {len(data)} signals")

            # 1. Overall Performance
            logger.info("")
            logger.info("━" * 50)
            logger.info("📈 OVERALL PERFORMANCE")
            logger.info("━" * 50)

            overall = self._analyze_overall(data)
            results['overall'] = overall

            # 2. Threshold Optimization
            logger.info("")
            logger.info("━" * 50)
            logger.info("🎯 THRESHOLD OPTIMIZATION")
            logger.info("━" * 50)

            threshold_analysis = self._optimize_thresholds(data)
            results['threshold_analysis'] = threshold_analysis

            # Add threshold recommendations
            if threshold_analysis.get('pre_grad', {}).get('optimal'):
                opt = threshold_analysis['pre_grad']['optimal']
                curr = config.MIN_CONVICTION_SCORE
                if opt != curr:
                    opt_wr = threshold_analysis['pre_grad']['thresholds'].get(opt, {}).get('win_rate', 0)
                    curr_wr = threshold_analysis['pre_grad']['thresholds'].get(curr, {}).get('win_rate', 0)
                    if opt_wr > curr_wr:
                        results['recommendations'].append({
                            'type': 'threshold',
                            'setting': 'MIN_CONVICTION_SCORE',
                            'current': curr,
                            'recommended': opt,
                            'impact': f"+{opt_wr - curr_wr:.0f}% WR"
                        })

            # 3. KOL Performance
            logger.info("")
            logger.info("━" * 50)
            logger.info("👑 KOL PERFORMANCE")
            logger.info("━" * 50)

            kol_analysis = await self._analyze_kols(data)
            results['kol_analysis'] = kol_analysis

            # Add KOL recommendations
            if kol_analysis.get('underperformers'):
                for kol in kol_analysis['underperformers'][:3]:
                    if kol['rug_rate'] > 50:
                        results['recommendations'].append({
                            'type': 'kol',
                            'action': 'remove',
                            'wallet': kol['name'],
                            'reason': f"{kol['rug_rate']:.0f}% rug rate"
                        })

            # 4. Conviction Score Distribution
            logger.info("")
            logger.info("━" * 50)
            logger.info("📊 SCORE DISTRIBUTION")
            logger.info("━" * 50)

            score_dist = self._analyze_score_distribution(data)
            results['score_distribution'] = score_dist

            # 5. Summary & Recommendations
            logger.info("")
            logger.info("=" * 60)
            logger.info("🎯 RECOMMENDATIONS")
            logger.info("=" * 60)

            if results['recommendations']:
                for rec in results['recommendations']:
                    if rec['type'] == 'threshold':
                        logger.info(f"   • {rec['setting']}: {rec['current']} → {rec['recommended']} ({rec['impact']})")
                    elif rec['type'] == 'kol':
                        logger.info(f"   • Remove KOL '{rec['wallet']}': {rec['reason']}")
            else:
                logger.info("   ✅ No critical issues found")

            # Health score
            health = self._calculate_health_score(results)
            results['health_score'] = health

            logger.info("")
            logger.info(f"   📊 Overall Health: {health['score']}/100 ({health['grade']})")
            logger.info("=" * 60)

            return results

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            results['error'] = str(e)
            return results

    def _analyze_overall(self, data: List[Dict]) -> Dict:
        """Analyze overall performance."""
        total = len(data)
        wins = sum(1 for d in data if d['is_win'])
        rugs = sum(1 for d in data if d['is_rug'])
        losses = sum(1 for d in data if d['is_loss'])

        win_rate = (wins / total * 100) if total > 0 else 0
        rug_rate = (rugs / total * 100) if total > 0 else 0

        # ROI stats
        rois = [d.get('roi', 1) for d in data if d.get('roi')]
        avg_roi = sum(rois) / len(rois) if rois else 1
        max_roi = max(rois) if rois else 1

        emoji = "🟢" if win_rate >= 40 else "🟡" if win_rate >= 25 else "🔴"
        logger.info(f"   {emoji} Win Rate: {win_rate:.0f}% ({wins}W / {losses}L / {rugs}R)")
        logger.info(f"   📈 Avg ROI: {avg_roi:.1f}x | Best: {max_roi:.0f}x")

        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'rugs': rugs,
            'win_rate': round(win_rate, 1),
            'rug_rate': round(rug_rate, 1),
            'avg_roi': round(avg_roi, 2),
            'max_roi': round(max_roi, 1)
        }

    def _optimize_thresholds(self, data: List[Dict]) -> Dict:
        """Find optimal conviction thresholds."""
        results = {'pre_grad': {}, 'post_grad': {}}

        # Pre-grad analysis
        pre_grad = [d for d in data if d.get('is_pre_grad', True)]
        if len(pre_grad) >= 5:
            results['pre_grad'] = self._test_threshold_range(
                pre_grad,
                thresholds=[30, 35, 40, 45, 50, 55, 60],
                current=config.MIN_CONVICTION_SCORE,
                label="Pre-grad"
            )

        # Post-grad analysis
        post_grad = [d for d in data if not d.get('is_pre_grad', True)]
        if len(post_grad) >= 5:
            results['post_grad'] = self._test_threshold_range(
                post_grad,
                thresholds=[40, 45, 50, 55, 60, 65],
                current=config.POST_GRAD_THRESHOLD,
                label="Post-grad"
            )

        return results

    def _test_threshold_range(self, data: List[Dict], thresholds: List[int],
                               current: int, label: str) -> Dict:
        """Test a range of thresholds and find optimal."""
        results = {'thresholds': {}, 'optimal': None, 'current': current}

        best_threshold = current
        best_score = 0  # Score = WR * log(signal_count) to balance quality and quantity

        import math

        for threshold in thresholds:
            passing = [d for d in data if (d.get('conviction_score') or 0) >= threshold]

            if len(passing) < 3:
                continue

            wins = sum(1 for d in passing if d['is_win'])
            rugs = sum(1 for d in passing if d['is_rug'])
            total = len(passing)
            wr = (wins / total * 100) if total > 0 else 0
            rr = (rugs / total * 100) if total > 0 else 0

            results['thresholds'][threshold] = {
                'signals': total,
                'wins': wins,
                'rugs': rugs,
                'win_rate': round(wr, 1),
                'rug_rate': round(rr, 1)
            }

            # Score balances WR with having enough signals
            # Penalize if too few signals
            score = wr * math.log(max(total, 1) + 1)
            if total >= 5 and score > best_score:
                best_score = score
                best_threshold = threshold

            # Log
            emoji = "🟢" if wr >= 50 else "🟡" if wr >= 35 else "🔴"
            curr_mark = " ←" if threshold == current else ""
            opt_mark = " 🎯" if threshold == best_threshold and threshold != current else ""
            logger.info(f"   {emoji} {label} {threshold}: {wr:.0f}% WR ({total} signals){curr_mark}{opt_mark}")

        results['optimal'] = best_threshold
        return results

    async def _analyze_kols(self, data: List[Dict]) -> Dict:
        """Analyze individual KOL performance."""
        results = {
            'kol_vs_organic': {},
            'top_performers': [],
            'underperformers': []
        }

        # KOL vs non-KOL comparison
        kol_data = [d for d in data if d['has_kol']]
        non_kol_data = [d for d in data if not d['has_kol']]

        if kol_data:
            kol_wins = sum(1 for d in kol_data if d['is_win'])
            kol_rugs = sum(1 for d in kol_data if d['is_rug'])
            kol_wr = (kol_wins / len(kol_data) * 100) if kol_data else 0
            kol_rr = (kol_rugs / len(kol_data) * 100) if kol_data else 0

            results['kol_vs_organic']['kol'] = {
                'total': len(kol_data),
                'win_rate': round(kol_wr, 1),
                'rug_rate': round(kol_rr, 1)
            }

            emoji = "🟢" if kol_wr >= 40 else "🟡" if kol_wr >= 25 else "🔴"
            logger.info(f"   {emoji} KOL-backed: {kol_wr:.0f}% WR, {kol_rr:.0f}% RR ({len(kol_data)} signals)")

        if non_kol_data:
            non_kol_wins = sum(1 for d in non_kol_data if d['is_win'])
            non_kol_rugs = sum(1 for d in non_kol_data if d['is_rug'])
            non_kol_wr = (non_kol_wins / len(non_kol_data) * 100)
            non_kol_rr = (non_kol_rugs / len(non_kol_data) * 100)

            results['kol_vs_organic']['organic'] = {
                'total': len(non_kol_data),
                'win_rate': round(non_kol_wr, 1),
                'rug_rate': round(non_kol_rr, 1)
            }

            emoji = "🟢" if non_kol_wr >= 40 else "🟡" if non_kol_wr >= 25 else "🔴"
            logger.info(f"   {emoji} Organic: {non_kol_wr:.0f}% WR, {non_kol_rr:.0f}% RR ({len(non_kol_data)} signals)")

        # Per-KOL analysis (from database)
        if self.db and self.db.pool:
            try:
                async with self.db.pool.acquire() as conn:
                    kol_stats = await conn.fetch('''
                        SELECT
                            swa.wallet_name,
                            swa.wallet_address,
                            COUNT(DISTINCT swa.token_address) as tokens,
                            SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                            SUM(CASE WHEN s.outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                            SUM(CASE WHEN s.outcome IN ('loss','rug') THEN 1 ELSE 0 END) as losses
                        FROM smart_wallet_activity swa
                        LEFT JOIN signals s ON s.token_address = swa.token_address AND s.signal_posted = TRUE
                        WHERE swa.transaction_type = 'buy'
                        GROUP BY swa.wallet_name, swa.wallet_address
                        HAVING COUNT(DISTINCT swa.token_address) >= 2
                    ''')

                    for row in kol_stats:
                        decided = row['wins'] + row['losses']
                        if decided < 2:
                            continue

                        wr = (row['wins'] / decided * 100)
                        rr = (row['rugs'] / decided * 100) if decided > 0 else 0

                        kol_info = {
                            'name': row['wallet_name'] or 'Unknown',
                            'address': row['wallet_address'],
                            'tokens': row['tokens'],
                            'wins': row['wins'],
                            'losses': row['losses'],
                            'rugs': row['rugs'],
                            'win_rate': round(wr, 1),
                            'rug_rate': round(rr, 1)
                        }

                        if wr >= 40:
                            results['top_performers'].append(kol_info)
                        elif wr < 25 or rr > 40:
                            results['underperformers'].append(kol_info)

                    # Sort
                    results['top_performers'].sort(key=lambda x: x['win_rate'], reverse=True)
                    results['underperformers'].sort(key=lambda x: x['rug_rate'], reverse=True)

                    # Log underperformers
                    if results['underperformers']:
                        logger.info("")
                        logger.info("   ⚠️ Underperforming KOLs:")
                        for kol in results['underperformers'][:5]:
                            logger.info(f"      🔴 {kol['name']}: {kol['win_rate']:.0f}% WR, {kol['rug_rate']:.0f}% RR")

            except Exception as e:
                logger.warning(f"   Could not analyze individual KOLs: {e}")

        return results

    def _analyze_score_distribution(self, data: List[Dict]) -> Dict:
        """Analyze conviction score distribution and outcomes."""
        buckets = {
            '80-100': {'signals': 0, 'wins': 0, 'rugs': 0},
            '60-79': {'signals': 0, 'wins': 0, 'rugs': 0},
            '40-59': {'signals': 0, 'wins': 0, 'rugs': 0},
            '20-39': {'signals': 0, 'wins': 0, 'rugs': 0},
            '0-19': {'signals': 0, 'wins': 0, 'rugs': 0},
        }

        for d in data:
            score = d.get('conviction_score', 0) or 0

            if score >= 80:
                bucket = '80-100'
            elif score >= 60:
                bucket = '60-79'
            elif score >= 40:
                bucket = '40-59'
            elif score >= 20:
                bucket = '20-39'
            else:
                bucket = '0-19'

            buckets[bucket]['signals'] += 1
            if d['is_win']:
                buckets[bucket]['wins'] += 1
            if d['is_rug']:
                buckets[bucket]['rugs'] += 1

        # Calculate rates and log
        for bucket, stats in buckets.items():
            if stats['signals'] > 0:
                stats['win_rate'] = round(stats['wins'] / stats['signals'] * 100, 1)
                stats['rug_rate'] = round(stats['rugs'] / stats['signals'] * 100, 1)

                emoji = "🟢" if stats['win_rate'] >= 50 else "🟡" if stats['win_rate'] >= 35 else "🔴"
                logger.info(f"   {emoji} Score {bucket}: {stats['win_rate']:.0f}% WR ({stats['signals']} signals)")
            else:
                stats['win_rate'] = 0
                stats['rug_rate'] = 0

        return buckets

    def _calculate_health_score(self, results: Dict) -> Dict:
        """Calculate overall system health score."""
        score = 50  # Start at 50

        overall = results.get('overall', {})

        # Win rate impact (-20 to +30)
        wr = overall.get('win_rate', 0)
        if wr >= 50:
            score += 30
        elif wr >= 40:
            score += 20
        elif wr >= 30:
            score += 10
        elif wr < 20:
            score -= 20

        # Rug rate impact (-20 to +10)
        rr = overall.get('rug_rate', 0)
        if rr <= 20:
            score += 10
        elif rr <= 30:
            score += 5
        elif rr >= 50:
            score -= 20
        elif rr >= 40:
            score -= 10

        # Recommendations impact (-5 each)
        recs = results.get('recommendations', [])
        score -= len(recs) * 5

        # Clamp
        score = max(0, min(100, score))

        # Grade
        if score >= 80:
            grade = "A - Excellent"
        elif score >= 60:
            grade = "B - Good"
        elif score >= 40:
            grade = "C - Needs Work"
        elif score >= 20:
            grade = "D - Poor"
        else:
            grade = "F - Critical"

        return {'score': score, 'grade': grade}


async def run_full_analysis(db, days: int = 7) -> Dict:
    """Convenience function to run full analysis."""
    analyzer = RalphAnalysis(db)
    return await analyzer.full_analysis(days)
