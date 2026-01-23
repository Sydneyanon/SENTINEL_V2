#!/usr/bin/env python3
"""
Prometheus Wallet Management CLI
Easy command-line tool for discovering and managing KOL wallets
"""
import asyncio
import sys
from loguru import logger
from wallet_autodiscovery import WalletAutoDiscovery, discover_top_traders, auto_discover_wallets
import config


async def cmd_discover(args):
    """Discover top traders from gmgn.ai"""
    limit = int(args[0]) if args else 20
    
    print(f"\n🔍 Discovering top {limit} traders from gmgn.ai...\n")
    
    traders = await discover_top_traders(limit)
    
    if not traders:
        print("❌ No traders found. Check your internet connection.")
        return
    
    print(f"✅ Found {len(traders)} elite traders:\n")
    print("=" * 80)
    
    for i, trader in enumerate(traders, 1):
        tier_emoji = "🏆" if trader['tier'] == 'elite' else "👑" if trader['tier'] == 'top_kol' else "✅"
        
        print(f"{i}. {tier_emoji} {trader['name']} ({trader['tier'].upper()})")
        print(f"   Address: {trader['address']}")
        print(f"   Win Rate: {trader['win_rate']*100:.1f}%")
        print(f"   Profit: ${trader['total_profit']:,.0f}")
        print(f"   Specialty: {trader.get('specialty', 'General')}")
        print()
    
    print("=" * 80)
    print("\n💡 To add these to your config:")
    print("   1. Copy addresses you want")
    print("   2. Add to config.py SMART_WALLETS list")
    print("   3. Or run: python wallet_cli.py export > wallets.txt\n")


async def cmd_check(args):
    """Check metadata for a specific wallet"""
    if not args:
        print("❌ Usage: python wallet_cli.py check <wallet_address>")
        return
    
    address = args[0]
    
    print(f"\n🔍 Checking wallet: {address[:8]}...\n")
    
    async with WalletAutoDiscovery() as discovery:
        metadata = await discovery.discover_wallet(address)
    
    if not metadata:
        print("❌ Failed to discover wallet metadata")
        return
    
    print("✅ Wallet Metadata:\n")
    print("=" * 60)
    for key, value in metadata.items():
        if key == 'win_rate':
            print(f"  {key:15}: {value*100:.1f}%")
        elif key == 'total_profit':
            print(f"  {key:15}: ${value:,.0f}")
        else:
            print(f"  {key:15}: {value}")
    print("=" * 60)


async def cmd_enrich(args):
    """Enrich current SMART_WALLETS with metadata"""
    print("\n🔄 Enriching SMART_WALLETS with metadata...\n")
    
    if not config.SMART_WALLETS:
        print("❌ SMART_WALLETS is empty in config.py")
        return
    
    # Check format
    first = config.SMART_WALLETS[0]
    
    if isinstance(first, str):
        print(f"📝 Simple format detected: {len(config.SMART_WALLETS)} addresses")
        addresses = config.SMART_WALLETS
    elif isinstance(first, dict):
        print(f"📊 Detailed format detected: {len(config.SMART_WALLETS)} wallets")
        addresses = [w['address'] for w in config.SMART_WALLETS if 'address' in w]
    else:
        print(f"❌ Unknown format: {type(first)}")
        return
    
    print(f"🔍 Discovering metadata for {len(addresses)} wallets...\n")
    
    metadata = await auto_discover_wallets(addresses)
    
    print(f"✅ Enriched {len(metadata)} wallets:\n")
    print("=" * 80)
    
    for addr, data in metadata.items():
        tier_emoji = "🏆" if data['tier'] == 'elite' else "👑" if data['tier'] == 'top_kol' else "✅"
        print(f"{tier_emoji} {data['name']} ({data['tier'].upper()})")
        print(f"   Address: {addr}")
        print(f"   Win Rate: {data['win_rate']*100:.1f}%")
        print(f"   Source: {data.get('source', 'unknown')}")
        print()
    
    print("=" * 80)


async def cmd_export(args):
    """Export current config to Python format"""
    print("\n# Copy this to your config.py:\n")
    print("SMART_WALLETS = [")
    
    traders = await discover_top_traders(20)
    
    for trader in traders:
        print("    {")
        print(f"        'address': '{trader['address']}',")
        print(f"        'name': '{trader['name']}',")
        print(f"        'tier': '{trader['tier']}',")
        print(f"        'win_rate': {trader['win_rate']:.3f},")
        print(f"        'source': 'gmgn.ai',")
        print(f"        'active': True")
        print("    },")
    
    print("]")


async def cmd_helius(args):
    """Generate Helius webhook command"""
    print("\n📋 Helius Webhook Setup:\n")
    
    if not config.SMART_WALLETS:
        print("❌ SMART_WALLETS is empty")
        return
    
    # Get addresses
    first = config.SMART_WALLETS[0]
    if isinstance(first, str):
        addresses = config.SMART_WALLETS
    elif isinstance(first, dict):
        addresses = [w['address'] for w in config.SMART_WALLETS if 'address' in w]
    else:
        print("❌ Unknown format")
        return
    
    print(f"✅ {len(addresses)} wallets configured\n")
    print("📝 Add these addresses to your Helius webhook:\n")
    print("1. Go to: https://dashboard.helius.dev")
    print("2. Create webhook → Enhanced type")
    print("3. Add these addresses:")
    print()
    
    for addr in addresses:
        print(f"  {addr}")
    
    print(f"\n4. Set webhook URL: https://your-app.railway.app/webhook/smart-wallet")
    print("5. Enable transaction types: SWAP, TRANSFER")
    print("\n✅ Done!")


async def cmd_status(args):
    """Show current wallet configuration status"""
    print("\n📊 PROMETHEUS WALLET STATUS\n")
    print("=" * 60)
    
    if not config.SMART_WALLETS:
        print("❌ No wallets configured")
        print("\n💡 Run: python wallet_cli.py discover")
        print("=" * 60)
        return
    
    # Check format
    first = config.SMART_WALLETS[0]
    
    if isinstance(first, str):
        print(f"📝 Format: Simple (addresses only)")
        print(f"📊 Count: {len(config.SMART_WALLETS)} wallets")
        print(f"⚠️  No metadata - run 'enrich' to add")
    elif isinstance(first, dict):
        print(f"📝 Format: Detailed (with metadata)")
        print(f"📊 Count: {len(config.SMART_WALLETS)} wallets\n")
        
        # Count tiers
        tiers = {}
        active = 0
        for wallet in config.SMART_WALLETS:
            tier = wallet.get('tier', 'unknown')
            tiers[tier] = tiers.get(tier, 0) + 1
            if wallet.get('active', True):
                active += 1
        
        print("Tier Breakdown:")
        for tier, count in sorted(tiers.items(), key=lambda x: x[1], reverse=True):
            emoji = "🏆" if tier == 'elite' else "👑" if tier == 'top_kol' else "✅"
            print(f"  {emoji} {tier.capitalize()}: {count}")
        
        print(f"\n✅ Active: {active}")
        print(f"⏸️  Inactive: {len(config.SMART_WALLETS) - active}")
    
    print("=" * 60)


def print_help():
    """Print help message"""
    print("""
🔥 PROMETHEUS WALLET MANAGEMENT CLI

COMMANDS:

  discover [limit]     Discover top traders from gmgn.ai (default: 20)
                       Example: python wallet_cli.py discover 50

  check <address>      Check metadata for a specific wallet
                       Example: python wallet_cli.py check 7xKXtg2...

  enrich               Enrich current SMART_WALLETS with metadata
                       Example: python wallet_cli.py enrich

  export               Export top traders in Python format for config.py
                       Example: python wallet_cli.py export > config_wallets.txt

  helius               Show Helius webhook setup instructions
                       Example: python wallet_cli.py helius

  status               Show current wallet configuration status
                       Example: python wallet_cli.py status

  help                 Show this help message

EXAMPLES:

  # Discover top 20 traders
  python wallet_cli.py discover

  # Check a specific wallet
  python wallet_cli.py check 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU

  # Export to config format
  python wallet_cli.py export >> config.py

  # Show current status
  python wallet_cli.py status

💡 TIP: Start with 'discover' to find elite traders!
""")


async def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    args = sys.argv[2:]
    
    commands = {
        'discover': cmd_discover,
        'check': cmd_check,
        'enrich': cmd_enrich,
        'export': cmd_export,
        'helius': cmd_helius,
        'status': cmd_status,
        'help': lambda _: print_help()
    }
    
    if command in commands:
        await commands[command](args)
    else:
        print(f"❌ Unknown command: {command}")
        print_help()


if __name__ == "__main__":
    # Configure minimal logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<level>{message}</level>",
        level="WARNING"
    )
    
    asyncio.run(main())
