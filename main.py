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

# Configure logging (environment-based to avoid Railway 500 logs/sec limit)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'WARNING').upper()  # Default: WARNING (minimal logs)
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level=LOG_LEVEL
)

# Import existing modules
import config
from database import Database
from pump_monitor_v2 import PumpMonitorV2
from performance_tracker import PerformanceTracker
from trackers.smart_wallets import SmartWalletTracker
from trackers.narrative_detector import NarrativeDetector
from scoring.conviction_engine import ConvictionEngine
from publishers.telegram import TelegramPublisher
from active_token_tracker import ActiveTokenTracker
from helius_fetcher import HeliusDataFetcher
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
    NOW: Only used for graduation signals or tokens not yet tracked by KOLs
    
    Args:
        token_data: Token information from PumpPortal
        signal_type: 'NEW_TOKEN', 'PRE_GRADUATION', or 'POST_GRADUATION'
    """
    try:
        token_address = token_data.get('token_address')
        
        # If this is a NEW_TOKEN event, check if it's tracked by ActiveTracker
        if signal_type == 'NEW_TOKEN':
            # Check if we're already tracking this (KOL bought it)
            if active_tracker and active_tracker.is_tracked(token_address):
                # Update with PumpPortal data
                await active_tracker.update_token_trade(token_address, token_data)
                return  # Don't process further, ActiveTracker handles it
            else:
                # Not tracked by KOLs, skip
                return
        
        # For PRE_GRADUATION and POST_GRADUATION, check if tracked
        if active_tracker and active_tracker.is_tracked(token_address):
            # Just update the tracked token with graduation info
            await active_tracker.update_token_trade(token_address, token_data)
            return
        
        # If we get here, it's a graduation for a non-KOL token
        # You can optionally score these too, but they're lower priority
        logger.debug(f"⏭️  Graduation for non-KOL token: {token_address[:8]}")
        
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
                        
                        # Log changes
                        logger.info(f"✅ Refreshed {len(enriched_wallets)} wallets")
                        
                        # Show any significant changes
                        for wallet in enriched_wallets:
                            name = wallet.get('name', 'Unknown')
                            tier = wallet.get('tier', 'unknown')
                            win_rate = wallet.get('win_rate', 0)
                            logger.info(f"   📊 {name} ({tier}): {win_rate*100:.1f}% WR")
                        
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

async def run_daily_pipeline():
    """
    Daily pipeline that runs at midnight UTC:
    1. Collects yesterday's top 50 tokens from DexScreener/Moralis
    2. Extracts whale wallets and saves to database
    3. Retrains ML model if enough new data (200+ tokens, 50+ new)
    4. Deploys new model for next conviction scoring cycle
    """
    logger.info("=" * 80)
    logger.info("🌅 DAILY PIPELINE STARTING")
    logger.info("=" * 80)
    logger.info(f"   Date: {datetime.utcnow().date()}")
    logger.info("")

    try:
        # Step 1: Daily token collection
        logger.info("📊 STEP 1: Collecting yesterday's top tokens...")
        from tools.daily_token_collector import DailyTokenCollector
        collector = DailyTokenCollector()
        await collector.collect_daily()
        logger.info("✅ Token collection complete")
        logger.info("")

        # Step 2: ML model retraining (if needed)
        logger.info("🎓 STEP 2: Checking if ML retraining needed...")
        from tools.automated_ml_retrain import AutomatedMLRetrainer
        retrainer = AutomatedMLRetrainer()
        await retrainer.run()
        logger.info("✅ ML retraining check complete")
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
    global conviction_engine, pumpportal_monitor, db, performance_tracker, active_tracker, helius_fetcher, smart_wallet_tracker, telegram_monitor

    # ========== STARTUP ==========
    
    logger.info("=" * 70)
    logger.info("🔥 PROMETHEUS - AUTONOMOUS SIGNAL SYSTEM")
    logger.info("=" * 70)
    
    # Initialize database FIRST
    logger.info("📊 Initializing database...")
    db = Database()
    await db.connect()
    logger.info("✅ Database connected and tables created")

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
        database=db  # Pass database for persistent telegram call tracking
        # narrative_detector is not needed - ConvictionEngine loads from config
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
    
    # Start holder polling task (NEW!)
    logger.info("🔄 Starting token polling task...")
    asyncio.create_task(smart_polling_task())
    logger.info("✅ Polling started (30s interval)")

    # Log configuration
    logger.info("=" * 70)
    logger.info("⚙️  CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"🎯 KOL-Triggered Tracking: ENABLED")
    logger.info(f"Min Conviction Score: {config.MIN_CONVICTION_SCORE}/100")
    logger.info(f"Elite Wallets: {len(smart_wallet_tracker.tracked_wallets)} tracked")
    logger.info(f"💰 Data Sources: Helius + Bonding Curve + DexScreener")
    logger.info(f"⚡ PumpPortal: {'DISABLED' if config.DISABLE_PUMPPORTAL else 'ENABLED'} (saves resources)")
    logger.info(f"💎 Credit Optimization: {'ENABLED' if config.DISABLE_POLLING_BELOW_THRESHOLD else 'DISABLED'}")
    logger.info(f"Performance Tracking: ✅ Enabled")
    logger.info(f"Milestones: {', '.join(f'{m}x' for m in config.MILESTONES)}")
    logger.info(f"Daily Reports: ✅ Midnight UTC")
    logger.info("=" * 70)

    logger.info("✅ PROMETHEUS READY")
    logger.info("=" * 70)
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

    NEW BEHAVIOR:
    1. Process webhook to save KOL activity
    2. Extract tokens that were bought
    3. Start real-time tracking for those tokens
    """
    try:
        data = await request.json()

        # 🎬 SCENE 1: WEBHOOK ARRIVAL
        print("\n" + "="*80)
        print("🎬 SCENE 1: KOL ACTIVITY DETECTED - HELIUS WEBHOOK ARRIVAL")
        print("="*80)
        print("📡 A transaction just hit the Solana blockchain...")
        print("🔍 Helius detected activity from one of our 36 elite KOL wallets")
        print("⚡ Webhook delivered to PROMETHEUS in real-time")
        print("📊 Analyzing transaction data to identify token purchases...")
        print("="*80 + "\n")

        logger.info("📥 Received smart wallet webhook")

        # Process through smart wallet tracker (saves to DB)
        await smart_wallet_tracker.process_webhook(data)

        # Extract token addresses that were bought
        token_addresses = extract_token_addresses_from_webhook(data)

        if token_addresses:
            # 🎬 SCENE 2: TOKEN EXTRACTION
            print("\n" + "="*80)
            print("🎬 SCENE 2: TOKEN EXTRACTION - IDENTIFYING THE MEMECOIN")
            print("="*80)
            print(f"💰 KOL purchased {len(token_addresses)} token(s)")
            print("🔬 Filtering out stablecoins, wrapped SOL, and established tokens...")
            print(f"✅ Found {len(token_addresses)} memecoin purchase(s) to analyze")
            for addr in token_addresses:
                print(f"   📍 Token: {addr[:8]}...{addr[-6:]}")
            print("🎯 Initiating real-time tracking system...")
            print("="*80 + "\n")

            logger.info(f"🎯 KOL bought {len(token_addresses)} token(s) - starting tracking...")

            # Start tracking each token
            for i, token_address in enumerate(token_addresses, 1):
                # 🎬 SCENE 3: TRACKING INITIATION
                print("\n" + "="*80)
                print(f"🎬 SCENE 3: TRACKING INITIATION ({i}/{len(token_addresses)})")
                print("="*80)
                print(f"🎯 Target: {token_address[:8]}...{token_address[-6:]}")
                print("📊 Launching ActiveTokenTracker...")
                print("   ├─ Fetching token metadata from pump.fun...")
                print("   ├─ Decoding bonding curve progress...")
                print("   ├─ Checking if already graduated to Raydium...")
                print("   ├─ Collecting initial price & liquidity data...")
                print("   ├─ Identifying unique buyers from blockchain...")
                print("   └─ Preparing real-time conviction scoring...")
                print("⏱️  Polling interval: Every 5-30 seconds based on activity")
                print("="*80 + "\n")

                await active_tracker.start_tracking(token_address)

                # Track unique buyers from this webhook
                active_tracker.track_buyers_from_webhook(token_address, data)

        return {"status": "success"}

    except Exception as e:
        logger.error(f"❌ Error processing smart wallet webhook: {e}")
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
