"""
Admin script to check Railway DB - run this ON Railway
Usage: python admin_check_db.py
"""
import asyncio
from database import Database
from loguru import logger

async def main():
    db = Database()
    await db.connect()

    print("\n" + "="*70)
    print("📊 RAILWAY DATABASE CHECK")
    print("="*70)

    # Check smart wallet activity
    print("\n🔍 Recent Smart Wallet Activity (last 10):")
    print("-" * 70)

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT wallet_name, wallet_tier, token_address,
                   amount, timestamp
            FROM smart_wallet_activity
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        if rows:
            for row in rows:
                print(f"\n👑 KOL: {row['wallet_name']} ({row['wallet_tier']})")
                print(f"   Token: {row['token_address'][:12]}...")
                print(f"   Amount: {row['amount']} SOL")
                print(f"   Time: {row['timestamp']}")
        else:
            print("⚠️ No smart wallet activity found!")

    # Check total counts
    print("\n" + "="*70)
    print("📈 DATABASE STATS:")
    print("-" * 70)

    async with db.pool.acquire() as conn:
        smart_count = await conn.fetchval("SELECT COUNT(*) FROM smart_wallet_activity")
        signals_count = await conn.fetchval("SELECT COUNT(*) FROM signals")
        kol_count = await conn.fetchval("SELECT COUNT(*) FROM kol_buys")

        print(f"Smart Wallet Activities: {smart_count}")
        print(f"KOL Buys (legacy table): {kol_count}")
        print(f"Signals Posted: {signals_count}")

    # Check schema
    print("\n" + "="*70)
    print("📋 SMART_WALLET_ACTIVITY SCHEMA:")
    print("-" * 70)

    async with db.pool.acquire() as conn:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'smart_wallet_activity'
            ORDER BY ordinal_position
        """)

        for col in columns:
            print(f"   {col['column_name']}: {col['data_type']}")

    await db.close()
    print("\n✅ Check complete!\n")

if __name__ == "__main__":
    asyncio.run(main())
