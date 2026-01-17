"""
Sentinel Signals v2 - Clean, focused memecoin trading signals
"""
import asyncio
from datetime import datetime
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

# Import modules
import config
import database
from trackers.smart_wallets import SmartWalletTracker
from trackers.narrative_detector import NarrativeDetector
from scoring.conviction_engine import ConvictionEngine
from publishers.telegram import TelegramPublisher

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

app = FastAPI(title="Sentinel Signals v2")

# Trackers
smart_wallet_tracker = SmartWalletTracker()
narrative_detector = NarrativeDetector()

# Scoring
conviction_engine = None  # Initialized after trackers

# Publishers
telegram_publisher = TelegramPublisher()

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize all components"""
    logger.info("=" * 70)
    logger.info("🚀 SENTINEL SIGNALS V2 STARTING")
    logger.info("=" * 70)
    
    # Initialize database
    logger.info("📊 Initializing database...")
    database.init_db()
    
    # Initialize trackers
    logger.info("🔍 Starting trackers...")
    await smart_wallet_tracker.start()
    await narrative_detector.start()
    
    # Initialize conviction engine (needs trackers)
    global conviction_engine
    conviction_engine = ConvictionEngine(
        smart_wallet_tracker=smart_wallet_tracker,
        narrative_detector=narrative_detector
    )
    logger.info("✅ Conviction engine initialized")
    
    # Initialize Telegram
    logger.info("📱 Initializing Telegram...")
    telegram_initialized = await telegram_publisher.initialize()
    
    if telegram_initialized:
        # Send test message
        await telegram_publisher.post_test_message()
    
    # Log configuration
    logger.info("=" * 70)
    logger.info("⚙️  CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"Min Conviction Score: {config.MIN_CONVICTION_SCORE}/100")
    logger.info(f"Min Liquidity: ${config.MIN_LIQUIDITY:,}")
    logger.info(f"Min Holders: {config.MIN_HOLDERS}")
    logger.info(f"Max Age: {config.MAX_AGE_MINUTES} minutes")
    logger.info(f"Smart Wallets: {'✅ Enabled' if config.ENABLE_SMART_WALLETS else '❌ Disabled'}")
    logger.info(f"Narratives: {'✅ Enabled' if config.ENABLE_NARRATIVES else '❌ Enabled'}")
    logger.info(f"Telegram: {'✅ Enabled' if config.ENABLE_TELEGRAM else '❌ Disabled'}")
    logger.info("=" * 70)
    
    # Show scoring system
    logger.info(conviction_engine.get_scoring_summary())
    logger.info("=" * 70)
    
    logger.info("✅ SENTINEL SIGNALS V2 READY")
    logger.info("=" * 70)
    
    # Start background tasks
    asyncio.create_task(cleanup_task())

# ============================================================================
# WEBHOOKS
# ============================================================================

@app.post("/webhook/graduation")
async def graduation_webhook(request: Request):
    """
    Helius webhook for token graduations
    Receives notifications when tokens graduate from pump.fun
    """
    try:
        data = await request.json()
        logger.info("📥 Received graduation webhook")
        
        # Process graduation event
        await process_graduation(data)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"❌ Error processing graduation webhook: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/smart-wallet")
async def smart_wallet_webhook(request: Request):
    """
    Helius webhook for smart wallet transactions
    Receives notifications when tracked wallets make transactions
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
# GRADUATION PROCESSING
# ============================================================================

async def process_graduation(webhook_data: list):
    """Process token graduation event"""
    
    for event in webhook_data:
        try:
            # Extract token data
            token_address = event.get('tokenTransfers', [{}])[0].get('mint', '')
            
            if not token_address:
                continue
            
            logger.info(f"🎓 Processing graduation: {token_address[:8]}...")
            
            # Fetch token data from DexScreener
            token_data = await fetch_token_data(token_address)
            
            if not token_data:
                logger.warning(f"⚠️ Could not fetch data for {token_address}")
                continue
            
            # Analyze and score
            await analyze_and_signal(token_address, token_data)
            
        except Exception as e:
            logger.error(f"❌ Error processing graduation: {e}")


async def fetch_token_data(token_address: str) -> dict:
    """Fetch token data from DexScreener API"""
    
    import aiohttp
    
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        # Get the main pair (usually first one)
                        pair = pairs[0]
                        
                        # Calculate age
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at:
                            age_ms = datetime.utcnow().timestamp() * 1000 - created_at
                            age_minutes = age_ms / (1000 * 60)
                        else:
                            age_minutes = 0
                        
                        return {
                            'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                            'name': pair.get('baseToken', {}).get('name', ''),
                            'price': float(pair.get('priceUsd', 0)),
                            'market_cap': float(pair.get('marketCap', 0) or 0),
                            'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                            'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                            'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                            'age_minutes': age_minutes,
                            'holders': 50,  # DexScreener doesn't provide this, use default
                        }
    except Exception as e:
        logger.error(f"❌ Error fetching token data: {e}")
    
    return None


async def analyze_and_signal(token_address: str, token_data: dict):
    """Analyze token and post signal if conviction is high enough"""
    
    # Calculate conviction
    conviction_result = conviction_engine.calculate_conviction(
        token_address=token_address,
        symbol=token_data['symbol'],
        name=token_data.get('name', ''),
        age_minutes=token_data.get('age_minutes', 0),
        liquidity=token_data.get('liquidity', 0),
        holders=token_data.get('holders', 50),
    )
    
    # Check if we should signal
    if not conviction_result['should_signal']:
        return
    
    # Get additional data for the signal
    wallet_activity = smart_wallet_tracker.get_smart_wallet_activity(token_address)
    narrative_data = narrative_detector.analyze_token(
        token_data['symbol'],
        token_data.get('name', ''),
        ''
    )
    
    # Build signal data
    signal_data = {
        'token_address': token_address,
        'symbol': token_data['symbol'],
        'conviction_score': conviction_result['conviction_score'],
        'breakdown': conviction_result['breakdown'],
        'reasons': conviction_result['reasons'],
        'price': token_data.get('price', 0),
        'market_cap': token_data.get('market_cap', 0),
        'liquidity': token_data.get('liquidity', 0),
        'holders': token_data.get('holders', 50),
        'age_minutes': token_data.get('age_minutes', 0),
        'wallet_activity': wallet_activity,
        'narrative_data': narrative_data,
    }
    
    # Post to Telegram
    posted = await telegram_publisher.post_signal(signal_data)
    
    # Save to database
    if posted:
        save_signal_to_db(signal_data, wallet_activity, narrative_data)


def save_signal_to_db(signal_data: dict, wallet_activity: dict, narrative_data: dict):
    """Save posted signal to database"""
    
    session = database.get_session()
    if not session:
        return
    
    try:
        signal = database.Signal(
            token_address=signal_data['token_address'],
            symbol=signal_data['symbol'],
            conviction_score=signal_data['conviction_score'],
            signal_type='standard',
            entry_price=signal_data.get('price', 0),
            entry_mcap=signal_data.get('market_cap', 0),
            entry_liquidity=signal_data.get('liquidity', 0),
            entry_holders=signal_data.get('holders', 0),
            smart_wallet_score=signal_data['breakdown'].get('smart_wallets', 0),
            narrative_score=signal_data['breakdown'].get('narrative', 0),
            timing_score=signal_data['breakdown'].get('timing', 0),
            kol_buyers=[w['name'] for w in wallet_activity.get('wallets', [])],
            narratives=[n['name'] for n in narrative_data.get('narratives', [])],
        )
        
        session.add(signal)
        session.commit()
        logger.info(f"💾 Saved signal to database: {signal_data['symbol']}")
        
    except Exception as e:
        logger.error(f"❌ Error saving signal to database: {e}")
        session.rollback()
    finally:
        session.close()


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
            logger.info("✅ Cleanup complete")
            
        except Exception as e:
            logger.error(f"❌ Error in cleanup task: {e}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Sentinel Signals v2",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/status")
async def status():
    """Detailed status endpoint"""
    
    # Get trending narratives
    trending = narrative_detector.get_trending_narratives(24)
    
    return {
        "status": "operational",
        "config": {
            "min_conviction": config.MIN_CONVICTION_SCORE,
            "smart_wallets_enabled": config.ENABLE_SMART_WALLETS,
            "narratives_enabled": config.ENABLE_NARRATIVES,
            "telegram_enabled": config.ENABLE_TELEGRAM,
        },
        "trackers": {
            "smart_wallets": len(smart_wallet_tracker.tracked_wallets),
            "narratives": len(narrative_detector.narratives),
        },
        "trending_narratives": trending[:5],
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
