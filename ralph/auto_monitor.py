#!/usr/bin/env python3
"""
Auto Monitor for Ralph
Runs every 4 hours to check if monitoring windows are complete
Makes KEEP/REVERT decisions automatically based on metrics
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deployment_tracker import DeploymentTracker
from database import Database
import config


class AutoMonitor:
    """Automatically monitor and decide on Ralph's deployments"""

    def __init__(self):
        self.tracker = DeploymentTracker()
        self.db = Database()

    async def collect_current_metrics(self, hours_back: int = 6) -> Dict:
        """
        Collect current performance metrics from database

        Args:
            hours_back: How many hours of data to analyze

        Returns:
            Dict with current metrics
        """
        logger.info(f"📊 Collecting metrics from last {hours_back} hours...")

        since = datetime.utcnow() - timedelta(hours=hours_back)

        # Query signals from database
        async with self.db.pool.acquire() as conn:
            signals = await conn.fetch("""
                SELECT
                    outcome,
                    conviction_score,
                    created_at,
                    roi_percent,
                    helius_credits_used
                FROM signals
                WHERE created_at >= $1
                ORDER BY created_at DESC
            """, since)

        if not signals:
            logger.warning("⚠️  No signals found in monitoring window")
            return {
                'signal_count': 0,
                'win_rate': 0,
                'avg_roi': 0,
                'avg_credits_per_signal': 0,
                'rug_rate': 0
            }

        # Calculate metrics
        total_signals = len(signals)
        wins = sum(1 for s in signals if s['outcome'] in ['2x', '10x', '50x', '100x'])
        rugs = sum(1 for s in signals if s['outcome'] == 'rug')
        total_roi = sum(s['roi_percent'] or 0 for s in signals)
        total_credits = sum(s['helius_credits_used'] or 0 for s in signals)

        metrics = {
            'signal_count': total_signals,
            'win_rate': wins / total_signals if total_signals > 0 else 0,
            'avg_roi': total_roi / total_signals if total_signals > 0 else 0,
            'avg_credits_per_signal': total_credits / total_signals if total_signals > 0 else 0,
            'rug_rate': rugs / total_signals if total_signals > 0 else 0,
            'collection_time': datetime.utcnow().isoformat()
        }

        logger.info(f"   Signals: {total_signals}")
        logger.info(f"   Win rate: {metrics['win_rate']*100:.1f}%")
        logger.info(f"   Avg ROI: {metrics['avg_roi']:.1f}%")
        logger.info(f"   Credits/signal: {metrics['avg_credits_per_signal']:.1f}")

        return metrics

    def evaluate_deployment(self, deployment: Dict, current_metrics: Dict) -> tuple[str, str]:
        """
        Decide KEEP or REVERT based on acceptance criteria

        Args:
            deployment: Deployment data with baseline and criteria
            current_metrics: Current performance metrics

        Returns:
            Tuple of (decision, reason)
        """
        opt_id = deployment['optimization_id']
        criteria = deployment['acceptance_criteria']
        baseline = deployment['baseline_metrics']

        logger.info(f"\n🔍 Evaluating {opt_id}...")

        # If no baseline, can't compare
        if not baseline:
            return ('keep', 'No baseline to compare - assuming success')

        # Check each criterion
        reasons = []
        passes = 0
        total_checks = 0

        # Win rate improvement
        if 'win_rate_improvement' in criteria:
            total_checks += 1
            required = float(criteria['win_rate_improvement'].replace('%', '').replace('>', ''))
            baseline_wr = baseline.get('win_rate', 0)
            current_wr = current_metrics.get('win_rate', 0)
            improvement = ((current_wr - baseline_wr) / baseline_wr * 100) if baseline_wr > 0 else 0

            if improvement >= required:
                passes += 1
                reasons.append(f"✅ Win rate improved {improvement:.1f}% (target: >{required}%)")
            else:
                reasons.append(f"❌ Win rate only improved {improvement:.1f}% (target: >{required}%)")

        # Credit reduction
        if 'credits_reduced' in criteria:
            total_checks += 1
            required = float(criteria['credits_reduced'].replace('%', '').replace('>', ''))
            baseline_credits = baseline.get('avg_credits_per_signal', 0)
            current_credits = current_metrics.get('avg_credits_per_signal', 0)
            reduction = ((baseline_credits - current_credits) / baseline_credits * 100) if baseline_credits > 0 else 0

            if reduction >= required:
                passes += 1
                reasons.append(f"✅ Credits reduced {reduction:.1f}% (target: >{required}%)")
            else:
                reasons.append(f"❌ Credits only reduced {reduction:.1f}% (target: >{required}%)")

        # Rug rate reduction
        if 'rug_rate_reduction' in criteria:
            total_checks += 1
            required = float(criteria['rug_rate_reduction'].replace('%', '').replace('>', ''))
            baseline_rugs = baseline.get('rug_rate', 0)
            current_rugs = current_metrics.get('rug_rate', 0)
            reduction = ((baseline_rugs - current_rugs) / baseline_rugs * 100) if baseline_rugs > 0 else 0

            if reduction >= required:
                passes += 1
                reasons.append(f"✅ Rug rate reduced {reduction:.1f}% (target: >{required}%)")
            else:
                reasons.append(f"❌ Rug rate only reduced {reduction:.1f}% (target: >{required}%)")

        # Signal count minimum
        if 'min_signal_count' in criteria:
            total_checks += 1
            required = int(criteria['min_signal_count'])
            current_count = current_metrics.get('signal_count', 0)

            if current_count >= required:
                passes += 1
                reasons.append(f"✅ Signal count {current_count} >= {required}")
            else:
                reasons.append(f"❌ Signal count {current_count} < {required}")

        # Make decision
        if total_checks == 0:
            decision = 'keep'
            reason = 'No specific criteria - assuming success'
        elif passes >= total_checks / 2:  # Pass if 50%+ criteria met
            decision = 'keep'
            reason = f"Passed {passes}/{total_checks} criteria:\n" + '\n'.join(reasons)
        else:
            decision = 'revert'
            reason = f"Failed - only {passes}/{total_checks} criteria met:\n" + '\n'.join(reasons)

        return (decision, reason)

    async def process_ready_deployments(self):
        """Check and decide on all deployments ready for review"""
        logger.info("\n" + "="*60)
        logger.info("🤖 Ralph Auto-Monitor Running")
        logger.info("="*60)

        ready = self.tracker.get_ready_for_review()

        if not ready:
            logger.info("✅ No deployments ready for review")
            return

        logger.info(f"📋 {len(ready)} deployment(s) ready for review\n")

        for deployment in ready:
            opt_id = deployment['optimization_id']
            monitor_hours = deployment['monitor_duration_hours']

            logger.info(f"\n{'='*60}")
            logger.info(f"Reviewing: {opt_id}")
            logger.info(f"Deployed: {deployment['deployed_at']}")
            logger.info(f"Monitored: {monitor_hours} hours")
            logger.info(f"{'='*60}")

            # Collect current metrics
            current_metrics = await self.collect_current_metrics(hours_back=monitor_hours)

            # Evaluate
            decision, reason = self.evaluate_deployment(deployment, current_metrics)

            # Record decision
            self.tracker.record_decision(
                optimization_id=opt_id,
                decision=decision,
                reason=reason,
                final_metrics=current_metrics
            )

            # Log decision
            logger.info(f"\n🎯 DECISION: {decision.upper()}")
            logger.info(f"📝 Reason:\n{reason}")

            # TODO: Actually execute REVERT if needed
            if decision == 'revert':
                logger.warning(f"⚠️  Would revert {opt_id} (auto-revert not implemented yet)")
                logger.warning(f"   Manual action needed: git revert <commit>")

        logger.info("\n" + "="*60)
        logger.info("✅ Auto-monitor complete")
        logger.info("="*60)

    async def run(self):
        """Main entry point"""
        try:
            await self.db.connect()
            await self.process_ready_deployments()
        finally:
            await self.db.close()


async def main():
    """Run the auto-monitor"""
    monitor = AutoMonitor()
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
