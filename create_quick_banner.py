"""
Quick Prometheus Banner Generator
Creates a simple but effective animated GIF
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_fire_gradient(width, height, frame, total_frames):
    """Create a fire-like gradient that animates"""
    img = Image.new('RGB', (width, height), (0, 0, 0))
    pixels = img.load()

    offset = int((frame / total_frames) * height * 0.3)

    for y in range(height):
        for x in range(width):
            # Create fire effect
            adjusted_y = (y + offset) % height
            intensity = 1 - (adjusted_y / height)

            # Fire colors: black -> red -> orange -> yellow
            if intensity < 0.3:
                r = int(intensity * 255 / 0.3)
                g = 0
                b = 0
            elif intensity < 0.6:
                r = 255
                g = int((intensity - 0.3) * 255 / 0.3)
                b = 0
            else:
                r = 255
                g = 200 + int((intensity - 0.6) * 55 / 0.4)
                b = int((intensity - 0.6) * 100 / 0.4)

            pixels[x, y] = (r, g, b)

    return img

def create_animated_banner():
    """Create animated Prometheus banner GIF"""
    width, height = 800, 450  # 16:9 aspect ratio, smaller for fast upload
    frames = []
    total_frames = 20  # Short loop for small file size

    print("🎨 Creating Prometheus animated banner...")

    for frame in range(total_frames):
        # Create fire background
        img = create_fire_gradient(width, height, frame, total_frames)
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default
        try:
            # Try common system fonts
            for font_path in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf"
            ]:
                if os.path.exists(font_path):
                    title_font = ImageFont.truetype(font_path, 80)
                    subtitle_font = ImageFont.truetype(font_path, 40)
                    break
            else:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()

        # Pulsing effect
        pulse = abs((frame / total_frames) - 0.5) * 2  # 0 to 1 to 0
        alpha_mod = int(50 + pulse * 50)

        # Draw title "PROMETHEUS"
        title = "🔥 PROMETHEUS"
        # Get text size
        try:
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_height = title_bbox[3] - title_bbox[1]
        except:
            title_width, title_height = 400, 80

        title_x = (width - title_width) // 2
        title_y = height // 2 - 60

        # Draw shadow
        draw.text((title_x + 3, title_y + 3), title, font=title_font, fill=(0, 0, 0))
        # Draw main text
        draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))

        # Draw subtitle "SIGNAL"
        subtitle = "SIGNAL INCOMING"
        try:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        except:
            subtitle_width = 300

        subtitle_x = (width - subtitle_width) // 2
        subtitle_y = title_y + 100

        # Draw shadow
        draw.text((subtitle_x + 2, subtitle_y + 2), subtitle, font=subtitle_font, fill=(0, 0, 0))
        # Draw main text with pulse
        color = (255, 200 + alpha_mod, 0)
        draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=color)

        frames.append(img)
        print(f"  Frame {frame + 1}/{total_frames}...")

    # Save as animated GIF
    output_path = "/home/user/SENTINEL_V2/prometheus_banner.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=100,  # 100ms per frame = 2 second loop
        loop=0  # Infinite loop
    )

    file_size = os.path.getsize(output_path) / 1024  # KB
    print(f"\n✅ Banner created: {output_path}")
    print(f"   Size: {file_size:.1f} KB")
    print(f"   Frames: {total_frames}")
    print(f"   Duration: 2 seconds (loops)")

    return output_path

if __name__ == "__main__":
    banner_path = create_animated_banner()
    print("\n🚀 Next step: Upload to Telegram")
    print(f"   python tools/upload_banner.py {banner_path}")
