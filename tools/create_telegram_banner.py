"""
Create Prometheus Telegram Banner
Simple version using Python - for full cinematic version, use AI tools like Runway
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os

def create_simple_banner():
    """
    Creates a simple animated banner concept
    For production: Use Runway Gen-3, Pika Labs, or After Effects for cinematic quality
    """

    # Banner specs
    width, height = 1280, 720
    duration_frames = 90  # 3 seconds at 30fps

    print("🎨 PROMETHEUS TELEGRAM BANNER CREATOR")
    print("=" * 60)
    print("\n⚠️  THIS IS A CONCEPT GENERATOR")
    print("For production-quality animation, use:")
    print("  1. Runway Gen-3 (AI video generation)")
    print("  2. Pika Labs (AI animation)")
    print("  3. Blender + After Effects (professional)")
    print("\n" + "=" * 60)

    # For actual implementation, recommend AI tools
    print("\n📝 RECOMMENDED APPROACH:")
    print("\n1. Go to: https://runwayml.com/")
    print("   - Use Gen-3 Alpha Turbo")
    print("   - Prompt:")
    print('     "Prometheus Greek god holding flame in hand, throws flame')
    print('      directly at camera, screen engulfs in fire, text FIRE')
    print('      INCOMING emerges from flames, cinematic lighting, dark')
    print('      background, dramatic, 3 seconds"')
    print("\n2. Or use: https://pika.art/")
    print("   - Upload Prometheus image")
    print("   - Add motion: flame throw toward camera")
    print("\n3. Or commission on Fiverr:")
    print("   - Search: 'animated logo intro fire effect'")
    print("   - Budget: $20-50 for 3-5 second animation")

    print("\n" + "=" * 60)
    print("\n🎬 ANIMATION STORYBOARD:")
    print("=" * 60)
    print("Frame 1-30 (0-1s):   Prometheus holding flame, builds up")
    print("Frame 31-60 (1-2s):  Throws flame at camera, grows larger")
    print("Frame 61-75 (2-2.5s): Screen engulfed in flames")
    print("Frame 76-90 (2.5-3s): Text 'FIRE INCOMING' emerges")

    print("\n" + "=" * 60)
    print("\n🔥 TEXT OPTIONS:")
    print("=" * 60)
    print("Option 1: 'FIRE INCOMING'")
    print("Option 2: 'INCOMING FIRE'")
    print("Option 3: '🔥 PROMETHEUS SIGNAL 🔥'")
    print("Option 4: 'THE FIRE SPREADS'")

    print("\n" + "=" * 60)
    print("\n📤 AFTER CREATION:")
    print("=" * 60)
    print("1. Save as MP4 or GIF (< 10MB)")
    print("2. Upload to Telegram:")
    print("   python upload_banner.py <path_to_banner.mp4>")
    print("3. Get file_id and add to Railway env:")
    print("   TELEGRAM_BANNER_FILE_ID=<file_id>")

    print("\n✅ Script complete - follow recommended approach above")

def create_text_overlay():
    """Sample text styling for 'FIRE INCOMING'"""
    img = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try to use a bold font (fallback to default if not available)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
    except:
        font = ImageFont.load_default()

    text = "FIRE INCOMING"

    # Get text bbox
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center text
    x = (1280 - text_width) // 2
    y = (720 - text_height) // 2

    # Draw text with glow effect
    # Red glow
    for offset in range(10, 0, -1):
        alpha = int(255 * (offset / 10))
        draw.text((x, y), text, font=font, fill=(255, 100, 0, alpha))

    # Main text (white/yellow)
    draw.text((x, y), text, font=font, fill=(255, 200, 0, 255))

    img.save('/tmp/fire_incoming_text_sample.png')
    print("\n✅ Sample text overlay saved to: /tmp/fire_incoming_text_sample.png")
    print("   (Use this as reference for text styling)")

if __name__ == "__main__":
    create_simple_banner()
    create_text_overlay()

    print("\n" + "=" * 60)
    print("🎯 QUICK START:")
    print("=" * 60)
    print("\nEasiest path:")
    print("1. Go to https://runwayml.com/")
    print("2. Generate with prompt above")
    print("3. Download MP4")
    print("4. Run: python upload_banner.py banner.mp4")
    print("\nOr hire on Fiverr for $20-50")
    print("=" * 60)
