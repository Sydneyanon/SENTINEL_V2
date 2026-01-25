#!/usr/bin/env python3
"""
Runner Data Collection - Working Version
Uses DexScreener's discovery endpoints to find trending Solana tokens
"""
import os
import sys
import json
import requests
import time
from datetime import datetime
from typing import List, Dict
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_trending_tokens() -> List[str]:
    """
    Get trending token addresses from DexScreener discovery endpoints

    Returns:
        List of Solana token addresses
    """
    tokens = set()

    # Endpoint 1: Recently boosted tokens
    try:
        resp = requests.get('https://api.dexscreener.com/token-boosts/latest/v1', timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                if item.get('chainId') == 'solana':
                    tokens.add(item.get('tokenAddress'))
            logger.info(f"  Got {len([i for i in data if i.get('chainId')=='solana'])} from boosted tokens")
    except Exception as e:
        logger.error(f"  Error fetching boosted: {e}")

    time.sleep(1)

    # Endpoint 2: Latest profiles
    try:
        resp = requests.get('https://api.dexscreener.com/token-profiles/latest/v1', timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                if item.get('chainId') == 'solana':
                    tokens.add(item.get('tokenAddress'))
            logger.info(f"  Got {len([i for i in data if i.get('chainId')=='solana'])} from profiles")
    except Exception as e:
        logger.error(f"  Error fetching profiles: {e}")

    return list(tokens)


def get_token_data(token_address: str) -> Dict:
    """
    Get detailed trading data for a token

    Args:
        token_address: Solana token address

    Returns:
        Dict with token trading data or None if error
    """
    try:
        url = f'https://api.dexscreener.com/latest/dex/tokens/{token_address}'
        resp = requests.get(url, timeout=30)

        if resp.status_code != 200:
            return None

        data = resp.json()
        pairs = data.get('pairs', [])

        if not pairs:
            return None

        # Get the pair with highest liquidity (most reliable)
        top_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))

        base_token = top_pair.get('baseToken', {})

        return {
            'address': token_address,
            'symbol': base_token.get('symbol', 'UNKNOWN'),
            'name': base_token.get('name', 'Unknown'),
            'price_usd': float(top_pair.get('priceUsd', 0) or 0),
            'fdv': float(top_pair.get('fdv', 0) or 0),
            'liquidity_usd': float(top_pair.get('liquidity', {}).get('usd', 0) or 0),
            'volume_24h': float(top_pair.get('volume', {}).get('h24', 0) or 0),
            'volume_6h': float(top_pair.get('volume', {}).get('h6', 0) or 0),
            'price_change_24h': float(top_pair.get('priceChange', {}).get('h24', 0) or 0),
            'price_change_6h': float(top_pair.get('priceChange', {}).get('h6', 0) or 0),
            'price_change_1h': float(top_pair.get('priceChange', {}).get('h1', 0) or 0),
            'txns_24h_buys': top_pair.get('txns', {}).get('h24', {}).get('buys', 0),
            'txns_24h_sells': top_pair.get('txns', {}).get('h24', {}).get('sells', 0),
            'pair_created_at': top_pair.get('pairCreatedAt'),
            'dex_url': top_pair.get('url'),
        }

    except Exception as e:
        logger.debug(f"  Error fetching {token_address[:12]}: {e}")
        return None


def collect_runners(min_mcap: int = 1_000_000, max_mcap: int = 50_000_000, max_tokens: int = 100) -> List[Dict]:
    """
    Collect runner tokens (high MCAP performers)

    Args:
        min_mcap: Minimum market cap
        max_mcap: Maximum market cap
        max_tokens: Maximum tokens to collect

    Returns:
        List of runner token data
    """
    logger.info("🔍 Step 1: Discovering trending Solana tokens...")
    token_addresses = get_trending_tokens()
    logger.info(f"  Found {len(token_addresses)} unique Solana tokens")

    logger.info(f"\n🔍 Step 2: Fetching detailed data (${min_mcap/1e6:.1f}M - ${max_mcap/1e6:.1f}M MCAP)...")
    runners = []

    for i, address in enumerate(token_addresses, 1):
        if len(runners) >= max_tokens:
            break

        logger.info(f"  [{i}/{len(token_addresses)}] Checking {address[:12]}...")

        token_data = get_token_data(address)

        if not token_data:
            continue

        fdv = token_data['fdv']

        # Filter by MCAP range
        if min_mcap <= fdv <= max_mcap:
            logger.info(f"    ✅ ${token_data['symbol']}: ${fdv/1e6:.2f}M MCAP")
            runners.append(token_data)
        else:
            logger.debug(f"    ⏭️  ${token_data['symbol']}: ${fdv/1e6:.2f}M (outside range)")

        # Rate limiting
        time.sleep(0.5)

    return runners


def save_results(runners: List[Dict], output_file: str = 'runner_data_collected.json'):
    """Save collected runner data to JSON file"""
    output_path = os.path.join(os.path.dirname(__file__), output_file)

    data = {
        'collected_at': datetime.utcnow().isoformat(),
        'total_runners': len(runners),
        'runners': runners
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"\n💾 Saved {len(runners)} runners to {output_path}")

    # Print summary
    if runners:
        logger.info("\n" + "=" * 70)
        logger.info("📊 RUNNER COLLECTION SUMMARY")
        logger.info("=" * 70)

        total_mcap = sum(r['fdv'] for r in runners)
        avg_mcap = total_mcap / len(runners) if runners else 0
        total_liq = sum(r['liquidity_usd'] for r in runners)
        total_vol = sum(r['volume_24h'] for r in runners)

        logger.info(f"Total runners: {len(runners)}")
        logger.info(f"Total market cap: ${total_mcap/1e6:.1f}M")
        logger.info(f"Average MCAP: ${avg_mcap/1e6:.2f}M")
        logger.info(f"Total liquidity: ${total_liq/1e6:.2f}M")
        logger.info(f"Total 24h volume: ${total_vol/1e6:.2f}M")

        logger.info(f"\nTop 10 Runners:")
        sorted_runners = sorted(runners, key=lambda x: x['fdv'], reverse=True)

        for i, runner in enumerate(sorted_runners[:10], 1):
            symbol = runner['symbol']
            mcap = runner['fdv']
            liq = runner['liquidity_usd']
            change_24h = runner.get('price_change_24h', 0)
            logger.info(f"  {i}. ${symbol}: ${mcap/1e6:.2f}M MCAP, ${liq/1e3:.0f}K liq ({change_24h:+.1f}% 24h)")

        logger.info("=" * 70)


def main():
    logger.info("🚀 Starting Runner Data Collection...")
    logger.info("📋 Strategy:")
    logger.info("   1. Discover trending Solana tokens from DexScreener")
    logger.info("   2. Filter for $1M-$50M MCAP range (current runners)")
    logger.info("   3. Collect detailed trading data")
    logger.info("   4. Export for ML pattern analysis")
    logger.info("")
    logger.info("🎯 Target: Up to 100 runner tokens")
    logger.info("")

    # Collect runners
    runners = collect_runners(
        min_mcap=1_000_000,   # $1M
        max_mcap=50_000_000,  # $50M
        max_tokens=100
    )

    if not runners:
        logger.error("\n❌ No runners found in target range")
        logger.error("This might mean:")
        logger.error("  - No pump.fun tokens currently in $1M-$50M range")
        logger.error("  - Rate limiting from DexScreener")
        logger.error("  - Try adjusting MCAP range")
        return

    # Save results
    save_results(runners)

    logger.info(f"\n✅ Collection complete!")
    logger.info(f"📊 Collected {len(runners)} runner tokens")
    logger.info(f"\n💡 Next step: Analyze patterns or train ML model")
    logger.info(f"    python ralph/analyze_patterns.py --data runner_data_collected.json")


if __name__ == '__main__':
    main()
