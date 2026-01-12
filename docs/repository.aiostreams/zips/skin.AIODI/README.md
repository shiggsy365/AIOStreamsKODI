# AIODI Skin Media Assets

This directory contains all media assets for the AIODI skin.

## Required Assets

### Icon and Fanart
- `icon.png` - 512x512 - Addon icon (shown in addon browser)
- `fanart.jpg` - 1920x1080 - Addon fanart background

### Common Assets (common/)
- `white.png` - 1x1 white pixel (used for solid colors with colordiffuse)
- `border.png` - Simple border texture for focused items
- `checkmark.png` - Checkmark icon for watched status
- `bookmark.png` - Bookmark icon for watchlist items
- `collection.png` - Collection icon for items in collection

### Screenshots (screenshots/)
- `home.jpg` - 1920x1080 - Home screen screenshot
- `movies.jpg` - 1920x1080 - Movies page screenshot
- `shows.jpg` - 1920x1080 - Shows page screenshot
- `config.jpg` - 1920x1080 - Widget configuration screenshot

### Icons (icons/)
- Various icons for different widget types and actions

## Creating Assets

You can create these assets using any image editor. For the white.png, a simple 1x1 white pixel is sufficient as Kodi will scale it and apply colordiffuse.

For borders, a simple semi-transparent white border works well.

For status icons (checkmark, bookmark, collection), simple white icons work best as they can be colored using colordiffuse in the skin XML.

## Placeholder Generation

For testing purposes, you can generate placeholder images using ImageMagick:

```bash
# White pixel
convert -size 1x1 xc:white media/common/white.png

# Border
convert -size 10x10 xc:transparent -bordercolor white -border 2 media/common/border.png

# Icon placeholder
convert -size 512x512 xc:#1E90FF -fill white -pointsize 72 -gravity center -annotate +0+0 "AIODI" media/icon.png

# Fanart placeholder
convert -size 1920x1080 gradient:#1E90FF-#000000 media/fanart.jpg
```

## Attribution

Make sure to properly attribute any third-party assets or use your own original artwork.
