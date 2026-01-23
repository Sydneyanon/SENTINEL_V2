"""
Quick script to upload banner and get file_id for Telegram
Run this once to get your banner file_id
"""
import asyncio
import os
from telegram import Bot

async def upload_banner():
    """Upload banner GIF and get file_id"""

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')

    if not bot_token or not channel_id:
        print("❌ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID env vars first!")
        return

    bot = Bot(token=bot_token)

    # Upload your GIF file (replace with your file path)
    banner_path = "banner.gif"  # PUT YOUR GIF FILE HERE

    if not os.path.exists(banner_path):
        print(f"❌ Banner file not found: {banner_path}")
        print("   Create a Prometheus fire-themed GIF and save it as banner.gif")
        return

    print(f"📤 Uploading {banner_path} to Telegram...")

    with open(banner_path, 'rb') as f:
        message = await bot.send_animation(
            chat_id=channel_id,
            animation=f,
            caption="🔥 PROMETHEUS BANNER TEST 🔥\n\nIf you see this, the banner works!"
        )

    file_id = message.animation.file_id

    print("\n✅ Banner uploaded successfully!")
    print(f"\n📋 Add this to your Railway environment variables:")
    print(f"\nTELEGRAM_BANNER_FILE_ID={file_id}")
    print(f"\nOr add to config.py:")
    print(f"TELEGRAM_BANNER_FILE_ID = '{file_id}'")

    return file_id

if __name__ == "__main__":
    asyncio.run(upload_banner())
