"""
Ralph Data Manager - Single source of truth for all ML and analysis data.

All data flows through the database. No more JSON file juggling.
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger


class DataManager:
    """Unified data management - database is the single source of truth."""

    def __init__(self, db):
        self.db = db

    async def get_status(self) -> Dict:
        """Get comprehensive data status."""
        if not self.db or not self.db.pool:
            return {'error': 'Database not available'}

        async with self.db.pool.acquire() as conn:
            # Total signals
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE"
            )

            # Signals with outcomes (usable for ML)
            with_outcomes = await conn.fetchval(
                "SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE AND outcome IS NOT NULL"
            )

            # Outcome breakdown
            outcomes = await conn.fetch('''
                SELECT outcome, COUNT(*) as count
                FROM signals
                WHERE signal_posted = TRUE AND outcome IS NOT NULL
                GROUP BY outcome
            ''')
            outcome_dist = {row['outcome']: row['count'] for row in outcomes}

            # Recent signals (24h)
            recent_24h = await conn.fetchval('''
                SELECT COUNT(*) FROM signals
                WHERE signal_posted = TRUE AND created_at > NOW() - INTERVAL '24 hours'
            ''')

            # Recent with outcomes (24h)
            recent_with_outcomes = await conn.fetchval('''
                SELECT COUNT(*) FROM signals
                WHERE signal_posted = TRUE AND outcome IS NOT NULL
                  AND created_at > NOW() - INTERVAL '24 hours'
            ''')

            # KOL activity
            kol_signals = await conn.fetchval('''
                SELECT COUNT(*) FROM signals
                WHERE signal_posted = TRUE AND kol_wallets IS NOT NULL
                  AND array_length(kol_wallets, 1) > 0
            ''')

            # Smart wallet activity count
            wallet_activity = await conn.fetchval(
                "SELECT COUNT(*) FROM smart_wallet_activity"
            )

            # Tracked wallets
            tracked_wallets = await conn.fetchval(
                "SELECT COUNT(*) FROM tracked_wallets"
            )

            # ML readiness
            ml_ready = with_outcomes >= 30
            ml_status = "✅ Ready" if ml_ready else f"⏳ Need {30 - with_outcomes} more"

        return {
            'total_signals': total or 0,
            'with_outcomes': with_outcomes or 0,
            'pending_outcomes': (total or 0) - (with_outcomes or 0),
            'outcome_distribution': outcome_dist,
            'recent_24h': recent_24h or 0,
            'recent_with_outcomes': recent_with_outcomes or 0,
            'kol_signals': kol_signals or 0,
            'wallet_activity': wallet_activity or 0,
            'tracked_wallets': tracked_wallets or 0,
            'ml_ready': ml_ready,
            'ml_status': ml_status,
            'min_for_ml': 30
        }

    async def get_training_data(self, days: Optional[int] = None) -> List[Dict]:
        """
        Get training data directly from database.
        No JSON files - database is the source of truth.
        """
        if not self.db or not self.db.pool:
            return []

        async with self.db.pool.acquire() as conn:
            query = '''
                SELECT
                    token_address, token_symbol, conviction_score,
                    entry_price, max_price_reached, outcome, max_roi,
                    bonding_curve_pct, buy_percentage, unique_buyers,
                    buys_24h, sells_24h, volume_24h, liquidity, market_cap,
                    kol_wallets, narrative_tags, holder_pattern, created_at
                FROM signals
                WHERE signal_posted = TRUE
                  AND outcome IS NOT NULL
                  AND entry_price > 0
            '''

            if days:
                query += f" AND created_at > NOW() - INTERVAL '{days} days'"

            query += " ORDER BY created_at DESC"

            rows = await conn.fetch(query)

            training_data = []
            for row in rows:
                signal = dict(row)

                # Calculate ROI
                if signal['entry_price'] and signal['max_price_reached']:
                    signal['roi'] = signal['max_price_reached'] / signal['entry_price']
                else:
                    signal['roi'] = signal.get('max_roi', 1.0) or 1.0

                # Determine if pre-grad
                bonding = signal.get('bonding_curve_pct', 0) or 0
                mcap = signal.get('market_cap', 0) or 0
                signal['is_pre_grad'] = bonding < 100 and mcap < 69000

                # Win/loss classification
                outcome = signal.get('outcome', '')
                signal['is_win'] = outcome in ('2x', '5x', '10x', '50x', '100x')
                signal['is_rug'] = outcome == 'rug'
                signal['is_loss'] = outcome == 'loss'

                # KOL info
                kol_wallets = signal.get('kol_wallets') or []
                signal['has_kol'] = len(kol_wallets) > 0
                signal['kol_count'] = len(kol_wallets)

                training_data.append(signal)

            return training_data

    async def get_win_rate_stats(self, days: int = 7) -> Dict:
        """Get win rate statistics for analysis."""
        data = await self.get_training_data(days=days)

        if not data:
            return {'error': 'No data available'}

        total = len(data)
        wins = sum(1 for d in data if d['is_win'])
        rugs = sum(1 for d in data if d['is_rug'])
        losses = sum(1 for d in data if d['is_loss'])
        pending = total - wins - rugs - losses

        # Pre-grad vs post-grad
        pre_grad = [d for d in data if d.get('is_pre_grad', True)]
        post_grad = [d for d in data if not d.get('is_pre_grad', True)]

        pre_grad_wins = sum(1 for d in pre_grad if d['is_win'])
        post_grad_wins = sum(1 for d in post_grad if d['is_win'])

        # KOL vs non-KOL
        kol_data = [d for d in data if d['has_kol']]
        non_kol_data = [d for d in data if not d['has_kol']]

        kol_wins = sum(1 for d in kol_data if d['is_win'])
        non_kol_wins = sum(1 for d in non_kol_data if d['is_win'])

        return {
            'total': total,
            'wins': wins,
            'rugs': rugs,
            'losses': losses,
            'pending': pending,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'rug_rate': (rugs / total * 100) if total > 0 else 0,
            'pre_grad': {
                'total': len(pre_grad),
                'wins': pre_grad_wins,
                'win_rate': (pre_grad_wins / len(pre_grad) * 100) if pre_grad else 0
            },
            'post_grad': {
                'total': len(post_grad),
                'wins': post_grad_wins,
                'win_rate': (post_grad_wins / len(post_grad) * 100) if post_grad else 0
            },
            'kol': {
                'total': len(kol_data),
                'wins': kol_wins,
                'win_rate': (kol_wins / len(kol_data) * 100) if kol_data else 0
            },
            'non_kol': {
                'total': len(non_kol_data),
                'wins': non_kol_wins,
                'win_rate': (non_kol_wins / len(non_kol_data) * 100) if non_kol_data else 0
            }
        }

    async def collect_missed_winners(self) -> Dict:
        """Collect yesterday's winners we missed (for learning)."""
        try:
            from tools.missed_winners_collector import MissedWinnersCollector

            collector = MissedWinnersCollector(self.db)
            missed = await collector.collect_missed_winners()

            return {
                'collected': len(missed),
                'tokens': missed
            }
        except Exception as e:
            logger.error(f"Failed to collect missed winners: {e}")
            return {'error': str(e), 'collected': 0}
