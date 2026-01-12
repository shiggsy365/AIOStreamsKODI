# AIODI Skin Media Assets

This directory contains media assets for the AIODI skin.

## Required Files

### icon.png
- **Size**: 512x512 pixels
- **Format**: PNG
- **Description**: Skin icon shown in Kodi addon browser
- **Current Status**: Placeholder (needs replacement)

### fanart.jpg
- **Size**: 1920x1080 pixels
- **Format**: JPG
- **Description**: Background fanart for skin
- **Current Status**: Placeholder (needs replacement)

## Creating Assets

### Icon Design Suggestions
- Use the AIODI branding colors (Dodger Blue #1E90FF)
- Include "AIODI" text or logo
- Keep it simple and recognizable at small sizes
- Use transparent background or solid color

### Fanart Design Suggestions
- Netflix-style streaming theme
- Include AIOStreams branding elements
- Dodger Blue accent colors
- 16:9 aspect ratio
- High quality (1920x1080)

## Generating Placeholders

If you have ImageMagick installed:

```bash
# Icon (512x512 with AIODI text)
convert -size 512x512 xc:#1E90FF \
  -fill white \
  -pointsize 72 \
  -gravity center \
  -annotate +0+0 "AIODI" \
  icon.png

# Fanart (1920x1080 gradient)
convert -size 1920x1080 \
  gradient:#1E90FF-#000000 \
  fanart.jpg
```

## Current Status

These placeholder files will work but should be replaced with professional artwork for production release.
