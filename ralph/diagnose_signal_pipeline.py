"""
Diagnostic script to test signal creation pipeline
Run this to see WHY signals aren't being created
"""
import asyncio
import sys
sys.path.append('/app')

from database import Database
from active_token_tracker import ActiveTokenTracker
from scoring.conviction_engine import ConvictionEngine
from publishers.telegram import TelegramPublisher
from helius_fetcher import HeliusDataFetcher
from trackers.narrative_detector import NarrativeDetector
import config

async def diagnose():
    print("🔍 Diagnostic: Signal Creation Pipeline")
    print("=" * 80)

    # Initialize components
    print("\n1. Initializing components...")
    db = Database()
    await db.connect()
    print("   ✅ Database connected")

    helius_fetcher = HeliusDataFetcher()
    print("   ✅ Helius fetcher initialized")

    # Initialize smart wallet tracker first (needed for conviction engine)
    from trackers.smart_wallets import SmartWalletTracker
    from wallet_enrichment import initialize_smart_wallets

    enriched_wallets, wallet_addresses = await initialize_smart_wallets()
    smart_wallet_tracker = SmartWalletTracker()
    smart_wallet_tracker.db = db
    smart_wallet_tracker.tracked_wallets = {
        wallet['address']: wallet
        for wallet in enriched_wallets
    }
    print("   ✅ Smart wallet tracker initialized")

    conviction_engine = ConvictionEngine(smart_wallet_tracker=smart_wallet_tracker)
    print("   ✅ Conviction engine initialized")

    telegram_publisher = TelegramPublisher()
    print("   ✅ Telegram publisher initialized")

    active_tracker = ActiveTokenTracker(
        db=db,
        conviction_engine=conviction_engine,
        telegram_publisher=telegram_publisher,
        helius_fetcher=helius_fetcher
    )
    print("   ✅ Active token tracker initialized")

    # Get a recent token with KOL buys
    print("\n2. Finding recent token with KOL activity...")
    async with db.pool.acquire() as conn:
        recent_token = await conn.fetchrow('''
            SELECT token_address, COUNT(DISTINCT wallet_address) as kol_count
            FROM smart_wallet_activity
            WHERE detected_at > NOW() - INTERVAL '1 hour'
            GROUP BY token_address
            ORDER BY kol_count DESC
            LIMIT 1
        ''')

    if not recent_token:
        print("   ❌ No recent KOL activity in last hour")
        return

    token_address = recent_token['token_address']
    kol_count = recent_token['kol_count']
    print(f"   ✅ Found token: {token_address}")
    print(f"      KOLs who bought: {kol_count}")

    # Check if it's being tracked
    print("\n3. Checking if token is in active tracker...")
    is_tracked = active_tracker.is_tracked(token_address)
    print(f"   {'✅' if is_tracked else '❌'} Tracked: {is_tracked}")

    if not is_tracked:
        print("\n   🔧 Starting tracking for this token...")
        try:
            await active_tracker.start_tracking(token_address)
            print("   ✅ Tracking started successfully")
        except Exception as e:
            print(f"   ❌ Failed to start tracking: {e}")
            import traceback
            traceback.print_exc()
            return

    # Try to poll the token
    print("\n4. Attempting to poll token (check conviction)...")
    try:
        await active_tracker.smart_poll_token(token_address)
        print("   ✅ Poll completed (check above for conviction score)")
    except Exception as e:
        print(f"   ❌ Poll failed: {e}")
        import traceback
        traceback.print_exc()

    # Check if signal was created
    print("\n5. Checking if signal was created in database...")
    async with db.pool.acquire() as conn:
        signal = await conn.fetchrow('''
            SELECT conviction_score, signal_posted, created_at
            FROM signals
            WHERE token_address = $1
            ORDER BY created_at DESC
            LIMIT 1
        ''', token_address)

    if signal:
        print(f"   ✅ Signal exists!")
        print(f"      Conviction: {signal['conviction_score']}")
        print(f"      Posted: {signal['signal_posted']}")
        print(f"      Created: {signal['created_at']}")
    else:
        print(f"   ❌ NO SIGNAL created for this token")
        print(f"      This means:")
        print(f"      - Conviction score < {config.MIN_CONVICTION_SCORE} (threshold)")
        print(f"      - OR conviction engine failed to calculate score")
        print(f"      - OR smart_poll_token not being called")

    # Get active tokens count
    print("\n6. Active tracker stats...")
    active_tokens = active_tracker.get_active_tokens()
    print(f"   Currently tracking: {len(active_tokens)} tokens")
    stats = active_tracker.get_stats()
    print(f"   Signals sent today: {stats.get('signals_sent_total', 0)}")
    print(f"   Tokens tracked (lifetime): {stats.get('tokens_tracked_total', 0)}")

    await db.close()
    print("\n" + "=" * 80)
    print("Diagnostic complete.")

if __name__ == "__main__":
    asyncio.run(diagnose())
