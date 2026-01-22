"""
Quick Diagnostic Check - Why No Signals?
Run this to debug your SENTINEL setup
"""
import os
import asyncio
import aiohttp
from loguru import logger

async def check_system():
    """Check all critical system components"""

    print("\n" + "="*70)
    print("SENTINEL DIAGNOSTIC CHECK")
    print("="*70 + "\n")

    issues = []
    warnings = []

    # 1. Check environment variables
    print("1️⃣  CHECKING ENVIRONMENT VARIABLES...")

    helius_key = os.getenv('HELIUS_API_KEY')
    db_url = os.getenv('DATABASE_URL')
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_channel = os.getenv('TELEGRAM_CHANNEL_ID')
    twitter_token = os.getenv('TWITTER_BEARER_TOKEN')

    if not helius_key:
        issues.append("❌ HELIUS_API_KEY not set - NO WEBHOOKS WILL WORK!")
    else:
        print(f"   ✅ HELIUS_API_KEY: {helius_key[:10]}...")

    if not db_url:
        warnings.append("⚠️  DATABASE_URL not set - signals won't be saved")
    else:
        print(f"   ✅ DATABASE_URL: Set")

    if not telegram_token or not telegram_channel:
        issues.append("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set - NO SIGNALS WILL BE SENT!")
    else:
        print(f"   ✅ Telegram configured: {telegram_channel}")

    if not twitter_token:
        warnings.append("⚠️  TWITTER_BEARER_TOKEN not set - no Twitter bonus")
    else:
        print(f"   ✅ TWITTER_BEARER_TOKEN: Set")

    print()

    # 2. Check Helius webhooks
    print("2️⃣  CHECKING HELIUS WEBHOOKS...")

    if helius_key:
        try:
            url = f"https://api.helius.xyz/v0/webhooks?api-key={helius_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        webhooks = await resp.json()

                        if not webhooks:
                            issues.append("❌ NO HELIUS WEBHOOKS CONFIGURED - You won't receive KOL buy alerts!")
                            print("   ❌ No webhooks found")
                        else:
                            print(f"   ✅ Found {len(webhooks)} webhook(s)")

                            # Check if any are for smart wallets
                            smart_wallet_webhooks = [w for w in webhooks if 'smart-wallet' in w.get('webhookURL', '')]

                            if not smart_wallet_webhooks:
                                issues.append("❌ No smart wallet webhooks - check webhook URL contains '/webhook/smart-wallet'")
                            else:
                                print(f"   ✅ Smart wallet webhooks: {len(smart_wallet_webhooks)}")
                                for webhook in smart_wallet_webhooks:
                                    print(f"      - {webhook.get('webhookURL', 'unknown')}")
                                    print(f"        Addresses: {len(webhook.get('accountAddresses', []))}")
                    else:
                        issues.append(f"❌ Helius API error: {resp.status}")
        except Exception as e:
            issues.append(f"❌ Failed to check Helius webhooks: {e}")

    print()

    # 3. Check config.py settings
    print("3️⃣  CHECKING CONFIG.PY SETTINGS...")

    try:
        import config

        print(f"   STRICT_KOL_ONLY_MODE: {config.STRICT_KOL_ONLY_MODE}")
        print(f"   DISABLE_PUMPPORTAL: {config.DISABLE_PUMPPORTAL}")
        print(f"   MIN_CONVICTION_SCORE: {config.MIN_CONVICTION_SCORE}")
        print(f"   POST_GRAD_THRESHOLD: {config.POST_GRAD_THRESHOLD}")
        print(f"   ENABLE_TWITTER: {config.ENABLE_TWITTER}")

        if config.MIN_CONVICTION_SCORE > 85:
            warnings.append(f"⚠️  MIN_CONVICTION_SCORE very high ({config.MIN_CONVICTION_SCORE}) - you might miss signals")

        print(f"\n   Smart wallets tracked: {len(config.SMART_WALLETS)}")
        if len(config.SMART_WALLETS) < 5:
            warnings.append(f"⚠️  Only {len(config.SMART_WALLETS)} smart wallets - add more for better coverage")

    except Exception as e:
        issues.append(f"❌ Failed to load config.py: {e}")

    print()

    # 4. Check if SENTINEL is running
    print("4️⃣  CHECKING IF SENTINEL IS RUNNING...")

    railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN') or os.getenv('RAILWAY_STATIC_URL')

    if railway_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://{railway_url}/health", timeout=5) as resp:
                    if resp.status == 200:
                        print(f"   ✅ SENTINEL is running: https://{railway_url}")
                    else:
                        issues.append(f"❌ SENTINEL returned {resp.status}")
        except Exception as e:
            issues.append(f"❌ SENTINEL not responding: {e}")
    else:
        warnings.append("⚠️  Can't detect Railway URL - check manually")

    print()

    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70 + "\n")

    if issues:
        print("🚨 CRITICAL ISSUES (Fix these NOW):\n")
        for issue in issues:
            print(f"   {issue}")
        print()

    if warnings:
        print("⚠️  WARNINGS (Should fix but not critical):\n")
        for warning in warnings:
            print(f"   {warning}")
        print()

    if not issues and not warnings:
        print("✅ ALL CHECKS PASSED!\n")
        print("If you're still not getting signals, check:")
        print("  1. Are KOLs actually trading today?")
        print("  2. Check Railway logs for errors")
        print("  3. Test webhook manually (see below)")

    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70 + "\n")

    if issues:
        print("🔧 TO FIX ISSUES:")
        print("\n1. Set missing environment variables in Railway:")
        print("   - Go to your Railway project → Variables")
        print("   - Add the missing variables listed above")
        print("\n2. If no Helius webhooks configured:")
        print("   - Go to https://dashboard.helius.dev/")
        print("   - Create webhook for your KOL wallet addresses")
        print(f"   - Webhook URL: https://YOUR-RAILWAY-URL/webhook/smart-wallet")
        print("\n3. Redeploy SENTINEL after fixing")
    else:
        print("✅ System looks good!")
        print("\n📊 TO CHECK ACTIVITY:")
        print("   - View Railway logs")
        print("   - Look for: '🎯 KOL bought' messages")
        print("   - Look for: '🚀 SIGNAL' messages")
        print("\n🧪 TO TEST MANUALLY:")
        print("   - Send test webhook (creates fake KOL buy)")
        print("   - Watch logs for signal generation")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(check_system())
