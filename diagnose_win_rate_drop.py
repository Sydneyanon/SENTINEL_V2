#!/usr/bin/env python3
"""
Emergency Diagnostic: Win Rate Drop Analysis
Analyzes why win rate dropped from 67% to <50% in last 12-14 hours
"""
import asyncio
import asyncpg
import os
import sys
from datetime import datetime, timedelta

DATABASE_URL = os.getenv('DATABASE_URL', 
    'postgresql://postgres:wCohdopAOCYQLiowDhqHOkHixWnOmbqp@switchyard.proxy.rlwy.net:14667/railway')

async def diagnose():
    print("🔍 CONNECTING TO DATABASE...")
    conn = await asyncpg.connect(DATABASE_URL)
    print("✅ Connected\n")
    
    now = datetime.utcnow()
    cutoff_14h = now - timedelta(hours=14)
    cutoff_24h = now - timedelta(hours=24)
    
    print("=" * 90)
    print("CRITICAL DIAGNOSTIC: WIN RATE DROP ANALYSIS")
    print("=" * 90)
    print(f"Current Time: {now}")
    print(f"Analyzing: Last 24 hours")
    print(f"Comparing: Before vs After {cutoff_14h}")
    print()
    
    # 1. OVERALL PERFORMANCE COMPARISON
    print("=" * 90)
    print("1. OVERALL PERFORMANCE - BEFORE vs AFTER 14 HOURS AGO")
    print("=" * 90)
    
    before = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            COUNT(*) FILTER (WHERE outcome IS NULL OR outcome = '' OR outcome = 'pending') as pending,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate,
            AVG(conviction_score) as avg_conviction,
            COUNT(*) FILTER (WHERE signal_posted = true) as posted,
            COUNT(*) FILTER (WHERE signal_sent = true) as sent
        FROM signals 
        WHERE created_at >= $1 AND created_at < $2
    ''', cutoff_24h, cutoff_14h)
    
    after = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            COUNT(*) FILTER (WHERE outcome IS NULL OR outcome = '' OR outcome = 'pending') as pending,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate,
            AVG(conviction_score) as avg_conviction,
            COUNT(*) FILTER (WHERE signal_posted = true) as posted,
            COUNT(*) FILTER (WHERE signal_sent = true) as sent
        FROM signals 
        WHERE created_at >= $1
    ''', cutoff_14h)
    
    print(f"\n📊 BEFORE (24h-14h ago - GOOD PERIOD):")
    print(f"   Total Signals: {before['total']}")
    print(f"   Wins: {before['wins']} | Losses: {before['losses']} | Pending: {before['pending']}")
    print(f"   WIN RATE: {before['win_rate']}%")
    print(f"   Avg Conviction: {before['avg_conviction']:.2f if before['avg_conviction'] else 0}")
    print(f"   Posted: {before['posted']} | Sent: {before['sent']}")
    
    print(f"\n📊 AFTER (Last 14h - BAD PERIOD):")
    print(f"   Total Signals: {after['total']}")
    print(f"   Wins: {after['wins']} | Losses: {after['losses']} | Pending: {after['pending']}")
    print(f"   WIN RATE: {after['win_rate']}%")
    print(f"   Avg Conviction: {after['avg_conviction']:.2f if after['avg_conviction'] else 0}")
    print(f"   Posted: {after['posted']} | Sent: {after['sent']}")
    
    if before['win_rate'] and after['win_rate']:
        delta = after['win_rate'] - before['win_rate']
        print(f"\n🚨 WIN RATE CHANGE: {delta:+.2f} percentage points")
        if delta < -10:
            print(f"   ⚠️  CRITICAL DROP - Immediate action required!")
    
    # 2. CHECK IF SIGNALS ARE EVEN BEING POSTED
    print("\n" + "=" * 90)
    print("2. SIGNAL POSTING STATUS - Are signals even reaching Telegram?")
    print("=" * 90)
    
    posting_before = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE signal_posted = true) as posted_true,
            COUNT(*) FILTER (WHERE signal_sent = true) as sent_true,
            COUNT(*) FILTER (WHERE signal_posted = false OR signal_sent = false) as not_posted,
            ROUND(100.0 * COUNT(*) FILTER (WHERE signal_posted = true) / NULLIF(COUNT(*), 0), 2) as post_rate
        FROM signals 
        WHERE created_at >= $1 AND created_at < $2
    ''', cutoff_24h, cutoff_14h)
    
    posting_after = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE signal_posted = true) as posted_true,
            COUNT(*) FILTER (WHERE signal_sent = true) as sent_true,
            COUNT(*) FILTER (WHERE signal_posted = false OR signal_sent = false) as not_posted,
            ROUND(100.0 * COUNT(*) FILTER (WHERE signal_posted = true) / NULLIF(COUNT(*), 0), 2) as post_rate
        FROM signals 
        WHERE created_at >= $1
    ''', cutoff_14h)
    
    print(f"\nBEFORE: {posting_before['post_rate']}% posted ({posting_before['posted_true']}/{posting_before['total']})")
    print(f"AFTER:  {posting_after['post_rate']}% posted ({posting_after['posted_true']}/{posting_after['total']})")
    
    if posting_after['post_rate'] < posting_before['post_rate']:
        print(f"\n🚨 POSTING RATE DROPPED BY {posting_before['post_rate'] - posting_after['post_rate']:.2f}%")
        print("   Possible cause: Telegram posting failures or threshold changes")
    
    # 3. CONVICTION SCORE ANALYSIS
    print("\n" + "=" * 90)
    print("3. CONVICTION SCORE DISTRIBUTION - Did filtering change?")
    print("=" * 90)
    
    print("\n📊 BEFORE (24h-14h ago):")
    conv_before = await conn.fetch('''
        SELECT 
            CASE 
                WHEN conviction_score >= 80 THEN '80-100'
                WHEN conviction_score >= 60 THEN '60-79'
                WHEN conviction_score >= 45 THEN '45-59'
                WHEN conviction_score >= 30 THEN '30-44'
                ELSE '0-29'
            END as range,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate
        FROM signals 
        WHERE created_at >= $1 AND created_at < $2
        GROUP BY range
        ORDER BY range DESC
    ''', cutoff_24h, cutoff_14h)
    
    for row in conv_before:
        print(f"   {row['range']}: {row['count']:3d} signals | W:{row['wins']:3d} L:{row['losses']:3d} | WR: {row['win_rate']}%")
    
    print("\n📊 AFTER (Last 14h):")
    conv_after = await conn.fetch('''
        SELECT 
            CASE 
                WHEN conviction_score >= 80 THEN '80-100'
                WHEN conviction_score >= 60 THEN '60-79'
                WHEN conviction_score >= 45 THEN '45-59'
                WHEN conviction_score >= 30 THEN '30-44'
                ELSE '0-29'
            END as range,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate
        FROM signals 
        WHERE created_at >= $1
        GROUP BY range
        ORDER BY range DESC
    ''', cutoff_14h)
    
    for row in conv_after:
        print(f"   {row['range']}: {row['count']:3d} signals | W:{row['wins']:3d} L:{row['losses']:3d} | WR: {row['win_rate']}%")
    
    # 4. KOL TIER ANALYSIS
    print("\n" + "=" * 90)
    print("4. KOL TIER PERFORMANCE - Which tiers are failing?")
    print("=" * 90)
    
    print("\n📊 BEFORE:")
    kol_before = await conn.fetch('''
        SELECT 
            COALESCE(kol_tier, 'None') as tier,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate
        FROM signals 
        WHERE created_at >= $1 AND created_at < $2
        GROUP BY tier
        ORDER BY tier
    ''', cutoff_24h, cutoff_14h)
    
    for row in kol_before:
        print(f"   Tier {row['tier']:4s}: {row['count']:3d} signals | W:{row['wins']:3d} L:{row['losses']:3d} | WR: {row['win_rate']}%")
    
    print("\n📊 AFTER:")
    kol_after = await conn.fetch('''
        SELECT 
            COALESCE(kol_tier, 'None') as tier,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate
        FROM signals 
        WHERE created_at >= $1
        GROUP BY tier
        ORDER BY tier
    ''', cutoff_14h)
    
    for row in kol_after:
        print(f"   Tier {row['tier']:4s}: {row['count']:3d} signals | W:{row['wins']:3d} L:{row['losses']:3d} | WR: {row['win_rate']}%")
    
    # 5. TOP FAILING TOKENS
    print("\n" + "=" * 90)
    print("5. TOP FAILING TOKENS (Last 14h) - What's losing?")
    print("=" * 90)
    
    failing = await conn.fetch('''
        SELECT 
            token_address,
            token_symbol,
            COUNT(*) as signals,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            MAX(conviction_score) as max_conv,
            MAX(kol_tier) as kol_tier
        FROM signals 
        WHERE created_at >= $1 AND outcome = 'loss'
        GROUP BY token_address, token_symbol
        ORDER BY losses DESC
        LIMIT 15
    ''', cutoff_14h)
    
    for i, row in enumerate(failing, 1):
        print(f"{i:2d}. {row['token_symbol'] or 'Unknown':15s} | Losses: {row['losses']} | Conv: {row['max_conv']:.1f} | Tier: {row['kol_tier']}")
        print(f"    {row['token_address']}")
    
    # 6. HOURLY BREAKDOWN
    print("\n" + "=" * 90)
    print("6. HOURLY BREAKDOWN - When did it break?")
    print("=" * 90)
    
    hourly = await conn.fetch('''
        SELECT 
            date_trunc('hour', created_at) as hour,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE outcome = 'win') as wins,
            COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
            ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / 
                NULLIF(COUNT(*) FILTER (WHERE outcome IN ('win', 'loss')), 0), 2) as win_rate,
            AVG(conviction_score) as avg_conv
        FROM signals 
        WHERE created_at >= $1
        GROUP BY hour
        ORDER BY hour DESC
    ''', cutoff_24h)
    
    print()
    for row in hourly:
        marker = "🔴" if row['win_rate'] and row['win_rate'] < 50 else "🟢" if row['win_rate'] and row['win_rate'] >= 60 else "🟡"
        wr = row['win_rate'] if row['win_rate'] else 0
        conv = row['avg_conv'] if row['avg_conv'] else 0
        print(f"{marker} {row['hour']}: {row['total']:3d} signals | W:{row['wins']:3d} L:{row['losses']:3d} | WR:{wr:5.1f}% | Conv:{conv:5.1f}")
    
    # 7. SAMPLE RECENT LOSSES
    print("\n" + "=" * 90)
    print("7. SAMPLE RECENT LOSSES - What went wrong?")
    print("=" * 90)
    
    recent_losses = await conn.fetch('''
        SELECT 
            created_at,
            token_symbol,
            token_address,
            conviction_score,
            kol_tier,
            signal_posted,
            wallet_address
        FROM signals 
        WHERE outcome = 'loss' AND created_at >= $1
        ORDER BY created_at DESC
        LIMIT 15
    ''', cutoff_14h)
    
    print()
    for loss in recent_losses:
        print(f"• {loss['created_at']}")
        print(f"  Token: {loss['token_symbol']} | Conv: {loss['conviction_score']:.1f} | Tier: {loss['kol_tier']} | Posted: {loss['signal_posted']}")
        print(f"  Wallet: {loss['wallet_address'][:12]}...")
        print(f"  Address: {loss['token_address']}")
    
    # 8. CHECK FOR SYSTEM CHANGES
    print("\n" + "=" * 90)
    print("8. POSSIBLE ROOT CAUSES")
    print("=" * 90)
    
    print("\nAnalyzing possible causes:")
    
    # Check if conviction threshold changed
    min_conv_before = await conn.fetchval('SELECT MIN(conviction_score) FROM signals WHERE created_at >= $1 AND created_at < $2 AND signal_posted = true', cutoff_24h, cutoff_14h)
    min_conv_after = await conn.fetchval('SELECT MIN(conviction_score) FROM signals WHERE created_at >= $1 AND signal_posted = true', cutoff_14h)
    
    print(f"\n✓ Conviction threshold check:")
    print(f"  Before: Min conviction posted = {min_conv_before:.1f if min_conv_before else 0}")
    print(f"  After:  Min conviction posted = {min_conv_after:.1f if min_conv_after else 0}")
    if min_conv_after and min_conv_before and min_conv_after < min_conv_before - 5:
        print(f"  🚨 THRESHOLD LOWERED - More low-quality signals getting through!")
    
    # Check if volume of signals changed dramatically
    if after['total'] > before['total'] * 1.5:
        print(f"\n✓ Signal volume:")
        print(f"  🚨 VOLUME SPIKE: {after['total']} signals (was {before['total']})")
        print(f"  Possible cause: Threshold lowered or new wallets added")
    
    # Check for bad wallet influx
    new_wallets = await conn.fetchval('''
        SELECT COUNT(DISTINCT wallet_address)
        FROM signals
        WHERE created_at >= $1
        AND wallet_address NOT IN (
            SELECT DISTINCT wallet_address
            FROM signals
            WHERE created_at >= $2 AND created_at < $1
        )
    ''', cutoff_14h, cutoff_24h)
    
    if new_wallets > 10:
        print(f"\n✓ New wallets:")
        print(f"  🚨 {new_wallets} NEW WALLETS added in last 14h")
        print(f"  Possible cause: Auto-discovery added bad wallets")
    
    await conn.close()
    
    print("\n" + "=" * 90)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 90)
    print("\nNext steps:")
    print("1. If conviction threshold dropped: Raise MIN_CONVICTION_SCORE")
    print("2. If bad wallets were added: Check wallet_autodiscovery.py blacklist")
    print("3. If posting rate dropped: Check Telegram API connectivity")
    print("4. If specific tokens failing: Add to token blacklist")
    print("5. Check recent code deploys for bugs")
    print()

if __name__ == '__main__':
    try:
        asyncio.run(diagnose())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
