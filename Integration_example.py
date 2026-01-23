"""
Integration Example - How to wire PumpMonitorV2 with ConvictionEngine
"""
import asyncio
from pump_monitor_v2 import PumpMonitorV2
from conviction_engine import ConvictionEngine
from smart_wallet_tracker import SmartWalletTracker
from active_token_tracker import ActiveTokenTracker
import config


async def on_signal(token_data: dict, signal_type: str):
    """
    Callback function triggered when tokens hit signal thresholds
    
    Args:
        token_data: Token data from PumpPortal
        signal_type: 'NEW_TOKEN', 'PRE_GRADUATION', or 'POST_GRADUATION'
    """
    token_address = token_data.get('token_address')
    symbol = token_data.get('token_symbol', 'UNKNOWN')
    
    print(f"\n{'='*60}")
    print(f"📡 Signal Type: {signal_type}")
    print(f"Token: ${symbol} ({token_address[:8]}...)")
    print(f"{'='*60}")
    
    # Run conviction analysis
    result = await conviction_engine.analyze_token(token_address, token_data)
    
    if result['meets_threshold']:
        print(f"\n🚨 HIGH CONVICTION SIGNAL - POSTING TO TELEGRAM")
        # await post_to_telegram(result)
    else:
        print(f"\n⏭️ Below threshold - no signal posted")


async def main():
    """Main bot loop"""
    
    # Initialize components
    print("🎬 Initializing Sentinel Signals v2...")
    
    # 1. Smart Wallet Tracker (monitors KOL activity via Helius webhooks)
    smart_wallet_tracker = SmartWalletTracker(
        tracked_wallets=config.SMART_WALLETS
    )
    
    # 2. Active Token Tracker (tracks tokens that KOLs bought)
    active_tracker = ActiveTokenTracker()
    
    # 3. Conviction Engine (scores tokens with tiered system)
    global conviction_engine
    conviction_engine = ConvictionEngine(
        smart_wallet_tracker=smart_wallet_tracker,
        helius_client=True  # Enable Helius for post-grad holder checks
    )
    
    # 4. PumpPortal Monitor (monitors bonding curves + unique buyers)
    pump_monitor = PumpMonitorV2(
        on_signal_callback=on_signal,
        active_tracker=active_tracker
    )
    
    print("✅ All components initialized")
    print("\n📊 CREDIT OPTIMIZATION STATUS:")
    print(f"   • Pre-grad distribution: FREE (unique buyers)")
    print(f"   • Post-grad distribution: 10 credits (real holders)")
    print(f"   • Distribution check only if base_score >= 50")
    print(f"   • Expected daily usage: ~25k credits (~750k/month)")
    print(f"   • Free tier limit: 1M/month ✅")
    
    # Start monitoring
    print("\n🚀 Starting monitoring...")
    await pump_monitor.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
