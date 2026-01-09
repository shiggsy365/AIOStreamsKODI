# AIODI Skin Version Update Script
# Updates version number, creates new ZIP, updates checksums, and deploys to repository

# 1. Inputs
$OLDREF = Read-Host "Enter the Old Skin Version (e.g., 1.0.0)"
$NEWREF = Read-Host "Enter the New Skin Version (e.g., 1.0.1)"

# Base Path - Update this to your actual path
$baseDir = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"

# Specific File Paths for Version Updates
$xmlPaths = @(
    "$baseDir\skin.AIODI\addon.xml",
    "$baseDir\docs\repository.aiostreams\zips\addons.xml"
)

# ZIP Destination Path
$zipDest = "$baseDir\docs\repository.aiostreams\zips\skin.aiodi\skin.aiodi-$NEWREF.zip"

# Old ZIP Path (for optional cleanup)
$oldZipPath = "$baseDir\docs\repository.aiostreams\zips\skin.aiodi\skin.aiodi-$OLDREF.zip"
$oldZipMd5Path = "$oldZipPath.md5"

$OldRefEscaped = [regex]::Escape($OLDREF)
$Utf8NoBOM = New-Object System.Text.UTF8Encoding($false)

# Load Assemblies
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AIODI Skin Version Update Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Old Version: $OLDREF" -ForegroundColor Yellow
Write-Host "New Version: $NEWREF" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# 2. Update Version Numbers in All Files
Write-Host "[1/5] Updating version numbers in XML files..." -ForegroundColor Cyan
function Update-KodiFile($path, $old, $new) {
    if (Test-Path $path) {
        $content = Get-Content $path -Raw
        $updated = $content -replace $old, $new

        if ($content -ne $updated) {
            $updated = $updated.Trim()
            [System.IO.File]::WriteAllText($path, $updated, $Utf8NoBOM)
            Write-Host "  ✓ Updated: $path" -ForegroundColor Gray
        } else {
            Write-Host "  ℹ No changes needed: $path" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  ✗ Warning: Path not found - $path" -ForegroundColor Yellow
    }
}

foreach ($xml in $xmlPaths) {
    Update-KodiFile $xml $OldRefEscaped $NEWREF
}

# 3. Create ZIP File
Write-Host "`n[2/5] Building skin ZIP file..." -ForegroundColor Cyan
function Build-SkinZip($destination, $sourceDir) {
    # Ensure the destination directory exists
    $destDir = Split-Path $destination
    if (!(Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Write-Host "  ✓ Created directory: $destDir" -ForegroundColor Gray
    }

    # Remove old ZIP if it exists
    if (Test-Path $destination) {
        Remove-Item $destination -Force
        Write-Host "  ✓ Removed existing ZIP" -ForegroundColor Gray
    }

    $zipArchive = [System.IO.Compression.ZipFile]::Open($destination, [System.IO.Compression.ZipArchiveMode]::Create)

    try {
        # Files to exclude from the ZIP
        $excludeFiles = @(
            "CUSTOM_SKIN_PLAN.md",
            "IMPLEMENTATION_SUMMARY.md",
            "TESTING_INSTRUCTIONS.md"
        )

        $excludePattern = "(" + ($excludeFiles -join "|") + ")$"

        # Add addon.xml FIRST (Critical for Kodi)
        $addonXmlPath = "$sourceDir\addon.xml"
        if (Test-Path $addonXmlPath) {
            $entryName = "skin.aiodi/addon.xml"
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $addonXmlPath, $entryName)
            Write-Host "  ✓ Added: addon.xml (priority file)" -ForegroundColor Gray
        }

        # Add all other files except excluded ones
        $files = Get-ChildItem $sourceDir -Recurse | Where-Object {
            $_.Name -ne "addon.xml" -and
            !$_.PSIsContainer -and
            $_.Name -notmatch $excludePattern
        }

        $fileCount = 0
        foreach ($file in $files) {
            $relativePath = $file.FullName.Substring($sourceDir.Length + 1).Replace("\", "/")
            $entryName = "skin.aiodi/$relativePath"
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file.FullName, $entryName)
            $fileCount++
        }

        Write-Host "  ✓ Added: $fileCount additional files" -ForegroundColor Gray

    } finally {
        $zipArchive.Dispose()
    }

    $zipSize = (Get-Item $destination).Length
    $zipSizeKB = [math]::Round($zipSize / 1KB, 2)
    Write-Host "  ✓ Created: $destination ($zipSizeKB KB)" -ForegroundColor Green
}

Build-SkinZip $zipDest "$baseDir\skin.AIODI"

# 4. Generate Checksums
Write-Host "`n[3/5] Generating MD5 checksums..." -ForegroundColor Cyan
function Write-MD5($targetFile, $md5Path) {
    if (Test-Path $targetFile) {
        $hash = (Get-FileHash $targetFile -Algorithm MD5).Hash.ToLower()
        [System.IO.File]::WriteAllText($md5Path, "$hash  $(Split-Path $targetFile -Leaf)", $Utf8NoBOM)
        Write-Host "  ✓ Created: $(Split-Path $md5Path -Leaf)" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ Warning: File not found - $targetFile" -ForegroundColor Yellow
    }
}

# Generate MD5 for new ZIP
Write-MD5 $zipDest "$zipDest.md5"

# Generate MD5 for addons.xml
Write-MD5 "$baseDir\docs\repository.aiostreams\zips\addons.xml" "$baseDir\docs\repository.aiostreams\zips\addons.xml.md5"

# 5. Cleanup Old Version
Write-Host "`n[4/5] Checking for old version files..." -ForegroundColor Cyan
if (Test-Path $oldZipPath) {
    $cleanup = Read-Host "Found old version $OLDREF. Delete old ZIP files? (y/n)"
    if ($cleanup -eq "y" -or $cleanup -eq "Y") {
        Remove-Item $oldZipPath -Force
        Write-Host "  ✓ Deleted: $oldZipPath" -ForegroundColor Gray

        if (Test-Path $oldZipMd5Path) {
            Remove-Item $oldZipMd5Path -Force
            Write-Host "  ✓ Deleted: $oldZipMd5Path" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ℹ Keeping old version files" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  ℹ No old version files found" -ForegroundColor DarkGray
}

# 6. Verification & Summary
Write-Host "`n[5/5] Verifying deployment..." -ForegroundColor Cyan

$verifyItems = @(
    @{ Path = "$baseDir\skin.AIODI\addon.xml"; Description = "Skin addon.xml" },
    @{ Path = "$baseDir\docs\repository.aiostreams\zips\addons.xml"; Description = "Repository addons.xml" },
    @{ Path = $zipDest; Description = "Skin ZIP file" },
    @{ Path = "$zipDest.md5"; Description = "Skin ZIP MD5" },
    @{ Path = "$baseDir\docs\repository.aiostreams\zips\addons.xml.md5"; Description = "Repository addons.xml MD5" }
)

$allValid = $true
foreach ($item in $verifyItems) {
    if (Test-Path $item.Path) {
        # Check if file contains new version
        if ($item.Path -match "\.xml$") {
            $content = Get-Content $item.Path -Raw
            if ($content -match $NEWREF) {
                Write-Host "  ✓ $($item.Description) - Version updated" -ForegroundColor Green
            } else {
                Write-Host "  ✗ $($item.Description) - Version NOT found!" -ForegroundColor Red
                $allValid = $false
            }
        } else {
            Write-Host "  ✓ $($item.Description) - Exists" -ForegroundColor Green
        }
    } else {
        Write-Host "  ✗ $($item.Description) - Missing!" -ForegroundColor Red
        $allValid = $false
    }
}

# Final Summary
Write-Host "`n========================================" -ForegroundColor Cyan
if ($allValid) {
    Write-Host "✓ SUCCESS! Skin version $NEWREF deployed!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "`nNext Steps:" -ForegroundColor Yellow
    Write-Host "  1. Review changes in Git" -ForegroundColor White
    Write-Host "  2. Test the new ZIP in Kodi" -ForegroundColor White
    Write-Host "  3. Commit changes:" -ForegroundColor White
    Write-Host "     git add skin.AIODI/ docs/" -ForegroundColor DarkGray
    Write-Host "     git commit -m 'Update AIODI skin to v$NEWREF'" -ForegroundColor DarkGray
    Write-Host "     git push" -ForegroundColor DarkGray
    Write-Host "`n  ZIP Location: $zipDest" -ForegroundColor Cyan
} else {
    Write-Host "✗ ERRORS DETECTED - Please review!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Cyan
}

Write-Host ""
