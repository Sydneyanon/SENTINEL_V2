"""
Telegram Authentication Script
Run this once to create the sentinel_session.session file
"""
import asyncio
import os
from telethon import TelegramClient

# Credentials from environment or hardcoded
api_id = os.getenv('TELEGRAM_API_ID', '33811421')
api_hash = os.getenv('TELEGRAM_API_HASH', 'ec5a841d8e108a980c3af61ed4f97df9')
phone = os.getenv('TELEGRAM_PHONE', '+61413194229')

async def main():
    print("=" * 70)
    print("TELEGRAM AUTHENTICATION")
    print("=" * 70)
    print(f"\nAPI ID: {api_id}")
    print(f"Phone: {phone}")
    print("\nConnecting to Telegram...")

    # Create client with same session name as main app
    client = TelegramClient('sentinel_session', int(api_id), api_hash)

    # Start will prompt for code if needed
    await client.start(phone=phone)

    # Get user info to confirm
    me = await client.get_me()
    print("\n" + "=" * 70)
    print("✅ AUTHENTICATION SUCCESSFUL!")
    print("=" * 70)
    print(f"Logged in as: {me.first_name} (@{me.username or 'no username'})")
    print(f"Phone: {me.phone}")
    print(f"\n📁 Session file created: sentinel_session.session")
    print("\nNext steps:")
    print("1. Commit this file: git add sentinel_session.session")
    print("2. Push to repo: git commit -m 'Add Telegram session' && git push")
    print("3. Railway will auto-redeploy and use this session!")
    print("=" * 70)

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
