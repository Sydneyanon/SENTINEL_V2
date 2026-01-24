"""
OPT-055: Helius Credit Usage Tracker
Tracks credit spending and savings from smart gating
"""
from datetime import datetime
from pathlib import Path
import json
from loguru import logger

class CreditTracker:
    """Track Helius API credit usage and savings"""

    def __init__(self, log_file: str = "helius_credits.jsonl"):
        self.log_file = Path(log_file)
        self.session_stats = {
            'holder_checks_executed': 0,
            'holder_checks_skipped': 0,
            'credits_spent': 0,
            'credits_saved': 0,
            'tokens_analyzed': 0,
            'session_start': datetime.utcnow().isoformat()
        }

    def log_holder_check(self, executed: bool, credits: int, reason: str, token_address: str):
        """
        Log a holder check decision

        Args:
            executed: True if check was executed, False if skipped
            credits: Credits spent (10 if executed) or saved (10 if skipped)
            reason: Reason for the decision
            token_address: Token being analyzed
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'holder_check_executed' if executed else 'holder_check_skipped',
            'credits': credits,
            'reason': reason,
            'token': token_address[:8]
        }

        # Update session stats
        if executed:
            self.session_stats['holder_checks_executed'] += 1
            self.session_stats['credits_spent'] += credits
        else:
            self.session_stats['holder_checks_skipped'] += 1
            self.session_stats['credits_saved'] += credits

        self.session_stats['tokens_analyzed'] += 1

        # Append to log file (JSON Lines format)
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.debug(f"Failed to write credit log: {e}")

    def get_session_stats(self) -> dict:
        """Get current session statistics"""
        # Calculate savings percentage
        total_potential = (self.session_stats['holder_checks_executed'] +
                          self.session_stats['holder_checks_skipped']) * 10

        if total_potential > 0:
            savings_pct = (self.session_stats['credits_saved'] / total_potential) * 100
        else:
            savings_pct = 0

        return {
            **self.session_stats,
            'total_tokens_analyzed': self.session_stats['tokens_analyzed'],
            'savings_percentage': savings_pct,
            'efficiency': f"{self.session_stats['credits_saved']}/{total_potential} credits saved"
        }

    def log_session_summary(self):
        """Log session summary to logger"""
        stats = self.get_session_stats()

        logger.info("=" * 60)
        logger.info("💰 OPT-055: HELIUS CREDIT USAGE SUMMARY")
        logger.info(f"   Tokens analyzed: {stats['tokens_analyzed']}")
        logger.info(f"   Holder checks executed: {stats['holder_checks_executed']}")
        logger.info(f"   Holder checks skipped: {stats['holder_checks_skipped']}")
        logger.info(f"   Credits spent: {stats['credits_spent']}")
        logger.info(f"   Credits saved: {stats['credits_saved']}")
        logger.info(f"   Savings: {stats['savings_percentage']:.1f}%")
        logger.info(f"   Efficiency: {stats['efficiency']}")
        logger.info("=" * 60)

# Global instance
_credit_tracker = None

def get_credit_tracker() -> CreditTracker:
    """Get or create global credit tracker instance"""
    global _credit_tracker
    if _credit_tracker is None:
        _credit_tracker = CreditTracker()
    return _credit_tracker
