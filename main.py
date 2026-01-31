"""
🔥 PROMETHEUS - Autonomous Signal System
KOL-Triggered Real-Time Tracking with Conviction Scoring + Telegram Alpha Calls
"""
import asyncio
from typing import Dict, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from loguru import logger
from datetime import datetime, timedelta
import sys
import os

# Import config first for LOG_LEVEL default
import config

# Configure logging (environment-based to avoid Railway 500 logs/sec limit)
# Falls back to config.LOG_LEVEL if env var not set
LOG_LEVEL = os.getenv('LOG_LEVEL', config.LOG_LEVEL).upper()
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level=LOG_LEVEL
)

# Import existing modules
from database import Database
from pump_monitor_v2 import PumpMonitorV2
from performance_tracker import PerformanceTracker
from trackers.smart_wallets import SmartWalletTracker
from trackers.narrative_detector import NarrativeDetector
from scoring.conviction_engine import ConvictionEngine
from publishers.telegram import TelegramPublisher
from active_token_tracker import ActiveTokenTracker
from helius_fetcher import HeliusDataFetcher
from post_call_monitor import get_post_call_monitor  # Post-signal fade detection
from wallet_enrichment import initialize_smart_wallets  # ← NEW: Auto-discover wallet metadata
from startup_diagnostics import run_diagnostics, check_telegram_session  # ← Diagnostics for database & OPT-041

# NEW: Daily pipeline automation
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("⚠️  APScheduler not installed - daily pipeline will not run automatically")

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Database
db = None

# Monitors
pumpportal_monitor = None
performance_tracker = None

# Trackers
smart_wallet_tracker = None  # ← FIXED: Will initialize with enriched wallets in startup()
narrative_detector = NarrativeDetector()
active_tracker = None  # NEW: Tracks KOL-bought tokens
helius_fetcher = None  # NEW: Fetches data from Helius
revival_scanner = None  # NEW: Monitors post-grad tokens for revival patterns

# Scoring
conviction_engine = None

# Publishers
telegram_publisher = TelegramPublisher()

# Telegram Alpha Calls Cache (tracks calls from Telegram scraper)
# Format: {token_address: {'mentions': [{'timestamp': datetime, 'group': str}], 'first_seen': datetime}}
telegram_calls_cache = {}

# Telegram Monitor (Built-in) - optional alternative to external scraper
telegram_monitor = None

# Daily Pipeline Scheduler (NEW: Automated data collection + ML retraining)
daily_pipeline_scheduler = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_token_addresses_from_webhook(webhook_data: List[Dict]) -> List[str]:
    """
    Extract token addresses from Helius webhook data

    Args:
        webhook_data: List of transactions from Helius

    Returns:
        List of unique token addresses that were bought (filtered for memecoins only)
    """
    # Known tokens to IGNORE (not memecoins)
    IGNORE_TOKENS = {
        'So11111111111111111111111111111111111111112',  # Wrapped SOL
        'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
        'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        'USD1ttGYdB3UVrGt5YGWiFaFzQnj5JR7rKdmDuz8Fhvt',  # USD1 (stablecoin)
        '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs',  # BONK (established)
        'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # Bonk (alternate)
    }

    token_addresses = set()

    try:
        for transaction in webhook_data:
            fee_payer = transaction.get('feePayer', '')

            # Only process if it's a tracked wallet
            if fee_payer not in smart_wallet_tracker.tracked_wallets:
                continue

            # Get token transfers
            token_transfers = transaction.get('tokenTransfers', [])

            for transfer in token_transfers:
                to_address = transfer.get('toUserAccount', '')

                # If the tracked wallet received tokens (bought)
                if to_address == fee_payer:
                    token_address = transfer.get('mint', '')

                    # Filter out ignored tokens (SOL, USDC, etc.)
                    if token_address and token_address not in IGNORE_TOKENS:
                        token_addresses.add(token_address)
                        logger.debug(f"   💰 KOL bought: {token_address[:8]}...")
                    elif token_address in IGNORE_TOKENS:
                        logger.debug(f"   ⏭️  Skipping known token: {token_address[:8]}...")

        return list(token_addresses)

    except Exception as e:
        logger.error(f"❌ Error extracting token addresses: {e}")
        return []

# ============================================================================
# SIGNAL PROCESSING (OLD - kept for PumpPortal graduations)
# ============================================================================

async def handle_pumpportal_signal(token_data: Dict, signal_type: str):
    """
    Handle signals from PumpPortal monitor
    NOW: Handles organic scanner discoveries + graduation signals

    Args:
        token_data: Token information from PumpPortal
        signal_type: 'NEW_TOKEN', 'PRE_GRADUATION', 'POST_GRADUATION', or 'ORGANIC_DISCOVERY'
    """
    try:
        token_address = token_data.get('token_address')

        # ORGANIC DISCOVERY: Token passed organic scanner filters
        if signal_type == 'ORGANIC_DISCOVERY':
            symbol = token_data.get('token_symbol', 'UNKNOWN')
            if active_tracker and not active_tracker.is_tracked(token_address):
                logger.info(f"🔬 Organic discovery via callback: ${symbol} - starting tracking")
                await active_tracker.start_tracking(token_address, source='organic_scanner')
            return

        # If this is a NEW_TOKEN event, check if it's tracked by ActiveTracker
        if signal_type == 'NEW_TOKEN':
            # Check if we're already tracking this
            if active_tracker and active_tracker.is_tracked(token_address):
                # Update with PumpPortal data
                await active_tracker.update_token_trade(token_address, token_data)
                return  # Don't process further, ActiveTracker handles it
            else:
                # Not tracked, skip (organic scanner handles discovery separately)
                return

        # For PRE_GRADUATION and POST_GRADUATION, check if tracked
        if active_tracker and active_tracker.is_tracked(token_address):
            # Just update the tracked token with graduation info
            await active_tracker.update_token_trade(token_address, token_data)
            return

        # If we get here, it's a graduation for a non-tracked token
        logger.debug(f"⏭️  Graduation for non-tracked token: {token_address[:8]}")

    except Exception as e:
        logger.error(f"❌ Error handling PumpPortal signal: {e}")

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def start_pumpportal_task():
    """Wrapper for PumpPortal task with error handling"""
    try:
        logger.info("🚨 Starting PumpPortal background task...")
        logger.info(f"🚨 Monitor object exists: {pumpportal_monitor is not None}")
        logger.info(f"🚨 Monitor type: {type(pumpportal_monitor)}")
        logger.info("🚨 About to call pumpportal_monitor.start()...")
        
        await pumpportal_monitor.start()
        
        logger.info("🚨 After calling pumpportal_monitor.start() - THIS SHOULD NEVER PRINT")
    except Exception as e:
        logger.error(f"❌ PumpPortal task crashed: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def smart_polling_task():
    """
    Polling for actively tracked tokens
    Fixed 30-second interval for real-time updates
    Uses Helius bonding curve decoder + DexScreener
    """
    while True:
        try:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            if not active_tracker:
                continue
            
            active_tokens = active_tracker.get_active_tokens()
            
            if not active_tokens:
                continue
            
            # Smart poll each active token
            # The smart_poll_token method handles its own interval checking
            for token_address in active_tokens:
                try:
                    await active_tracker.smart_poll_token(token_address)
                except Exception as e:
                    logger.debug(f"⚠️ Error polling {token_address[:8]}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error in smart polling task: {e}")


async def cleanup_task():
    """Periodic cleanup of old data and wallet metadata refresh"""
    
    # Track when we last refreshed wallets
    last_wallet_refresh = datetime.utcnow()
    
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            
            logger.info("🧹 Running cleanup...")
            smart_wallet_tracker.cleanup_old_data()
            narrative_detector.cleanup_old_data()
            
            if pumpportal_monitor:
                pumpportal_monitor.cleanup_old_tokens()
            
            if active_tracker:
                active_tracker.cleanup_old_tokens(max_age_hours=24)
            
            logger.info("✅ Cleanup complete")
            
            # Check if we need to refresh wallet metadata (every 6 hours)
            time_since_refresh = (datetime.utcnow() - last_wallet_refresh).total_seconds()
            
            if time_since_refresh >= 21600:  # 6 hours = 21600 seconds
                logger.info("=" * 70)
                logger.info("🔄 REFRESHING WALLET METADATA (6-hour update)")
                logger.info("=" * 70)
                
                try:
                    # Fetch fresh metadata from gmgn.ai
                    from wallet_enrichment import initialize_smart_wallets
                    enriched_wallets, _ = await initialize_smart_wallets()
                    
                    if enriched_wallets:
                        # Update smart_wallet_tracker with fresh data
                        old_count = len(smart_wallet_tracker.tracked_wallets)

                        smart_wallet_tracker.tracked_wallets = {
                            wallet['address']: wallet
                            for wallet in enriched_wallets
                        }

                        # Also merge DB wallets (from /refreshwallets)
                        if db:
                            try:
                                db_wallets = await db.get_tracked_wallets_for_conviction()
                                if db_wallets:
                                    smart_wallet_tracker.tracked_wallets.update(db_wallets)
                                    logger.info(f"   📥 Merged {len(db_wallets)} DB wallets")
                            except Exception as db_e:
                                logger.warning(f"   ⚠️ Could not load DB wallets: {db_e}")

                        # Log changes
                        logger.info(f"✅ Refreshed {len(smart_wallet_tracker.tracked_wallets)} total wallets")

                        last_wallet_refresh = datetime.utcnow()
                        logger.info("=" * 70)
                    else:
                        logger.warning("⚠️ Wallet refresh returned no data - keeping existing")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to refresh wallet metadata: {e}")
                    logger.info("   💡 Will retry in 6 hours")
            
        except Exception as e:
            logger.error(f"❌ Error in cleanup task: {e}")

# ============================================================================
# DAILY PIPELINE - Automated Data Collection + ML Retraining
# ============================================================================

async def run_ralph_analysis():
    """
    Ralph's conviction analysis - analyzes recent signals and makes recommendations.
    Runs as part of daily pipeline.
    """
    logger.info("🤖 RALPH CONVICTION ANALYSIS")
    logger.info("-" * 40)

    try:
        if not db or not db.pool:
            logger.warning("   Database not available for analysis")
            return

        async with db.pool.acquire() as conn:
            # Get signals from last 24 hours
            signals = await conn.fetch('''
                SELECT conviction_score, outcome, max_roi, entry_price, max_price_reached,
                       bonding_curve_pct, buy_percentage, kol_wallets
                FROM signals
                WHERE signal_posted = TRUE
                  AND created_at > NOW() - INTERVAL '24 hours'
            ''')

            if not signals:
                logger.info("   No signals in last 24 hours to analyze")
                return

            # Analyze conviction score buckets
            buckets = {
                '90-100': {'wins': 0, 'rugs': 0, 'total': 0},
                '70-89': {'wins': 0, 'rugs': 0, 'total': 0},
                '50-69': {'wins': 0, 'rugs': 0, 'total': 0},
                '40-49': {'wins': 0, 'rugs': 0, 'total': 0},
                '0-39': {'wins': 0, 'rugs': 0, 'total': 0},
            }

            total_wins = 0
            total_rugs = 0
            total_signals = len(signals)

            for s in signals:
                score = s['conviction_score'] or 0
                outcome = s['outcome']

                # Determine bucket
                if score >= 90:
                    bucket = '90-100'
                elif score >= 70:
                    bucket = '70-89'
                elif score >= 50:
                    bucket = '50-69'
                elif score >= 40:
                    bucket = '40-49'
                else:
                    bucket = '0-39'

                buckets[bucket]['total'] += 1

                if outcome in ('2x', '5x', '10x', '50x', '100x'):
                    buckets[bucket]['wins'] += 1
                    total_wins += 1
                elif outcome == 'rug':
                    buckets[bucket]['rugs'] += 1
                    total_rugs += 1

            # Log analysis
            logger.info(f"   📊 Last 24h: {total_signals} signals, {total_wins} wins, {total_rugs} rugs")

            # Recommendations
            recommendations = []

            # Check for rug-heavy buckets
            for bucket, data in buckets.items():
                if data['total'] >= 3:  # Need at least 3 signals for meaningful data
                    rug_rate = data['rugs'] / data['total'] * 100
                    if rug_rate > 50:
                        recommendations.append(f"⚠️ Score {bucket}: {rug_rate:.0f}% rug rate - consider raising threshold")

            # Check overall rug rate
            if total_signals >= 5:
                overall_rug_rate = total_rugs / total_signals * 100
                overall_win_rate = total_wins / total_signals * 100

                logger.info(f"   📈 Win rate: {overall_win_rate:.0f}% | Rug rate: {overall_rug_rate:.0f}%")

                if overall_rug_rate > 40:
                    recommendations.append(f"🚨 High rug rate ({overall_rug_rate:.0f}%) - raise MIN_CONVICTION_SCORE")
                if overall_win_rate < 25:
                    recommendations.append(f"🚨 Low win rate ({overall_win_rate:.0f}%) - tighten filters")

            # Check KOL performance
            kol_wins = 0
            kol_rugs = 0
            kol_total = 0
            for s in signals:
                if s['kol_wallets'] and len(s['kol_wallets']) > 0:
                    kol_total += 1
                    if s['outcome'] in ('2x', '5x', '10x', '50x', '100x'):
                        kol_wins += 1
                    elif s['outcome'] == 'rug':
                        kol_rugs += 1

            if kol_total >= 3:
                kol_rug_rate = kol_rugs / kol_total * 100
                if kol_rug_rate > 30:
                    recommendations.append(f"⚠️ KOL-backed signals: {kol_rug_rate:.0f}% rug rate - review tracked wallets")

            # Log recommendations
            if recommendations:
                logger.info("   🤖 RALPH RECOMMENDATIONS:")
                for rec in recommendations:
                    logger.info(f"      {rec}")
            else:
                logger.info("   ✅ No immediate concerns detected")

    except Exception as e:
        logger.error(f"   ❌ Ralph analysis failed: {e}")


async def run_daily_pipeline():
    """
    Daily pipeline that runs at 2 AM UTC:
    1. Sync data from database
    2. Retrain ML model if enough data
    3. Run Ralph unified analysis (includes optimization)
    """
    logger.info("=" * 80)
    logger.info("🌅 DAILY PIPELINE STARTING")
    logger.info("=" * 80)
    logger.info(f"   Date: {datetime.utcnow().date()}")
    logger.info("")

    try:
        # Step 1: Merge database signals with external data
        logger.info("📊 STEP 1: Merging database signals with external data...")
        try:
            import json
            import os
            from ralph.data_manager import DataManager

            training_file = 'data/historical_training_data.json'

            # Load existing external data (if any)
            existing_tokens = []
            existing_addresses = set()
            if os.path.exists(training_file):
                try:
                    with open(training_file, 'r') as f:
                        existing_data = json.load(f)
                        existing_tokens = existing_data.get('tokens', [])
                        existing_addresses = {t.get('token_address') for t in existing_tokens}
                        logger.info(f"   📂 Loaded {len(existing_tokens)} existing tokens from file")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not load existing data: {e}")

            # Get database signals
            dm = DataManager(db)
            db_signals = await dm.get_training_data()
            logger.info(f"   🗄️ Fetched {len(db_signals)} signals from database")

            # Convert DB signals to training format and merge
            db_tokens = []
            for d in db_signals:
                token = {
                    'token_address': d.get('token_address'),
                    'symbol': d.get('token_symbol'),
                    'outcome': d.get('outcome'),
                    'conviction_score': d.get('conviction_score'),
                    'entry_price': d.get('entry_price'),
                    'max_price_reached': d.get('max_price_reached'),
                    'max_roi': d.get('max_roi') or d.get('roi'),
                    'market_cap': d.get('market_cap'),
                    'liquidity': d.get('liquidity'),
                    'volume_24h': d.get('volume_24h'),
                    'unique_buyers': d.get('unique_buyers'),
                    'buys_24h': d.get('buys_24h'),
                    'sells_24h': d.get('sells_24h'),
                    'bonding_curve_pct': d.get('bonding_curve_pct'),
                    'buy_percentage': d.get('buy_percentage'),
                    'kol_wallets': d.get('kol_wallets'),
                    'kol_count': len(d.get('kol_wallets') or []),
                    'narrative_tags': d.get('narrative_tags'),
                    'created_at': str(d.get('created_at')),
                    'source': 'database'
                }
                db_tokens.append(token)

            # Merge: DB signals take priority (fresher data)
            db_addresses = {t['token_address'] for t in db_tokens}

            # Keep external tokens that aren't in our DB
            external_only = [t for t in existing_tokens if t.get('token_address') not in db_addresses]

            # Combined: our signals + external data we don't have
            combined_tokens = db_tokens + external_only

            # Write merged data
            os.makedirs('data', exist_ok=True)
            with open(training_file, 'w') as f:
                json.dump({
                    'tokens': combined_tokens,
                    'total_tokens': len(combined_tokens),
                    'db_signals': len(db_tokens),
                    'external_tokens': len(external_only),
                    'last_sync': datetime.utcnow().isoformat()
                }, f, indent=2, default=str)

            logger.info(f"   ✅ Merged: {len(db_tokens)} DB signals + {len(external_only)} external = {len(combined_tokens)} total")
        except Exception as e:
            logger.warning(f"   ⚠️ Data sync skipped: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        logger.info("")

        # Step 2: ML model retraining (if enough data)
        logger.info("🎓 STEP 2: ML model retraining...")
        try:
            from tools.automated_ml_retrain import AutomatedMLRetrainer
            retrainer = AutomatedMLRetrainer()
            await retrainer.run()
            logger.info("   ✅ ML check complete")
        except Exception as e:
            logger.warning(f"   ⚠️ ML skipped: {e}")
        logger.info("")

        # Step 3: Ralph unified analysis (includes optimization + recommendations)
        logger.info("🤖 STEP 3: Ralph unified analysis...")
        try:
            from ralph.unified_analysis import run_full_analysis
            await run_full_analysis(db, days=7)
            logger.info("   ✅ Ralph analysis complete")
        except Exception as e:
            logger.warning(f"   ⚠️ Analysis skipped: {e}")
        logger.info("")

        logger.info("=" * 80)
        logger.info("✅ DAILY PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info("")

    except Exception as e:
        logger.error(f"❌ Daily pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================================================
# LIFESPAN HANDLER (FastAPI lifespan events)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all components on startup and cleanup on shutdown"""
    global conviction_engine, pumpportal_monitor, db, performance_tracker, active_tracker, helius_fetcher, smart_wallet_tracker, telegram_monitor, revival_scanner

    # ========== STARTUP ==========
    
    logger.info("=" * 70)
    logger.info("🔥 PROMETHEUS - AUTONOMOUS SIGNAL SYSTEM")
    logger.info("=" * 70)
    
    # Initialize database FIRST
    logger.info("📊 Initializing database...")
    db = Database()
    await db.connect()
    logger.info("✅ Database connected and tables created")

    # CRITICAL: Sync training tokens from DB to file (survives Railway deploys)
    # Railway's ephemeral filesystem resets files on each deploy, but DB persists
    try:
        import json
        db_tokens = await db.load_training_tokens()
        if db_tokens:
            # Load existing file to preserve metadata
            file_data = {}
            data_file = 'data/historical_training_data.json'
            try:
                with open(data_file, 'r') as f:
                    file_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            file_count = len(file_data.get('tokens', []))
            db_count = len(db_tokens)

            # Only sync if DB has more tokens than file (prevents accidental data loss)
            if db_count > file_count:
                logger.info(f"🔄 Syncing training data: DB has {db_count} tokens, file has {file_count}")

                # Calculate outcome distribution
                outcome_dist = {}
                for token in db_tokens:
                    outcome = token.get('outcome', 'unknown')
                    outcome_dist[outcome] = outcome_dist.get(outcome, 0) + 1

                output = {
                    'collected_at': datetime.utcnow().isoformat(),
                    'total_tokens': db_count,
                    'synced_from_db': True,
                    'last_sync': datetime.utcnow().isoformat(),
                    'outcome_distribution': outcome_dist,
                    'tokens': db_tokens
                }

                os.makedirs('data', exist_ok=True)
                with open(data_file, 'w') as f:
                    json.dump(output, f, indent=2)
                logger.info(f"✅ Synced {db_count} training tokens from DB to file")
            else:
                logger.info(f"📊 Training data in sync: DB={db_count}, file={file_count}")
        else:
            logger.info("📊 No training tokens in database yet")
    except Exception as e:
        logger.warning(f"⚠️ Could not sync training tokens: {e}")

    # Run startup diagnostics (database check + OPT-041 verification)
    asyncio.create_task(run_diagnostics(db))

    # Initialize smart wallet tracker with enriched wallets (NEW!)
    logger.info("🔍 Enriching smart wallets with metadata...")
    enriched_wallets, wallet_addresses = await initialize_smart_wallets()
    logger.info(f"✅ Enriched {len(enriched_wallets)} wallets")
    
    # Create SmartWalletTracker
    logger.info("👑 Initializing Smart Wallet Tracker...")
    smart_wallet_tracker = SmartWalletTracker()  # ← No parameters
    
    # Pass database to smart wallet tracker
    smart_wallet_tracker.db = db
    
    # Manually set the enriched wallets dict (address -> wallet_info)
    smart_wallet_tracker.tracked_wallets = {
        wallet['address']: wallet 
        for wallet in enriched_wallets
    }
    
    logger.info(f"✅ Smart Wallet Tracker configured with {len(enriched_wallets)} wallets")

    # Load additional wallets from DB (added via /refreshwallets from Dune)
    try:
        db_wallets = await db.get_tracked_wallets_for_conviction()
        if db_wallets:
            # Merge DB wallets into tracker (DB wallets override if conflict)
            before_count = len(smart_wallet_tracker.tracked_wallets)
            smart_wallet_tracker.tracked_wallets.update(db_wallets)
            added_count = len(smart_wallet_tracker.tracked_wallets) - before_count
            logger.info(f"✅ Loaded {len(db_wallets)} wallets from DB ({added_count} new, {len(db_wallets) - added_count} updated)")
            logger.info(f"   📊 Total tracked wallets for conviction: {len(smart_wallet_tracker.tracked_wallets)}")
    except Exception as e:
        logger.warning(f"⚠️ Could not load DB wallets: {e}")

    # Initialize Helius fetcher
    logger.info("🔗 Initializing Helius data fetcher...")
    helius_fetcher = HeliusDataFetcher()
    logger.info("✅ Helius fetcher initialized")
    
    # Initialize trackers
    logger.info("🔍 Starting trackers...")
    await smart_wallet_tracker.start()
    await narrative_detector.start()
    logger.info("✅ Trackers initialized")
    
    # Initialize conviction engine
    logger.info("🧠 Initializing conviction engine...")
    conviction_engine = ConvictionEngine(
        smart_wallet_tracker=smart_wallet_tracker,
        narrative_detector=narrative_detector,
        database=db  # Pass database for persistent telegram call tracking
    )
    logger.info("✅ Conviction engine initialized")
    
    # Initialize Telegram
    logger.info("📱 Initializing Telegram...")
    telegram_initialized = await telegram_publisher.initialize()

    if telegram_initialized:
        await telegram_publisher.post_test_message()

    # Initialize Admin Bot (for admin commands)
    admin_bot = None
    admin_bot_initialized = False
    if config.ADMIN_TELEGRAM_USER_ID:
        logger.info("🤖 Initializing admin bot...")
        from admin_bot import AdminBot
        admin_bot = AdminBot(
            active_tracker=None,  # Will be set after active_tracker is created
            database=db,
            performance_tracker=None,  # Will be set after performance_tracker is created
            telegram_calls_cache=telegram_calls_cache
        )
        admin_bot_initialized = await admin_bot.initialize()
        if admin_bot_initialized:
            # Start admin bot in background with error wrapper
            async def start_admin_bot():
                try:
                    logger.info("🚀 Starting admin bot polling...")
                    await admin_bot.start()
                except Exception as e:
                    logger.error(f"❌ Admin bot crashed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

            asyncio.create_task(start_admin_bot())
            # Give it a moment to start
            await asyncio.sleep(2)
            logger.info("✅ Admin bot task created")
    else:
        logger.info("ℹ️ Admin bot disabled (ADMIN_TELEGRAM_USER_ID not set)")

    # Initialize Performance Tracker
    logger.info("📊 Initializing performance tracker...")
    performance_tracker = PerformanceTracker(db=db, telegram_publisher=telegram_publisher)
    await performance_tracker.start()
    logger.info("✅ Performance tracker started")

    # Link performance tracker to admin bot
    if admin_bot_initialized:
        admin_bot.performance_tracker = performance_tracker

    # Set up daily pipeline scheduler (ML auto-retraining at 2 AM UTC)
    global daily_pipeline_scheduler
    if APSCHEDULER_AVAILABLE and admin_bot_initialized:
        logger.info("⏰ Setting up daily ML pipeline scheduler...")
        daily_pipeline_scheduler = AsyncIOScheduler()

        async def scheduled_daily_pipeline():
            """Run daily pipeline if auto ML is enabled"""
            if admin_bot and admin_bot.auto_ml_enabled:
                logger.info("🔄 Running scheduled daily ML pipeline...")
                await run_daily_pipeline()
            else:
                logger.info("⏭️ Skipping daily pipeline (auto ML disabled)")

        # Schedule for 2 AM UTC daily
        daily_pipeline_scheduler.add_job(
            scheduled_daily_pipeline,
            CronTrigger(hour=2, minute=0),
            id='daily_ml_pipeline',
            name='Daily ML Pipeline (collect + retrain)'
        )
        daily_pipeline_scheduler.start()
        logger.info("✅ Daily pipeline scheduled for 2:00 AM UTC")
    elif not APSCHEDULER_AVAILABLE:
        logger.warning("⚠️ APScheduler not installed - install with: pip install apscheduler")

    # Initialize Active Token Tracker (NEW!)
    logger.info("🎯 Initializing active token tracker...")
    active_tracker = ActiveTokenTracker(
        conviction_engine=conviction_engine,
        telegram_publisher=telegram_publisher,
        db=db,
        helius_fetcher=helius_fetcher  # Pass Helius fetcher
    )

    # CRITICAL: Assign active_tracker back to conviction_engine for unique buyers scoring
    conviction_engine.active_tracker = active_tracker
    logger.info("✅ Active token tracker initialized and linked to conviction engine")

    # Link active tracker to admin bot
    if admin_bot_initialized:
        admin_bot.active_tracker = active_tracker
    
    # Initialize PumpPortal monitor (OPTIONAL - can be disabled to save resources)
    if config.DISABLE_PUMPPORTAL:
        logger.info("⏭️  PumpPortal DISABLED (strict KOL-only mode)")
        logger.info("   Only tracking tokens from Helius webhook (KOL buys)")
        pumpportal_monitor = None
    else:
        logger.info("🔌 Initializing PumpPortal monitor...")
        pumpportal_monitor = PumpMonitorV2(
            on_signal_callback=handle_pumpportal_signal,
            active_tracker=active_tracker  # Pass active tracker
        )
        logger.info("✅ PumpPortal monitor initialized")

        # Link pump monitor to conviction engine for velocity spike detection
        conviction_engine.pump_monitor = pumpportal_monitor

        # Wait a bit for everything to stabilize before starting background task
        logger.info("⏳ Waiting 2 seconds before starting PumpPortal task...")
        await asyncio.sleep(2)

        # Start monitoring in background with error handling
        logger.info("🚨 Creating PumpPortal background task...")
        asyncio.create_task(start_pumpportal_task())
        logger.info("✅ PumpPortal monitor task created")
    
    # Initialize post-call monitor (fade detection after signals)
    post_call_monitor = get_post_call_monitor(
        dexscreener_fetcher=helius_fetcher,
        telegram_poster=telegram_publisher,
        pump_monitor=pumpportal_monitor
    )
    active_tracker.post_call_monitor = post_call_monitor
    logger.info("✅ Post-call monitor initialized (10min fade detection)")

    # Initialize Post-Grad Revival Scanner (NEW!)
    # Monitors graduated tokens for bottom reversal patterns
    if config.POST_GRAD_REVIVAL_SCANNER.get('enabled', True):
        logger.info("🔄 Initializing post-grad revival scanner...")
        from trackers.post_grad_revival_scanner import PostGradRevivalScanner
        revival_scanner = PostGradRevivalScanner(active_tracker=active_tracker)

        # Link to pump monitor so graduations are added to watchlist
        if pumpportal_monitor:
            pumpportal_monitor.revival_scanner = revival_scanner

        # Start revival scanner polling in background
        asyncio.create_task(revival_scanner.start())
        logger.info("✅ Revival scanner started (watching post-grad tokens for bottoms)")
    else:
        logger.info("⏭️ Revival scanner disabled in config")

    # Helius Pump.fun program webhook
    if config.HELIUS_PUMP_WEBHOOK.get('enabled', False) and config.HELIUS_PUMP_WEBHOOK.get('auto_register', False):
        logger.info("🔗 Registering Helius Pump.fun program webhook...")
        try:
            railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
            if railway_url:
                if not railway_url.startswith('http'):
                    railway_url = f"https://{railway_url}"
                pump_webhook_url = f"{railway_url}{config.HELIUS_PUMP_WEBHOOK['endpoint_path']}"
                webhook_id = await helius_fetcher.ensure_pump_webhook(pump_webhook_url)
                if webhook_id:
                    logger.info(f"✅ Pump.fun webhook active: {webhook_id}")
                else:
                    logger.warning("⚠️ Failed to register Pump.fun webhook")
            else:
                logger.warning("⚠️ RAILWAY_PUBLIC_DOMAIN not set - skipping webhook")
        except Exception as e:
            logger.error(f"❌ Pump webhook registration failed: {e}")
    else:
        # CLEANUP: Delete any existing pump webhooks to stop credit burn
        logger.info("🧹 Pump.fun webhook DISABLED - cleaning up existing webhooks to stop credit burn...")
        try:
            existing = await helius_fetcher.get_webhooks()
            pump_program_id = config.HELIUS_PUMP_WEBHOOK.get('program_id', '')
            deleted = 0
            for wh in existing:
                accounts = wh.get('accountAddresses', [])
                if pump_program_id in accounts:
                    wh_id = wh.get('webhookID', '')
                    if wh_id:
                        await helius_fetcher.delete_webhook(wh_id)
                        deleted += 1
                        logger.info(f"   🗑️ Deleted pump webhook: {wh_id}")
            if deleted:
                logger.info(f"✅ Cleaned up {deleted} pump webhook(s) - credits saved!")
            else:
                logger.info("   No pump webhooks found to clean up")
            logger.info("   📡 Organic discovery via PumpPortal WebSocket (FREE)")
        except Exception as e:
            logger.warning(f"⚠️ Webhook cleanup failed: {e} - manually delete via Helius dashboard")

    # Start holder polling task (NEW!)
    logger.info("🔄 Starting token polling task...")
    asyncio.create_task(smart_polling_task())
    logger.info("✅ Polling started (30s interval)")

    # Log configuration
    logger.info("=" * 70)
    logger.info("⚙️  CONFIGURATION")
    logger.info("=" * 70)
    discovery_mode = "ON-CHAIN ORGANIC SCANNER" if not config.STRICT_KOL_ONLY_MODE else "KOL-Triggered"
    logger.info(f"🎯 Discovery Mode: {discovery_mode}")
    if not config.STRICT_KOL_ONLY_MODE:
        scanner_cfg = config.ORGANIC_SCANNER
        logger.info(f"   🔬 Organic Scanner: ENABLED (min {scanner_cfg['min_unique_buyers']} buyers, {scanner_cfg['min_buy_ratio']:.0%} buy ratio)")
        logger.info(f"   👑 KOL Scoring: DISABLED (structure preserved)")
    logger.info(f"Min Conviction Score: {config.MIN_CONVICTION_SCORE}/100 (pre-grad) | {config.POST_GRAD_THRESHOLD}/100 (post-grad)")
    logger.info(f"Elite Wallets: {len(smart_wallet_tracker.tracked_wallets)} loaded (scoring {'active' if config.SMART_WALLET_WEIGHTS.get('max_score', 0) > 0 else 'disabled'})")
    logger.info(f"💰 Data Sources: PumpPortal + Helius + Bonding Curve + DexScreener")
    logger.info(f"⚡ PumpPortal: {'DISABLED' if config.DISABLE_PUMPPORTAL else 'ENABLED'}")
    logger.info(f"💎 Credit Optimization: {'ENABLED' if config.DISABLE_POLLING_BELOW_THRESHOLD else 'DISABLED'}")
    logger.info(f"Performance Tracking: ✅ Enabled")
    logger.info(f"Milestones: {', '.join(f'{m}x' for m in config.MILESTONES)}")
    logger.info(f"Daily Reports: ✅ Midnight UTC")
    logger.info("=" * 70)

    logger.info("✅ PROMETHEUS READY")
    logger.info("=" * 70)
    if not config.STRICT_KOL_ONLY_MODE:
        logger.info("🔬 Organic scanner watching ALL new pump.fun tokens...")
        logger.info("⚡ Auto-discovering tokens with strong on-chain activity")
    else:
        logger.info("🔥 Watching all elite trader activity...")
    logger.info("⚡ Real-time analysis on every trade")
    logger.info("💰 Helius bonding curve decoder for pump.fun tokens")
    logger.info("🚀 Signals posted the moment threshold is crossed")
    logger.info("")
    logger.info("The fire has been stolen. Let it spread. 🔥")
    logger.info("=" * 70)

    # Check Telegram session status BEFORE attempting to start monitor
    # This provides clear feedback about session availability
    telegram_session_valid = False
    if config.ENABLE_BUILTIN_TELEGRAM_MONITOR:
        telegram_session_valid = await check_telegram_session()

    # Start Telegram monitor (if enabled and session is valid)
    if config.ENABLE_BUILTIN_TELEGRAM_MONITOR:
        if config.TELEGRAM_GROUPS:
            if telegram_session_valid:
                logger.info("\n📱 Initializing built-in Telegram monitor...")
                try:
                    from telegram_monitor import TelegramMonitor
                    # OPT-052: Pass active_tracker so TG calls can trigger tracking immediately
                    telegram_monitor = TelegramMonitor(telegram_calls_cache, active_tracker=active_tracker)

                    success = await telegram_monitor.initialize(config.TELEGRAM_GROUPS)
                    if success:
                        # Start monitor in background
                        asyncio.create_task(telegram_monitor.run())
                        logger.info(f"✅ Telegram monitor started ({len(config.TELEGRAM_GROUPS)} groups)")
                    else:
                        logger.warning("\n⚠️ Telegram monitor failed to initialize")
                        logger.warning("   Check the session diagnostics above for details")
                        logger.warning("   Run: python check_session.py for detailed diagnosis")
                except Exception as e:
                    logger.error(f"\n❌ Failed to start Telegram monitor: {e}")
                    logger.error("   Check logs above for session diagnostics")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning("\n⚠️ Telegram monitor NOT started - session invalid or missing")
                logger.warning("   See session diagnostics above for fix instructions")
                logger.warning("   Run: python check_session.py for detailed diagnosis")
        else:
            logger.warning("\n⚠️ ENABLE_BUILTIN_TELEGRAM_MONITOR=True but no TELEGRAM_GROUPS configured")
            logger.info("   Run: python telegram_monitor.py to generate group list")

    # Start automated historical data collector (weekly)
    logger.info("🤖 Starting automated historical data collector (weekly)...")
    from automated_collector import start_automated_collector
    await start_automated_collector()

    # Start automated DAILY token collector (midnight UTC)
    logger.info("📅 Starting automated daily token collector (midnight UTC)...")
    from automated_daily_collector import start_automated_daily_collector
    await start_automated_daily_collector()

    # Start background tasks
    asyncio.create_task(cleanup_task())

    # ========== YIELD - App is now running ==========
    yield

    # ========== SHUTDOWN ==========
    logger.info("🛑 Shutting down Prometheus...")

    if pumpportal_monitor:
        await pumpportal_monitor.stop()

    if performance_tracker:
        await performance_tracker.stop()

    if telegram_monitor:
        await telegram_monitor.stop()

    if db:
        await db.close()

    logger.info("✅ Shutdown complete")

# ============================================================================
# FASTAPI APP INSTANCE
# ============================================================================

app = FastAPI(
    title="Prometheus - Autonomous Signals",
    lifespan=lifespan
)

# ============================================================================
# WEBHOOKS
# ============================================================================

@app.post("/webhook/smart-wallet")
async def smart_wallet_webhook(request: Request):
    """
    Helius webhook for smart wallet transactions

    DISABLED (2026-01-31): KOLs have 18% WR vs Organic 29% WR
    Going pure organic until we find consistently good wallets.
    Delete webhook from Helius dashboard with /syncwebhook or run:
    python tools/kill_webhooks.py
    """
    # Early exit when KOL tracking is disabled
    if not getattr(config, 'ENABLE_KOL_TRACKING', True):
        return {"status": "disabled", "reason": "KOL tracking disabled - organic only mode"}

    try:
        data = await request.json()

        # Process through smart wallet tracker (saves to DB)
        await smart_wallet_tracker.process_webhook(data)

        # Extract token addresses that were bought
        token_addresses = extract_token_addresses_from_webhook(data)

        if token_addresses:
            # Only log when actual token purchase detected
            logger.info(f"🎯 KOL bought {len(token_addresses)} token(s): {[t[:8] for t in token_addresses]}")

            for token_address in token_addresses:
                await active_tracker.start_tracking(token_address)
                active_tracker.track_buyers_from_webhook(token_address, data)

        # Non-purchase webhooks are silent (no log spam)
        return {"status": "success"}

    except Exception as e:
        logger.error(f"❌ Error processing smart wallet webhook: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/pump-program")
async def pump_program_webhook(request: Request):
    """
    Helius enhanced webhook for Pump.fun program events.
    DISABLED: Returns immediately to save CPU. Delete webhook from Helius dashboard
    or run: python tools/kill_webhooks.py
    """
    # Early exit when disabled - webhook still registered on Helius side
    if not config.HELIUS_PUMP_WEBHOOK.get('enabled', False):
        return {"status": "disabled"}

    """
    Event flow:
    1. Helius detects transaction on Pump.fun program
    2. Sends enhanced (parsed) transaction data here
    3. We extract token mint + event type
    4. For new token creates: add to organic scanner watch list
    5. For trades on tracked tokens: update real-time data

    This replaces flaky PumpPortal WS for discovery.
    Cost: ~1 credit per event (very cheap vs polling).
    """
    try:
        data = await request.json()

        if not isinstance(data, list):
            data = [data]

        for tx in data:
            tx_type = tx.get('type', '')
            source = tx.get('source', '')
            fee_payer = tx.get('feePayer', '')

            # Extract token mint from the transaction
            token_transfers = tx.get('tokenTransfers', [])
            account_data = tx.get('accountData', [])
            instructions = tx.get('instructions', [])

            token_address = None

            # Method 1: From token transfers
            for transfer in token_transfers:
                mint = transfer.get('mint', '')
                if mint and mint not in {
                    'So11111111111111111111111111111111111111112',
                    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                }:
                    token_address = mint
                    break

            # Method 2: From instructions (for token creation events)
            if not token_address:
                for ix in instructions:
                    for inner_ix in ix.get('innerInstructions', []):
                        for inner in inner_ix if isinstance(inner_ix, list) else [inner_ix]:
                            accounts = inner.get('accounts', []) if isinstance(inner, dict) else []
                            # Pump.fun create instruction has mint as first account
                            if len(accounts) >= 2:
                                potential_mint = accounts[0]
                                if len(potential_mint) > 30:  # Looks like a pubkey
                                    token_address = potential_mint
                                    break

            if not token_address:
                continue

            # Route event based on type
            if active_tracker and active_tracker.is_tracked(token_address):
                # Already tracked token - update with Helius data (more accurate)
                await active_tracker.update_token_trade(token_address, tx)
            elif pumpportal_monitor and not active_tracker.is_tracked(token_address):
                # New token from Pump.fun program - feed to organic scanner
                # Extract basic info for the scanner
                bonding_pct = 0  # Will be calculated by scanner from trade data

                # If we have trade stats already, the organic scanner will evaluate
                # Otherwise, just record the trade for tracking
                if token_address not in pumpportal_monitor.trade_stats:
                    pumpportal_monitor.trade_stats[token_address] = {
                        'buys': 0, 'sells': 0, 'blocks': {}
                    }

                # Determine if this is a buy or sell from token transfers
                for transfer in token_transfers:
                    if transfer.get('mint') == token_address:
                        to_account = transfer.get('toUserAccount', '')
                        from_account = transfer.get('fromUserAccount', '')
                        token_amount = float(transfer.get('tokenAmount', 0))

                        if to_account == fee_payer:
                            # Buy
                            pumpportal_monitor.trade_stats[token_address]['buys'] += 1
                            # Track unique buyer
                            if token_address not in pumpportal_monitor.unique_buyers:
                                pumpportal_monitor.unique_buyers[token_address] = set()
                                pumpportal_monitor.buyer_tracking_start[token_address] = datetime.now()
                            pumpportal_monitor.unique_buyers[token_address].add(fee_payer)

                            # Sync to active_tracker
                            if active_tracker:
                                if token_address not in active_tracker.unique_buyers:
                                    active_tracker.unique_buyers[token_address] = set()
                                active_tracker.unique_buyers[token_address].add(fee_payer)

                        elif from_account == fee_payer:
                            # Sell
                            pumpportal_monitor.trade_stats[token_address]['sells'] += 1

                        # Track SOL volume for rolling window analysis
                        native_transfers = tx.get('nativeTransfers', [])
                        for nt in native_transfers:
                            if nt.get('fromUserAccount') == fee_payer:
                                sol_amount = float(nt.get('amount', 0)) / 1e9  # lamports to SOL
                                if sol_amount > 0 and token_address in pumpportal_monitor.sol_volume_history:
                                    pumpportal_monitor.sol_volume_history[token_address].append(
                                        (datetime.now(), sol_amount)
                                    )
                                elif sol_amount > 0:
                                    pumpportal_monitor.sol_volume_history[token_address] = [
                                        (datetime.now(), sol_amount)
                                    ]

        return {"status": "success", "processed": len(data)}

    except Exception as e:
        logger.error(f"❌ Error processing pump-program webhook: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/webhook/telegram-call")
async def telegram_call_webhook(token: str, group: str = "unknown"):
    """
    Webhook for Telegram scraper (solana-token-scraper)
    Receives CA when detected in alpha groups

    Supports:
    - Multiple mentions (stacking bonus)
    - Group quality tracking (for future weighting)
    - Call-triggered tracking (optional)

    Args:
        token: Contract address (Solana CA)
        group: Group name/ID (optional, for quality tracking)

    Example:
        GET /webhook/telegram-call?token=GDfn...abc&group=bullish_bangers
    """
    try:
        logger.info(f"🔥 TELEGRAM CALL detected: {token[:8]}... (group: {group})")

        # Add to cache with timestamp
        now = datetime.utcnow()

        if token not in telegram_calls_cache:
            telegram_calls_cache[token] = {
                'mentions': [],
                'first_seen': now,
                'groups': set()
            }

        # Add this mention
        telegram_calls_cache[token]['mentions'].append({
            'timestamp': now,
            'group': group
        })
        telegram_calls_cache[token]['groups'].add(group)

        mention_count = len(telegram_calls_cache[token]['mentions'])
        group_count = len(telegram_calls_cache[token]['groups'])

        logger.info(f"   📊 Total mentions: {mention_count} from {group_count} group(s)")

        # ================================================================
        # PERSISTENT CALL TRACKING - Store in database
        # ================================================================
        try:
            await db.insert_telegram_call(
                token_address=token,
                group_name=group,
                message_text=None,  # Could be passed if scraper provides it
                timestamp=now
            )
            logger.debug(f"   💾 Stored call in database: {group} → {token[:8]}")
        except Exception as db_err:
            logger.error(f"   ⚠️  Failed to store call in database: {db_err}")

        # ================================================================
        # GROUP CORRELATION TRACKING
        # ================================================================
        # Track which groups call together for correlation analysis
        if group_count >= 2:
            try:
                # Get all groups that called this token
                all_groups = list(telegram_calls_cache[token]['groups'])
                current_group_idx = all_groups.index(group)

                # Compare with all other groups that called this token
                for other_group in all_groups[:current_group_idx]:
                    # Find the time difference between calls
                    other_mentions = [
                        m for m in telegram_calls_cache[token]['mentions']
                        if m['group'] == other_group
                    ]
                    if other_mentions:
                        time_diff = abs((now - other_mentions[-1]['timestamp']).total_seconds())

                        # Store correlation (only if within 30 min)
                        if time_diff <= 1800:  # 30 minutes
                            await db.insert_group_correlation(
                                group_a=group,
                                group_b=other_group,
                                token_address=token,
                                time_diff_seconds=int(time_diff)
                            )
                            logger.debug(f"   🔗 Correlation: {group} + {other_group} ({time_diff:.0f}s apart)")

            except Exception as corr_err:
                logger.error(f"   ⚠️  Failed to track group correlation: {corr_err}")

        # Cleanup old entries (>4 hours)
        cutoff = now - timedelta(hours=4)
        for ca in list(telegram_calls_cache.keys()):
            # Remove old mentions
            telegram_calls_cache[ca]['mentions'] = [
                m for m in telegram_calls_cache[ca]['mentions']
                if m['timestamp'] > cutoff
            ]
            # Remove token if no recent mentions
            if not telegram_calls_cache[ca]['mentions']:
                del telegram_calls_cache[ca]
                logger.debug(f"   🧹 Cleaned up old call: {ca[:8]}")

        # OPT-052: ALWAYS start tracking TG calls (same as KOL buys)
        # This enables full analysis: data quality, emergency stops, rug detection, etc.
        if 'tracked' not in telegram_calls_cache[token]:
            telegram_calls_cache[token]['tracked'] = False

        if not telegram_calls_cache[token]['tracked']:
            logger.info(f"   🎯 OPT-052: Starting full analysis (same as KOL buy)")
            telegram_calls_cache[token]['tracked'] = True

            # Start tracking immediately
            if active_tracker and not active_tracker.is_tracked(token):
                try:
                    await active_tracker.start_tracking(token, source='telegram_call')
                    logger.info(f"   ✅ Tracking started for {token[:8]}...")
                except Exception as track_err:
                    logger.error(f"   ❌ Failed to start tracking: {track_err}")

        # Additional bonus if multi-group call
        if group_count >= 2:
            first_mention = telegram_calls_cache[token]['first_seen']
            time_spread = (now - first_mention).total_seconds()
            if time_spread <= 300:  # 5 minutes
                logger.info(f"   🔥 MULTI-GROUP CALL: {group_count} groups in {time_spread:.0f}s - extra conviction bonus!")

        return {
            "status": "received",
            "token": token,
            "mentions": mention_count,
            "groups": group_count
        }

    except Exception as e:
        logger.error(f"❌ Error processing Telegram call: {e}")
        return {"status": "error", "message": str(e)}

# ============================================================================
# HEALTH CHECK & STATUS
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "Prometheus - Autonomous Signals",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/status")
async def status():
    """Detailed status endpoint"""
    from datetime import datetime
    
    trending = narrative_detector.get_trending_narratives(24) if narrative_detector else []
    perf_stats = await performance_tracker.get_stats() if performance_tracker else {}
    tracker_stats = active_tracker.get_stats() if active_tracker else {}
    
    return {
        "status": "operational",
        "mode": "KOL-Triggered Tracking",
        "config": {
            "min_conviction": config.MIN_CONVICTION_SCORE,
        },
        "trackers": {
            "elite_wallets": len(smart_wallet_tracker.tracked_wallets) if smart_wallet_tracker else 0,
            "active_tokens": tracker_stats.get('active_tokens', 0),
            "tokens_tracked_total": tracker_stats.get('tokens_tracked_total', 0),
            "signals_sent": tracker_stats.get('signals_sent', 0),
        },
        "performance": perf_stats,
        "trending_narratives": trending[:5],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/pumpportal-status")
async def pumpportal_diagnostic():
    """PumpPortal monitor diagnostic endpoint"""
    return {
        "monitor_exists": pumpportal_monitor is not None,
        "is_running": pumpportal_monitor.running if pumpportal_monitor else False,
        "tracked_tokens": len(pumpportal_monitor.tracked_tokens) if pumpportal_monitor else 0,
        "websocket_connected": pumpportal_monitor.ws is not None if pumpportal_monitor else False,
        "connection_attempts": pumpportal_monitor.connection_attempts if pumpportal_monitor else 0,
        "messages_received": pumpportal_monitor.messages_received if pumpportal_monitor else 0,
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
