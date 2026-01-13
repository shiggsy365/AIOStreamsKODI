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

# Base Path
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper Functions
get_source_version() {
    local xml_path="$1"
    if [[ -f "$xml_path" ]]; then
        # Look for version inside the <addon tag specifically
        local version=$(grep -E "<addon " "$xml_path" | grep -m 1 "version=" | sed -n 's/.*version="\([^"]*\)".*/\1/p')
        echo "$version"
    else
        echo ""
    fi
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
        # Specifically target <addon ... version="[old]" to avoid breaking XML headers or dependencies
        if grep -qE "<addon .*version=\"$old\"" "$path"; then
            sed -i "s/\(<addon .*\)version=\"$old\"/\1version=\"$new\"/g" "$path"
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
        echo -n "$hash" > "$md5_path"
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

    local temp_dir=$(mktemp -d)
    local plugin_dir="$temp_dir/plugin.video.aiostreams"
    mkdir -p "$plugin_dir"

    rsync -a "$source_dir/" "$plugin_dir/"
    (cd "$temp_dir" && zip -r -q "$destination" plugin.video.aiostreams/)

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

    local temp_dir=$(mktemp -d)
    local skin_dir="$temp_dir/skin.AIODI"
    mkdir -p "$skin_dir"

    rsync -a --exclude='CUSTOM_SKIN_PLAN.md' \
             --exclude='IMPLEMENTATION_SUMMARY.md' \
             --exclude='TESTING_INSTRUCTIONS.md' \
             "$source_dir/" "$skin_dir/"

    (cd "$temp_dir" && zip -r -q "$destination" skin.AIODI/)
    rm -rf "$temp_dir"

    local zip_size=$(du -k "$destination" | cut -f1)
    echo -e "  ${GREEN}[+]${GRAY} Created: $destination (${zip_size} KB)${NC}"
}

build_repository_zip() {
    local destination="$1"
    local source_dir="$2"

    local dest_dir=$(dirname "$destination")
    mkdir -p "$dest_dir"

    if [[ -f "$destination" ]]; then
        rm -f "$destination"
    fi

    local temp_dir=$(mktemp -d)
    local repo_dir="$temp_dir/repository.aiostreams"
    mkdir -p "$repo_dir"

    cp "$source_dir/addon.xml" "$repo_dir/"
    cp "$source_dir/icon.png" "$repo_dir/"

    (cd "$temp_dir" && zip -r -q "$destination" repository.aiostreams/)
    rm -rf "$temp_dir"

    local zip_size=$(du -k "$destination" | cut -f1)
    echo -e "  ${GREEN}[+]${GRAY} Created: $destination (${zip_size} KB)${NC}"
}

rebuild_addons_xml() {
    local addons_xml="$BASE_DIR/docs/repository.aiostreams/zips/addons.xml"
    local addons_md5="$addons_xml.md5"
    
    echo -e "\n${CYAN}[*] Regenerating addons.xml...${NC}"
    
    # Start fresh
    echo '<?xml version="1.0" encoding="UTF-8"?>' > "$addons_xml"
    echo '<addons>' >> "$addons_xml"
    
    # Files to include
    local source_files=(
        "$BASE_DIR/docs/repository.aiostreams/addon.xml"
        "$BASE_DIR/plugin.video.aiostreams/addon.xml"
        "$BASE_DIR/skin.AIODI/addon.xml"
    )
    
    for f in "${source_files[@]}"; do
        if [[ -f "$f" ]]; then
            # Extract only the <addon>...</addon> block
            sed -n '/<addon/,/<\/addon>/p' "$f" >> "$addons_xml"
            echo "" >> "$addons_xml"
            echo -e "  ${GREEN}[+]${GRAY} Added: $(grep -m 1 "id=" "$f" | sed -n 's/.*id="\([^"]*\)".*/\1/p')${NC}"
        else
            echo -e "  ${YELLOW}[!] Warning: Source addon.xml not found: $f${NC}"
        fi
    done
    
    echo '</addons>' >> "$addons_xml"
    
    # Update checksum
    write_md5 "$addons_xml" "$addons_md5"
}

update_plugin() {
    local old_version="$1"
    local new_version="$2"

    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}Updating Plugin: $old_version -> $new_version${NC}"
    echo -e "${CYAN}========================================${NC}"

    local xml_paths=(
        "$BASE_DIR/plugin.video.aiostreams/addon.xml"
        "$BASE_DIR/docs/plugin.video.aiostreams/addon.xml"
        "$BASE_DIR/docs/repository.aiostreams/addon.xml"
    )

    local zip_dest1="$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/plugin.video.aiostreams-$new_version.zip"
    local zip_dest2="$BASE_DIR/docs/plugin.video.aiostreams/plugin.video.aiostreams-$new_version.zip"

    echo -e "\n${CYAN}[1/4] Updating version numbers...${NC}"
    for xml_path in "${xml_paths[@]}"; do
        update_kodi_file "$xml_path" "$old_version" "$new_version"
    done

    echo -e "\n${CYAN}[2/4] Building plugin ZIP files...${NC}"
    build_plugin_zip "$zip_dest1" "$BASE_DIR/plugin.video.aiostreams"
    build_plugin_zip "$zip_dest2" "$BASE_DIR/plugin.video.aiostreams"
    
    write_md5 "$zip_dest1" "$zip_dest1.md5"
    write_md5 "$zip_dest2" "$zip_dest2.md5"

    local repo_xml="$BASE_DIR/docs/repository.aiostreams/addon.xml"
    local repo_version=$(grep -m 1 "id=\"repository.aiostreams\"" "$repo_xml" | sed -n 's/.*version="\([^"]*\)".*/\1/p')
    if [[ -z "$repo_version" ]]; then repo_version="1.0.0"; fi

    echo -e "\n${CYAN}[3/4] Rebuilding repository ZIPs...${NC}"
    local repo_zip_id_dir="$BASE_DIR/docs/repository.aiostreams/zips/repository.aiostreams"
    mkdir -p "$repo_zip_id_dir"
    
    build_repository_zip "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams"
    local internal_repo_zip="$repo_zip_id_dir/repository.aiostreams-$repo_version.zip"
    cp "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$internal_repo_zip"
    
    write_md5 "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip.md5"
    write_md5 "$internal_repo_zip" "$internal_repo_zip.md5"
    
    echo -e "  ${GREEN}[+]${GRAY} Copying assets to repository directory${NC}"
    mkdir -p "$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/"
    cp "$BASE_DIR/plugin.video.aiostreams/resources/icon.png" "$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/" 2>/dev/null || true
    cp "$BASE_DIR/plugin.video.aiostreams/resources/fanart.jpg" "$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/" 2>/dev/null || true
    cp "$BASE_DIR/plugin.video.aiostreams/addon.xml" "$BASE_DIR/docs/repository.aiostreams/zips/plugin.video.aiostreams/addon.xml"

    for f in "$repo_zip_id_dir"/repository.aiostreams-*.zip; do
        if [[ -f "$f" && "$f" != "$internal_repo_zip" ]]; then
            rm -f "$f" "$f.md5"
            echo -e "  ${GREEN}[+]${GRAY} Deleted old repo version: $(basename "$f")${NC}"
        fi
    done

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
        fi
    fi

    echo -e "\n${GREEN}[+] Plugin update complete: $new_version${NC}"
}

update_skin() {
    local old_version="$1"
    local new_version="$2"

    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}Updating Skin: $old_version -> $new_version${NC}"
    echo -e "${CYAN}========================================${NC}"

    local xml_paths=(
        "$BASE_DIR/skin.AIODI/addon.xml"
        "$BASE_DIR/docs/skin.AIODI/addon.xml"
        "$BASE_DIR/docs/repository.aiostreams/addon.xml"
    )

    local zip_dest_repo="$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/skin.AIODI-$new_version.zip"
    local zip_dest_docs="$BASE_DIR/docs/skin.AIODI/skin.AIODI-$new_version.zip"

    echo -e "\n${CYAN}[1/4] Updating version numbers...${NC}"
    for xml_path in "${xml_paths[@]}"; do
        update_kodi_file "$xml_path" "$old_version" "$new_version"
    done

    echo -e "\n${CYAN}[2/4] Building skin ZIP file...${NC}"
    build_skin_zip "$zip_dest_repo" "$BASE_DIR/skin.AIODI"
    cp "$zip_dest_repo" "$zip_dest_docs"

    write_md5 "$zip_dest_repo" "$zip_dest_repo.md5"
    write_md5 "$zip_dest_docs" "$zip_dest_docs.md5"

    echo -e "  ${GREEN}[+]${GRAY} Copying assets to repository directory${NC}"
    mkdir -p "$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/"
    cp "$BASE_DIR/skin.AIODI/resources/icon.png" "$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/" 2>/dev/null || true
    cp "$BASE_DIR/skin.AIODI/resources/fanart.jpg" "$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/" 2>/dev/null || true
    cp "$BASE_DIR/skin.AIODI/addon.xml" "$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/addon.xml"

    local repo_xml="$BASE_DIR/docs/repository.aiostreams/addon.xml"
    local repo_version=$(grep -m 1 "id=\"repository.aiostreams\"" "$repo_xml" | sed -n 's/.*version="\([^"]*\)".*/\1/p')
    if [[ -z "$repo_version" ]]; then repo_version="1.0.0"; fi

    echo -e "\n${CYAN}[3/4] Rebuilding repository ZIPs...${NC}"
    local repo_zip_id_dir="$BASE_DIR/docs/repository.aiostreams/zips/repository.aiostreams"
    mkdir -p "$repo_zip_id_dir"
    build_repository_zip "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams"
    local internal_repo_zip="$repo_zip_id_dir/repository.aiostreams-$repo_version.zip"
    cp "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$internal_repo_zip"

    write_md5 "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip" "$BASE_DIR/docs/repository.aiostreams-1.0.0.zip.md5"
    write_md5 "$internal_repo_zip" "$internal_repo_zip.md5"
    
    for f in "$repo_zip_id_dir"/repository.aiostreams-*.zip; do
        if [[ -f "$f" && "$f" != "$internal_repo_zip" ]]; then
            rm -f "$f" "$f.md5"
            echo -e "  ${GREEN}[+]${GRAY} Deleted old repo version: $(basename "$f")${NC}"
        fi
    done

    echo -e "\n${CYAN}[4/4] Checking for old version files...${NC}"
    local old_zip_path_repo="$BASE_DIR/docs/repository.aiostreams/zips/skin.AIODI/skin.AIODI-$old_version.zip"
    local old_zip_path_docs="$BASE_DIR/docs/skin.AIODI/skin.AIODI-$old_version.zip"

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
        fi
    fi

    echo -e "\n${GREEN}[+] Skin update complete: $new_version${NC}"
}


push_to_git() {
    echo -e "\n${CYAN}[*] Pushing changes to main branch...${NC}"
    git add .
    local plugin_v=$(get_source_version "$BASE_DIR/plugin.video.aiostreams/addon.xml")
    local skin_v=$(get_source_version "$BASE_DIR/skin.AIODI/addon.xml")
    git commit -m "Repository Update: Plugin $plugin_v, Skin $skin_v"
    git push origin main
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}[+]${GRAY} Successfully pushed to main branch${NC}"
    else
        echo -e "  ${RED}[!] Error: Failed to push to main branch${NC}"
    fi
}

# Main Script
clear
echo -e "\n${CYAN}========================================${NC}"
echo -e "${CYAN}AIOStreams Repository Update Tool${NC}"
echo -e "${CYAN}========================================${NC}"

# Detect current versions
echo -e "\n${YELLOW}Detecting current versions...${NC}"

plugin_version=$(get_source_version "$BASE_DIR/plugin.video.aiostreams/addon.xml")
skin_version=$(get_source_version "$BASE_DIR/skin.AIODI/addon.xml")

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
            echo -e "\n${RED}[!] Error: Could not detect plugin version${NC}"
            exit 1
        fi
        new_plugin_version=$(increment_version "$plugin_version")
        echo -e "\n${YELLOW}Plugin will be updated: $plugin_version -> $new_plugin_version${NC}"
        read -p "Continue? (y/n) " confirm
        if [[ "$confirm" == "y" ]] || [[ "$confirm" == "Y" ]]; then
            update_plugin "$plugin_version" "$new_plugin_version"
            rebuild_addons_xml
        fi
        ;;
    2)
        if [[ -z "$skin_version" ]]; then
            echo -e "\n${RED}[!] Error: Could not detect skin version${NC}"
            exit 1
        fi
        new_skin_version=$(increment_version "$skin_version")
        echo -e "\n${YELLOW}Skin will be updated: $skin_version -> $new_skin_version${NC}"
        read -p "Continue? (y/n) " confirm
        if [[ "$confirm" == "y" ]] || [[ "$confirm" == "Y" ]]; then
            update_skin "$skin_version" "$new_skin_version"
            rebuild_addons_xml
        fi
        ;;
    3)
        if [[ -z "$plugin_version" ]] || [[ -z "$skin_version" ]]; then
            echo -e "\n${RED}[!] Error: Could not detect both versions${NC}"
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
            rebuild_addons_xml
        fi
        ;;
    *)
        echo -e "\n${RED}[!] Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "\n${CYAN}========================================${NC}"
echo -e "${GREEN}[+] Update process complete!${NC}"
echo -e "${CYAN}========================================${NC}"

echo -e "\n${YELLOW}Would you like to push these changes to GitHub main branch? (y/n)${NC}"
read -p "Choice: " push_confirm
if [[ "$push_confirm" == "y" ]] || [[ "$push_confirm" == "Y" ]]; then
    push_to_git
fi

echo ""
