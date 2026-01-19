import os
from PIL import Image, ImageDraw

WIDTH = 512
HEIGHT = 128
RADIUS = 20
STROKE_WIDTH = 3
ICON_SIZE = 64
ICON_OFFSET_X = 40  # Left padding for icon

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE_DIR, 'skin.AIODI', 'media')
BUTTONS_DIR = os.path.join(MEDIA_DIR, 'buttons')
ICONS_DIR = os.path.join(MEDIA_DIR, 'icons')

if not os.path.exists(BUTTONS_DIR):
    os.makedirs(BUTTONS_DIR)

BUTTONS = [
    ('home', 'widgetmanager/home.png'),
    ('movies', 'widgetmanager/movies.png'),
    ('tvshows', 'widgetmanager/tvshows.png'),
    ('youtube', 'search/youtube.png'),
    ('play', 'infodialog/play.png'),
    ('browse', 'infodialog/browse.png'),
    ('trailer', 'infodialog/trailer.png'),
    ('watchlist_add', 'DRAW_PLUS'),
    ('watchlist_remove', 'DRAW_MINUS'),
    ('watched_add', 'DRAW_CHECK'),
    ('watched_remove', 'DRAW_CROSS'),
]

def rounded_rectangle(draw, box, radius, fill, outline, width):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def draw_plus(draw, center_x, center_y, size, color):
    half = size // 2
    # Horizontal
    draw.rectangle([center_x - half, center_y - 3, center_x + half, center_y + 3], fill=color)
    # Vertical
    draw.rectangle([center_x - 3, center_y - half, center_x + 3, center_y + half], fill=color)

def draw_minus(draw, center_x, center_y, size, color):
    half = size // 2
    draw.rectangle([center_x - half, center_y - 3, center_x + half, center_y + 3], fill=color)

def draw_check(draw, center_x, center_y, size, color):
    # Simple checkmark
    # Points: left-mid, bottom-mid, top-right
    points = [
        (center_x - size//2, center_y),
        (center_x - size//6, center_y + size//2),
        (center_x + size//2, center_y - size//2)
    ]
    draw.line(points, fill=color, width=6, joint='curve')

def draw_cross(draw, center_x, center_y, size, color):
    half = size // 2
    draw.line([center_x - half, center_y - half, center_x + half, center_y + half], fill=color, width=6)
    draw.line([center_x + half, center_y - half, center_x - half, center_y + half], fill=color, width=6)

def create_button(name, icon_src, is_focus):
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background
    if is_focus:
        # Red background, White border
        fill_color = (255, 0, 0, 255)
        outline_color = (255, 255, 255, 255)
    else:
        # 50% Black background, White border
        fill_color = (0, 0, 0, 128)
        outline_color = (255, 255, 255, 255)

    # Draw Button Background
    box = [STROKE_WIDTH, STROKE_WIDTH, WIDTH - STROKE_WIDTH, HEIGHT - STROKE_WIDTH]
    rounded_rectangle(draw, box, RADIUS, fill_color, outline_color, STROKE_WIDTH)

    # Icon Processing
    icon_center_x = ICON_OFFSET_X + ICON_SIZE // 2
    icon_center_y = HEIGHT // 2
    
    if icon_src.startswith('DRAW_'):
        color = (255, 255, 255, 255)
        if icon_src == 'DRAW_PLUS':
            draw_plus(draw, icon_center_x, icon_center_y, ICON_SIZE - 20, color)
        elif icon_src == 'DRAW_MINUS':
            draw_minus(draw, icon_center_x, icon_center_y, ICON_SIZE - 20, color)
        elif icon_src == 'DRAW_CHECK':
            draw_check(draw, icon_center_x, icon_center_y, ICON_SIZE - 20, color)
        elif icon_src == 'DRAW_CROSS':
            draw_cross(draw, icon_center_x, icon_center_y, ICON_SIZE - 20, color)
    else:
        icon_path = os.path.join(ICONS_DIR, icon_src)
        if os.path.exists(icon_path):
            try:
                icon = Image.open(icon_path).convert("RGBA")
                # Resize keeping aspect ratio
                icon.thumbnail((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
                
                # Center placement
                paste_x = icon_center_x - icon.width // 2
                paste_y = icon_center_y - icon.height // 2
                
                # Tint icon white if needed (most are likely white already, but just in case)
                # For now assume they are white or appropriate color. 
                # If we need to colorize:
                # r, g, b, a = icon.split()
                # icon = Image.merge('RGBA', (r, g, b, a)) # naive
                
                img.paste(icon, (paste_x, paste_y), icon)
            except Exception as e:
                print(f"Error loading icon {icon_path}: {e}")
        else:
            print(f"Warning: Icon not found: {icon_path}")

    filename = f"{name}_{'fo' if is_focus else 'nofo'}.png"
    save_path = os.path.join(BUTTONS_DIR, filename)
    img.save(save_path)
    print(f"Created: {save_path}")

def main():
    print("Generating PNG buttons...")
    for name, icon_src in BUTTONS:
        create_button(name, icon_src, is_focus=True)
        create_button(name, icon_src, is_focus=False)
    print("Done.")

if __name__ == "__main__":
    main()
