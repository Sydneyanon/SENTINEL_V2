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

            # 5. Metrics Breakdown (What Actually Predicts Wins?)
            metrics_breakdown = self._analyze_metrics_breakdown(data)
            results['metrics_breakdown'] = metrics_breakdown

            # 6. Hidden Pattern Discovery (What are we missing?)
            hidden_patterns = self._discover_hidden_patterns(data)
            results['hidden_patterns'] = hidden_patterns

            # Add pattern-based recommendations
            if hidden_patterns.get('recommendations'):
                results['recommendations'].extend(hidden_patterns['recommendations'])

            # 7. Summary & Recommendations
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

    def _analyze_metrics_breakdown(self, data: List[Dict]) -> Dict:
        """
        Analyze which metrics correlate with wins vs rugs.
        Shows what thresholds work and which don't.
        Generates actionable recommendations for each metric.
        """
        results = {
            'metrics': {},
            'recommendations': [],
            'summary': {}
        }

        # Define metrics to analyze with current config values
        metrics_config = [
            ('conviction_score', 'Conviction Score', [30, 40, 50, 55, 60, 65, 70], config.MIN_CONVICTION_SCORE),
            ('buy_percentage', 'Buy %', [50, 55, 60, 65, 70, 75, 80], config.ORGANIC_SCANNER.get('min_buy_ratio', 0.65) * 100),
            ('unique_buyers', 'Unique Buyers', [20, 30, 50, 75, 100, 150, 200], config.ORGANIC_SCANNER.get('min_unique_buyers', 50)),
            ('bonding_curve_pct', 'Bonding %', [10, 20, 30, 40, 50, 60, 70, 80], config.ORGANIC_SCANNER.get('min_bonding_pct', 20)),
            ('buys_24h', 'Buys 24h', [25, 50, 100, 200, 500, 1000], None),
            ('sells_24h', 'Sells 24h', [10, 25, 50, 100, 200], None),  # Lower is better
            ('volume_24h', 'Volume 24h ($)', [500, 1000, 5000, 10000, 50000], None),
            ('market_cap', 'Market Cap ($)', [5000, 10000, 15000, 25000, 50000], None),
            ('liquidity', 'Liquidity ($)', [1000, 5000, 8000, 10000, 25000], config.MIN_LIQUIDITY),
        ]

        # Also calculate buy/sell ratio
        for d in data:
            buys = d.get('buys_24h') or 0
            sells = d.get('sells_24h') or 1  # Avoid division by zero
            d['buy_sell_ratio'] = buys / sells if sells > 0 else buys

        # Add B/S ratio to metrics
        metrics_config.append(('buy_sell_ratio', 'Buy/Sell Ratio', [0.5, 1.0, 1.5, 2.0, 3.0, 5.0], None))

        logger.info("")
        logger.info("━" * 50)
        logger.info("🔬 METRICS BREAKDOWN (What Predicts Wins?)")
        logger.info("━" * 50)

        # Analyze wins vs rugs for each metric
        wins = [d for d in data if d['is_win']]
        rugs = [d for d in data if d['is_rug']]
        losses = [d for d in data if d['is_loss']]

        strong_predictors = []
        weak_predictors = []

        for metric_key, metric_name, thresholds, current_config in metrics_config:
            metric_data = {
                'name': metric_name,
                'wins_avg': None,
                'rugs_avg': None,
                'losses_avg': None,
                'current_config': current_config,
                'thresholds': {},
                'best_threshold': None,
                'best_wr': 0,
                'recommendation': None,
                'is_predictive': False,
                'direction': 'higher'  # Whether higher is better
            }

            # Calculate averages
            win_values = [d.get(metric_key) for d in wins if d.get(metric_key) is not None]
            rug_values = [d.get(metric_key) for d in rugs if d.get(metric_key) is not None]
            loss_values = [d.get(metric_key) for d in losses if d.get(metric_key) is not None]

            if win_values:
                metric_data['wins_avg'] = sum(win_values) / len(win_values)
                metric_data['wins_median'] = sorted(win_values)[len(win_values) // 2]
            if rug_values:
                metric_data['rugs_avg'] = sum(rug_values) / len(rug_values)
                metric_data['rugs_median'] = sorted(rug_values)[len(rug_values) // 2]
            if loss_values:
                metric_data['losses_avg'] = sum(loss_values) / len(loss_values)

            # Determine if higher or lower is better
            if metric_data['wins_avg'] and metric_data['rugs_avg']:
                metric_data['direction'] = 'higher' if metric_data['wins_avg'] > metric_data['rugs_avg'] else 'lower'

            # Test thresholds (for "higher is better" metrics)
            best_wr = 0
            best_thresh = None
            baseline_wr = (len(wins) / len(data) * 100) if data else 0

            for threshold in thresholds:
                if metric_data['direction'] == 'higher':
                    passing = [d for d in data if (d.get(metric_key) or 0) >= threshold]
                else:
                    passing = [d for d in data if (d.get(metric_key) or float('inf')) <= threshold]

                if len(passing) >= 5:
                    thresh_wins = sum(1 for d in passing if d['is_win'])
                    thresh_rugs = sum(1 for d in passing if d['is_rug'])
                    thresh_wr = (thresh_wins / len(passing) * 100)
                    thresh_rr = (thresh_rugs / len(passing) * 100)

                    metric_data['thresholds'][threshold] = {
                        'signals': len(passing),
                        'win_rate': round(thresh_wr, 1),
                        'rug_rate': round(thresh_rr, 1),
                        'improvement': round(thresh_wr - baseline_wr, 1)
                    }

                    # Best threshold = highest WR with at least 10% of signals
                    if thresh_wr > best_wr and len(passing) >= len(data) * 0.1:
                        best_wr = thresh_wr
                        best_thresh = threshold

            metric_data['best_threshold'] = best_thresh
            metric_data['best_wr'] = best_wr

            # Determine if predictive (>10% difference between wins and rugs)
            if metric_data['wins_avg'] is not None and metric_data['rugs_avg'] is not None:
                diff = abs(metric_data['wins_avg'] - metric_data['rugs_avg'])
                max_val = max(metric_data['wins_avg'], metric_data['rugs_avg'], 1)
                metric_data['is_predictive'] = diff > 0.1 * max_val

            # Generate recommendation
            if best_thresh and current_config is not None:
                if metric_data['direction'] == 'higher' and best_thresh > current_config:
                    best_data = metric_data['thresholds'].get(best_thresh, {})
                    if best_data.get('win_rate', 0) > baseline_wr + 5:  # At least 5% improvement
                        metric_data['recommendation'] = {
                            'action': 'raise',
                            'from': current_config,
                            'to': best_thresh,
                            'impact': f"+{best_data['improvement']:.0f}% WR"
                        }
                        results['recommendations'].append({
                            'metric': metric_key,
                            'name': metric_name,
                            'action': 'raise',
                            'from': current_config,
                            'to': best_thresh,
                            'impact': f"+{best_data['improvement']:.0f}% WR",
                            'signals_kept': best_data['signals']
                        })
                elif metric_data['direction'] == 'lower' and best_thresh < current_config:
                    best_data = metric_data['thresholds'].get(best_thresh, {})
                    if best_data.get('win_rate', 0) > baseline_wr + 5:
                        metric_data['recommendation'] = {
                            'action': 'lower',
                            'from': current_config,
                            'to': best_thresh,
                            'impact': f"+{best_data['improvement']:.0f}% WR"
                        }

            results['metrics'][metric_key] = metric_data

            # Classify as strong or weak predictor
            if metric_data['is_predictive']:
                strong_predictors.append(metric_data)
            else:
                weak_predictors.append(metric_data)

            # Log findings
            if metric_data['wins_avg'] is not None and metric_data['rugs_avg'] is not None:
                diff = metric_data['wins_avg'] - metric_data['rugs_avg']
                direction = "↑" if diff > 0 else "↓"

                if metric_data['is_predictive']:
                    indicator = "✅"
                    logger.info(f"   {indicator} {metric_name}:")
                    logger.info(f"      Wins: {metric_data['wins_avg']:.1f} | Rugs: {metric_data['rugs_avg']:.1f} ({direction} wins)")
                    if best_thresh:
                        best_data = metric_data['thresholds'].get(best_thresh, {})
                        op = "≥" if metric_data['direction'] == 'higher' else "≤"
                        logger.info(f"      Best: {op}{best_thresh} → {best_data.get('win_rate', 0):.0f}% WR ({best_data.get('signals', 0)} signals)")
                    if metric_data.get('recommendation'):
                        rec = metric_data['recommendation']
                        logger.info(f"      💡 RECOMMEND: {rec['from']} → {rec['to']} ({rec['impact']})")
                else:
                    logger.info(f"   ➖ {metric_name}: Weak predictor (W:{metric_data['wins_avg']:.1f} R:{metric_data['rugs_avg']:.1f})")

        # Summary
        results['summary'] = {
            'strong_predictors': [m['name'] for m in strong_predictors],
            'weak_predictors': [m['name'] for m in weak_predictors],
            'total_recommendations': len(results['recommendations'])
        }

        logger.info("")
        logger.info(f"   📊 Summary: {len(strong_predictors)} strong predictors, {len(results['recommendations'])} recommendations")

        return results

    def _discover_hidden_patterns(self, data: List[Dict]) -> Dict:
        """
        Discover hidden patterns in the data that we might be missing.
        Analyzes: time patterns, narratives, entry characteristics, signal sources.
        """
        results = {
            'time_patterns': {},
            'narrative_analysis': {},
            'entry_patterns': {},
            'source_analysis': {},
            'insights': [],
            'recommendations': []
        }

        logger.info("")
        logger.info("━" * 50)
        logger.info("🔍 HIDDEN PATTERN DISCOVERY")
        logger.info("━" * 50)

        wins = [d for d in data if d['is_win']]
        rugs = [d for d in data if d['is_rug']]
        baseline_wr = (len(wins) / len(data) * 100) if data else 0

        # 1. TIME PATTERNS - When do wins happen?
        logger.info("")
        logger.info("   ⏰ TIME PATTERNS:")

        hour_stats = {}
        day_stats = {}

        for d in data:
            created = d.get('created_at')
            if created:
                try:
                    if hasattr(created, 'hour'):
                        hour = created.hour
                        day = created.weekday()  # 0=Monday, 6=Sunday
                    else:
                        # Parse if string
                        from datetime import datetime
                        if isinstance(created, str):
                            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        hour = created.hour
                        day = created.weekday()

                    # Hour stats
                    if hour not in hour_stats:
                        hour_stats[hour] = {'total': 0, 'wins': 0}
                    hour_stats[hour]['total'] += 1
                    if d['is_win']:
                        hour_stats[hour]['wins'] += 1

                    # Day stats
                    if day not in day_stats:
                        day_stats[day] = {'total': 0, 'wins': 0}
                    day_stats[day]['total'] += 1
                    if d['is_win']:
                        day_stats[day]['wins'] += 1
                except Exception:
                    pass

        # Find best/worst hours
        best_hours = []
        worst_hours = []
        for hour, stats in hour_stats.items():
            if stats['total'] >= 5:
                wr = stats['wins'] / stats['total'] * 100
                stats['win_rate'] = wr
                if wr >= baseline_wr + 10:
                    best_hours.append((hour, wr, stats['total']))
                elif wr <= baseline_wr - 10:
                    worst_hours.append((hour, wr, stats['total']))

        best_hours.sort(key=lambda x: x[1], reverse=True)
        worst_hours.sort(key=lambda x: x[1])

        if best_hours:
            logger.info(f"      ✅ Best hours (UTC): {', '.join(f'{h}:00 ({wr:.0f}%)' for h, wr, _ in best_hours[:3])}")
            results['time_patterns']['best_hours'] = best_hours[:3]
        if worst_hours:
            logger.info(f"      ⚠️ Worst hours (UTC): {', '.join(f'{h}:00 ({wr:.0f}%)' for h, wr, _ in worst_hours[:3])}")
            results['time_patterns']['worst_hours'] = worst_hours[:3]

        # Find best/worst days
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        best_days = []
        worst_days = []
        for day, stats in day_stats.items():
            if stats['total'] >= 5:
                wr = stats['wins'] / stats['total'] * 100
                stats['win_rate'] = wr
                if wr >= baseline_wr + 10:
                    best_days.append((day_names[day], wr, stats['total']))
                elif wr <= baseline_wr - 10:
                    worst_days.append((day_names[day], wr, stats['total']))

        if best_days:
            logger.info(f"      ✅ Best days: {', '.join(f'{d} ({wr:.0f}%)' for d, wr, _ in best_days)}")
            results['time_patterns']['best_days'] = best_days
        if worst_days:
            logger.info(f"      ⚠️ Worst days: {', '.join(f'{d} ({wr:.0f}%)' for d, wr, _ in worst_days)}")
            results['time_patterns']['worst_days'] = worst_days

        results['time_patterns']['hour_stats'] = hour_stats
        results['time_patterns']['day_stats'] = day_stats

        # 2. NARRATIVE ANALYSIS - Which narratives win?
        logger.info("")
        logger.info("   📖 NARRATIVE PATTERNS:")

        narrative_stats = {}
        for d in data:
            tags = d.get('narrative_tags') or []
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                if tag:
                    if tag not in narrative_stats:
                        narrative_stats[tag] = {'total': 0, 'wins': 0, 'rugs': 0}
                    narrative_stats[tag]['total'] += 1
                    if d['is_win']:
                        narrative_stats[tag]['wins'] += 1
                    if d['is_rug']:
                        narrative_stats[tag]['rugs'] += 1

        winning_narratives = []
        losing_narratives = []
        for tag, stats in narrative_stats.items():
            if stats['total'] >= 3:
                wr = stats['wins'] / stats['total'] * 100
                rr = stats['rugs'] / stats['total'] * 100
                stats['win_rate'] = wr
                stats['rug_rate'] = rr
                if wr >= baseline_wr + 10:
                    winning_narratives.append((tag, wr, stats['total']))
                elif wr <= baseline_wr - 10 or rr > 50:
                    losing_narratives.append((tag, wr, rr, stats['total']))

        winning_narratives.sort(key=lambda x: x[1], reverse=True)
        losing_narratives.sort(key=lambda x: x[2], reverse=True)  # Sort by rug rate

        if winning_narratives:
            logger.info(f"      ✅ Winning narratives: {', '.join(f'{t} ({wr:.0f}%)' for t, wr, _ in winning_narratives[:5])}")
            results['narrative_analysis']['winners'] = winning_narratives[:5]
            results['insights'].append(f"Narratives that win: {', '.join(t for t, _, _ in winning_narratives[:3])}")
        if losing_narratives:
            logger.info(f"      ⚠️ Losing narratives: {', '.join(f'{t} ({wr:.0f}% WR, {rr:.0f}% RR)' for t, wr, rr, _ in losing_narratives[:5])}")
            results['narrative_analysis']['losers'] = losing_narratives[:5]

        if not narrative_stats:
            logger.info("      ➖ No narrative data available")

        results['narrative_analysis']['stats'] = narrative_stats

        # 3. ENTRY CHARACTERISTICS - What distinguishes winners at entry?
        logger.info("")
        logger.info("   🎯 ENTRY CHARACTERISTICS (Wins vs Rugs):")

        # Calculate entry characteristics
        win_bonding = [d.get('bonding_curve_pct', 0) for d in wins if d.get('bonding_curve_pct')]
        rug_bonding = [d.get('bonding_curve_pct', 0) for d in rugs if d.get('bonding_curve_pct')]

        win_mcap = [d.get('market_cap', 0) for d in wins if d.get('market_cap')]
        rug_mcap = [d.get('market_cap', 0) for d in rugs if d.get('market_cap')]

        win_unique = [d.get('unique_buyers', 0) for d in wins if d.get('unique_buyers')]
        rug_unique = [d.get('unique_buyers', 0) for d in rugs if d.get('unique_buyers')]

        if win_bonding and rug_bonding:
            win_avg = sum(win_bonding) / len(win_bonding)
            rug_avg = sum(rug_bonding) / len(rug_bonding)
            if abs(win_avg - rug_avg) > 5:
                direction = "higher" if win_avg > rug_avg else "lower"
                logger.info(f"      Entry Bonding: Wins {win_avg:.0f}% vs Rugs {rug_avg:.0f}% ({direction} wins)")
                results['entry_patterns']['bonding'] = {'wins': win_avg, 'rugs': rug_avg}

        if win_mcap and rug_mcap:
            win_avg = sum(win_mcap) / len(win_mcap)
            rug_avg = sum(rug_mcap) / len(rug_mcap)
            if abs(win_avg - rug_avg) > 5000:
                direction = "lower" if win_avg < rug_avg else "higher"
                logger.info(f"      Entry MCAP: Wins ${win_avg/1000:.0f}K vs Rugs ${rug_avg/1000:.0f}K ({direction} wins)")
                results['entry_patterns']['mcap'] = {'wins': win_avg, 'rugs': rug_avg}

                # Generate recommendation if we're entering too late
                if win_avg < rug_avg and rug_avg > config.MAX_MARKET_CAP_FILTER:
                    results['recommendations'].append({
                        'type': 'pattern',
                        'insight': 'entry_mcap',
                        'message': f"Lower MCAP cap to ${win_avg/1000:.0f}K (wins enter earlier)"
                    })

        if win_unique and rug_unique:
            win_avg = sum(win_unique) / len(win_unique)
            rug_avg = sum(rug_unique) / len(rug_unique)
            if abs(win_avg - rug_avg) > 20:
                direction = "more" if win_avg > rug_avg else "fewer"
                logger.info(f"      Unique Buyers: Wins {win_avg:.0f} vs Rugs {rug_avg:.0f} ({direction} buyers)")
                results['entry_patterns']['unique_buyers'] = {'wins': win_avg, 'rugs': rug_avg}

        # 4. SIGNAL SOURCE ANALYSIS
        logger.info("")
        logger.info("   📡 SIGNAL SOURCE:")

        source_stats = {}
        for d in data:
            source = d.get('signal_source') or d.get('signal_type') or 'unknown'
            if source not in source_stats:
                source_stats[source] = {'total': 0, 'wins': 0}
            source_stats[source]['total'] += 1
            if d['is_win']:
                source_stats[source]['wins'] += 1

        for source, stats in source_stats.items():
            if stats['total'] >= 3:
                wr = stats['wins'] / stats['total'] * 100
                emoji = "✅" if wr >= baseline_wr else "⚠️" if wr < baseline_wr - 10 else "➖"
                logger.info(f"      {emoji} {source}: {wr:.0f}% WR ({stats['total']} signals)")

        results['source_analysis'] = source_stats

        # 5. MULTI-METRIC COMBOS - Do tokens with multiple strong signals win more?
        logger.info("")
        logger.info("   🔗 MULTI-METRIC COMBOS:")

        # Count how many "strong" metrics each token has
        for d in data:
            strong_count = 0
            if (d.get('bonding_curve_pct') or 0) >= 40:
                strong_count += 1
            if (d.get('unique_buyers') or 0) >= 75:
                strong_count += 1
            if (d.get('buy_percentage') or 0) >= 70:
                strong_count += 1
            bs_ratio = (d.get('buys_24h') or 0) / max(d.get('sells_24h') or 1, 1)
            if bs_ratio >= 2.0:
                strong_count += 1
            if (d.get('market_cap') or float('inf')) <= 15000:
                strong_count += 1
            d['strong_metric_count'] = strong_count

        combo_stats = {}
        for d in data:
            count = d['strong_metric_count']
            if count not in combo_stats:
                combo_stats[count] = {'total': 0, 'wins': 0}
            combo_stats[count]['total'] += 1
            if d['is_win']:
                combo_stats[count]['wins'] += 1

        for count in sorted(combo_stats.keys()):
            stats = combo_stats[count]
            if stats['total'] >= 3:
                wr = stats['wins'] / stats['total'] * 100
                emoji = "✅" if wr >= baseline_wr + 5 else "🟡" if wr >= baseline_wr else "🔴"
                logger.info(f"      {emoji} {count} strong metrics: {wr:.0f}% WR ({stats['total']} signals)")

        results['combo_stats'] = combo_stats

        # Check if more strong metrics = better WR
        sorted_combos = sorted(combo_stats.items(), key=lambda x: x[0])
        if len(sorted_combos) >= 2:
            low_combo = sorted_combos[0]
            high_combo = sorted_combos[-1]
            if high_combo[1]['total'] >= 3 and low_combo[1]['total'] >= 3:
                low_wr = low_combo[1]['wins'] / low_combo[1]['total'] * 100
                high_wr = high_combo[1]['wins'] / high_combo[1]['total'] * 100
                if high_wr > low_wr + 10:
                    results['insights'].append(f"More strong metrics = higher WR ({high_combo[0]} metrics: {high_wr:.0f}% vs {low_combo[0]} metrics: {low_wr:.0f}%)")
                    logger.info(f"      💡 Pattern: More strong metrics correlates with higher WR")

        # Summary of insights
        logger.info("")
        if results['insights']:
            logger.info("   💡 KEY INSIGHTS:")
            for insight in results['insights']:
                logger.info(f"      • {insight}")

        return results

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
