#!/usr/bin/env python3
"""
Check Database Signal Count and Export Data for ML Training

Run this on Railway to see if we have enough signals to train ML models.
"""
import asyncio
import asyncpg
import os
import json
import csv
from datetime import datetime

async def main():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ DATABASE_URL not set")
        return

    print("=" * 80)
    print("🔍 DATABASE SIGNAL ANALYSIS")
    print("=" * 80)

    # Connect
    conn = await asyncpg.connect(database_url)

    try:
        # Total signals
        total_signals = await conn.fetchval(
            "SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE"
        )
        print(f"\n📊 Total Signals Posted: {total_signals}")

        # Signals by date
        by_date = await conn.fetch("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM signals
            WHERE signal_posted = TRUE
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 10
        """)

        print(f"\n📅 Signals by Date (last 10 days):")
        for row in by_date:
            print(f"   {row['date']}: {row['count']} signals")

        # Conviction score distribution
        score_dist = await conn.fetch("""
            SELECT
                conviction_score,
                COUNT(*) as count
            FROM signals
            WHERE signal_posted = TRUE
            GROUP BY conviction_score
            ORDER BY conviction_score DESC
        """)

        print(f"\n💯 Conviction Score Distribution:")
        for row in score_dist:
            print(f"   Score {row['conviction_score']}: {row['count']} signals")

        # Check if we have outcome data
        with_outcomes = await conn.fetchval(
            "SELECT COUNT(*) FROM signals WHERE outcome IS NOT NULL"
        )

        print(f"\n✅ Signals with Outcomes: {with_outcomes}")

        if with_outcomes > 0:
            outcome_dist = await conn.fetch("""
                SELECT outcome, COUNT(*) as count
                FROM signals
                WHERE outcome IS NOT NULL
                GROUP BY outcome
                ORDER BY count DESC
            """)

            print(f"\n📈 Outcome Distribution:")
            for row in outcome_dist:
                print(f"   {row['outcome']}: {row['count']} tokens")

        # Export all signals to JSON for ML training
        if total_signals > 0:
            print(f"\n💾 Exporting signal data for ML training...")

            signals = await conn.fetch("""
                SELECT
                    token_address,
                    token_name,
                    token_symbol,
                    signal_type,
                    bonding_curve_pct,
                    conviction_score,
                    entry_price,
                    current_price,
                    liquidity,
                    volume_24h,
                    market_cap,
                    outcome,
                    outcome_price,
                    max_price_reached,
                    max_roi,
                    narrative_tags,
                    kol_wallets,
                    kol_tiers,
                    holder_pattern,
                    created_at,
                    outcome_timestamp
                FROM signals
                WHERE signal_posted = TRUE
                ORDER BY created_at DESC
            """)

            # Convert to list of dicts
            signal_data = []
            for row in signals:
                signal_dict = dict(row)
                # Convert datetime to ISO string
                if signal_dict.get('created_at'):
                    signal_dict['created_at'] = signal_dict['created_at'].isoformat()
                if signal_dict.get('outcome_timestamp'):
                    signal_dict['outcome_timestamp'] = signal_dict['outcome_timestamp'].isoformat()
                signal_data.append(signal_dict)

            # Save to JSON
            export_file = 'ralph/signals_export.json'
            with open(export_file, 'w') as f:
                json.dump({
                    'exported_at': datetime.utcnow().isoformat(),
                    'total_signals': len(signal_data),
                    'signals_with_outcomes': with_outcomes,
                    'signals': signal_data
                }, f, indent=2)

            print(f"✅ Exported {len(signal_data)} signals to {export_file}")

            # Also save CSV for easy viewing
            csv_file = 'ralph/signals_export.csv'
            with open(csv_file, 'w', newline='') as f:
                if signal_data:
                    writer = csv.DictWriter(f, fieldnames=signal_data[0].keys())
                    writer.writeheader()
                    writer.writerows(signal_data)

            print(f"✅ Also saved to {csv_file} for spreadsheet viewing")

        # Smart wallet activity count
        smart_wallet_count = await conn.fetchval(
            "SELECT COUNT(*) FROM smart_wallet_activity"
        )
        print(f"\n🎯 Smart Wallet Transactions Logged: {smart_wallet_count}")

        # KOL buy count
        kol_buy_count = await conn.fetchval(
            "SELECT COUNT(*) FROM kol_buys"
        )
        print(f"💎 KOL Buy Events Tracked: {kol_buy_count}")

        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)

        if total_signals >= 50 and with_outcomes >= 30:
            print("✅ READY FOR ML TRAINING!")
            print(f"   - {total_signals} total signals")
            print(f"   - {with_outcomes} signals with outcomes")
            print(f"   - Minimum 30 needed, you have enough!")
            print(f"\n🚀 Next step: python ralph/ml_pipeline.py --train")

        elif total_signals >= 50:
            print("⚠️  SIGNALS EXIST BUT NEED OUTCOME LABELING")
            print(f"   - {total_signals} total signals")
            print(f"   - Only {with_outcomes} have outcomes labeled")
            print(f"   - Need to track which ones succeeded/rugged")
            print(f"\n🔧 Next step: Implement outcome tracker")

        elif total_signals > 0:
            print("⏳ COLLECTING DATA - NOT READY YET")
            print(f"   - {total_signals} signals so far")
            print(f"   - Need 50+ for ML training")
            print(f"   - Keep bot running to collect more!")

        else:
            print("❌ NO SIGNALS YET")
            print("   - Database is empty")
            print("   - Is the bot running and posting signals?")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
