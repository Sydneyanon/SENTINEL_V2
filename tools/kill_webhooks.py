#!/usr/bin/env python3
"""
Emergency: Delete ALL Helius webhooks to stop credit burn.
Run once: python tools/kill_webhooks.py
"""
import asyncio
import aiohttp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def kill_all_webhooks():
    api_key = os.getenv('HELIUS_API_KEY')
    if not api_key:
        print("ERROR: HELIUS_API_KEY not set")
        return

    url = f"https://api.helius.xyz/v0/webhooks?api-key={api_key}"

    async with aiohttp.ClientSession() as session:
        # List all webhooks
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                print(f"ERROR: Failed to list webhooks (HTTP {resp.status})")
                return
            webhooks = await resp.json()

        print(f"Found {len(webhooks)} webhook(s):")
        for wh in webhooks:
            wh_id = wh.get('webhookID', 'unknown')
            wh_url = wh.get('webhookURL', 'unknown')
            accounts = wh.get('accountAddresses', [])
            wh_type = wh.get('webhookType', 'unknown')
            print(f"  - {wh_id}: {wh_type} → {wh_url} ({len(accounts)} accounts)")

        if not webhooks:
            print("No webhooks to delete!")
            return

        # Delete all
        for wh in webhooks:
            wh_id = wh.get('webhookID')
            if not wh_id:
                continue
            del_url = f"https://api.helius.xyz/v0/webhooks/{wh_id}?api-key={api_key}"
            async with session.delete(del_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    print(f"  DELETED: {wh_id}")
                else:
                    print(f"  FAILED to delete {wh_id}: HTTP {resp.status}")

        print("\nDone! Webhook spam should stop within seconds.")

if __name__ == '__main__':
    asyncio.run(kill_all_webhooks())
