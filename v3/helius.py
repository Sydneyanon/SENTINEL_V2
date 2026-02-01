"""
SENTINEL V3 - Helius Webhook Manager
Register/manage webhooks for tracked wallets.
"""
import aiohttp
from loguru import logger
from typing import List, Optional

from config import HELIUS_API_KEY

HELIUS_API_URL = "https://api.helius.xyz/v0"


async def get_all_webhooks() -> List[dict]:
    """Get all registered webhooks."""
    if not HELIUS_API_KEY:
        return []

    try:
        url = f"{HELIUS_API_URL}/webhooks?api-key={HELIUS_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Failed to get webhooks: {resp.status}")
                    return []
    except Exception as e:
        logger.error(f"Error getting webhooks: {e}")
        return []


async def create_webhook(
    wallet_addresses: List[str],
    webhook_url: str,
    webhook_type: str = "enhanced"
) -> Optional[str]:
    """
    Create a webhook for wallet addresses.
    Returns webhook ID if successful.
    """
    if not HELIUS_API_KEY:
        logger.error("HELIUS_API_KEY not set")
        return None

    try:
        url = f"{HELIUS_API_URL}/webhooks?api-key={HELIUS_API_KEY}"

        payload = {
            "webhookURL": webhook_url,
            "transactionTypes": ["ANY"],
            "accountAddresses": wallet_addresses,
            "webhookType": webhook_type,
        }

        logger.info(f"Creating webhook with URL: {webhook_url}")
        logger.info(f"Wallet count: {len(wallet_addresses)}")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    webhook_id = data.get('webhookID')
                    logger.info(f"Created webhook: {webhook_id}")
                    return webhook_id
                else:
                    error = await resp.text()
                    logger.error(f"Failed to create webhook: {resp.status} - {error}")
                    return None

    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        return None


async def update_webhook(
    webhook_id: str,
    wallet_addresses: List[str],
    webhook_url: str
) -> bool:
    """Update an existing webhook with new addresses."""
    if not HELIUS_API_KEY:
        return False

    try:
        url = f"{HELIUS_API_URL}/webhooks/{webhook_id}?api-key={HELIUS_API_KEY}"

        payload = {
            "webhookURL": webhook_url,
            "accountAddresses": wallet_addresses,
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    logger.info(f"Updated webhook: {webhook_id}")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Failed to update webhook: {resp.status} - {error}")
                    return False

    except Exception as e:
        logger.error(f"Error updating webhook: {e}")
        return False


async def delete_webhook(webhook_id: str) -> bool:
    """Delete a webhook."""
    if not HELIUS_API_KEY:
        return False

    try:
        url = f"{HELIUS_API_URL}/webhooks/{webhook_id}?api-key={HELIUS_API_KEY}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"Deleted webhook: {webhook_id}")
                    return True
                else:
                    logger.error(f"Failed to delete webhook: {resp.status}")
                    return False

    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return False


async def sync_wallets(wallet_addresses: List[str], webhook_url: str) -> dict:
    """
    Sync tracked wallets with Helius webhooks.
    Creates or updates webhook as needed.

    Returns:
        {
            'success': bool,
            'webhook_id': str or None,
            'wallets_synced': int,
            'message': str
        }
    """
    if not HELIUS_API_KEY:
        return {
            'success': False,
            'webhook_id': None,
            'wallets_synced': 0,
            'message': 'HELIUS_API_KEY not set'
        }

    if not wallet_addresses:
        return {
            'success': False,
            'webhook_id': None,
            'wallets_synced': 0,
            'message': 'No wallets to sync'
        }

    # Get existing webhooks
    webhooks = await get_all_webhooks()

    # Find our wallet webhook (look for one with our endpoint)
    our_webhook = None
    for wh in webhooks:
        if webhook_url in wh.get('webhookURL', ''):
            our_webhook = wh
            break

    if our_webhook:
        # Update existing webhook
        webhook_id = our_webhook['webhookID']
        success = await update_webhook(webhook_id, wallet_addresses, webhook_url)

        if success:
            return {
                'success': True,
                'webhook_id': webhook_id,
                'wallets_synced': len(wallet_addresses),
                'message': f'Updated webhook with {len(wallet_addresses)} wallets'
            }
        else:
            return {
                'success': False,
                'webhook_id': webhook_id,
                'wallets_synced': 0,
                'message': 'Failed to update webhook'
            }
    else:
        # Create new webhook
        webhook_id = await create_webhook(wallet_addresses, webhook_url)

        if webhook_id:
            return {
                'success': True,
                'webhook_id': webhook_id,
                'wallets_synced': len(wallet_addresses),
                'message': f'Created webhook with {len(wallet_addresses)} wallets'
            }
        else:
            return {
                'success': False,
                'webhook_id': None,
                'wallets_synced': 0,
                'message': 'Failed to create webhook'
            }
