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
            
            logger.info("✅ Database tables created/verified")
    
    async def insert_signal(self, signal_data: Dict):
        """Insert a new signal"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO signals 
                (token_address, token_name, token_symbol, signal_type, bonding_curve_pct, 
                 conviction_score, entry_price, liquidity, volume_24h, market_cap)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (token_address) DO UPDATE SET
                    conviction_score = EXCLUDED.conviction_score,
                    bonding_curve_pct = EXCLUDED.bonding_curve_pct,
                    updated_at = NOW()
            ''', signal_data['token_address'], signal_data.get('token_name'),
                signal_data.get('token_symbol'), signal_data['signal_type'],
                signal_data.get('bonding_curve_pct'), signal_data['conviction_score'],
                signal_data.get('entry_price'), signal_data.get('liquidity'),
                signal_data.get('volume_24h'), signal_data.get('market_cap'))
    
    async def mark_signal_posted(self, token_address: str, message_id: int):
        """Mark a signal as posted to Telegram"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE signals 
                SET signal_posted = TRUE, telegram_message_id = $1, updated_at = NOW()
                WHERE token_address = $2
            ''', message_id, token_address)
    
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
