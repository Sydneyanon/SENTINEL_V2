"""
Wallet Enrichment Startup Script
Automatically enriches SMART_WALLETS with metadata on bot startup
"""
import asyncio
from loguru import logger
from typing import List, Dict
import config
from wallet_autodiscovery import auto_discover_wallets, discover_top_traders
from data.curated_wallets import KOL_WALLETS


async def enrich_smart_wallets() -> List[Dict]:
    """
    Enrich SMART_WALLETS with auto-discovered metadata

    Priority:
    1. Use curated_wallets.py KOL_WALLETS as base (36 wallets with tier data)
    2. Override with config.SMART_WALLETS if provided
    3. Auto-discover metadata from GMGN when wallet is first used

    Returns: List of enriched wallet dictionaries
    """
    logger.info("🔍 Enriching smart wallets with metadata...")

    enriched_wallets = []

    # Start with curated wallets as base
    logger.info(f"📚 Loading {len(KOL_WALLETS)} wallets from curated_wallets.py")

    for address, curated_info in KOL_WALLETS.items():
        # Skip Ethereum addresses (safety check)
        if address.startswith('0x'):
            logger.warning(f"⚠️ Skipping Ethereum address in curated list: {address[:10]}...")
            continue

        enriched_wallets.append({
            'address': address,
            'name': curated_info.get('name') or f"KOL_{address[:6]}",
            'tier': curated_info.get('tier', 'top_kol'),
            'win_rate': 0.50,  # Will be fetched live when first used
            'source': 'curated',
            'active': True,
            'fetch_metadata': curated_info.get('fetch_metadata', True)
        })

    logger.info(f"✅ Loaded {len(enriched_wallets)} wallets from curated list")

    # If config.SMART_WALLETS has additional addresses not in curated, add them
    if config.SMART_WALLETS:
        curated_addresses = set(KOL_WALLETS.keys())
        # Filter out Ethereum addresses and duplicates
        config_only = [
            addr for addr in config.SMART_WALLETS
            if addr not in curated_addresses and not addr.startswith('0x')
        ]

        if config_only:
            logger.info(f"📝 Found {len(config_only)} additional wallets in config.py")
            metadata_dict = await auto_discover_wallets(config_only)

            for address in config_only:
                if address in metadata_dict:
                    enriched_wallets.append(metadata_dict[address])
                else:
                    enriched_wallets.append({
                        'address': address,
                        'name': f"Wallet_{address[:8]}",
                        'tier': 'unknown',
                        'win_rate': 0.50,
                        'source': 'config',
                        'active': True
                    })

    # Log summary
    logger.info("=" * 60)
    logger.info("📊 WALLET SUMMARY")
    logger.info("=" * 60)
    
    tier_counts = {}
    for wallet in enriched_wallets:
        tier = wallet.get('tier', 'unknown')
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    logger.info(f"Total Wallets: {len(enriched_wallets)}")
    for tier, count in sorted(tier_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {tier.capitalize()}: {count}")
    
    logger.info("=" * 60)
    
    return enriched_wallets


async def get_wallet_addresses(enriched_wallets: List[Dict]) -> List[str]:
    """Extract just the addresses for Helius webhook setup"""
    return [w['address'] for w in enriched_wallets if w.get('active', True)]


# For use in main.py startup
async def initialize_smart_wallets():
    """
    Call this in main.py startup to auto-enrich wallets
    
    Returns: (enriched_wallets, addresses_for_helius)
    """
    enriched = await enrich_smart_wallets()
    addresses = await get_wallet_addresses(enriched)
    
    return enriched, addresses
