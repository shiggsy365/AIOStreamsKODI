#!/bin/bash
# AIOStreams Repository Update Tool
# Unified script for updating plugin and/or skin versions

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Base Path - Update this to your actual path
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper Functions
get_latest_version() {
    local docs_path="$1"

    if [[ ! -d "$docs_path" ]]; then
        echo ""
        return
    fi

    local latest_version=""
    local max_major=0
    local max_minor=0
    local max_patch=0

    for zip_file in "$docs_path"/*.zip; do
        if [[ -f "$zip_file" ]]; then
            local filename=$(basename "$zip_file")
            if [[ $filename =~ -([0-9]+)\.([0-9]+)\.([0-9]+)\.zip$ ]]; then
                local major="${BASH_REMATCH[1]}"
                local minor="${BASH_REMATCH[2]}"
                local patch="${BASH_REMATCH[3]}"

                if [[ $major -gt $max_major ]] || \
                   [[ $major -eq $max_major && $minor -gt $max_minor ]] || \
                   [[ $major -eq $max_major && $minor -eq $max_minor && $patch -gt $max_patch ]]; then
                    max_major=$major
                    max_minor=$minor
                    max_patch=$patch
                    latest_version="$major.$minor.$patch"
                fi
            fi
        fi
    done

    echo "$latest_version"
}

increment_version() {
    local version="$1"

    if [[ $version =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        local major="${BASH_REMATCH[1]}"
        local minor="${BASH_REMATCH[2]}"
        local patch="${BASH_REMATCH[3]}"

        patch=$((patch + 1))
        echo "$major.$minor.$patch"
    else
        echo ""
    fi
}

update_kodi_file() {
    local path="$1"
    local old="$2"
    local new="$3"

    if [[ -f "$path" ]]; then
        if grep -q "$old" "$path"; then
            sed -i "s/$old/$new/g" "$path"
            echo -e "  ${GREEN}[+]${GRAY} Updated: $path${NC}"
        else
            echo -e "  ${GRAY}[i] No changes needed: $path${NC}"
        fi
    else
        echo -e "  ${YELLOW}[!] Warning: Path not found - $path${NC}"
    fi
}

write_md5() {
    local target_file="$1"
    local md5_path="$2"

    if [[ -f "$target_file" ]]; then
        local filename=$(basename "$target_file")
        local hash=$(md5sum "$target_file" | awk '{print $1}')
        echo "$hash  $filename" > "$md5_path"
        echo -e "  ${GREEN}[+]${GRAY} Created: $(basename "$md5_path")${NC}"
    else
        echo -e "  ${YELLOW}[!] Warning: File not found - $target_file${NC}"
    fi
}

build_plugin_zip() {
    local destination="$1"
    local source_dir="$2"

    local dest_dir=$(dirname "$destination")
    mkdir -p "$dest_dir"

    if [[ -f "$destination" ]]; then
        rm -f "$destination"
    fi

    # Create temporary directory for ZIP structure
    local temp_dir=$(mktemp -d)
    local plugin_dir="$temp_dir/plugin.video.aiostreams"
    mkdir -p "$plugin_dir"

    # Copy all files to temp directory
    cp -r "$source_dir"/* "$plugin_dir/"

    # Create ZIP from temp directory
    (cd "$temp_dir" && zip -r -q "$destination" plugin.video.aiostreams/)

    # Cleanup
    rm -rf "$temp_dir"

    local zip_size=$(du -k "$destination" | cut -f1)
    echo -e "  ${GREEN}[+]${GRAY} Created: $destination (${zip_size} KB)${NC}"
}

build_skin_zip() {
    local destination="$1"
    local source_dir="$2"

    local dest_dir=$(dirname "$destination")
    mkdir -p "$dest_dir"

    if [[ -f "$destination" ]]; then
        rm -f "$destination"
    fi

    # Create temporary directory for ZIP structure
    local temp_dir=$(mktemp -d)
    local skin_dir="$temp_dir/skin.aiodi"
    mkdir -p "$skin_dir"

    # Copy all files except excluded ones
    rsync -a --exclude='CUSTOM_SKIN_PLAN.md' \
             --exclude='IMPLEMENTATION_SUMMARY.md' \
             --exclude='TESTING_INSTRUCTIONS.md' \
             "$source_dir/" "$skin_dir/"

    # Create ZIP from temp directory
    (cd "$temp_dir" && zip -r -q "$destination" skin.aiodi/)

    # Cleanup
    rm -rf "$temp_dir"

    local zip_size=$(du -k "$destination" | cut -f1)
    echo -e "  ${GREEN}[+]${GRAY} Created: $destination (${zip_size} KB)${NC}"
}

update_plugin() {
    local old_version="$1"
    local new_version="$2"

    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}Updating Plugin: $old_version -> $new_version${NC}"
    echo -e "${CYAN}========================================${NC}"

    # File paths for plugin
    local xml_paths=(
        "$BASE_DIR/plugin.video.aiostreams/addon.xml"
        "$BASE_DIR/docs/plugin.video.aiostreams/addon.xml"
        "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml"
        "$BASE_DIR/docs/index.html"
    )

    local zip_dest1="$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/plugin.video.aiostreams-$new_version.zip"
    local zip_dest2="$BASE_DIR/docs/plugin.video.aiostreams/plugin.video.aiostreams-$new_version.zip"

    # Update version numbers
    echo -e "\n${CYAN}[1/4] Updating version numbers...${NC}"
    for xml_path in "${xml_paths[@]}"; do
        update_kodi_file "$xml_path" "$old_version" "$new_version"
    done

    # Create ZIP files
    echo -e "\n${CYAN}[2/4] Building plugin ZIP files...${NC}"
    build_plugin_zip "$zip_dest1" "$BASE_DIR/plugin.video.aiostreams"
    build_plugin_zip "$zip_dest2" "$BASE_DIR/plugin.video.aiostreams"

    # Generate checksums
    echo -e "\n${CYAN}[3/4] Generating MD5 checksums...${NC}"
    write_md5 "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip.md5"
    write_md5 "$BASE_DIR/docs/repository.aiostreams/zips/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams/zips/repository.aiostreams-1.0.0.zip.md5"
    write_md5 "$zip_dest1" "$zip_dest1.md5"
    write_md5 "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml" "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml.md5"
    write_md5 "$zip_dest2" "$zip_dest2.md5"

    # Cleanup old version
    echo -e "\n${CYAN}[4/4] Checking for old version files...${NC}"
    local old_zip_path1="$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/plugin.video.aiostreams-$old_version.zip"
    local old_zip_path2="$BASE_DIR/docs/plugin.video.aiostreams/plugin.video.aiostreams-$old_version.zip"

    if [[ -f "$old_zip_path1" ]] || [[ -f "$old_zip_path2" ]]; then
        read -p "Found old plugin version $old_version. Delete old ZIP files? (y/n) " cleanup
        if [[ "$cleanup" == "y" ]] || [[ "$cleanup" == "Y" ]]; then
            if [[ -f "$old_zip_path1" ]]; then
                rm -f "$old_zip_path1" "$old_zip_path1.md5"
                echo -e "  ${GREEN}[+]${GRAY} Deleted: $old_zip_path1${NC}"
            fi
            if [[ -f "$old_zip_path2" ]]; then
                rm -f "$old_zip_path2" "$old_zip_path2.md5"
                echo -e "  ${GREEN}[+]${GRAY} Deleted: $old_zip_path2${NC}"
            fi
        else
            echo -e "  ${GRAY}[i] Keeping old version files${NC}"
        fi
    else
        echo -e "  ${GRAY}[i] No old version files found${NC}"
    fi

    echo -e "\n${GREEN}[+] Plugin update complete: $new_version${NC}"
}

update_skin() {
    local old_version="$1"
    local new_version="$2"

    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}Updating Skin: $old_version -> $new_version${NC}"
    echo -e "${CYAN}========================================${NC}"

    # File paths for skin
    local xml_paths=(
        "$BASE_DIR/skin.AIODI/addon.xml"
        "$BASE_DIR/docs/skin.aiodi/addon.xml"
        "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml"
    )

    local zip_dest_repo="$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi/skin.aiodi-$new_version.zip"
    local zip_dest_docs="$BASE_DIR/docs/skin.aiodi/skin.aiodi-$new_version.zip"

    # Update version numbers
    echo -e "\n${CYAN}[1/4] Updating version numbers...${NC}"
    for xml_path in "${xml_paths[@]}"; do
        update_kodi_file "$xml_path" "$old_version" "$new_version"
    done

    # Create ZIP files
    echo -e "\n${CYAN}[2/4] Building skin ZIP file...${NC}"
    build_skin_zip "$zip_dest_repo" "$BASE_DIR/skin.AIODI"
    echo -e "  ${GREEN}[+]${GRAY} Copying ZIP to docs/skin.aiodi/${NC}"
    cp "$zip_dest_repo" "$zip_dest_docs"

    # Copy assets to repository resources directory (for Kodi browsing)
    echo -e "  ${GREEN}[+]${GRAY} Copying assets to repository resources directory${NC}"
    mkdir -p "$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi/resources"
    cp "$BASE_DIR/skin.AIODI/resources/icon.png" "$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi/resources/"
    cp "$BASE_DIR/skin.AIODI/resources/fanart.jpg" "$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi/resources/"

    # Generate checksums
    echo -e "\n${CYAN}[3/4] Generating MD5 checksums...${NC}"
    write_md5 "$zip_dest_repo" "$zip_dest_repo.md5"
    write_md5 "$zip_dest_docs" "$zip_dest_docs.md5"
    write_md5 "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml" "$BASE_DIR/docs/repository.aiostreams/zips/addons.xml.md5"

    # Cleanup old version
    echo -e "\n${CYAN}[4/4] Checking for old version files...${NC}"
    local old_zip_path_repo="$BASE_DIR/docs/repository.aiostreams/zips/skin.aiodi/skin.aiodi-$old_version.zip"
    local old_zip_path_docs="$BASE_DIR/docs/skin.aiodi/skin.aiodi-$old_version.zip"

    if [[ -f "$old_zip_path_repo" ]] || [[ -f "$old_zip_path_docs" ]]; then
        read -p "Found old skin version $old_version. Delete old ZIP files? (y/n) " cleanup
        if [[ "$cleanup" == "y" ]] || [[ "$cleanup" == "Y" ]]; then
            if [[ -f "$old_zip_path_repo" ]]; then
                rm -f "$old_zip_path_repo" "$old_zip_path_repo.md5"
                echo -e "  ${GREEN}[+]${GRAY} Deleted: $old_zip_path_repo${NC}"
            fi
            if [[ -f "$old_zip_path_docs" ]]; then
                rm -f "$old_zip_path_docs" "$old_zip_path_docs.md5"
                echo -e "  ${GREEN}[+]${GRAY} Deleted: $old_zip_path_docs${NC}"
            fi
        else
            echo -e "  ${GRAY}[i] Keeping old version files${NC}"
        fi
    else
        echo -e "  ${GRAY}[i] No old version files found${NC}"
    fi

    echo -e "\n${GREEN}[+] Skin update complete: $new_version${NC}"
}

# Main Script
clear
echo -e "\n${CYAN}========================================${NC}"
echo -e "${CYAN}AIOStreams Repository Update Tool${NC}"
echo -e "${CYAN}========================================${NC}"

# Detect current versions
echo -e "\n${YELLOW}Detecting current versions...${NC}"

plugin_version=$(get_latest_version "$BASE_DIR/docs/plugin.video.aiostreams")
skin_version=$(get_latest_version "$BASE_DIR/docs/skin.aiodi")

if [[ -n "$plugin_version" ]]; then
    echo -e "  ${WHITE}Plugin current version: $plugin_version${NC}"
else
    echo -e "  ${GRAY}Plugin version: Not found${NC}"
fi

if [[ -n "$skin_version" ]]; then
    echo -e "  ${WHITE}Skin current version: $skin_version${NC}"
else
    echo -e "  ${GRAY}Skin version: Not found${NC}"
fi

echo -e "\n${CYAN}========================================${NC}"
echo -e "${YELLOW}What would you like to update?${NC}"
echo -e "  ${WHITE}1. Plugin only${NC}"
echo -e "  ${WHITE}2. Skin only${NC}"
echo -e "  ${WHITE}3. Both plugin and skin${NC}"
echo -e "${CYAN}========================================${NC}"

read -p $'\nEnter your choice (1, 2, or 3): ' choice

case "$choice" in
    1)
        if [[ -z "$plugin_version" ]]; then
            echo -e "\n${RED}[!] Error: Could not detect plugin version. Please check docs/plugin.video.aiostreams/${NC}"
            exit 1
        fi
        new_plugin_version=$(increment_version "$plugin_version")
        echo -e "\n${YELLOW}Plugin will be updated: $plugin_version -> $new_plugin_version${NC}"
        read -p "Continue? (y/n) " confirm
        if [[ "$confirm" == "y" ]] || [[ "$confirm" == "Y" ]]; then
            update_plugin "$plugin_version" "$new_plugin_version"
        else
            echo -e "\n${GRAY}[i] Update cancelled${NC}"
        fi
        ;;
    2)
        if [[ -z "$skin_version" ]]; then
            echo -e "\n${RED}[!] Error: Could not detect skin version. Please check docs/skin.aiodi/${NC}"
            exit 1
        fi
        new_skin_version=$(increment_version "$skin_version")
        echo -e "\n${YELLOW}Skin will be updated: $skin_version -> $new_skin_version${NC}"
        read -p "Continue? (y/n) " confirm
        if [[ "$confirm" == "y" ]] || [[ "$confirm" == "Y" ]]; then
            update_skin "$skin_version" "$new_skin_version"
        else
            echo -e "\n${GRAY}[i] Update cancelled${NC}"
        fi
        ;;
    3)
        can_proceed=true

        if [[ -z "$plugin_version" ]]; then
            echo -e "\n${RED}[!] Error: Could not detect plugin version${NC}"
            can_proceed=false
        fi
        if [[ -z "$skin_version" ]]; then
            echo -e "${RED}[!] Error: Could not detect skin version${NC}"
            can_proceed=false
        fi

        if [[ "$can_proceed" == false ]]; then
            echo -e "\n${YELLOW}Please check docs folder for version detection issues${NC}"
            exit 1
        fi

        new_plugin_version=$(increment_version "$plugin_version")
        new_skin_version=$(increment_version "$skin_version")

        echo -e "\n${YELLOW}Updates planned:${NC}"
        echo -e "  ${WHITE}Plugin: $plugin_version -> $new_plugin_version${NC}"
        echo -e "  ${WHITE}Skin: $skin_version -> $new_skin_version${NC}"

        read -p $'\nContinue? (y/n) ' confirm
        if [[ "$confirm" == "y" ]] || [[ "$confirm" == "Y" ]]; then
            update_plugin "$plugin_version" "$new_plugin_version"
            update_skin "$skin_version" "$new_skin_version"
        else
            echo -e "\n${GRAY}[i] Update cancelled${NC}"
        fi
        ;;
    *)
        echo -e "\n${RED}[!] Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

echo -e "\n${CYAN}========================================${NC}"
echo -e "${GREEN}[+] Update process complete!${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  ${WHITE}1. Review changes in Git${NC}"
echo -e "  ${WHITE}2. Test the new ZIP files in Kodi${NC}"
echo -e "  ${WHITE}3. Commit and push changes${NC}"
echo ""
