#!/usr/bin/env python3
"""
Simple Session Check Script
Checks if Telegram session file exists and can be loaded
"""
import os
import asyncio

# Check if session file exists
session_file = 'sentinel_session.session'

print('=' * 70)
print('TELEGRAM SESSION FILE CHECK')
print('=' * 70)

if os.path.exists(session_file):
    size = os.path.getsize(session_file)
    print(f'\n✅ Session file exists: {session_file}')
    print(f'   File size: {size} bytes')
    print(f'   Last modified: {os.path.getmtime(session_file)}')

    # Check environment variables
    print('\n📋 Environment Variables:')
    api_id = os.getenv('TELEGRAM_API_ID', '33811421')
    api_hash = os.getenv('TELEGRAM_API_HASH', 'ec5a841d8e108a980c3af61ed4f97df9')
    phone = os.getenv('TELEGRAM_PHONE', '+61413194229')

    print(f'   TELEGRAM_API_ID: {api_id}')
    print(f'   TELEGRAM_API_HASH: {api_hash[:10]}...')
    print(f'   TELEGRAM_PHONE: {phone}')

    # Try to test connection
    print('\n🔌 Attempting connection test...')
    try:
        from telethon import TelegramClient

        async def test_connection():
            client = TelegramClient(session_file.replace('.session', ''), int(api_id), api_hash)
            try:
                await client.connect()

                if await client.is_user_authorized():
                    me = await client.get_me()
                    print('\n✅ SESSION IS VALID AND WORKING!')
                    print('=' * 70)
                    print(f'Logged in as: {me.first_name}')
                    print(f'Username: @{me.username or "no username"}')
                    print(f'Phone: {me.phone}')
                    print(f'User ID: {me.id}')
                    print('=' * 70)
                    print('\n✅ The Telegram session is working correctly!')
                    print('   You can monitor Telegram groups with this session.')
                    return True
                else:
                    print('\n❌ SESSION EXISTS BUT IS NOT AUTHORIZED')
                    print('   Run: python auth_telegram.py')
                    return False

            except Exception as e:
                print(f'\n❌ CONNECTION ERROR: {e}')
                print('\nPossible causes:')
                print('  1. Session file is corrupted')
                print('  2. API credentials are incorrect')
                print('  3. Network connectivity issues')
                print('\nTry re-authenticating: python auth_telegram.py')
                return False
            finally:
                await client.disconnect()

        asyncio.run(test_connection())

    except ImportError:
        print('\n⚠️  Telethon module not installed')
        print('   Install with: pip install telethon')
        print('\n   However, the session file exists and appears valid.')
        print('   On Railway/production, it should work if telethon is installed.')

else:
    print(f'\n❌ Session file NOT found: {session_file}')
    print('\nYou need to create a Telegram session first.')
    print('\nSteps:')
    print('1. Run: python auth_telegram.py')
    print('2. Enter the code sent to your phone')
    print('3. Session file will be created')
    print('4. Commit and push the session file to your repo')

print('\n' + '=' * 70)
