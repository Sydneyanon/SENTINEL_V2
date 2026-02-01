"""
SENTINEL V3 - Database
Single source of truth. Clean schema.
"""
import asyncpg
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional, List, Dict, Any

from config import DATABASE_URL, SEED_WALLETS

# Connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db():
    """Initialize database tables."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Wallets table - tracked KOL wallets with performance stats
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                name TEXT,
                tier TEXT DEFAULT 'new',
                signals INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                rugs INTEGER DEFAULT 0,
                total_return REAL DEFAULT 0,
                last_signal TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Signals table - all signals posted
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id SERIAL PRIMARY KEY,
                token_address TEXT NOT NULL,
                symbol TEXT,
                name TEXT,

                -- Discovery
                wallet_address TEXT REFERENCES wallets(address),
                wallet_tier TEXT,
                discovered_at TIMESTAMP DEFAULT NOW(),

                -- Entry metrics
                entry_price REAL,
                entry_mcap REAL,
                entry_liquidity REAL,
                entry_holders INTEGER,
                entry_volume_1h REAL,

                -- Scoring
                score INTEGER,
                score_breakdown JSONB,

                -- Telegram
                message_id BIGINT,
                posted_at TIMESTAMP,

                -- Tracking
                current_price REAL,
                max_price REAL,
                max_multiplier REAL DEFAULT 1.0,
                current_multiplier REAL DEFAULT 1.0,

                -- Outcome (filled after 24h)
                outcome TEXT,  -- 'win', 'rug', 'neutral'
                final_multiplier REAL,
                outcome_at TIMESTAMP,

                -- Metadata
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Milestones table - 2x, 5x, 10x etc
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS milestones (
                id SERIAL PRIMARY KEY,
                signal_id INTEGER REFERENCES signals(id),
                token_address TEXT NOT NULL,
                multiplier INTEGER NOT NULL,
                price_at_milestone REAL,
                message_id BIGINT,
                reached_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(signal_id, multiplier)
            )
        ''')

        # Smart Money Discovery table - wallets discovered via GMGN/Apify
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smart_money (
                address TEXT PRIMARY KEY,
                source TEXT,  -- 'smart_degen', 'copytrade', 'manual'
                win_rate REAL,
                total_trades INTEGER,
                pnl_7d REAL,
                pnl_30d REAL,
                honeypot_ratio REAL,
                tier TEXT,  -- 'elite', 'smart_money', 'verified'
                is_tracking BOOLEAN DEFAULT FALSE,  -- Added to main wallets?
                signals INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                discovered_at TIMESTAMP DEFAULT NOW(),
                last_checked TIMESTAMP DEFAULT NOW(),
                notes TEXT
            )
        ''')

        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_signals_token ON signals(token_address)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_signals_wallet ON signals(wallet_address)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_milestones_signal ON milestones(signal_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_smart_money_tier ON smart_money(tier)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_smart_money_tracking ON smart_money(is_tracking)')

        # Seed wallets if empty
        count = await conn.fetchval('SELECT COUNT(*) FROM wallets')
        if count == 0:
            logger.info(f"Seeding {len(SEED_WALLETS)} wallets...")
            for address, data in SEED_WALLETS.items():
                await conn.execute('''
                    INSERT INTO wallets (address, name, tier)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (address) DO NOTHING
                ''', address, data.get('name'), data.get('tier', 'new'))

    logger.info("Database initialized")


# =============================================================================
# WALLET OPERATIONS
# =============================================================================

async def get_wallet(address: str) -> Optional[Dict]:
    """Get wallet by address."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM wallets WHERE address = $1', address)
        return dict(row) if row else None


async def get_all_wallets() -> List[Dict]:
    """Get all tracked wallets."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM wallets ORDER BY wins DESC')
        return [dict(row) for row in rows]


async def add_wallet(address: str, name: str = None, tier: str = 'new') -> bool:
    """Add a new wallet to track."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO wallets (address, name, tier)
                VALUES ($1, $2, $3)
            ''', address, name, tier)
            return True
        except asyncpg.UniqueViolationError:
            return False


async def update_wallet_stats(address: str, is_win: bool, multiplier: float):
    """Update wallet stats after signal outcome."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if is_win:
            await conn.execute('''
                UPDATE wallets
                SET signals = signals + 1,
                    wins = wins + 1,
                    total_return = total_return + $2,
                    updated_at = NOW()
                WHERE address = $1
            ''', address, multiplier)
        else:
            await conn.execute('''
                UPDATE wallets
                SET signals = signals + 1,
                    rugs = rugs + 1,
                    updated_at = NOW()
                WHERE address = $1
            ''', address)

        # Auto-adjust tier based on win rate
        wallet = await get_wallet(address)
        if wallet and wallet['signals'] >= 5:
            win_rate = wallet['wins'] / wallet['signals']
            if win_rate >= 0.7:
                new_tier = 'elite'
            elif win_rate >= 0.5:
                new_tier = 'top_kol'
            elif win_rate >= 0.3:
                new_tier = 'verified'
            else:
                new_tier = 'new'

            if new_tier != wallet['tier']:
                await conn.execute(
                    'UPDATE wallets SET tier = $1 WHERE address = $2',
                    new_tier, address
                )
                logger.info(f"Wallet {address[:8]} tier changed: {wallet['tier']} -> {new_tier}")


# =============================================================================
# SIGNAL OPERATIONS
# =============================================================================

async def create_signal(
    token_address: str,
    symbol: str,
    name: str,
    wallet_address: str,
    wallet_tier: str,
    entry_price: float,
    entry_mcap: float,
    entry_liquidity: float,
    entry_holders: int,
    entry_volume_1h: float,
    score: int,
    score_breakdown: dict
) -> int:
    """Create a new signal. Returns signal ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        signal_id = await conn.fetchval('''
            INSERT INTO signals (
                token_address, symbol, name,
                wallet_address, wallet_tier,
                entry_price, entry_mcap, entry_liquidity,
                entry_holders, entry_volume_1h,
                score, score_breakdown,
                current_price, max_price
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $6, $6)
            RETURNING id
        ''', token_address, symbol, name,
            wallet_address, wallet_tier,
            entry_price, entry_mcap, entry_liquidity,
            entry_holders, entry_volume_1h,
            score, score_breakdown)

        # Update wallet last_signal
        await conn.execute(
            'UPDATE wallets SET last_signal = NOW() WHERE address = $1',
            wallet_address
        )

        return signal_id


async def mark_signal_posted(signal_id: int, message_id: int):
    """Mark signal as posted to Telegram."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE signals
            SET message_id = $2, posted_at = NOW()
            WHERE id = $1
        ''', signal_id, message_id)


async def update_signal_price(signal_id: int, current_price: float):
    """Update signal's current price and max price."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        signal = await conn.fetchrow('SELECT * FROM signals WHERE id = $1', signal_id)
        if not signal or not signal['entry_price']:
            return

        multiplier = current_price / signal['entry_price']
        max_price = max(signal['max_price'] or current_price, current_price)
        max_mult = max_price / signal['entry_price']

        await conn.execute('''
            UPDATE signals
            SET current_price = $2,
                current_multiplier = $3,
                max_price = $4,
                max_multiplier = $5,
                updated_at = NOW()
            WHERE id = $1
        ''', signal_id, current_price, multiplier, max_price, max_mult)


async def set_signal_outcome(signal_id: int, outcome: str, final_multiplier: float):
    """Set signal outcome after tracking period."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        signal = await conn.fetchrow('SELECT * FROM signals WHERE id = $1', signal_id)
        if not signal:
            return

        await conn.execute('''
            UPDATE signals
            SET outcome = $2, final_multiplier = $3, outcome_at = NOW()
            WHERE id = $1
        ''', signal_id, outcome, final_multiplier)

        # Update wallet stats
        if signal['wallet_address']:
            is_win = outcome == 'win'
            await update_wallet_stats(signal['wallet_address'], is_win, final_multiplier)


async def get_active_signals() -> List[Dict]:
    """Get signals that are still being tracked (< 24h old, no outcome yet)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM signals
            WHERE outcome IS NULL
            AND posted_at > NOW() - INTERVAL '24 hours'
            ORDER BY posted_at DESC
        ''')
        return [dict(row) for row in rows]


async def get_signal(signal_id: int) -> Optional[Dict]:
    """Get signal by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM signals WHERE id = $1', signal_id)
        return dict(row) if row else None


async def get_signal_by_token(token_address: str) -> Optional[Dict]:
    """Get most recent signal for a token."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT * FROM signals
            WHERE token_address = $1
            ORDER BY created_at DESC
            LIMIT 1
        ''', token_address)
        return dict(row) if row else None


# =============================================================================
# MILESTONE OPERATIONS
# =============================================================================

async def record_milestone(signal_id: int, token_address: str, multiplier: int, price: float) -> bool:
    """Record a milestone. Returns True if new, False if already exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO milestones (signal_id, token_address, multiplier, price_at_milestone)
                VALUES ($1, $2, $3, $4)
            ''', signal_id, token_address, multiplier, price)
            return True
        except asyncpg.UniqueViolationError:
            return False


async def update_milestone_message(signal_id: int, multiplier: int, message_id: int):
    """Update milestone with Telegram message ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE milestones
            SET message_id = $3
            WHERE signal_id = $1 AND multiplier = $2
        ''', signal_id, multiplier, message_id)


async def get_signal_milestones(signal_id: int) -> List[int]:
    """Get list of milestones already reached for a signal."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT multiplier FROM milestones WHERE signal_id = $1',
            signal_id
        )
        return [row['multiplier'] for row in rows]


# =============================================================================
# STATS
# =============================================================================

async def get_stats() -> Dict[str, Any]:
    """Get overall statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_signals = await conn.fetchval('SELECT COUNT(*) FROM signals WHERE posted_at IS NOT NULL')
        total_wins = await conn.fetchval("SELECT COUNT(*) FROM signals WHERE outcome = 'win'")
        total_rugs = await conn.fetchval("SELECT COUNT(*) FROM signals WHERE outcome = 'rug'")
        total_wallets = await conn.fetchval('SELECT COUNT(*) FROM wallets')

        # Last 24h
        signals_24h = await conn.fetchval('''
            SELECT COUNT(*) FROM signals
            WHERE posted_at > NOW() - INTERVAL '24 hours'
        ''')

        # Best performer
        best = await conn.fetchrow('''
            SELECT symbol, max_multiplier
            FROM signals
            WHERE max_multiplier IS NOT NULL
            ORDER BY max_multiplier DESC
            LIMIT 1
        ''')

        return {
            'total_signals': total_signals or 0,
            'total_wins': total_wins or 0,
            'total_rugs': total_rugs or 0,
            'win_rate': (total_wins / total_signals * 100) if total_signals else 0,
            'signals_24h': signals_24h or 0,
            'total_wallets': total_wallets or 0,
            'best_performer': dict(best) if best else None,
        }


async def get_daily_stats(days: int = 7) -> List[Dict]:
    """Get daily win rate stats."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                DATE(posted_at) as date,
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE outcome = 'win') as wins,
                COUNT(*) FILTER (WHERE outcome = 'rug') as rugs
            FROM signals
            WHERE posted_at > NOW() - make_interval(days => $1)
            AND outcome IS NOT NULL
            GROUP BY DATE(posted_at)
            ORDER BY date DESC
        ''', days)
        return [dict(row) for row in rows]


# =============================================================================
# SMART MONEY OPERATIONS
# =============================================================================

async def add_smart_money(
    address: str,
    source: str,
    win_rate: float,
    total_trades: int,
    pnl_7d: float,
    pnl_30d: float,
    honeypot_ratio: float,
    tier: str
) -> bool:
    """Add or update a discovered smart money wallet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO smart_money (address, source, win_rate, total_trades, pnl_7d, pnl_30d, honeypot_ratio, tier)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (address) DO UPDATE SET
                win_rate = $3,
                total_trades = $4,
                pnl_7d = $5,
                pnl_30d = $6,
                honeypot_ratio = $7,
                tier = $8,
                last_checked = NOW()
        ''', address, source, win_rate, total_trades, pnl_7d, pnl_30d, honeypot_ratio, tier)
        return True


async def get_smart_money_wallets(tier: str = None, tracking_only: bool = False) -> List[Dict]:
    """Get discovered smart money wallets."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = 'SELECT * FROM smart_money WHERE 1=1'
        params = []

        if tier:
            params.append(tier)
            query += f' AND tier = ${len(params)}'

        if tracking_only:
            query += ' AND is_tracking = TRUE'

        query += ' ORDER BY win_rate DESC, pnl_30d DESC'

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_smart_money_stats() -> Dict:
    """Get smart money discovery stats."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval('SELECT COUNT(*) FROM smart_money')
        tracking = await conn.fetchval('SELECT COUNT(*) FROM smart_money WHERE is_tracking = TRUE')
        elite = await conn.fetchval("SELECT COUNT(*) FROM smart_money WHERE tier = 'elite'")
        smart = await conn.fetchval("SELECT COUNT(*) FROM smart_money WHERE tier = 'smart_money'")
        verified = await conn.fetchval("SELECT COUNT(*) FROM smart_money WHERE tier = 'verified'")

        # Performance of tracked smart money
        perf = await conn.fetchrow('''
            SELECT
                COUNT(*) as signals,
                COUNT(*) FILTER (WHERE s.outcome = 'win') as wins
            FROM signals s
            JOIN smart_money sm ON s.wallet_address = sm.address
            WHERE sm.is_tracking = TRUE
        ''')

        return {
            'total_discovered': total or 0,
            'tracking': tracking or 0,
            'by_tier': {
                'elite': elite or 0,
                'smart_money': smart or 0,
                'verified': verified or 0,
            },
            'signals': perf['signals'] if perf else 0,
            'wins': perf['wins'] if perf else 0,
            'win_rate': (perf['wins'] / perf['signals'] * 100) if perf and perf['signals'] else 0,
        }


async def enable_smart_money_tracking(address: str) -> bool:
    """Enable tracking for a smart money wallet (add to main wallets)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get the smart money wallet
        sm = await conn.fetchrow('SELECT * FROM smart_money WHERE address = $1', address)
        if not sm:
            return False

        # Add to main wallets table
        await conn.execute('''
            INSERT INTO wallets (address, name, tier)
            VALUES ($1, $2, $3)
            ON CONFLICT (address) DO NOTHING
        ''', address, f"SM_{address[:6]}", sm['tier'])

        # Mark as tracking
        await conn.execute('''
            UPDATE smart_money SET is_tracking = TRUE WHERE address = $1
        ''', address)

        return True


async def auto_enable_top_smart_money(max_wallets: int = 10, min_win_rate: float = 50.0) -> int:
    """Automatically enable tracking for top smart money wallets."""
    count, _ = await auto_enable_top_smart_money_with_details(max_wallets, min_win_rate)
    return count


async def auto_enable_top_smart_money_with_details(
    max_wallets: int = 10,
    min_win_rate: float = 50.0
) -> tuple:
    """
    Automatically enable tracking for top smart money wallets.
    Returns tuple of (count, wallet_details_list).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get top performers not yet tracking
        rows = await conn.fetch('''
            SELECT address, tier, win_rate, total_trades, pnl_30d FROM smart_money
            WHERE is_tracking = FALSE
            AND win_rate >= $1
            ORDER BY win_rate DESC, pnl_30d DESC
            LIMIT $2
        ''', min_win_rate, max_wallets)

        count = 0
        wallet_details = []

        for row in rows:
            # Add to wallets
            await conn.execute('''
                INSERT INTO wallets (address, name, tier)
                VALUES ($1, $2, $3)
                ON CONFLICT (address) DO NOTHING
            ''', row['address'], f"SM_{row['address'][:6]}", row['tier'])

            # Mark as tracking
            await conn.execute('''
                UPDATE smart_money SET is_tracking = TRUE WHERE address = $1
            ''', row['address'])

            wallet_details.append({
                'address': row['address'],
                'tier': row['tier'],
                'win_rate': row['win_rate'],
                'total_trades': row['total_trades'],
                'pnl_30d': row['pnl_30d'],
            })

            count += 1

        return count, wallet_details


async def cleanup_stale_smart_money(days_inactive: int = 30, min_signals: int = 3) -> int:
    """
    Remove underperforming smart money wallets from tracking.

    Removes wallets that:
    - Have been tracking for at least `days_inactive` days
    - Have at least `min_signals` signals
    - Have a win rate below 30%

    Returns number of wallets removed from tracking.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Find underperforming tracked wallets
        rows = await conn.fetch('''
            SELECT sm.address, w.signals, w.wins
            FROM smart_money sm
            JOIN wallets w ON sm.address = w.address
            WHERE sm.is_tracking = TRUE
            AND sm.discovered_at < NOW() - make_interval(days => $1)
            AND w.signals >= $2
            AND (w.wins::float / w.signals) < 0.30
        ''', days_inactive, min_signals)

        count = 0
        for row in rows:
            # Remove from main wallets
            await conn.execute('DELETE FROM wallets WHERE address = $1', row['address'])

            # Mark as not tracking
            await conn.execute('''
                UPDATE smart_money SET is_tracking = FALSE WHERE address = $1
            ''', row['address'])

            logger.info(
                f"Removed stale wallet {row['address'][:8]}... "
                f"({row['wins']}/{row['signals']} = {row['wins']/row['signals']*100:.0f}% WR)"
            )

            count += 1

        return count
