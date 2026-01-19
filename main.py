"""
Sentinel Signals v2 - KOL-Triggered Real-Time Tracking
Now with ActiveTokenTracker for intelligent monitoring
"""
import asyncio
from typing import Dict, List
from fastapi import FastAPI, Request
from loguru import logger
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

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

app = FastAPI(title="Sentinel Signals v2")

# Database
db = None

# Monitors
pumpportal_monitor = None
performance_tracker = None

# Trackers
smart_wallet_tracker = SmartWalletTracker()
narrative_detector = NarrativeDetector()
active_tracker = None  # NEW: Tracks KOL-bought tokens

# Scoring
conviction_engine = None

# Publishers
telegram_publisher = TelegramPublisher()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_token_addresses_from_webhook(webhook_data: List[Dict]) -> List[str]:
    """
    Extract token addresses from Helius webhook data
    
    Args:
        webhook_data: List of transactions from Helius
        
    Returns:
        List of unique token addresses that were bought
    """
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
                    if token_address:
                        token_addresses.add(token_address)
        
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

async def holder_polling_task():
    """
    Poll holder counts for actively tracked tokens
    Runs every 15 seconds to stay real-time
    """
    while True:
        try:
            await asyncio.sleep(15)  # Every 15 seconds
            
            if not active_tracker:
                continue
            
            active_tokens = active_tracker.get_active_tokens()
            
            if not active_tokens:
                continue
            
            logger.debug(f"👥 Polling holders for {len(active_tokens)} tokens...")
            
            # Poll each active token
            for token_address in active_tokens:
                try:
                    holder_count = await fetch_holder_count(token_address)
                    if holder_count > 0:
                        await active_tracker.update_holder_count(token_address, holder_count)
                except Exception as e:
                    logger.debug(f"⚠️ Error polling holders for {token_address[:8]}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error in holder polling task: {e}")

async def fetch_holder_count(token_address: str) -> int:
    """Fetch holder count from Helius"""
    try:
        import aiohttp
        
        url = f"https://mainnet.helius-rpc.com/?api-key={config.HELIUS_API_KEY}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccounts",
            "params": {
                "mint": token_address,
                "options": {
                    "showZeroBalance": False
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status != 200:
                    return 0
                
                data = await resp.json()
                token_accounts = data.get('result', {}).get('token_accounts', [])
                return len(token_accounts)
                
    except Exception as e:
        logger.debug(f"⚠️ Error fetching holders: {e}")
        return 0

async def cleanup_task():
    """Periodic cleanup of old data"""
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
            
        except Exception as e:
            logger.error(f"❌ Error in cleanup task: {e}")

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize all components"""
    global conviction_engine, pumpportal_monitor, db, performance_tracker, active_tracker
    
    logger.info("=" * 70)
    logger.info("🚀 SENTINEL SIGNALS V2 - KOL-TRIGGERED TRACKING")
    logger.info("=" * 70)
    
    # Initialize database FIRST
    logger.info("📊 Initializing database...")
    db = Database()
    await db.connect()
    logger.info("✅ Database connected and tables created")
    
    # Pass database to smart wallet tracker
    smart_wallet_tracker.db = db
    
    # Initialize trackers
    logger.info("🔍 Starting trackers...")
    await smart_wallet_tracker.start()
    await narrative_detector.start()
    logger.info("✅ Trackers initialized")
    
    # Initialize conviction engine
    logger.info("🧠 Initializing conviction engine...")
    conviction_engine = ConvictionEngine(
        smart_wallet_tracker=smart_wallet_tracker,
        narrative_detector=narrative_detector
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
        pumpportal_monitor=None  # Will set after pumpportal_monitor is created
    )
    logger.info("✅ Active token tracker initialized")
    
    # Initialize PumpPortal monitor
    logger.info("🔌 Initializing PumpPortal monitor...")
    pumpportal_monitor = PumpMonitorV2(
        on_signal_callback=handle_pumpportal_signal,
        active_tracker=active_tracker  # Pass active tracker
    )
    
    # Set pumpportal_monitor reference in active_tracker
    active_tracker.pumpportal_monitor = pumpportal_monitor
    logger.info("✅ PumpPortal monitor initialized and linked to tracker")
    
    # Wait a bit for everything to stabilize before starting background task
    logger.info("⏳ Waiting 2 seconds before starting PumpPortal task...")
    await asyncio.sleep(2)
    
    # Start monitoring in background with error handling
    logger.info("🚨 Creating PumpPortal background task...")
    asyncio.create_task(start_pumpportal_task())
    logger.info("✅ PumpPortal monitor task created")
    
    # Start holder polling task (NEW!)
    logger.info("👥 Starting holder polling task...")
    asyncio.create_task(holder_polling_task())
    logger.info("✅ Holder polling started (every 15s)")
    
    # Log configuration
    logger.info("=" * 70)
    logger.info("⚙️  CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"🎯 KOL-Triggered Tracking: ENABLED")
    logger.info(f"Min Conviction Score: {config.MIN_CONVICTION_SCORE}/100")
    logger.info(f"Smart Wallets: {len(smart_wallet_tracker.tracked_wallets)} tracked")
    logger.info(f"Holder Polling: Every 15 seconds")
    logger.info(f"Performance Tracking: ✅ Enabled")
    logger.info(f"Milestones: {', '.join(f'{m}x' for m in config.MILESTONES)}")
    logger.info(f"Daily Reports: ✅ Midnight UTC")
    logger.info("=" * 70)
    
    logger.info("✅ SENTINEL SIGNALS V2 READY")
    logger.info("=" * 70)
    logger.info("🎯 Waiting for KOL buys to trigger tracking...")
    logger.info("⚡ Real-time analysis on every trade")
    logger.info("👥 Holder counts polled every 15 seconds")
    logger.info("🚀 Signals sent the moment threshold is crossed")
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
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"❌ Error processing smart wallet webhook: {e}")
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
        "service": "Sentinel Signals v2 - KOL-Triggered",
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
            "smart_wallets": len(smart_wallet_tracker.tracked_wallets) if smart_wallet_tracker else 0,
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
    logger.info("🛑 Shutting down...")
    
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
