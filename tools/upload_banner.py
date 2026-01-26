"""
Upload Prometheus banner to Telegram and get file_id
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publishers.telegram import TelegramPublisher
import config

async def upload_banner(banner_path: str):
    """
    Upload banner GIF/MP4 to Telegram and get file_id

    Args:
        banner_path: Path to banner file (GIF or MP4)
    """
    if not os.path.exists(banner_path):
        print(f"❌ File not found: {banner_path}")
        return

    # Check file size
    file_size = os.path.getsize(banner_path) / (1024 * 1024)  # MB
    if file_size > 10:
        print(f"⚠️  Warning: File size is {file_size:.2f}MB (Telegram limit: 10MB)")
        print("   Consider compressing the video")

    print("🚀 Uploading banner to Telegram...")
    print(f"   File: {banner_path}")
    print(f"   Size: {file_size:.2f}MB")

    # Initialize Telegram publisher
    publisher = TelegramPublisher()
    success = await publisher.initialize()

    if not success:
        print("❌ Failed to initialize Telegram bot")
        print("   Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in env")
        return

    # Upload banner
    file_id = await publisher.upload_banner(banner_path)

    if file_id:
        print("\n" + "=" * 70)
        print("✅ BANNER UPLOADED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\n📝 Add this to your Railway environment variables:")
        print(f"\nTELEGRAM_BANNER_FILE_ID={file_id}")
        print("\n" + "=" * 70)
        print("\n📌 NEXT STEPS:")
        print("1. Copy the file_id above")
        print("2. Go to Railway dashboard → SENTINEL_V2 → Variables")
        print("3. Add: TELEGRAM_BANNER_FILE_ID = <file_id>")
        print("4. Redeploy (Railway auto-deploys on variable change)")
        print("\n✅ Future signals will include your animated banner!")
        print("=" * 70)
    else:
        print("❌ Failed to upload banner")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_banner.py <path_to_banner.mp4>")
        print("\nExample:")
        print("  python upload_banner.py prometheus_banner.mp4")
        print("  python upload_banner.py ~/Downloads/banner.gif")
        sys.exit(1)

    banner_path = sys.argv[1]
    asyncio.run(upload_banner(banner_path))
