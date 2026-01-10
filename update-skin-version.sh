#!/bin/bash
# AIODI Skin Version Update Script (Linux/Mac)
# Updates version number, creates new ZIP, updates checksums, and deploys to repository

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# 1. Inputs
echo -e "${CYAN}========================================"
echo "AIODI Skin Version Update Tool"
echo -e "========================================${NC}"
read -p "Enter the Old Skin Version (e.g., 1.0.0): " OLDREF
read -p "Enter the New Skin Version (e.g., 1.0.1): " NEWREF

# Get the base directory (script's parent directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# File paths
SKIN_ADDON_XML="$BASE_DIR/skin.AIODI/addon.xml"
REPO_ADDONS_XML="$BASE_DIR/docs/repository.aiostreams/zips/addons.xml"
REPO_ADDONS_MD5="$BASE_DIR/docs/repository.aiostreams/zips/addons.xml.md5"

# ZIP paths
ZIP_DIR="$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi"
NEW_ZIP="$ZIP_DIR/skin.aiodi-$NEWREF.zip"
NEW_ZIP_MD5="$NEW_ZIP.md5"
OLD_ZIP="$ZIP_DIR/skin.aiodi-$OLDREF.zip"
OLD_ZIP_MD5="$OLD_ZIP.md5"

echo -e "${YELLOW}Old Version: $OLDREF${NC}"
echo -e "${GREEN}New Version: $NEWREF${NC}"
echo -e "${CYAN}========================================${NC}\n"

# 2. Update Version Numbers
echo -e "${CYAN}[1/5] Updating version numbers in XML files...${NC}"

update_xml_version() {
    local file=$1
    if [ -f "$file" ]; then
        if grep -q "$OLDREF" "$file"; then
            sed -i "s/$OLDREF/$NEWREF/g" "$file"
            echo -e "${GRAY}  ✓ Updated: $file${NC}"
        else
            echo -e "${GRAY}  ℹ No changes needed: $file${NC}"
        fi
    else
        echo -e "${YELLOW}  ✗ Warning: File not found - $file${NC}"
    fi
}

update_xml_version "$SKIN_ADDON_XML"
update_xml_version "$REPO_ADDONS_XML"

# 3. Create ZIP File
echo -e "\n${CYAN}[2/5] Building skin ZIP file...${NC}"

# Create ZIP directory if it doesn't exist
mkdir -p "$ZIP_DIR"
echo -e "${GRAY}  ✓ Ensured directory exists: $ZIP_DIR${NC}"

# Remove old ZIP if it exists
if [ -f "$NEW_ZIP" ]; then
    rm "$NEW_ZIP"
    echo -e "${GRAY}  ✓ Removed existing ZIP${NC}"
fi

# Create ZIP excluding development documentation
cd "$BASE_DIR/skin.AIODI"
zip -r "$NEW_ZIP" . \
    -x "CUSTOM_SKIN_PLAN.md" \
    -x "IMPLEMENTATION_SUMMARY.md" \
    -x "TESTING_INSTRUCTIONS.md" \
    > /dev/null

cd "$BASE_DIR"

ZIP_SIZE=$(du -h "$NEW_ZIP" | cut -f1)
echo -e "${GREEN}  ✓ Created: $NEW_ZIP ($ZIP_SIZE)${NC}"

# 4. Generate Checksums
echo -e "\n${CYAN}[3/5] Generating MD5 checksums...${NC}"

generate_md5() {
    local file=$1
    local md5_file="${file}.md5"

    if [ -f "$file" ]; then
        if command -v md5sum &> /dev/null; then
            # Linux
            md5sum "$file" > "$md5_file"
        elif command -v md5 &> /dev/null; then
            # macOS
            md5 -r "$file" | awk '{print $1"  "$2}' > "$md5_file"
        else
            echo -e "${RED}  ✗ Error: No MD5 command available${NC}"
            return 1
        fi
        echo -e "${GRAY}  ✓ Created: $(basename "$md5_file")${NC}"
    else
        echo -e "${YELLOW}  ✗ Warning: File not found - $file${NC}"
    fi
}

# Generate MD5 for new ZIP
generate_md5 "$NEW_ZIP"

# Generate MD5 for addons.xml
generate_md5 "$REPO_ADDONS_XML"

# 5. Cleanup Old Version
echo -e "\n${CYAN}[4/5] Checking for old version files...${NC}"

if [ -f "$OLD_ZIP" ]; then
    read -p "Found old version $OLDREF. Delete old ZIP files? (y/n): " cleanup
    if [ "$cleanup" = "y" ] || [ "$cleanup" = "Y" ]; then
        rm -f "$OLD_ZIP"
        echo -e "${GRAY}  ✓ Deleted: $OLD_ZIP${NC}"

        if [ -f "$OLD_ZIP_MD5" ]; then
            rm -f "$OLD_ZIP_MD5"
            echo -e "${GRAY}  ✓ Deleted: $OLD_ZIP_MD5${NC}"
        fi
    else
        echo -e "${GRAY}  ℹ Keeping old version files${NC}"
    fi
else
    echo -e "${GRAY}  ℹ No old version files found${NC}"
fi

# 6. Verification & Summary
echo -e "\n${CYAN}[5/5] Verifying deployment...${NC}"

ALL_VALID=true

verify_file() {
    local file=$1
    local desc=$2
    local check_version=$3

    if [ -f "$file" ]; then
        if [ "$check_version" = "true" ]; then
            if grep -q "$NEWREF" "$file"; then
                echo -e "${GREEN}  ✓ $desc - Version updated${NC}"
            else
                echo -e "${RED}  ✗ $desc - Version NOT found!${NC}"
                ALL_VALID=false
            fi
        else
            echo -e "${GREEN}  ✓ $desc - Exists${NC}"
        fi
    else
        echo -e "${RED}  ✗ $desc - Missing!${NC}"
        ALL_VALID=false
    fi
}

verify_file "$SKIN_ADDON_XML" "Skin addon.xml" "true"
verify_file "$REPO_ADDONS_XML" "Repository addons.xml" "true"
verify_file "$NEW_ZIP" "Skin ZIP file" "false"
verify_file "$NEW_ZIP_MD5" "Skin ZIP MD5" "false"
verify_file "$REPO_ADDONS_MD5" "Repository addons.xml MD5" "false"

# Final Summary
echo -e "\n${CYAN}========================================${NC}"
if [ "$ALL_VALID" = true ]; then
    echo -e "${GREEN}✓ SUCCESS! Skin version $NEWREF deployed!${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo -e "  1. Review changes in Git"
    echo -e "  2. Test the new ZIP in Kodi"
    echo -e "  3. Commit changes:"
    echo -e "${GRAY}     git add skin.AIODI/ docs/${NC}"
    echo -e "${GRAY}     git commit -m 'Update AIODI skin to v$NEWREF'${NC}"
    echo -e "${GRAY}     git push${NC}"
    echo -e "\n${CYAN}  ZIP Location: $NEW_ZIP${NC}"
else
    echo -e "${RED}✗ ERRORS DETECTED - Please review!${NC}"
    echo -e "${CYAN}========================================${NC}"
fi

echo ""
