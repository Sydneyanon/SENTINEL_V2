"""
OPT-034: Dynamic conviction threshold adjustment based on time of day/week

Adjusts MIN_CONVICTION_SCORE dynamically based on historical win rate patterns:
- HOT ZONES (WR >= 65%): Keep threshold at base level (push hard)
- COLD ZONES (WR < 45%): Raise threshold by +10 pts (be selective)

Based on analysis of historical signal outcomes by hour (UTC) and day of week.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
import json
import os

logger = logging.getLogger(__name__)


class TimeOptimizer:
    """
    Dynamically adjusts conviction thresholds based on time of day and day of week.

    Uses historical performance data to identify HOT ZONES (high win rate) and
    COLD ZONES (low win rate), then adjusts thresholds accordingly.
    """

    def __init__(self, base_threshold: int = 75):
        """
        Initialize TimeOptimizer.

        Args:
            base_threshold: Base conviction threshold (default 75 from OPT-024)
        """
        self.base_threshold = base_threshold
        self.hot_hours = set()
        self.cold_hours = set()
        self.hot_days = set()
        self.cold_days = set()
        self.enabled = True

        # Load timing analysis results
        self._load_timing_data()

    def _load_timing_data(self):
        """Load timing analysis results from ralph/timing_analysis_results.json"""
        timing_file = '/app/ralph/timing_analysis_results.json'

        if not os.path.exists(timing_file):
            logger.warning(f"⚠️ Timing analysis file not found: {timing_file}")
            logger.warning("   Run 'python ralph/analyze_timing.py' first")
            logger.warning("   TimeOptimizer will be disabled until timing data is available")
            self.enabled = False
            return

        try:
            with open(timing_file, 'r') as f:
                data = json.load(f)

            self.hot_hours = set(data.get('hot_hours', []))
            self.cold_hours = set(data.get('cold_hours', []))
            self.hot_days = set(data.get('hot_days', []))
            self.cold_days = set(data.get('cold_days', []))

            total_signals = data.get('total_signals', 0)

            logger.info("✅ TimeOptimizer loaded timing data")
            logger.info(f"   Analyzed {total_signals} signals")
            logger.info(f"   Hot hours: {sorted(self.hot_hours)}")
            logger.info(f"   Cold hours: {sorted(self.cold_hours)}")
            logger.info(f"   Hot days: {sorted(self.hot_days)}")
            logger.info(f"   Cold days: {sorted(self.cold_days)}")

            if total_signals < 30:
                logger.warning(f"⚠️ Low sample size ({total_signals} signals)")
                logger.warning("   TimeOptimizer recommendations may not be reliable")

        except Exception as e:
            logger.error(f"❌ Failed to load timing data: {e}")
            logger.error("   TimeOptimizer will be disabled")
            self.enabled = False

    def get_adjusted_threshold(self, timestamp: datetime = None) -> Tuple[int, str]:
        """
        Get adjusted conviction threshold based on current time.

        Args:
            timestamp: Time to check (defaults to current UTC time)

        Returns:
            Tuple of (adjusted_threshold, reason)
        """
        if not self.enabled:
            return self.base_threshold, "TimeOptimizer disabled (no timing data)"

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        hour = timestamp.hour  # 0-23 UTC
        day = timestamp.weekday()  # 0=Monday, 6=Sunday

        # Check hour of day first (more granular)
        if hour in self.hot_hours:
            return self.base_threshold, f"🔥 HOT HOUR ({hour:02d}:00 UTC) - Normal threshold"

        if hour in self.cold_hours:
            adjusted = self.base_threshold + 10
            return adjusted, f"❄️ COLD HOUR ({hour:02d}:00 UTC) - Raised +10 pts"

        # Check day of week if hour is not in hot/cold zones
        if day in self.hot_days:
            return self.base_threshold, f"🔥 HOT DAY - Normal threshold"

        if day in self.cold_days:
            adjusted = self.base_threshold + 10
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            return adjusted, f"❄️ COLD DAY ({day_names[day]}) - Raised +10 pts"

        # Default: neither hot nor cold
        return self.base_threshold, "🌡️ WARM time - Normal threshold"

    def should_post_signal(self, conviction_score: int, timestamp: datetime = None) -> Tuple[bool, str]:
        """
        Check if a signal should be posted based on conviction score and time.

        Args:
            conviction_score: Signal's conviction score
            timestamp: Time to check (defaults to current UTC time)

        Returns:
            Tuple of (should_post, reason)
        """
        adjusted_threshold, time_reason = self.get_adjusted_threshold(timestamp)

        if conviction_score >= adjusted_threshold:
            return True, f"Score {conviction_score} >= {adjusted_threshold} ({time_reason})"
        else:
            return False, f"Score {conviction_score} < {adjusted_threshold} ({time_reason})"

    def get_stats(self) -> Dict:
        """Get optimizer statistics"""
        return {
            'enabled': self.enabled,
            'base_threshold': self.base_threshold,
            'hot_hours': sorted(self.hot_hours),
            'cold_hours': sorted(self.cold_hours),
            'hot_days': sorted(self.hot_days),
            'cold_days': sorted(self.cold_days),
            'hot_hour_count': len(self.hot_hours),
            'cold_hour_count': len(self.cold_hours)
        }


# Global instance (singleton)
_time_optimizer_instance = None


def get_time_optimizer(base_threshold: int = 75) -> TimeOptimizer:
    """
    Get global TimeOptimizer instance (singleton).

    Args:
        base_threshold: Base conviction threshold (only used on first call)

    Returns:
        TimeOptimizer instance
    """
    global _time_optimizer_instance

    if _time_optimizer_instance is None:
        _time_optimizer_instance = TimeOptimizer(base_threshold)

    return _time_optimizer_instance


if __name__ == '__main__':
    # Test the optimizer
    import sys

    logging.basicConfig(level=logging.INFO)

    optimizer = TimeOptimizer()

    if not optimizer.enabled:
        print("❌ TimeOptimizer is disabled (no timing data)")
        print("   Run: python ralph/analyze_timing.py")
        sys.exit(1)

    print("\nTimeOptimizer Statistics:")
    print(json.dumps(optimizer.get_stats(), indent=2))

    # Test current time
    current_threshold, current_reason = optimizer.get_adjusted_threshold()
    print(f"\nCurrent time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Adjusted threshold: {current_threshold}")
    print(f"Reason: {current_reason}")

    # Test various conviction scores
    print("\nTest Signal Scores:")
    for score in [70, 75, 80, 85, 90]:
        should_post, reason = optimizer.should_post_signal(score)
        status = "✅ POST" if should_post else "❌ BLOCK"
        print(f"  Score {score}: {status} - {reason}")
