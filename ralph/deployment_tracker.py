#!/usr/bin/env python3
"""
Deployment Tracker for Ralph
Tracks optimizations deployed by Ralph and their monitoring windows
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger


class DeploymentTracker:
    """Track Ralph's deployments and monitoring schedules"""

    def __init__(self, tracker_file: str = 'ralph/deployments.json'):
        self.tracker_file = tracker_file
        self.deployments = []
        self._load()

    def _load(self):
        """Load deployment tracking data"""
        if os.path.exists(self.tracker_file):
            with open(self.tracker_file, 'r') as f:
                self.deployments = json.load(f)
            logger.info(f"📋 Loaded {len(self.deployments)} tracked deployments")
        else:
            self.deployments = []

    def _save(self):
        """Save deployment tracking data"""
        with open(self.tracker_file, 'w') as f:
            json.dump(self.deployments, f, indent=2)
        logger.info(f"💾 Saved {len(self.deployments)} deployments to {self.tracker_file}")

    def track_deployment(
        self,
        optimization_id: str,
        monitor_duration_hours: int,
        acceptance_criteria: Dict,
        baseline_metrics: Optional[Dict] = None,
        changes_made: Optional[List[str]] = None
    ):
        """
        Track a new deployment that needs monitoring

        Args:
            optimization_id: e.g., "OPT-041"
            monitor_duration_hours: How long to monitor (e.g., 6)
            acceptance_criteria: What defines success
            baseline_metrics: Metrics before change
            changes_made: List of what was changed
        """
        now = datetime.utcnow()
        check_at = now + timedelta(hours=monitor_duration_hours)

        deployment = {
            'optimization_id': optimization_id,
            'deployed_at': now.isoformat(),
            'monitor_duration_hours': monitor_duration_hours,
            'check_at': check_at.isoformat(),
            'acceptance_criteria': acceptance_criteria,
            'baseline_metrics': baseline_metrics or {},
            'changes_made': changes_made or [],
            'status': 'monitoring',  # monitoring, decided_keep, decided_revert
            'decision_made_at': None,
            'decision_reason': None,
            'final_metrics': None
        }

        self.deployments.append(deployment)
        self._save()

        logger.info(f"📊 Tracking {optimization_id}")
        logger.info(f"   Monitor for: {monitor_duration_hours} hours")
        logger.info(f"   Check at: {check_at.strftime('%Y-%m-%d %H:%M UTC')}")

        return deployment

    def get_ready_for_review(self) -> List[Dict]:
        """Get deployments whose monitoring window is complete"""
        now = datetime.utcnow()
        ready = []

        for deployment in self.deployments:
            if deployment['status'] != 'monitoring':
                continue

            check_at = datetime.fromisoformat(deployment['check_at'])
            if now >= check_at:
                ready.append(deployment)

        logger.info(f"🔍 Found {len(ready)} deployments ready for review")
        return ready

    def record_decision(
        self,
        optimization_id: str,
        decision: str,  # 'keep' or 'revert'
        reason: str,
        final_metrics: Dict
    ):
        """Record the KEEP/REVERT decision"""
        for deployment in self.deployments:
            if deployment['optimization_id'] == optimization_id and deployment['status'] == 'monitoring':
                deployment['status'] = f'decided_{decision}'
                deployment['decision_made_at'] = datetime.utcnow().isoformat()
                deployment['decision_reason'] = reason
                deployment['final_metrics'] = final_metrics

                self._save()

                logger.info(f"✅ Recorded decision for {optimization_id}: {decision.upper()}")
                logger.info(f"   Reason: {reason}")

                return deployment

        logger.warning(f"⚠️  Could not find monitoring deployment: {optimization_id}")
        return None

    def get_active_deployments(self) -> List[Dict]:
        """Get all deployments currently being monitored"""
        return [d for d in self.deployments if d['status'] == 'monitoring']

    def get_deployment_history(self, limit: int = 10) -> List[Dict]:
        """Get recent deployment history"""
        sorted_deployments = sorted(
            self.deployments,
            key=lambda d: d['deployed_at'],
            reverse=True
        )
        return sorted_deployments[:limit]


if __name__ == "__main__":
    # Example usage
    tracker = DeploymentTracker()

    # Example: Track a deployment
    tracker.track_deployment(
        optimization_id="OPT-041",
        monitor_duration_hours=6,
        acceptance_criteria={
            "credits_reduced": ">40%",
            "signal_quality": "no drop >5%"
        },
        baseline_metrics={
            "credits_per_signal": 50,
            "win_rate": 0.45
        },
        changes_made=[
            "Increased holder cache TTL from 60min to 120min",
            "Added request deduplication"
        ]
    )

    # Check what's ready for review
    ready = tracker.get_ready_for_review()
    print(f"\n{len(ready)} deployments ready for review")
