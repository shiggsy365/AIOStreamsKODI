#!/bin/bash
# Deploy changes to local Kodi installation
# Usage: ./deploy_local.sh

# Destination directory
DEST_DIR="$HOME/.kodi/addons"

echo "========================================"
echo "Deploying to $DEST_DIR"
echo "========================================"

# Check if destination exists
if [ ! -d "$DEST_DIR" ]; then
    echo "Error: Kodi addons directory not found at $DEST_DIR"
    exit 1
fi

# Copy Skin
echo "[+] Copying skin.AIODI..."
rm -rf "$DEST_DIR/skin.AIODI"
cp -rf "$(pwd)/skin.AIODI" "$DEST_DIR/"

# Copy AIOStreams Plugin
echo "[+] Copying plugin.video.aiostreams..."
rm -rf "$DEST_DIR/plugin.video.aiostreams"
cp -rf "$(pwd)/plugin.video.aiostreams" "$DEST_DIR/"

# Copy IMVDb Plugin
echo "[+] Copying plugin.video.imvdb..."
rm -rf "$DEST_DIR/plugin.video.imvdb"
cp -rf "$(pwd)/plugin.video.imvdb" "$DEST_DIR/"

# Copy Onboarding Wizard
echo "[+] Copying script.aiodi.onboarding..."
rm -rf "$DEST_DIR/script.aiodi.onboarding"
cp -rf "$(pwd)/script.aiodi.onboarding" "$DEST_DIR/"

echo "========================================"
echo "Deployment Complete!"
echo "Please reload your skin to see changes."
echo "========================================"
