#!/usr/bin/env python3
"""
Test Birdseye API integration
"""
import asyncio
import os
from birdseye_fetcher import BirdseyeFetcher


async def test_birdseye():
    """Test Birdseye API with real pump.fun token"""

    # Get API key from environment
    api_key = os.getenv('BIRDSEYE_API_KEY')

    if not api_key:
        print("❌ BIRDSEYE_API_KEY not set!")
        print("   Add it to your environment or Railway variables")
        return

    print("=" * 70)
    print("🧪 TESTING BIRDSEYE API")
    print("=" * 70)
    print(f"API Key: {api_key[:10]}...")
    print()

    # Initialize fetcher
    fetcher = BirdseyeFetcher(api_key=api_key)

    # Test with a known Solana token (BONK - popular memecoin)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK

    print(f"🎯 Testing with BONK token: {test_token[:8]}...")
    print()

    try:
        # Fetch token data
        print("📡 Fetching token data from Birdseye...")
        data = await fetcher.get_token_data(test_token)

        if data:
            print("✅ SUCCESS! Birdseye API is working!")
            print()
            print("📊 Token Data Received:")
            print("-" * 70)
            print(f"Symbol: {data.get('token_symbol', 'N/A')}")
            print(f"Name: {data.get('token_name', 'N/A')}")
            print(f"Price (USD): ${data.get('price_usd', 0):.8f}")
            print(f"Market Cap: ${data.get('market_cap', 0):,.0f}")
            print(f"Liquidity: ${data.get('liquidity', 0):,.0f}")
            print(f"24h Volume: ${data.get('volume_24h', 0):,.0f}")
            print(f"Holder Count: {data.get('holder_count', 0):,}")
            print(f"Price Change 24h: {data.get('price_change_24h', 0):.2f}%")
            print("-" * 70)
            print()
            print("🎉 Your bot will now use Birdseye for:")
            print("   ✅ Price data")
            print("   ✅ Market cap")
            print("   ✅ Liquidity")
            print("   ✅ Volume")
            print("   ✅ Holder count (FREE!)")
            print()
            print("💡 This means NO MORE Helius credits wasted on holder checks!")

        else:
            print("❌ FAILED - Birdseye returned no data")
            print()
            print("Possible issues:")
            print("   1. API key is invalid")
            print("   2. Token address is wrong")
            print("   3. Birdseye API is down")
            print("   4. Rate limit exceeded")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("🔧 Troubleshooting:")
        print("   1. Check if BIRDSEYE_API_KEY is correct")
        print("   2. Verify you have API credits remaining")
        print("   3. Check Birdseye dashboard: https://birdeye.so/")


if __name__ == "__main__":
    asyncio.run(test_birdseye())
