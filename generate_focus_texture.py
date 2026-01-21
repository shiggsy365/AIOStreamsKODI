from PIL import Image, ImageDraw
import os

WIDTH = 450
HEIGHT = 75
RADIUS = 20
STROKE_WIDTH = 4
SAVE_PATH = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/script.aiodi.onboarding/resources/skins/Default/media/buttons/focus.png"

def create_plain_button():
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Red background, White border
    fill_color = (255, 0, 0, 255)
    outline_color = (255, 255, 255, 255)

    # Draw rounded rectangle
    box = [STROKE_WIDTH, STROKE_WIDTH, WIDTH - STROKE_WIDTH, HEIGHT - STROKE_WIDTH]
    draw.rounded_rectangle(box, radius=RADIUS, fill=fill_color, outline=outline_color, width=STROKE_WIDTH)

    # Ensure directory exists
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    img.save(SAVE_PATH)
    print(f"Created: {SAVE_PATH}")

if __name__ == "__main__":
    create_plain_button()
