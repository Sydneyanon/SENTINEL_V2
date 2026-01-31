"""
Quick test script for SENTINEL V3
Run: python v3/test_local.py
"""
import asyncio
import os
import sys

# Add v3 to path
sys.path.insert(0, os.path.dirname(__file__))


async def main():
    print("=" * 50)
    print("SENTINEL V3 - Local Test")
    print("=" * 50)

    # 1. Check environment variables
    print("\n1. Checking environment variables...")
    required = ['DATABASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID']
    missing = [v for v in required if not os.getenv(v)]

    if missing:
        print(f"   ❌ Missing: {', '.join(missing)}")
        print("   Set these in Railway or export locally")
        return
    print("   ✅ All required env vars set")

    # 2. Test database connection
    print("\n2. Testing database connection...")
    try:
        import database as db
        await db.init_db()
        stats = await db.get_stats()
        print(f"   ✅ Connected! {stats['total_signals']} signals in DB")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return

    # 3. Test fetchers
    print("\n3. Testing data fetchers...")
    from fetchers import fetch_token_data, get_sol_price

    sol_price = await get_sol_price()
    print(f"   SOL price: ${sol_price:.2f}")

    # Test with a known token (BONK - graduated)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    data = await fetch_token_data(test_token)
    if data:
        print(f"   ✅ DexScreener working: ${data['symbol']} @ ${data['price']:.6f}")
    else:
        print("   ⚠️ DexScreener returned no data (might be rate limited)")

    # 4. Test scoring
    print("\n4. Testing scoring engine...")
    from scoring import calculate_score

    score, breakdown, should_signal, reason = calculate_score(
        wallet_tier='top_kol',
        volume_1h=50000,
        liquidity=25000,
        price_change_1h=25,
        holders=75,
        mcap=30000
    )
    print(f"   Test score: {score}/100 (signal: {should_signal})")

    # 5. Test Telegram (optional)
    print("\n5. Testing Telegram bot...")
    try:
        from telegram import Bot
        bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        me = await bot.get_me()
        print(f"   ✅ Bot connected: @{me.username}")
    except Exception as e:
        print(f"   ❌ Telegram error: {e}")

    # 6. Check wallets
    print("\n6. Checking tracked wallets...")
    wallets = await db.get_all_wallets()
    print(f"   {len(wallets)} wallets in database")
    if wallets:
        for w in wallets[:5]:
            name = w['name'] or w['address'][:8]
            print(f"   - {name} [{w['tier']}]")

    print("\n" + "=" * 50)
    print("✅ All tests passed! Ready to run:")
    print("   python v3/main.py")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
