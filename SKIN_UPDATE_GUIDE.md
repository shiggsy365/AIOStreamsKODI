# AIODI Skin Update Guide

This guide explains how to use the automated skin version update scripts.

## Overview

Two scripts are provided for updating the AIODI skin version:
- **Update-Skin-Version.ps1** - PowerShell script (Windows)
- **update-skin-version.sh** - Bash script (Linux/Mac)

Both scripts automate the entire version update process.

## What the Scripts Do

The scripts automate the following tasks:

1. ✅ **Update Version Numbers**
   - Updates `skin.AIODI/addon.xml`
   - Updates `docs/repository.aiostreams/zips/addons.xml`

2. ✅ **Create New ZIP Package**
   - Creates `skin.aiodi-[VERSION].zip` from skin.AIODI directory
   - Excludes development files (CUSTOM_SKIN_PLAN.md, IMPLEMENTATION_SUMMARY.md, TESTING_INSTRUCTIONS.md)
   - Places ZIP in `docs/repository.aiostreams/zips/skin.aiodi/`

3. ✅ **Generate MD5 Checksums**
   - Creates checksum for the new ZIP file
   - Updates checksum for addons.xml

4. ✅ **Cleanup Old Versions** (optional)
   - Prompts to delete old version ZIP files
   - Keeps repository clean

5. ✅ **Verify Deployment**
   - Checks all files were created correctly
   - Confirms version numbers were updated
   - Provides next steps

## Usage

### Windows (PowerShell)

1. **Open PowerShell** in the repository root directory

2. **Run the script**:
   ```powershell
   .\Update-Skin-Version.ps1
   ```

3. **Enter version numbers** when prompted:
   ```
   Enter the Old Skin Version (e.g., 1.0.0): 1.0.0
   Enter the New Skin Version (e.g., 1.0.1): 1.0.1
   ```

4. **Choose cleanup option** when asked:
   ```
   Found old version 1.0.0. Delete old ZIP files? (y/n): y
   ```

5. **Review the output** and verify success

### Linux/Mac (Bash)

1. **Open terminal** in the repository root directory

2. **Make script executable** (first time only):
   ```bash
   chmod +x update-skin-version.sh
   ```

3. **Run the script**:
   ```bash
   ./update-skin-version.sh
   ```

4. **Enter version numbers** when prompted:
   ```
   Enter the Old Skin Version (e.g., 1.0.0): 1.0.0
   Enter the New Skin Version (e.g., 1.0.1): 1.0.1
   ```

5. **Choose cleanup option** when asked:
   ```
   Found old version 1.0.0. Delete old ZIP files? (y/n): y
   ```

6. **Review the output** and verify success

## Example Output

```
========================================
AIODI Skin Version Update Tool
========================================
Old Version: 1.0.0
New Version: 1.0.1
========================================

[1/5] Updating version numbers in XML files...
  ✓ Updated: C:\...\skin.AIODI\addon.xml
  ✓ Updated: C:\...\docs\repository.aiostreams\zips\addons.xml

[2/5] Building skin ZIP file...
  ✓ Created directory: C:\...\docs\repository.aiostreams\zips\skin.aiodi
  ✓ Added: addon.xml (priority file)
  ✓ Added: 19 additional files
  ✓ Created: C:\...\skin.aiodi-1.0.1.zip (23.45 KB)

[3/5] Generating MD5 checksums...
  ✓ Created: skin.aiodi-1.0.1.zip.md5
  ✓ Created: addons.xml.md5

[4/5] Checking for old version files...
Found old version 1.0.0. Delete old ZIP files? (y/n): y
  ✓ Deleted: C:\...\skin.aiodi-1.0.0.zip
  ✓ Deleted: C:\...\skin.aiodi-1.0.0.zip.md5

[5/5] Verifying deployment...
  ✓ Skin addon.xml - Version updated
  ✓ Repository addons.xml - Version updated
  ✓ Skin ZIP file - Exists
  ✓ Skin ZIP MD5 - Exists
  ✓ Repository addons.xml MD5 - Exists

========================================
✓ SUCCESS! Skin version 1.0.1 deployed!
========================================

Next Steps:
  1. Review changes in Git
  2. Test the new ZIP in Kodi
  3. Commit changes:
     git add skin.AIODI/ docs/
     git commit -m 'Update AIODI skin to v1.0.1'
     git push

  ZIP Location: C:\...\skin.aiodi-1.0.1.zip
```

## After Running the Script

### 1. Review Changes in Git

```bash
git status
git diff skin.AIODI/addon.xml
git diff docs/repository.aiostreams/zips/addons.xml
```

### 2. Test the New ZIP

**Manual Test in Kodi:**
1. Copy the new ZIP to a test system
2. Install from ZIP in Kodi
3. Switch to the AIODI skin
4. Verify functionality

**Check ZIP Contents:**
```bash
# Windows PowerShell
Expand-Archive -Path "docs/repository.aiostreams/zips/skin.aiodi/skin.aiodi-1.0.1.zip" -DestinationPath "temp_extract"

# Linux/Mac
unzip -l docs/repository.aiostreams/zips/skin.aiodi/skin.aiodi-1.0.1.zip
```

### 3. Commit and Push

```bash
git add skin.AIODI/ docs/repository.aiostreams/zips/
git commit -m "Update AIODI skin to v1.0.1

- Updated version number in addon.xml
- Created new ZIP package
- Updated repository checksums
"
git push origin main
```

## Version Naming Convention

Follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** (1.x.x): Breaking changes, major redesigns
  - Example: 1.0.0 → 2.0.0 (complete UI overhaul)

- **MINOR** (x.1.x): New features, non-breaking changes
  - Example: 1.0.0 → 1.1.0 (added new widget types)

- **PATCH** (x.x.1): Bug fixes, small improvements
  - Example: 1.0.0 → 1.0.1 (fixed widget sorting bug)

## Troubleshooting

### PowerShell Execution Policy Error

If you get an error about execution policy:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Script Not Found Error (Linux/Mac)

Make sure you're in the correct directory:
```bash
cd /path/to/AIOStreamsKODI
./update-skin-version.sh
```

### Version Not Updated in Files

Check that the old version number exists in the files:
```bash
grep -r "1.0.0" skin.AIODI/addon.xml
grep -r "1.0.0" docs/repository.aiostreams/zips/addons.xml
```

### ZIP Creation Failed

Ensure you have zip/unzip installed:
```bash
# Ubuntu/Debian
sudo apt-get install zip unzip

# macOS (should be pre-installed)
which zip
```

### MD5 Command Not Found (macOS)

macOS uses `md5` instead of `md5sum`. The script handles this automatically.

### Permission Denied Error

Make the script executable:
```bash
chmod +x update-skin-version.sh
```

## Manual Update Process

If you prefer to update manually without scripts:

1. **Update addon.xml**:
   ```bash
   sed -i 's/version="1.0.0"/version="1.0.1"/g' skin.AIODI/addon.xml
   ```

2. **Create ZIP**:
   ```bash
   cd skin.AIODI
   zip -r ../skin.aiodi-1.0.1.zip . \
       -x "CUSTOM_SKIN_PLAN.md" \
       -x "IMPLEMENTATION_SUMMARY.md" \
       -x "TESTING_INSTRUCTIONS.md"
   cd ..
   ```

3. **Move ZIP to repository**:
   ```bash
   mv skin.aiodi-1.0.1.zip docs/repository.aiostreams/zips/skin.aiodi/
   ```

4. **Generate MD5**:
   ```bash
   cd docs/repository.aiostreams/zips/skin.aiodi/
   md5sum skin.aiodi-1.0.1.zip > skin.aiodi-1.0.1.zip.md5
   cd ../..
   ```

5. **Update addons.xml**:
   - Manually edit `docs/repository.aiostreams/zips/addons.xml`
   - Change version="1.0.0" to version="1.0.1" in the skin.aiodi entry

6. **Update addons.xml checksum**:
   ```bash
   cd docs/repository.aiostreams/zips
   md5sum addons.xml > addons.xml.md5
   ```

## Configuration

### Update Base Path (Windows Only)

Edit `Update-Skin-Version.ps1` and change the base directory:
```powershell
$baseDir = "C:\Users\YourName\Documents\GitHub\AIOStreamsKODI"
```

The Linux/Mac script automatically detects the correct path.

## Files Modified by the Scripts

The scripts will modify these files:

```
skin.AIODI/
└── addon.xml                          (version updated)

docs/repository.aiostreams/zips/
├── addons.xml                         (version updated)
├── addons.xml.md5                     (checksum updated)
└── skin.aiodi/
    ├── skin.aiodi-[NEW_VERSION].zip   (created)
    └── skin.aiodi-[NEW_VERSION].zip.md5 (created)
```

## Best Practices

1. **Always test locally first** before pushing to production
2. **Create meaningful commit messages** with version numbers
3. **Tag releases in Git**:
   ```bash
   git tag -a v1.0.1 -m "AIODI Skin v1.0.1"
   git push origin v1.0.1
   ```
4. **Keep a changelog** in the skin's README
5. **Delete old versions** to keep repository size manageable

## Support

For issues with the update scripts:
- Check the troubleshooting section above
- Review the script output for specific errors
- Check Git status to see what changed
- Test the generated ZIP manually before committing

## See Also

- [AIODI Skin README](skin.AIODI/README.md) - User documentation
- [Testing Instructions](skin.AIODI/TESTING_INSTRUCTIONS.md) - How to test the skin
- [Implementation Summary](skin.AIODI/IMPLEMENTATION_SUMMARY.md) - Technical details
