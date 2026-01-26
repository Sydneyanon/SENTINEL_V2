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
                # Track signal source (kol_buy, telegram_call, whale_buy, etc.)
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS signal_source TEXT
                ''')
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
                # Buy/Sell ratio tracking for ML (2026-01-25)
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS buys_24h INTEGER
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS sells_24h INTEGER
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS buy_percentage REAL
                ''')
                await conn.execute('''
                    ALTER TABLE signals
                    ADD COLUMN IF NOT EXISTS buy_sell_score INTEGER
                ''')
            except Exception as e:
                # Columns might already exist, ignore
                logger.debug(f"Outcome tracking columns migration: {e}")
                pass
            
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

            # Whale wallets table (from historical data collector)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS whale_wallets (
                    id SERIAL PRIMARY KEY,
                    wallet_address TEXT UNIQUE NOT NULL,
                    tokens_bought_count INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    early_buyer BOOLEAN DEFAULT FALSE,
                    is_early_whale BOOLEAN DEFAULT FALSE,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Whale token purchases (many-to-many)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS whale_token_purchases (
                    id SERIAL PRIMARY KEY,
                    whale_address TEXT NOT NULL REFERENCES whale_wallets(wallet_address),
                    token_address TEXT NOT NULL,
                    token_symbol TEXT,
                    early_buyer BOOLEAN DEFAULT FALSE,
                    outcome TEXT,
                    detected_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(whale_address, token_address)
                )
            ''')

            # Index for fast whale lookups
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_whale_address
                ON whale_wallets(wallet_address)
            ''')

            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_whale_purchases
                ON whale_token_purchases(whale_address)
            ''')

            # Telegram calls table (persistent call tracking)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_calls (
                    id SERIAL PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    message_text TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    detected_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Indexes for fast telegram call lookups
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_telegram_calls_token
                ON telegram_calls(token_address)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_telegram_calls_timestamp
                ON telegram_calls(timestamp DESC)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_telegram_calls_group
                ON telegram_calls(group_name)
            ''')

            # Group correlations table (tracks which groups call together)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS group_correlations (
                    id SERIAL PRIMARY KEY,
                    group_a TEXT NOT NULL,
                    group_b TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    time_diff_seconds INTEGER NOT NULL,
                    correlation_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(group_a, group_b, token_address, correlation_date)
                )
            ''')

            # Index for group correlation analysis
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_group_correlations_groups
                ON group_correlations(group_a, group_b)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_group_correlations_date
                ON group_correlations(correlation_date DESC)
            ''')

            logger.info("✅ Database tables created/verified")
    
    async def insert_signal(self, signal_data: Dict):
        """Insert a new signal"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO signals
                (token_address, token_name, token_symbol, signal_type, signal_source, bonding_curve_pct,
                 conviction_score, entry_price, liquidity, volume_24h, market_cap,
                 buys_24h, sells_24h, buy_percentage, buy_sell_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (token_address) DO UPDATE SET
                    conviction_score = EXCLUDED.conviction_score,
                    bonding_curve_pct = EXCLUDED.bonding_curve_pct,
                    signal_source = EXCLUDED.signal_source,
                    buys_24h = EXCLUDED.buys_24h,
                    sells_24h = EXCLUDED.sells_24h,
                    buy_percentage = EXCLUDED.buy_percentage,
                    buy_sell_score = EXCLUDED.buy_sell_score,
                    updated_at = NOW()
            ''', signal_data['token_address'], signal_data.get('token_name'),
                signal_data.get('token_symbol'), signal_data['signal_type'],
                signal_data.get('signal_source', 'unknown'), signal_data.get('bonding_curve_pct'),
                signal_data['conviction_score'],
                signal_data.get('entry_price'), signal_data.get('liquidity'),
                signal_data.get('volume_24h'), signal_data.get('market_cap'),
                signal_data.get('buys_24h'), signal_data.get('sells_24h'),
                signal_data.get('buy_percentage'), signal_data.get('buy_sell_score'))
    
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
        """Update current price and track peak price for a token"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals
                SET current_price = $1,
                    max_price_reached = GREATEST(COALESCE(max_price_reached, 0), $1),
                    updated_at = NOW()
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


    # =========================================================================
    # WHALE WALLET METHODS (for historical collector whale tracking)
    # =========================================================================

    async def insert_whale_wallet(self, whale_data: Dict):
        """
        Insert or update a whale wallet from historical data

        Args:
            whale_data: {
                "address": "wallet_address",
                "tokens_bought_count": 20,
                "wins": 17,
                "win_rate": 0.85,
                "is_early_whale": True
            }
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO whale_wallets (
                    wallet_address, tokens_bought_count, wins, win_rate, is_early_whale, last_updated
                )
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (wallet_address)
                DO UPDATE SET
                    tokens_bought_count = $2,
                    wins = $3,
                    win_rate = $4,
                    is_early_whale = $5,
                    last_updated = NOW()
            """,
                whale_data["address"],
                whale_data.get("tokens_bought_count", 0),
                whale_data.get("wins", 0),
                whale_data.get("win_rate", 0.0),
                whale_data.get("is_early_whale", False)
            )

    async def insert_whale_token_purchase(self, whale_address: str, token_data: Dict):
        """
        Record a whale wallet purchasing a specific token

        Args:
            whale_address: Wallet address
            token_data: {
                "token_address": "...",
                "token_symbol": "...",
                "early_buyer": True,
                "outcome": "100x+"
            }
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO whale_token_purchases (
                    whale_address, token_address, token_symbol, early_buyer, outcome, detected_at
                )
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (whale_address, token_address)
                DO UPDATE SET
                    early_buyer = $4,
                    outcome = $5,
                    detected_at = NOW()
            """,
                whale_address,
                token_data["token_address"],
                token_data.get("token_symbol"),
                token_data.get("early_buyer", False),
                token_data.get("outcome")
            )

    async def is_successful_whale(self, wallet_address: str) -> Optional[Dict]:
        """
        Check if a wallet is a tracked successful whale

        Args:
            wallet_address: Wallet to check

        Returns:
            Whale data if successful whale (50%+ win rate), None otherwise
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM whale_wallets
                WHERE wallet_address = $1
                AND win_rate >= 0.5
            """, wallet_address)

            if row:
                return dict(row)
            return None

    async def get_whale_conviction_boost(self, wallet_address: str) -> int:
        """
        Get conviction score boost for a successful whale wallet

        Returns:
            Conviction points to add (0-20):
            - 85%+ win rate, early whale: +20 points
            - 75%+ win rate, early whale: +15 points
            - 65%+ win rate, early whale: +12 points
            - 50%+ win rate: +8 points
        """
        whale_data = await self.is_successful_whale(wallet_address)

        if not whale_data:
            return 0

        win_rate = whale_data.get("win_rate", 0)
        is_early = whale_data.get("is_early_whale", False)

        # Early whales get higher boost (they bought before the crowd)
        if is_early:
            if win_rate >= 0.85:
                return 20  # 85%+ early whale = MEGA signal
            elif win_rate >= 0.75:
                return 15  # 75%+ early whale = strong signal
            elif win_rate >= 0.65:
                return 12  # 65%+ early whale = good signal
            elif win_rate >= 0.50:
                return 10  # 50%+ early whale = decent signal
        else:
            # Late whales get smaller boost
            if win_rate >= 0.75:
                return 8
            elif win_rate >= 0.60:
                return 5

        return 0

    async def get_all_successful_whales(self, min_win_rate: float = 0.5) -> List[Dict]:
        """
        Get all successful whale wallets

        Args:
            min_win_rate: Minimum win rate (default 0.5 = 50%)

        Returns:
            List of whale wallet data
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM whale_wallets
                WHERE win_rate >= $1
                ORDER BY win_rate DESC, tokens_bought_count DESC
            """, min_win_rate)

            return [dict(row) for row in rows]

    # =========================================================================
    # TELEGRAM CALLS METHODS (persistent call tracking)
    # =========================================================================

    async def insert_telegram_call(
        self,
        token_address: str,
        group_name: str,
        message_text: Optional[str],
        timestamp: datetime
    ):
        """
        Record a telegram call for persistent tracking

        Args:
            token_address: Token contract address
            group_name: Name of the Telegram group
            message_text: Optional message content
            timestamp: When the call was made
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO telegram_calls (token_address, group_name, message_text, timestamp)
                VALUES ($1, $2, $3, $4)
            """, token_address, group_name, message_text, timestamp)

    async def get_telegram_calls(
        self,
        token_address: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get telegram calls for a token in the last N hours

        Args:
            token_address: Token contract address
            hours: Number of hours to look back

        Returns:
            List of call records
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM telegram_calls
                WHERE token_address = $1
                AND timestamp >= NOW() - INTERVAL '{} hours'
                ORDER BY timestamp DESC
            """.format(hours), token_address)
            return [dict(row) for row in rows]

    async def get_telegram_call_stats(
        self,
        token_address: str,
        minutes: int = 30
    ) -> Dict:
        """
        Get call statistics for multi-call bonus calculation

        Args:
            token_address: Token contract address
            minutes: Time window in minutes

        Returns:
            Dict with call_count, group_count, first_call_time, latest_call_time
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    COUNT(*) as call_count,
                    COUNT(DISTINCT group_name) as group_count,
                    MIN(timestamp) as first_call_time,
                    MAX(timestamp) as latest_call_time
                FROM telegram_calls
                WHERE token_address = $1
                AND timestamp >= NOW() - INTERVAL '{} minutes'
            """.format(minutes), token_address)

            if result:
                return dict(result)
            return {
                'call_count': 0,
                'group_count': 0,
                'first_call_time': None,
                'latest_call_time': None
            }

    async def get_group_call_history(
        self,
        group_name: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Get all calls from a specific group

        Args:
            group_name: Telegram group name
            days: Number of days to look back

        Returns:
            List of calls from this group
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM telegram_calls
                WHERE group_name = $1
                AND timestamp >= NOW() - INTERVAL '{} days'
                ORDER BY timestamp DESC
            """.format(days), group_name)
            return [dict(row) for row in rows]

    # =========================================================================
    # GROUP CORRELATION METHODS (track which groups call together)
    # =========================================================================

    async def insert_group_correlation(
        self,
        group_a: str,
        group_b: str,
        token_address: str,
        time_diff_seconds: int
    ):
        """
        Record a correlation between two groups calling the same token

        Args:
            group_a: First group (alphabetically)
            group_b: Second group (alphabetically)
            token_address: Token they both called
            time_diff_seconds: Time difference between calls
        """
        # Ensure consistent ordering (group_a < group_b alphabetically)
        if group_a > group_b:
            group_a, group_b = group_b, group_a

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO group_correlations
                (group_a, group_b, token_address, time_diff_seconds, correlation_date)
                VALUES ($1, $2, $3, $4, CURRENT_DATE)
                ON CONFLICT (group_a, group_b, token_address, correlation_date)
                DO UPDATE SET
                    time_diff_seconds = LEAST(group_correlations.time_diff_seconds, $4)
            """, group_a, group_b, token_address, time_diff_seconds)

    async def get_group_correlation_score(
        self,
        group_a: str,
        group_b: str,
        days: int = 30
    ) -> Dict:
        """
        Calculate correlation score between two groups

        Args:
            group_a: First group
            group_b: Second group
            days: Number of days to analyze

        Returns:
            Dict with correlation_count, avg_time_diff, correlation_strength
        """
        # Ensure consistent ordering
        if group_a > group_b:
            group_a, group_b = group_b, group_a

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    COUNT(*) as correlation_count,
                    AVG(time_diff_seconds) as avg_time_diff,
                    COUNT(DISTINCT token_address) as unique_tokens
                FROM group_correlations
                WHERE group_a = $1 AND group_b = $2
                AND correlation_date >= CURRENT_DATE - INTERVAL '{} days'
            """.format(days), group_a, group_b)

            if result and result['correlation_count'] > 0:
                # Calculate strength: more correlations + shorter time diff = stronger
                correlation_count = result['correlation_count']
                avg_time_diff = result['avg_time_diff'] or 0

                # Strength score (0-100)
                # More correlations = higher base score
                # Faster time diff = multiplier bonus
                base_score = min(correlation_count * 5, 70)  # Max 70 from count
                time_bonus = max(0, 30 - (avg_time_diff / 60))  # Max 30 from speed

                return {
                    'correlation_count': correlation_count,
                    'avg_time_diff': avg_time_diff,
                    'unique_tokens': result['unique_tokens'],
                    'correlation_strength': min(100, base_score + time_bonus)
                }

            return {
                'correlation_count': 0,
                'avg_time_diff': 0,
                'unique_tokens': 0,
                'correlation_strength': 0
            }

    async def get_top_group_pairs(self, days: int = 30, limit: int = 10) -> List[Dict]:
        """
        Get the top correlated group pairs

        Args:
            days: Number of days to analyze
            limit: Max number of pairs to return

        Returns:
            List of top group pairs with correlation stats
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    group_a,
                    group_b,
                    COUNT(*) as correlation_count,
                    AVG(time_diff_seconds) as avg_time_diff,
                    COUNT(DISTINCT token_address) as unique_tokens
                FROM group_correlations
                WHERE correlation_date >= CURRENT_DATE - INTERVAL '{} days'
                GROUP BY group_a, group_b
                ORDER BY correlation_count DESC, avg_time_diff ASC
                LIMIT $1
            """.format(days), limit)

            return [dict(row) for row in rows]

