"""
Sentinel Signals v2 - Now with PumpPortal for pre-graduation signals
"""
import asyncio
from typing import Dict
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
from pumpportal_monitor import PumpPortalMonitor
from trackers.smart_wallets import SmartWalletTracker
from trackers.narrative_detector import NarrativeDetector
from scoring.conviction_engine import ConvictionEngine
from publishers.telegram import TelegramPublisher

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

app = FastAPI(title="Sentinel Signals v2")

# Monitors
pumpportal_monitor = None

# Trackers
smart_wallet_tracker = SmartWalletTracker()
narrative_detector = NarrativeDetector()

# Scoring
conviction_engine = None

# Publishers
telegram_publisher = TelegramPublisher()

# ============================================================================
# SIGNAL PROCESSING
# ============================================================================

async def handle_pumpportal_signal(token_data: Dict, signal_type: str):
    """
    Handle signals from PumpPortal monitor
    
    Args:
        token_data: Token information from PumpPortal
        signal_type: 'PRE_GRADUATION' (40-60%) or 'POST_GRADUATION' (100%)
    """
    try:
        token_address = token_data.get('token_address')
        symbol = token_data.get('token_symbol', 'UNKNOWN')
        bonding_pct = token_data.get('bonding_curve_pct', 0)
        
        logger.info(f"🎯 Signal received: ${symbol} at {bonding_pct:.1f}% ({signal_type})")
        
        # Calculate conviction score using your existing conviction engine
        conviction_data = await conviction_engine.analyze_token(token_address, token_data)
        conviction_score = conviction_data.get('score', 0)
        
        # Different thresholds for pre vs post graduation
        min_score = 80 if signal_type == 'PRE_GRADUATION' else 75
        
        if conviction_score >= min_score:
            logger.info(f"✅ High conviction ({conviction_score}/100) - posting signal!")
            
            # Add signal type to conviction data
            conviction_data['signal_type'] = signal_type
            conviction_data['bonding_curve_pct'] = bonding_pct
            
            # Post to Telegram using your existing publisher
            await telegram_publisher.post_signal(conviction_data)
            
        else:
            logger.info(f"⏭️  Low conviction ({conviction_score}/100) - skipping")
            
    except Exception as e:
        logger.error(f"❌ Error handling PumpPortal signal: {e}", exc_info=True)

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize all components"""
    global conviction_engine, pumpportal_monitor
    
    logger.info("=" * 70)
    logger.info("🚀 SENTINEL SIGNALS V2 STARTING")
    logger.info("=" * 70)
    
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
    
    # Initialize PumpPortal monitor
    logger.info("🔌 Initializing PumpPortal monitor...")
    pumpportal_monitor = PumpPortalMonitor(on_signal_callback=handle_pumpportal_signal)
    
    # Start monitoring in background
    asyncio.create_task(pumpportal_monitor.start())
    logger.info("✅ PumpPortal monitor started")
    
    # Log configuration
    logger.info("=" * 70)
    logger.info("⚙️  CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"Pre-Graduation Threshold: 80/100 (40-60% bonding)")
    logger.info(f"Post-Graduation Threshold: 75/100 (graduated tokens)")
    logger.info(f"Min Conviction Score: {config.MIN_CONVICTION_SCORE}/100")
    logger.info(f"Smart Wallets: {len(smart_wallet_tracker.tracked_wallets)} tracked")
    logger.info("=" * 70)
    
    logger.info("✅ SENTINEL SIGNALS V2 READY")
    logger.info("=" * 70)
    logger.info("🔍 Monitoring PumpPortal for signals...")
    logger.info("⚡ Pre-graduation signals: 40-60% bonding curve (80+ conviction)")
    logger.info("🎓 Post-graduation signals: 100% bonding curve (75+ conviction)")
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
    Receives notifications when tracked KOL wallets make transactions
    """
    try:
        data = await request.json()
        logger.info("📥 Received smart wallet webhook")
        
        # Process through smart wallet tracker
        await smart_wallet_tracker.process_webhook(data)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"❌ Error processing smart wallet webhook: {e}")
        return {"status": "error", "message": str(e)}

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

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
            
            logger.info("✅ Cleanup complete")
            
        except Exception as e:
            logger.error(f"❌ Error in cleanup task: {e}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "Sentinel Signals v2",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/status")
async def status():
    """Detailed status endpoint"""
    from datetime import datetime
    
    trending = narrative_detector.get_trending_narratives(24) if narrative_detector else []
    
    return {
        "status": "operational",
        "config": {
            "pre_grad_conviction": 80,
            "post_grad_conviction": 75,
            "min_conviction": config.MIN_CONVICTION_SCORE,
        },
        "trackers": {
            "smart_wallets": len(smart_wallet_tracker.tracked_wallets) if smart_wallet_tracker else 0,
            "pumpportal_tracked": len(pumpportal_monitor.tracked_tokens) if pumpportal_monitor else 0,
        },
        "trending_narratives": trending[:5],
        "timestamp": datetime.utcnow().isoformat()
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
    
    logger.info("✅ Shutdown complete")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
