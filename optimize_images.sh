#!/bin/bash
# AIOStreams Skin Image Optimization Script
# Automatically optimizes PNG files for faster loading

set -e

echo "==========================================="
echo "AIOStreams Skin Image Optimization Script"
echo "==========================================="
echo ""

# Check for required tools
HAS_CONVERT=false
HAS_OPTIPNG=false
HAS_PNGQUANT=false

if command -v convert &> /dev/null; then
    HAS_CONVERT=true
    echo "✓ ImageMagick (convert) found"
else
    echo "✗ ImageMagick not found (install: apt-get install imagemagick)"
fi

if command -v optipng &> /dev/null; then
    HAS_OPTIPNG=true
    echo "✓ optipng found"
else
    echo "✗ optipng not found (install: apt-get install optipng)"
fi

if command -v pngquant &> /dev/null; then
    HAS_PNGQUANT=true
    echo "✓ pngquant found"
else
    echo "✗ pngquant not found (install: apt-get install pngquant)"
fi

echo ""

if [ "$HAS_CONVERT" = false ] && [ "$HAS_OPTIPNG" = false ] && [ "$HAS_PNGQUANT" = false ]; then
    echo "ERROR: No image optimization tools found!"
    echo "Install at least one of: imagemagick, optipng, pngquant"
    echo ""
    echo "Ubuntu/Debian:"
    echo "  sudo apt-get install imagemagick optipng pngquant"
    echo ""
    echo "macOS:"
    echo "  brew install imagemagick optipng pngquant"
    exit 1
fi

# Navigate to skin directory
cd "$(dirname "$0")/skin.AIODI"

echo "Working directory: $(pwd)"
echo ""

# Backup original files
BACKUP_DIR="../skin_images_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup at: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR/extras"
mkdir -p "$BACKUP_DIR/media"
mkdir -p "$BACKUP_DIR/resources"

# Function to get file size in human readable format
get_size() {
    du -h "$1" | cut -f1
}

# Function to optimize a single image
optimize_image() {
    local file="$1"
    local original_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")

    echo "Processing: $file"
    echo "  Original size: $(get_size "$file")"

    # Backup
    cp "$file" "$BACKUP_DIR/$file"

    # Step 1: Resize if oversized (for large backgrounds)
    if [ "$HAS_CONVERT" = true ]; then
        # Check dimensions
        dimensions=$(identify -format "%wx%h" "$file" 2>/dev/null || echo "")
        if [ ! -z "$dimensions" ]; then
            width=$(echo $dimensions | cut -dx -f1)
            if [ "$width" -gt 1920 ]; then
                echo "  Resizing from $dimensions to 1920x1080..."
                convert "$file" -resize 1920x1080 -strip "$file.tmp"
                mv "$file.tmp" "$file"
            fi

            # Remove alpha channel if not needed
            if [[ "$file" == *"splash.png"* ]] || [[ "$file" == *"background.png"* ]]; then
                echo "  Removing alpha channel..."
                convert "$file" -alpha off "$file.tmp"
                mv "$file.tmp" "$file"
            fi
        fi
    fi

    # Step 2: Lossless optimization
    if [ "$HAS_OPTIPNG" = true ]; then
        echo "  Running optipng..."
        optipng -o7 -strip all -quiet "$file" || true
    fi

    # Step 3: Lossy compression (high quality)
    if [ "$HAS_PNGQUANT" = true ]; then
        echo "  Running pngquant..."
        pngquant --quality=85-95 --ext .png --force --speed 1 "$file" 2>/dev/null || true
    fi

    # Calculate savings
    local new_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")
    local saved=$((original_size - new_size))
    local percent=$((saved * 100 / original_size))

    echo "  New size: $(get_size "$file")"
    echo "  Saved: $((saved / 1024)) KB ($percent%)"
    echo ""
}

# Optimize priority files
echo "==========================================="
echo "Optimizing Priority Images"
echo "==========================================="
echo ""

TOTAL_SAVED=0

# High priority files
PRIORITY_FILES=(
    "extras/splash.png"
    "extras/background.png"
    "media/more.png"
    "resources/icon.png"
    "media/logonew.png"
    "media/logo_unfocused.png"
)

for file in "${PRIORITY_FILES[@]}"; do
    if [ -f "$file" ]; then
        before=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")
        optimize_image "$file"
        after=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")
        TOTAL_SAVED=$((TOTAL_SAVED + before - after))
    else
        echo "Skipping $file (not found)"
        echo ""
    fi
done

echo "==========================================="
echo "Optimization Complete!"
echo "==========================================="
echo ""
echo "Total space saved: $((TOTAL_SAVED / 1024 / 1024)) MB"
echo "Backup location: $BACKUP_DIR"
echo ""
echo "To restore backups if needed:"
echo "  cp -r $BACKUP_DIR/* skin.AIODI/"
echo ""
echo "Next steps:"
echo "1. Test skin startup time (should be 1-2 seconds faster)"
echo "2. Verify image quality looks good"
echo "3. If satisfied, delete backup: rm -rf $BACKUP_DIR"
echo ""
