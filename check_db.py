"""
Quick script to check Railway database for KOL metadata
"""
import asyncpg
import asyncio

async def check_database():
    # Railway external connection
    DATABASE_URL = "postgresql://postgres:wCohdopAOCYQLiowDhqHOkHixWnOmbqp@switchyard.proxy.rlwy.net:14667/railway"

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to Railway database!\n")

        # Check tables
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        print("📊 Tables in database:")
        for table in tables:
            print(f"   - {table['table_name']}")

        print("\n" + "="*60)

        # Check smart_wallet_activity schema
        print("\n📋 smart_wallet_activity table schema:")
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'smart_wallet_activity'
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"   {col['column_name']}: {col['data_type']}")

        print("\n" + "="*60)

        # Check recent smart wallet activity
        print("\n🔍 Recent smart wallet activity (last 10):")
        recent = await conn.fetch("""
            SELECT wallet_name, wallet_tier, token_address,
                   transaction_type, amount, timestamp
            FROM smart_wallet_activity
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        if recent:
            for row in recent:
                print(f"\n   KOL: {row['wallet_name']} ({row['wallet_tier']})")
                print(f"   Token: {row['token_address'][:8]}...")
                print(f"   Type: {row['transaction_type']} | Amount: {row['amount']} SOL")
                print(f"   Time: {row['timestamp']}")
        else:
            print("   ⚠️ No smart wallet activity found!")

        print("\n" + "="*60)

        # Check kol_buys table
        print("\n💎 Recent KOL buys (last 10):")
        kol_buys = await conn.fetch("""
            SELECT * FROM kol_buys
            ORDER BY detected_at DESC
            LIMIT 10
        """)

        if kol_buys:
            for row in kol_buys:
                print(f"\n   Wallet: {row['kol_wallet'][:8]}...")
                print(f"   Token: {row['token_address'][:8]}...")
                print(f"   Amount: {row['amount_sol']} SOL")
                print(f"   Time: {row['detected_at']}")
        else:
            print("   ⚠️ No KOL buys found!")

        print("\n" + "="*60)

        # Count total records
        smart_count = await conn.fetchval("SELECT COUNT(*) FROM smart_wallet_activity")
        kol_count = await conn.fetchval("SELECT COUNT(*) FROM kol_buys")
        signals_count = await conn.fetchval("SELECT COUNT(*) FROM signals")

        print(f"\n📈 Database stats:")
        print(f"   - Smart wallet activities: {smart_count}")
        print(f"   - KOL buys: {kol_count}")
        print(f"   - Signals: {signals_count}")

        await conn.close()
        print("\n✅ Database check complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())
