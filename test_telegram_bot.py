#!/usr/bin/env python3
"""
Quick test to check Telegram bot status
"""
import asyncio
import os


async def test_bot():
    """Test if bot token is valid and can access the channel"""

    # Get credentials from environment
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '-1003380850002')

    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set in environment!")
        print("   Set it in Railway: Settings → Variables")
        return

    print(f"🤖 Testing bot token: {bot_token[:10]}...")
    print(f"📱 Testing channel: {channel_id}")
    print()

    try:
        from telegram import Bot
        from telegram.error import TelegramError

        bot = Bot(token=bot_token)

        # Test 1: Get bot info
        print("1️⃣ Testing bot info...")
        me = await bot.get_me()
        print(f"   ✅ Bot is valid: @{me.username}")
        print(f"   Bot ID: {me.id}")
        print(f"   Bot Name: {me.first_name}")
        print()

        # Test 2: Check if bot can see the chat
        print("2️⃣ Testing channel access...")
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            print(f"   ✅ Bot can see chat!")
            print(f"   Chat title: {chat.title}")
            print(f"   Chat type: {chat.type}")
            print()
        except TelegramError as e:
            print(f"   ❌ Cannot access chat: {e}")
            print()
            print("🔧 FIX:")
            print(f"   1. Go to your Telegram channel")
            print(f"   2. Add @{me.username} as administrator")
            print(f"   3. Grant 'Post Messages' permission")
            return

        # Test 3: Try to send a test message
        print("3️⃣ Testing message sending...")
        try:
            msg = await bot.send_message(
                chat_id=channel_id,
                text="🧪 Test message from Prometheus bot setup script\n\nIf you see this, the bot is working! ✅",
                parse_mode='HTML'
            )
            print(f"   ✅ Message sent successfully!")
            print(f"   Message ID: {msg.message_id}")
            print()
            print("🎉 TELEGRAM BOT IS FULLY OPERATIONAL!")

        except TelegramError as e:
            print(f"   ❌ Cannot send message: {e}")
            print()
            print("🔧 FIX:")
            print("   The bot can see the channel but cannot post.")
            print("   Make sure it has 'Post Messages' permission!")

    except ImportError:
        print("❌ python-telegram-bot not installed!")
        print("   Run: pip install python-telegram-bot")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_bot())
