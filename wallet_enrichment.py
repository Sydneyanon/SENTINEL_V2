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
    
    Handles both formats:
    - Simple list: ["addr1", "addr2"] → Auto-discover metadata
    - Detailed list: [{'address': 'addr1', 'name': 'KOL1'}] → Keep existing metadata
    
    Returns: List of enriched wallet dictionaries
    """
    logger.info("🔍 Enriching smart wallets with metadata...")
    
    enriched_wallets = []
    
    # Check if SMART_WALLETS is empty
    if not config.SMART_WALLETS:
        logger.warning("⚠️ SMART_WALLETS is empty!")
        logger.info("💡 Tip: Run 'python wallet_cli.py discover' to find top traders")
        return []
    
    # Determine format (simple list vs detailed)
    first_entry = config.SMART_WALLETS[0]
    
    if isinstance(first_entry, str):
        # Simple format: just addresses
        logger.info(f"📝 Simple format detected: {len(config.SMART_WALLETS)} addresses")
        logger.info("🔄 Auto-discovering metadata...")
        
        metadata_dict = await auto_discover_wallets(config.SMART_WALLETS)
        
        for address in config.SMART_WALLETS:
            if address in metadata_dict:
                enriched_wallets.append(metadata_dict[address])
            else:
                # Fallback: Check curated_wallets.py first
                if address in KOL_WALLETS:
                    curated_info = KOL_WALLETS[address]
                    enriched_wallets.append({
                        'address': address,
                        'name': curated_info.get('name') or f"KOL_{address[:6]}",
                        'tier': curated_info.get('tier', 'top_kol'),
                        'win_rate': 0.50,  # Will be fetched live when first used
                        'source': 'curated',
                        'active': True,
                        'fetch_metadata': curated_info.get('fetch_metadata', True)
                    })
                    logger.debug(f"   ✅ Using curated data for {address[:8]} (tier: {curated_info.get('tier')})")
                else:
                    # Last resort: create basic entry
                    enriched_wallets.append({
                        'address': address,
                        'name': f"Wallet_{address[:8]}",
                        'tier': 'unknown',
                        'win_rate': 0.50,
                        'source': 'config',
                        'active': True
                    })
        
        logger.info(f"✅ Enriched {len(enriched_wallets)} wallets with metadata")
        
    elif isinstance(first_entry, dict):
        # Detailed format: already has metadata
        logger.info(f"📊 Detailed format detected: {len(config.SMART_WALLETS)} wallets")
        
        # Check if metadata is stale (>7 days old)
        for wallet in config.SMART_WALLETS:
            if 'address' not in wallet:
                logger.warning(f"⚠️ Wallet missing address: {wallet}")
                continue
            
            # Check if needs refresh
            needs_refresh = False
            
            if 'last_updated' not in wallet:
                needs_refresh = True
            else:
                # Check if >7 days old
                from datetime import datetime, timedelta
                last_update = datetime.fromisoformat(wallet['last_updated'])
                if datetime.utcnow() - last_update > timedelta(days=7):
                    needs_refresh = True
            
            if needs_refresh:
                logger.info(f"🔄 Refreshing metadata for {wallet.get('name', wallet['address'][:8])}...")
                # Auto-discover fresh data
                fresh_metadata = await auto_discover_wallets([wallet['address']])
                if wallet['address'] in fresh_metadata:
                    # Merge: keep manual overrides, update auto-discovered fields
                    enriched = {**fresh_metadata[wallet['address']], **wallet}
                    enriched_wallets.append(enriched)
                else:
                    enriched_wallets.append(wallet)
            else:
                enriched_wallets.append(wallet)
        
        logger.info(f"✅ Loaded {len(enriched_wallets)} wallets (refreshed stale metadata)")
    
    else:
        logger.error(f"❌ Unknown SMART_WALLETS format: {type(first_entry)}")
        return []
    
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
