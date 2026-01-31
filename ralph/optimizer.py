"""
Ralph Threshold Optimizer - Backtests signals to find optimal conviction thresholds.

Analyzes historical signals with known outcomes to determine:
1. Optimal MIN_CONVICTION_SCORE (pre-grad)
2. Optimal POST_GRAD_THRESHOLD (post-grad)
3. Optimal ORGANIC_SCANNER settings
4. ML bonus impact on win rate

Run daily or manually via /optimize command.
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import config


class RalphOptimizer:
    """Backtests conviction thresholds to find optimal settings."""

    def __init__(self, db):
        self.db = db
        self.results = {}

    async def run_optimization(self, days: int = 7) -> Dict:
        """
        Run full optimization analysis on historical signals.

        Args:
            days: Number of days of history to analyze

        Returns:
            Dict with optimization results and recommendations
        """
        logger.info("=" * 60)
        logger.info("🤖 RALPH THRESHOLD OPTIMIZER")
        logger.info("=" * 60)
        logger.info(f"   Analyzing last {days} days of signals...")
        logger.info("")

        try:
            # Get all signals with outcomes
            signals = await self._get_historical_signals(days)

            if len(signals) < 20:
                logger.warning(f"   ⚠️ Only {len(signals)} signals - need 20+ for reliable optimization")
                return {'error': 'insufficient_data', 'signal_count': len(signals)}

            logger.info(f"   📊 Found {len(signals)} signals with outcomes")
            logger.info("")

            # Separate pre-grad and post-grad
            pre_grad_signals = [s for s in signals if s.get('is_pre_grad', True)]
            post_grad_signals = [s for s in signals if not s.get('is_pre_grad', True)]

            logger.info(f"   Pre-grad: {len(pre_grad_signals)} | Post-grad: {len(post_grad_signals)}")
            logger.info("")

            results = {
                'total_signals': len(signals),
                'pre_grad_count': len(pre_grad_signals),
                'post_grad_count': len(post_grad_signals),
                'current_settings': {
                    'min_conviction_score': config.MIN_CONVICTION_SCORE,
                    'post_grad_threshold': config.POST_GRAD_THRESHOLD,
                    'min_unique_buyers': config.ORGANIC_SCANNER.get('min_unique_buyers', 50),
                    'min_buy_ratio': config.ORGANIC_SCANNER.get('min_buy_ratio', 0.65),
                },
                'recommendations': []
            }

            # 1. Optimize PRE-GRAD threshold
            logger.info("━" * 50)
            logger.info("📊 PRE-GRAD THRESHOLD ANALYSIS")
            logger.info("━" * 50)

            pre_grad_results = self._test_thresholds(
                pre_grad_signals,
                thresholds=[25, 30, 35, 40, 45, 50, 55, 60],
                current=config.MIN_CONVICTION_SCORE
            )
            results['pre_grad_analysis'] = pre_grad_results

            if pre_grad_results.get('optimal_threshold'):
                opt = pre_grad_results['optimal_threshold']
                curr = config.MIN_CONVICTION_SCORE
                if opt != curr:
                    results['recommendations'].append({
                        'setting': 'MIN_CONVICTION_SCORE',
                        'current': curr,
                        'recommended': opt,
                        'reason': f"+{pre_grad_results['optimal_wr'] - pre_grad_results['current_wr']:.0f}% WR"
                    })

            # 2. Optimize POST-GRAD threshold
            if len(post_grad_signals) >= 5:
                logger.info("")
                logger.info("━" * 50)
                logger.info("📊 POST-GRAD THRESHOLD ANALYSIS")
                logger.info("━" * 50)

                post_grad_results = self._test_thresholds(
                    post_grad_signals,
                    thresholds=[40, 45, 50, 55, 60, 65, 70],
                    current=config.POST_GRAD_THRESHOLD
                )
                results['post_grad_analysis'] = post_grad_results

                if post_grad_results.get('optimal_threshold'):
                    opt = post_grad_results['optimal_threshold']
                    curr = config.POST_GRAD_THRESHOLD
                    if opt != curr:
                        results['recommendations'].append({
                            'setting': 'POST_GRAD_THRESHOLD',
                            'current': curr,
                            'recommended': opt,
                            'reason': f"+{post_grad_results['optimal_wr'] - post_grad_results['current_wr']:.0f}% WR"
                        })
            else:
                logger.info("")
                logger.info("   ⏭️ Skipping post-grad analysis (< 5 signals)")

            # 3. Analyze buyer count impact
            logger.info("")
            logger.info("━" * 50)
            logger.info("📊 BUYER COUNT ANALYSIS")
            logger.info("━" * 50)

            buyer_results = self._test_buyer_thresholds(pre_grad_signals)
            results['buyer_analysis'] = buyer_results

            # 4. Analyze buy ratio impact
            logger.info("")
            logger.info("━" * 50)
            logger.info("📊 BUY RATIO ANALYSIS")
            logger.info("━" * 50)

            ratio_results = self._test_buy_ratio(pre_grad_signals)
            results['buy_ratio_analysis'] = ratio_results

            # 5. ML Impact Analysis
            logger.info("")
            logger.info("━" * 50)
            logger.info("📊 ML BONUS IMPACT ANALYSIS")
            logger.info("━" * 50)

            ml_results = self._analyze_ml_impact(signals)
            results['ml_analysis'] = ml_results

            # 6. KOL Impact Analysis
            logger.info("")
            logger.info("━" * 50)
            logger.info("📊 KOL IMPACT ANALYSIS")
            logger.info("━" * 50)

            kol_results = self._analyze_kol_impact(signals)
            results['kol_analysis'] = kol_results

            # Summary
            logger.info("")
            logger.info("=" * 60)
            logger.info("🎯 OPTIMIZATION SUMMARY")
            logger.info("=" * 60)

            if results['recommendations']:
                logger.info("   RECOMMENDED CHANGES:")
                for rec in results['recommendations']:
                    logger.info(f"   • {rec['setting']}: {rec['current']} → {rec['recommended']} ({rec['reason']})")
            else:
                logger.info("   ✅ Current settings are optimal (or near-optimal)")

            logger.info("")
            logger.info("=" * 60)

            return results

        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'error': str(e)}

    async def _get_historical_signals(self, days: int) -> List[Dict]:
        """Get historical signals with outcomes for backtesting."""
        if not self.db or not self.db.pool:
            return []

        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT
                    token_address, token_symbol, conviction_score,
                    entry_price, max_price_reached, outcome, max_roi,
                    bonding_curve_pct, buy_percentage, unique_buyers,
                    buys_24h, sells_24h, kol_wallets, market_cap,
                    created_at
                FROM signals
                WHERE signal_posted = TRUE
                  AND outcome IS NOT NULL
                  AND created_at > NOW() - INTERVAL '%s days'
                ORDER BY created_at DESC
            ''' % days)

            signals = []
            for row in rows:
                signal = dict(row)

                # Calculate ROI if not set
                if signal['entry_price'] and signal['max_price_reached']:
                    signal['calculated_roi'] = signal['max_price_reached'] / signal['entry_price']
                else:
                    signal['calculated_roi'] = signal.get('max_roi', 1.0)

                # Determine if pre-grad (bonding < 100% or mcap < 69K at signal time)
                bonding = signal.get('bonding_curve_pct', 0) or 0
                mcap = signal.get('market_cap', 0) or 0
                signal['is_pre_grad'] = bonding < 100 and mcap < 69000

                # Determine win/loss
                outcome = signal.get('outcome', '')
                signal['is_win'] = outcome in ('2x', '5x', '10x', '50x', '100x')
                signal['is_rug'] = outcome == 'rug'
                signal['is_loss'] = outcome == 'loss'

                # KOL backed
                signal['has_kol'] = bool(signal.get('kol_wallets') and len(signal['kol_wallets']) > 0)
                signal['kol_count'] = len(signal.get('kol_wallets') or [])

                signals.append(signal)

            return signals

    def _test_thresholds(self, signals: List[Dict], thresholds: List[int], current: int) -> Dict:
        """Test different conviction score thresholds."""
        results = {'thresholds': {}, 'optimal_threshold': None, 'optimal_wr': 0, 'current_wr': 0}

        best_threshold = current
        best_wr = 0
        best_count = 0

        for threshold in thresholds:
            # Filter signals that would pass this threshold
            passing = [s for s in signals if (s.get('conviction_score') or 0) >= threshold]

            if len(passing) < 3:
                logger.info(f"   Score {threshold}: Too few signals ({len(passing)})")
                continue

            wins = sum(1 for s in passing if s['is_win'])
            rugs = sum(1 for s in passing if s['is_rug'])
            total = len(passing)
            wr = (wins / total * 100) if total > 0 else 0
            rr = (rugs / total * 100) if total > 0 else 0

            # Store result
            results['thresholds'][threshold] = {
                'signals': total,
                'wins': wins,
                'rugs': rugs,
                'win_rate': round(wr, 1),
                'rug_rate': round(rr, 1)
            }

            # Mark current
            marker = " ← Current" if threshold == current else ""
            if threshold == current:
                results['current_wr'] = wr

            # Find optimal (best WR with reasonable signal count)
            # Require at least 30% of max signals to avoid overfitting
            max_signals = max(r['signals'] for r in results['thresholds'].values())
            min_required = max(5, int(max_signals * 0.3))

            if total >= min_required and wr > best_wr:
                best_wr = wr
                best_threshold = threshold
                best_count = total

            # Determine emoji
            if wr >= 50:
                emoji = "🟢"
            elif wr >= 35:
                emoji = "🟡"
            else:
                emoji = "🔴"

            optimal_marker = " ← OPTIMAL" if threshold == best_threshold and threshold != current else ""
            logger.info(f"   {emoji} Score {threshold}: {wr:.0f}% WR ({wins}W/{rugs}R from {total} signals){marker}{optimal_marker}")

        results['optimal_threshold'] = best_threshold
        results['optimal_wr'] = best_wr
        results['optimal_count'] = best_count

        return results

    def _test_buyer_thresholds(self, signals: List[Dict]) -> Dict:
        """Test different minimum buyer count thresholds."""
        results = {'thresholds': {}}

        buyer_thresholds = [20, 30, 40, 50, 60, 80, 100]
        current = config.ORGANIC_SCANNER.get('min_unique_buyers', 50)

        for threshold in buyer_thresholds:
            passing = [s for s in signals if (s.get('unique_buyers') or 0) >= threshold]

            if len(passing) < 3:
                continue

            wins = sum(1 for s in passing if s['is_win'])
            total = len(passing)
            wr = (wins / total * 100) if total > 0 else 0

            results['thresholds'][threshold] = {
                'signals': total,
                'win_rate': round(wr, 1)
            }

            marker = " ← Current" if threshold == current else ""
            emoji = "🟢" if wr >= 50 else "🟡" if wr >= 35 else "🔴"
            logger.info(f"   {emoji} {threshold}+ buyers: {wr:.0f}% WR ({total} signals){marker}")

        return results

    def _test_buy_ratio(self, signals: List[Dict]) -> Dict:
        """Test different buy ratio thresholds."""
        results = {'thresholds': {}}

        ratio_thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        current = config.ORGANIC_SCANNER.get('min_buy_ratio', 0.65)

        for threshold in ratio_thresholds:
            passing = [s for s in signals if (s.get('buy_percentage') or 0) >= threshold * 100]

            if len(passing) < 3:
                continue

            wins = sum(1 for s in passing if s['is_win'])
            total = len(passing)
            wr = (wins / total * 100) if total > 0 else 0

            results['thresholds'][threshold] = {
                'signals': total,
                'win_rate': round(wr, 1)
            }

            marker = " ← Current" if abs(threshold - current) < 0.01 else ""
            emoji = "🟢" if wr >= 50 else "🟡" if wr >= 35 else "🔴"
            logger.info(f"   {emoji} {threshold:.0%}+ buy ratio: {wr:.0f}% WR ({total} signals){marker}")

        return results

    def _analyze_ml_impact(self, signals: List[Dict]) -> Dict:
        """Analyze impact of ML bonus on win rate."""
        # Note: We don't have ML bonus stored in signals, so we estimate
        # based on whether ML would have predicted win/loss

        # For now, just show overall stats
        # TODO: Add ml_bonus column to signals table for proper tracking

        total = len(signals)
        wins = sum(1 for s in signals if s['is_win'])
        wr = (wins / total * 100) if total > 0 else 0

        logger.info(f"   Overall: {wr:.0f}% WR ({wins}/{total})")
        logger.info(f"   ℹ️ ML bonus tracking not yet implemented in signals table")
        logger.info(f"   → Add 'ml_bonus' column to track ML impact over time")

        return {
            'overall_wr': round(wr, 1),
            'note': 'ML bonus column needed for proper analysis'
        }

    def _analyze_kol_impact(self, signals: List[Dict]) -> Dict:
        """Analyze impact of KOL backing on win rate."""
        kol_signals = [s for s in signals if s['has_kol']]
        non_kol_signals = [s for s in signals if not s['has_kol']]

        results = {}

        if len(kol_signals) >= 3:
            kol_wins = sum(1 for s in kol_signals if s['is_win'])
            kol_rugs = sum(1 for s in kol_signals if s['is_rug'])
            kol_wr = (kol_wins / len(kol_signals) * 100)
            kol_rr = (kol_rugs / len(kol_signals) * 100)

            results['kol_backed'] = {
                'signals': len(kol_signals),
                'win_rate': round(kol_wr, 1),
                'rug_rate': round(kol_rr, 1)
            }

            emoji = "🟢" if kol_wr >= 50 else "🟡" if kol_wr >= 35 else "🔴"
            logger.info(f"   {emoji} KOL-backed: {kol_wr:.0f}% WR, {kol_rr:.0f}% RR ({len(kol_signals)} signals)")
        else:
            logger.info(f"   ⏭️ KOL-backed: Insufficient data ({len(kol_signals)} signals)")

        if len(non_kol_signals) >= 3:
            non_kol_wins = sum(1 for s in non_kol_signals if s['is_win'])
            non_kol_rugs = sum(1 for s in non_kol_signals if s['is_rug'])
            non_kol_wr = (non_kol_wins / len(non_kol_signals) * 100)
            non_kol_rr = (non_kol_rugs / len(non_kol_signals) * 100)

            results['organic_only'] = {
                'signals': len(non_kol_signals),
                'win_rate': round(non_kol_wr, 1),
                'rug_rate': round(non_kol_rr, 1)
            }

            emoji = "🟢" if non_kol_wr >= 50 else "🟡" if non_kol_wr >= 35 else "🔴"
            logger.info(f"   {emoji} Organic only: {non_kol_wr:.0f}% WR, {non_kol_rr:.0f}% RR ({len(non_kol_signals)} signals)")
        else:
            logger.info(f"   ⏭️ Organic only: Insufficient data ({len(non_kol_signals)} signals)")

        # Compare
        if 'kol_backed' in results and 'organic_only' in results:
            diff = results['kol_backed']['win_rate'] - results['organic_only']['win_rate']
            if diff > 5:
                logger.info(f"   ✅ KOL backing adds +{diff:.0f}% to win rate")
            elif diff < -5:
                logger.info(f"   ⚠️ KOL backing hurts win rate by {diff:.0f}%")
            else:
                logger.info(f"   ➖ KOL backing has minimal impact ({diff:+.0f}%)")
            results['kol_impact'] = round(diff, 1)

        return results


async def run_optimization(db, days: int = 7) -> Dict:
    """Convenience function to run optimization."""
    optimizer = RalphOptimizer(db)
    return await optimizer.run_optimization(days)
