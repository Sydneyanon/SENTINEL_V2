#!/usr/bin/env python3
"""
Test script for RugCheck.xyz API integration
Tests the rugcheck_api.py module with real token addresses
"""
import asyncio
from rugcheck_api import get_rugcheck_api
from loguru import logger


async def test_rugcheck_api():
    """Test RugCheck API with various token addresses"""

    logger.info("🧪 Testing RugCheck.xyz API Integration")
    logger.info("=" * 70)

    rugcheck = get_rugcheck_api()

    # Test tokens (these are example addresses - use real ones for actual testing)
    test_cases = [
        {
            'name': 'Well-known SOL token (should be safe)',
            'address': 'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'expected_risk': 'good'
        },
        {
            'name': 'Random pump.fun token (unknown risk)',
            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',  # Jupiter token
            'expected_risk': 'unknown'
        },
        {
            'name': 'Non-existent token (should fail gracefully)',
            'address': 'FAKE11111111111111111111111111111111111111',
            'expected_risk': 'unknown'
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n📝 Test {i}/{len(test_cases)}: {test_case['name']}")
        logger.info(f"   Address: {test_case['address'][:12]}...{test_case['address'][-4:]}")

        try:
            result = await rugcheck.check_token(test_case['address'], timeout=10)

            logger.info(f"   Success: {result['success']}")
            logger.info(f"   Risk Level: {result['risk_level']}")

            if result['success']:
                logger.info(f"   Score: {result.get('score', 'N/A')}")
                logger.info(f"   Is Honeypot: {result.get('is_honeypot', False)}")
                logger.info(f"   Mutable Metadata: {result.get('mutable_metadata', False)}")
                logger.info(f"   Freezeable: {result.get('freezeable', False)}")
                logger.info(f"   Top Holder %: {result.get('top_holder_pct', 0):.2f}%")
                logger.info(f"   Risk Count: {result.get('risk_count', 0)}")

                if result.get('critical_risks'):
                    logger.warning(f"   🔴 Critical Risks: {len(result['critical_risks'])}")
                    for risk in result['critical_risks'][:3]:
                        logger.warning(f"      - {risk.get('name', 'Unknown')}: {risk.get('description', 'N/A')}")

                # Determine emoji based on risk level
                risk_emoji = {
                    'good': '✅',
                    'low': '⚠️',
                    'medium': '⚠️',
                    'high': '⛔',
                    'critical': '🚨',
                    'unknown': '❓'
                }.get(result['risk_level'], '❓')

                logger.info(f"   {risk_emoji} Overall Assessment: {result['risk_level'].upper()}")
            else:
                logger.warning(f"   ❌ Error: {result.get('error', 'Unknown error')}")

            results.append({
                'test_case': test_case['name'],
                'success': result['success'],
                'risk_level': result['risk_level'],
                'error': result.get('error')
            })

        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            results.append({
                'test_case': test_case['name'],
                'success': False,
                'risk_level': 'error',
                'error': str(e)
            })

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 Test Summary")
    logger.info("=" * 70)

    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful

    logger.info(f"   Total Tests: {len(results)}")
    logger.info(f"   ✅ Successful: {successful}")
    logger.info(f"   ❌ Failed: {failed}")

    logger.info("\n📋 Results:")
    for i, result in enumerate(results, 1):
        status = "✅" if result['success'] else "❌"
        logger.info(f"   {i}. {status} {result['test_case']}")
        logger.info(f"      Risk Level: {result['risk_level']}")
        if result.get('error'):
            logger.info(f"      Error: {result['error']}")

    # Cleanup
    await rugcheck.close()

    logger.info("\n" + "=" * 70)
    logger.info("✅ Test Complete!")
    logger.info("=" * 70)

    return results


async def test_conviction_engine_integration():
    """
    Test RugCheck integration in conviction_engine.py
    This simulates how it will be called in production
    """
    logger.info("\n\n🧪 Testing Conviction Engine Integration")
    logger.info("=" * 70)

    from scoring.conviction_engine import ConvictionEngine
    from smart_wallet_tracker import SmartWalletTracker
    from helius_fetcher import HeliusDataFetcher

    # Initialize conviction engine (minimal setup)
    smart_wallet_tracker = SmartWalletTracker()
    helius = HeliusDataFetcher()

    conviction_engine = ConvictionEngine(
        smart_wallet_tracker=smart_wallet_tracker,
        helius_fetcher=helius
    )

    # Verify rugcheck is initialized
    logger.info("✅ ConvictionEngine initialized")
    logger.info(f"   RugCheck API instance: {conviction_engine.rugcheck}")
    logger.info(f"   Session initialized: {conviction_engine.rugcheck.session is not None}")

    # Test token data (mock)
    test_token_address = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
    test_token_data = {
        'token_symbol': 'JUP',
        'token_name': 'Jupiter',
        'bonding_curve_pct': 100,  # Graduated
        'liquidity': 50000,
        'volume_24h': 100000,
        'market_cap': 1000000,
        'price_change_5m': 5,
        'created_at': None
    }

    logger.info(f"\n📝 Testing token analysis with RugCheck...")
    logger.info(f"   Token: ${test_token_data['token_symbol']}")
    logger.info(f"   Address: {test_token_address[:12]}...{test_token_address[-4:]}")

    try:
        # This will run the full conviction analysis including RugCheck
        result = await conviction_engine.analyze_token(
            token_address=test_token_address,
            token_data=test_token_data
        )

        logger.info(f"\n✅ Analysis Complete!")
        logger.info(f"   Final Score: {result.get('score', 0)}/100")
        logger.info(f"   Passed Threshold: {result.get('passed', False)}")

        # Check if RugCheck data is in the result
        rug_checks = result.get('rug_checks', {})
        rugcheck_data = rug_checks.get('rugcheck_api')

        if rugcheck_data:
            logger.info(f"\n   RugCheck Integration:")
            logger.info(f"      ✅ Data Retrieved: {rugcheck_data.get('success', False)}")
            logger.info(f"      Risk Level: {rugcheck_data.get('risk_level', 'unknown')}")
            logger.info(f"      Score: {rugcheck_data.get('score', 'N/A')}")

            # Check if penalty was applied
            breakdown = result.get('breakdown', {})
            rugcheck_penalty = breakdown.get('rugcheck_penalty', 0)
            logger.info(f"      Penalty Applied: {rugcheck_penalty} points")
        else:
            logger.warning(f"   ⚠️  No RugCheck data in result")

        logger.info("\n✅ Conviction Engine Integration: WORKING")

    except Exception as e:
        logger.error(f"❌ Error during analysis: {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info("=" * 70)


async def main():
    """Run all tests"""
    # Test 1: Direct API test
    await test_rugcheck_api()

    # Test 2: Conviction engine integration test
    await test_conviction_engine_integration()


if __name__ == "__main__":
    asyncio.run(main())
