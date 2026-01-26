"""
Diagnostic script to check why signals aren't posting
"""
import asyncio
import os
from database import Database
from datetime import datetime, timedelta

async def diagnose():
    db = Database()
    await db.connect()

    print("=" * 80)
    print("🔍 SIGNAL FLOW DIAGNOSTICS")
    print("=" * 80)

    # Check recent signals
    async with db.pool.acquire() as conn:
        # Check all signals in last 24 hours
        all_signals = await conn.fetch('''
            SELECT token_name, token_symbol, conviction_score, signal_posted,
                   posting_failed, posting_error, created_at
            FROM signals
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
        ''')

        print(f"\n📊 SIGNALS IN LAST 24 HOURS: {len(all_signals)}")
        print("-" * 80)

        posted = sum(1 for s in all_signals if s['signal_posted'])
        failed = sum(1 for s in all_signals if s['posting_failed'])
        pending = len(all_signals) - posted - failed

        print(f"✅ Posted:  {posted}")
        print(f"❌ Failed:  {failed}")
        print(f"⏳ Pending: {pending}")

        if all_signals:
            print("\n📝 Recent Signals:")
            for s in all_signals[:10]:
                status = "✅ POSTED" if s['signal_posted'] else ("❌ FAILED" if s['posting_failed'] else "⏳ PENDING")
                print(f"  {status} | {s['token_symbol']:10} | Conv: {s['conviction_score']:3} | {s['created_at']}")
                if s['posting_error']:
                    print(f"    Error: {s['posting_error']}")

        # Check for high conviction signals that weren't posted
        print("\n\n🔥 HIGH CONVICTION SIGNALS NOT POSTED:")
        print("-" * 80)
        high_conv = await conn.fetch('''
            SELECT token_name, token_symbol, conviction_score, posting_failed,
                   posting_error, created_at
            FROM signals
            WHERE conviction_score >= 50
            AND signal_posted = FALSE
            ORDER BY conviction_score DESC, created_at DESC
            LIMIT 10
        ''')

        if high_conv:
            for s in high_conv:
                print(f"❌ {s['token_symbol']:10} | Conv: {s['conviction_score']:3} | {s['created_at']}")
                if s['posting_error']:
                    print(f"   Error: {s['posting_error']}")
        else:
            print("  ✅ All high conviction signals have been posted!")

        # Search for shrimp
        print("\n\n🦐 SEARCHING FOR 'SHRIMP' TOKENS:")
        print("-" * 80)
        shrimp = await conn.fetch('''
            SELECT token_name, token_symbol, conviction_score, outcome, max_roi,
                   signal_posted, created_at, token_address
            FROM signals
            WHERE LOWER(token_name) LIKE '%shrimp%'
               OR LOWER(token_symbol) LIKE '%shrimp%'
            ORDER BY created_at DESC
        ''')

        if shrimp:
            for s in shrimp:
                posted = "✅" if s['signal_posted'] else "❌"
                outcome = s['outcome'] or "pending"
                roi = s['max_roi'] or 0
                print(f"{posted} {s['token_symbol']:10} | {s['token_name']:20}")
                print(f"   Conv: {s['conviction_score']:3} | Outcome: {outcome:8} | ROI: {roi:.1f}x")
                print(f"   Address: {s['token_address']}")
                print(f"   Created: {s['created_at']}")
        else:
            print("❌ No 'shrimp' tokens found in database")
            print("\n💡 POSSIBLE REASONS:")
            print("  1. Token wasn't bought by any tracked KOL wallets")
            print("  2. Conviction score was below threshold (< 50)")
            print("  3. Token failed rug detection checks")
            print("  4. System wasn't running when the trade happened")
            print("\n📝 NOTE: Prometheus only tracks tokens that:")
            print("  - Are bought by tracked KOL wallets (Helius webhook)")
            print("  - OR mentioned in Telegram groups (if enabled)")
            print("  - AND meet minimum conviction threshold")

    await db.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(diagnose())
