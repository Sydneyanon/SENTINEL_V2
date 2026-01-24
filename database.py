import asyncpg
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None
        self.database_url = os.getenv('DATABASE_URL')
        
        if not self.database_url:
            logger.error("❌ DATABASE_URL not found in environment variables")
            raise ValueError("DATABASE_URL environment variable is required")
    
    async def connect(self):
        """Create connection pool to PostgreSQL"""
        try:
            self.pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
            logger.info("✅ Database pool created")
            await self.create_tables()
        except Exception as e:
            logger.error(f"❌ Failed to create database pool: {e}")
            raise
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    async def create_tables(self):
        """Create necessary tables if they don't exist"""
        async with self.pool.acquire() as conn:
            # Signals table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY,
                    token_address TEXT UNIQUE NOT NULL,
                    token_name TEXT,
                    token_symbol TEXT,
                    signal_type TEXT NOT NULL,
                    bonding_curve_pct REAL,
                    conviction_score INTEGER NOT NULL,
                    entry_price REAL,
                    current_price REAL,
                    liquidity REAL,
                    volume_24h REAL,
                    market_cap REAL,
                    signal_posted BOOLEAN DEFAULT FALSE,
                    telegram_message_id INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Performance tracking table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    id SERIAL PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    milestone REAL NOT NULL,
                    price_at_milestone REAL NOT NULL,
                    time_to_milestone INTERVAL,
                    reached_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(token_address, milestone)
                )
            ''')
            
            # KOL buys table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS kol_buys (
                    id SERIAL PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    kol_wallet TEXT NOT NULL,
                    amount_sol REAL,
                    transaction_signature TEXT UNIQUE,
                    detected_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Smart wallet activity table (detailed tracking)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS smart_wallet_activity (
                    id SERIAL PRIMARY KEY,
                    wallet_address TEXT NOT NULL,
                    wallet_name TEXT NOT NULL,
                    wallet_tier TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount REAL,
                    transaction_signature TEXT UNIQUE NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    detected_at TIMESTAMP DEFAULT NOW(),
                    win_rate REAL,
                    pnl_30d REAL
                )
            ''')

            # Add win_rate and pnl_30d columns if they don't exist (migration)
            try:
                await conn.execute('''
                    ALTER TABLE smart_wallet_activity
                    ADD COLUMN IF NOT EXISTS win_rate REAL
                ''')
                await conn.execute('''
                    ALTER TABLE smart_wallet_activity
                    ADD COLUMN IF NOT EXISTS pnl_30d REAL
                ''')
            except Exception as e:
                # Columns might already exist, ignore
                pass

            # OPT-051: Add posting failure tracking columns
            try:
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS posting_failed BOOLEAN DEFAULT FALSE
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS posting_error TEXT
                ''')
            except Exception as e:
                # Columns might already exist, ignore
                pass

            # OPT-000 PREREQUISITE: Add outcome tracking for data-driven optimizations
            try:
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS outcome TEXT
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS outcome_price REAL
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS outcome_timestamp TIMESTAMP
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS max_price_reached REAL
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS max_roi REAL
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS narrative_tags TEXT[]
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS kol_wallets TEXT[]
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS kol_tiers TEXT[]
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS holder_pattern TEXT
                ''')
            except Exception as e:
                # Columns might already exist, ignore
                logger.debug(f"Outcome tracking columns migration: {e}")
                pass
            
            # OPT-016: KOL Performance tracking table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS kol_performance (
                    wallet_address TEXT PRIMARY KEY,
                    wallet_name TEXT,
                    wallet_tier TEXT,
                    total_signals INTEGER DEFAULT 0,
                    successful_signals INTEGER DEFAULT 0,
                    rug_signals INTEGER DEFAULT 0,
                    loss_signals INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    avg_roi REAL DEFAULT 0,
                    total_roi REAL DEFAULT 0,
                    last_signal_at TIMESTAMP,
                    performance_tier TEXT,
                    scoring_multiplier REAL DEFAULT 1.0,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Create indexes separately (PostgreSQL syntax)
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_smart_wallet_token
                ON smart_wallet_activity(token_address)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_smart_wallet_wallet
                ON smart_wallet_activity(wallet_address)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_smart_wallet_timestamp
                ON smart_wallet_activity(timestamp)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_kol_performance_win_rate
                ON kol_performance(win_rate DESC)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_kol_performance_total_signals
                ON kol_performance(total_signals DESC)
            ''')

            logger.info("✅ Database tables created/verified")
    
    async def insert_signal(self, signal_data: Dict):
        """
        Insert a new signal with full metadata tracking

        OPT-016: Now saves kol_wallets, kol_tiers, narrative_tags, holder_pattern
        This enables wallet performance tracking and pattern analysis
        """
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO signals
                (token_address, token_name, token_symbol, signal_type, bonding_curve_pct,
                 conviction_score, entry_price, liquidity, volume_24h, market_cap,
                 kol_wallets, kol_tiers, narrative_tags, holder_pattern)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (token_address) DO UPDATE SET
                    conviction_score = EXCLUDED.conviction_score,
                    bonding_curve_pct = EXCLUDED.bonding_curve_pct,
                    kol_wallets = EXCLUDED.kol_wallets,
                    kol_tiers = EXCLUDED.kol_tiers,
                    narrative_tags = EXCLUDED.narrative_tags,
                    holder_pattern = EXCLUDED.holder_pattern,
                    updated_at = NOW()
            ''', signal_data['token_address'], signal_data.get('token_name'),
                signal_data.get('token_symbol'), signal_data['signal_type'],
                signal_data.get('bonding_curve_pct'), signal_data['conviction_score'],
                signal_data.get('entry_price'), signal_data.get('liquidity'),
                signal_data.get('volume_24h'), signal_data.get('market_cap'),
                signal_data.get('kol_wallets', []), signal_data.get('kol_tiers', []),
                signal_data.get('narrative_tags', []), signal_data.get('holder_pattern'))
    
    async def mark_signal_posted(self, token_address: str, message_id: int):
        """Mark a signal as posted to Telegram"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET signal_posted = TRUE, telegram_message_id = $1, updated_at = NOW()
                WHERE token_address = $2
            ''', message_id, token_address)

    async def mark_posting_failed(self, token_address: str, error_reason: str):
        """
        OPT-051: Mark a signal as failed to post to Telegram

        Args:
            token_address: Token contract address
            error_reason: Reason for posting failure
        """
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET signal_posted = FALSE,
                    posting_failed = TRUE,
                    posting_error = $1,
                    updated_at = NOW()
                WHERE token_address = $2
            ''', error_reason, token_address)
    
    async def get_signal(self, token_address: str) -> Optional[Dict]:
        """Get a signal by token address"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM signals WHERE token_address = $1',
                token_address
            )
            return dict(row) if row else None
    
    async def update_price(self, token_address: str, current_price: float):
        """Update current price for a token"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals 
                SET current_price = $1, updated_at = NOW()
                WHERE token_address = $2
            ''', current_price, token_address)
    
    async def insert_milestone(self, token_address: str, milestone: float, price: float):
        """Record a milestone reached"""
        async with self.pool.acquire() as conn:
            # Get entry time
            signal = await self.get_signal(token_address)
            if signal:
                await conn.execute('''
                    INSERT INTO performance (token_address, milestone, price_at_milestone, time_to_milestone)
                    VALUES ($1, $2, $3, NOW() - $4)
                    ON CONFLICT (token_address, milestone) DO NOTHING
                ''', token_address, milestone, price, signal['created_at'])
    
    async def insert_kol_buy(self, token_address: str, kol_wallet: str, amount_sol: float, tx_sig: str):
        """Record a KOL buy"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO kol_buys (token_address, kol_wallet, amount_sol, transaction_signature)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (transaction_signature) DO NOTHING
            ''', token_address, kol_wallet, amount_sol, tx_sig)
    
    async def get_kol_buy_count(self, token_address: str) -> int:
        """Get count of KOL buys for a token"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM kol_buys WHERE token_address = $1',
                token_address
            )
            return count or 0
    
    async def get_posted_signals_count(self) -> int:
        """Get total count of posted signals"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE'
            )
            return count or 0
    
    async def get_signals_today(self) -> List[Dict]:
        """Get all signals posted today"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM signals
                WHERE signal_posted = TRUE
                AND DATE(created_at) = CURRENT_DATE
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in rows]

    async def get_total_signal_count(self) -> int:
        """Get total count of all signals ever posted"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE'
            )
            return count or 0

    async def get_signals_in_last_hours(self, hours: int) -> List[Dict]:
        """Get signals posted in the last N hours"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM signals
                WHERE signal_posted = TRUE
                AND created_at >= NOW() - make_interval(hours => $1)
                ORDER BY created_at DESC
            ''', hours)
            return [dict(row) for row in rows]

    async def get_highest_milestone(self, token_address: str) -> Optional[float]:
        """Get the highest milestone reached for a token"""
        async with self.pool.acquire() as conn:
            milestone = await conn.fetchval('''
                SELECT MAX(milestone) FROM performance
                WHERE token_address = $1
            ''', token_address)
            return milestone

    async def insert_smart_wallet_activity(
        self,
        wallet_address: str,
        wallet_name: str,
        wallet_tier: str,
        token_address: str,
        transaction_type: str,
        amount: float,
        transaction_signature: str,
        timestamp: datetime,
        win_rate: Optional[float] = None,
        pnl_30d: Optional[float] = None
    ):
        """Record smart wallet activity with KOL metadata"""
        # Handle None wallet_name (database has NOT NULL constraint)
        if wallet_name is None:
            wallet_name = f"KOL_{wallet_address[:8]}"

        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO smart_wallet_activity
                (wallet_address, wallet_name, wallet_tier, token_address,
                 transaction_type, amount, transaction_signature, timestamp, win_rate, pnl_30d)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (transaction_signature) DO NOTHING
            ''', wallet_address, wallet_name, wallet_tier, token_address,
                transaction_type, amount, transaction_signature, timestamp, win_rate, pnl_30d)
    
    async def get_smart_wallet_activity(
        self, 
        token_address: str, 
        hours: int = 24
    ) -> List[Dict]:
        """Get smart wallet activity for a token in the last N hours"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM smart_wallet_activity
                WHERE token_address = $1
                AND timestamp > NOW() - INTERVAL '{} hours'
                ORDER BY timestamp DESC
            '''.format(hours), token_address)  # FIXED: Use .format() for interval
            return [dict(row) for row in rows]
    
    async def get_wallet_performance(
        self,
        wallet_address: str,
        days: int = 30
    ) -> Dict:
        """Get performance stats for a specific wallet"""
        async with self.pool.acquire() as conn:
            total_trades = await conn.fetchval('''
                SELECT COUNT(*) FROM smart_wallet_activity
                WHERE wallet_address = $1
                AND timestamp > NOW() - INTERVAL '{} days'
            '''.format(days), wallet_address)  # FIXED: Use .format() for interval

            return {
                'wallet_address': wallet_address,
                'total_trades': total_trades or 0,
                'period_days': days
            }

    async def update_signal_outcome(
        self,
        token_address: str,
        outcome: str,
        outcome_price: float,
        max_price_reached: float,
        max_roi: float
    ):
        """
        OPT-000 PREREQUISITE: Update signal outcome for tracking

        Args:
            token_address: Token contract address
            outcome: rug, loss, 2x, 5x, 10x, 50x, 100x
            outcome_price: Final price at outcome determination
            max_price_reached: Highest price reached
            max_roi: Maximum ROI achieved
        """
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET outcome = $1,
                    outcome_price = $2,
                    outcome_timestamp = NOW(),
                    max_price_reached = $3,
                    max_roi = $4,
                    updated_at = NOW()
                WHERE token_address = $5
            ''', outcome, outcome_price, max_price_reached, max_roi, token_address)

    async def update_signal_metadata(
        self,
        token_address: str,
        narrative_tags: List[str],
        kol_wallets: List[str],
        kol_tiers: List[str],
        holder_pattern: str
    ):
        """
        OPT-000 PREREQUISITE: Update signal metadata for pattern analysis

        Args:
            token_address: Token contract address
            narrative_tags: List of narratives (AI, meme, cat, etc.)
            kol_wallets: List of KOL wallet addresses that bought
            kol_tiers: List of KOL tiers (god, elite, whale)
            holder_pattern: Holder distribution pattern (concentrated, distributed, etc.)
        """
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET narrative_tags = $1,
                    kol_wallets = $2,
                    kol_tiers = $3,
                    holder_pattern = $4,
                    updated_at = NOW()
                WHERE token_address = $5
            ''', narrative_tags, kol_wallets, kol_tiers, holder_pattern, token_address)

    async def get_signals_with_outcomes(
        self,
        days: int = 7,
        min_signals: int = 3
    ) -> List[Dict]:
        """
        OPT-000: Get signals with outcomes for pattern analysis

        Args:
            days: Number of days to look back
            min_signals: Minimum signals per pattern to consider

        Returns:
            List of signals with full metadata and outcomes
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM signals
                WHERE signal_posted = TRUE
                AND outcome IS NOT NULL
                AND created_at >= NOW() - make_interval(days => $1)
                ORDER BY created_at DESC
            ''', days)
            return [dict(row) for row in rows]

    async def get_pattern_win_rates(
        self,
        days: int = 7
    ) -> List[Dict]:
        """
        OPT-000: Calculate win rate by pattern (KOL tier + narrative + holder pattern)

        Args:
            days: Number of days to analyze

        Returns:
            List of patterns with win rates
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT
                    kol_tiers,
                    narrative_tags,
                    holder_pattern,
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN outcome IN ('2x', '5x', '10x', '50x', '100x') THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                    ROUND(
                        100.0 * SUM(CASE WHEN outcome IN ('2x', '5x', '10x', '50x', '100x') THEN 1 ELSE 0 END) /
                        NULLIF(COUNT(*), 0),
                        2
                    ) as win_rate_pct,
                    ROUND(AVG(max_roi), 2) as avg_roi
                FROM signals
                WHERE signal_posted = TRUE
                AND outcome IS NOT NULL
                AND created_at >= NOW() - make_interval(days => $1)
                GROUP BY kol_tiers, narrative_tags, holder_pattern
                HAVING COUNT(*) >= 3
                ORDER BY win_rate_pct DESC
            ''', days)
            return [dict(row) for row in rows]

    async def update_kol_performance(self, days: int = 30) -> Dict:
        """
        OPT-016: Calculate and update KOL performance metrics

        Analyzes signals from last N days and calculates per-wallet performance.
        Updates kol_performance table with win_rate, avg_roi, and scoring multiplier.

        Args:
            days: Number of days to analyze (default: 30)

        Returns:
            Dict with summary stats
        """
        async with self.pool.acquire() as conn:
            # Get all signals with outcomes and KOL wallets
            signals = await conn.fetch('''
                SELECT
                    token_address,
                    kol_wallets,
                    kol_tiers,
                    outcome,
                    max_roi,
                    created_at
                FROM signals
                WHERE signal_posted = TRUE
                AND outcome IS NOT NULL
                AND kol_wallets IS NOT NULL
                AND array_length(kol_wallets, 1) > 0
                AND created_at >= NOW() - make_interval(days => $1)
            ''', days)

            # Aggregate performance by wallet
            wallet_stats = {}

            for signal in signals:
                kol_wallets = signal['kol_wallets'] or []
                kol_tiers = signal['kol_tiers'] or []
                outcome = signal['outcome']
                roi = signal['max_roi'] or 1.0

                # Determine if win/rug/loss
                is_win = outcome in ['2x', '10x', '50x', '100x']
                is_rug = outcome == 'rug'
                is_loss = outcome == 'loss'

                # Update stats for each wallet involved
                for i, wallet in enumerate(kol_wallets):
                    if wallet not in wallet_stats:
                        wallet_stats[wallet] = {
                            'wallet': wallet,
                            'tier': kol_tiers[i] if i < len(kol_tiers) else 'unknown',
                            'total': 0,
                            'wins': 0,
                            'rugs': 0,
                            'losses': 0,
                            'total_roi': 0
                        }

                    wallet_stats[wallet]['total'] += 1
                    wallet_stats[wallet]['total_roi'] += roi

                    if is_win:
                        wallet_stats[wallet]['wins'] += 1
                    elif is_rug:
                        wallet_stats[wallet]['rugs'] += 1
                    elif is_loss:
                        wallet_stats[wallet]['losses'] += 1

            # Calculate metrics and update database
            updated_count = 0

            for wallet, stats in wallet_stats.items():
                win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
                avg_roi = stats['total_roi'] / stats['total'] if stats['total'] > 0 else 0

                # Determine performance tier and scoring multiplier
                # OPT-016: High performers (>70% WR): 2x multiplier
                # Medium performers (50-70% WR): 1.5x multiplier
                # Low performers (<50% WR): 0.5x multiplier
                if win_rate >= 75 and stats['total'] >= 10:
                    performance_tier = 'elite'
                    scoring_multiplier = 2.0
                elif win_rate >= 70:
                    performance_tier = 'high'
                    scoring_multiplier = 2.0
                elif win_rate >= 50:
                    performance_tier = 'medium'
                    scoring_multiplier = 1.5
                elif win_rate >= 40:
                    performance_tier = 'low'
                    scoring_multiplier = 1.0
                else:
                    performance_tier = 'poor'
                    scoring_multiplier = 0.5

                # Upsert to kol_performance table
                await conn.execute('''
                    INSERT INTO kol_performance
                    (wallet_address, wallet_tier, total_signals, successful_signals,
                     rug_signals, loss_signals, win_rate, avg_roi, total_roi,
                     performance_tier, scoring_multiplier, last_signal_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                    ON CONFLICT (wallet_address) DO UPDATE SET
                        wallet_tier = EXCLUDED.wallet_tier,
                        total_signals = EXCLUDED.total_signals,
                        successful_signals = EXCLUDED.successful_signals,
                        rug_signals = EXCLUDED.rug_signals,
                        loss_signals = EXCLUDED.loss_signals,
                        win_rate = EXCLUDED.win_rate,
                        avg_roi = EXCLUDED.avg_roi,
                        total_roi = EXCLUDED.total_roi,
                        performance_tier = EXCLUDED.performance_tier,
                        scoring_multiplier = EXCLUDED.scoring_multiplier,
                        last_signal_at = EXCLUDED.last_signal_at,
                        updated_at = NOW()
                ''', wallet, stats['tier'], stats['total'], stats['wins'],
                    stats['rugs'], stats['losses'], win_rate, avg_roi, stats['total_roi'],
                    performance_tier, scoring_multiplier)

                updated_count += 1

            logger.info(f"✅ Updated KOL performance for {updated_count} wallets")

            return {
                'wallets_updated': updated_count,
                'analysis_period_days': days,
                'timestamp': datetime.utcnow()
            }

    async def get_kol_performance(self, min_signals: int = 5) -> List[Dict]:
        """
        OPT-016: Get KOL performance leaderboard

        Args:
            min_signals: Minimum signals to include wallet (default: 5)

        Returns:
            List of wallets with performance metrics, sorted by win_rate
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT
                    wallet_address,
                    wallet_tier,
                    total_signals,
                    successful_signals,
                    rug_signals,
                    loss_signals,
                    win_rate,
                    avg_roi,
                    performance_tier,
                    scoring_multiplier,
                    last_signal_at
                FROM kol_performance
                WHERE total_signals >= $1
                ORDER BY win_rate DESC, total_signals DESC
                LIMIT 50
            ''', min_signals)
            return [dict(row) for row in rows]

    async def get_wallet_multiplier(self, wallet_address: str) -> float:
        """
        OPT-016: Get scoring multiplier for a specific wallet

        Args:
            wallet_address: Wallet address

        Returns:
            Scoring multiplier (default 1.0 if not found)
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT scoring_multiplier
                FROM kol_performance
                WHERE wallet_address = $1
            ''', wallet_address)

            if row:
                return row['scoring_multiplier']
            return 1.0  # Default multiplier for wallets with no performance history
