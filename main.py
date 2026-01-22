"""
🔥 PROMETHEUS - Autonomous Signal System
KOL-Triggered Real-Time Tracking with Conviction Scoring + Telegram Alpha Calls
"""
import asyncio
from typing import Dict, List
from fastapi import FastAPI, Request
from loguru import logger
from datetime import datetime, timedelta
import sys

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
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

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

app = FastAPI(title="Prometheus - Autonomous Signals")

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
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize all components"""
    global conviction_engine, pumpportal_monitor, db, performance_tracker, active_tracker, helius_fetcher, smart_wallet_tracker
    
    logger.info("=" * 70)
    logger.info("🔥 PROMETHEUS - AUTONOMOUS SIGNAL SYSTEM")
    logger.info("=" * 70)
    
    # Initialize database FIRST
    logger.info("📊 Initializing database...")
    db = Database()
    await db.connect()
    logger.info("✅ Database connected and tables created")
    
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
        smart_wallet_tracker=smart_wallet_tracker
        # narrative_detector is not needed - ConvictionEngine loads from config
    )
    logger.info("✅ Conviction engine initialized")
    
    # Initialize Telegram
    logger.info("📱 Initializing Telegram...")
    telegram_initialized = await telegram_publisher.initialize()
    
    if telegram_initialized:
        await telegram_publisher.post_test_message()
    
    # Initialize Performance Tracker
    logger.info("📊 Initializing performance tracker...")
    performance_tracker = PerformanceTracker(db=db, telegram_publisher=telegram_publisher)
    await performance_tracker.start()
    logger.info("✅ Performance tracker started")
    
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
    
    # Start background tasks
    asyncio.create_task(cleanup_task())

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
        logger.info("📥 Received smart wallet webhook")

        # Process through smart wallet tracker (saves to DB)
        await smart_wallet_tracker.process_webhook(data)

        # Extract token addresses that were bought
        token_addresses = extract_token_addresses_from_webhook(data)

        if token_addresses:
            logger.info(f"🎯 KOL bought {len(token_addresses)} token(s) - starting tracking...")

            # Start tracking each token
            for token_address in token_addresses:
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

        # OPTIONAL: Call-triggered tracking (if enabled)
        # Start tracking if mentioned in 2+ groups within 5 min
        if config.TELEGRAM_CALL_TRIGGER_ENABLED and group_count >= 2:
            # Check if mentions happened within 5 min window
            first_mention = telegram_calls_cache[token]['first_seen']
            time_spread = (now - first_mention).total_seconds()

            if time_spread <= 300:  # 5 minutes
                logger.info(f"   🚨 MULTI-GROUP CALL: {group_count} groups in {time_spread:.0f}s - starting tracking!")

                # Start tracking (even without KOL buy)
                if active_tracker and not active_tracker.is_tracked(token):
                    await active_tracker.start_tracking(token, source='telegram_call')

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
# SHUTDOWN
# ============================================================================

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Prometheus...")
    
    if pumpportal_monitor:
        await pumpportal_monitor.stop()
    
    if performance_tracker:
        await performance_tracker.stop()
    
    if db:
        await db.close()
    
    logger.info("✅ Shutdown complete")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
