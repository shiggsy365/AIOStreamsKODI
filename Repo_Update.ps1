# AIOStreams Repository Update Tool
# Unified script for updating plugin and/or skin versions

# Base Path - Update this to your actual path
$baseDir = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"

$Utf8NoBOM = New-Object System.Text.UTF8Encoding($false)

# Load Assemblies
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

# Helper Functions
function Get-LatestVersion($docsPath) {
    if (!(Test-Path $docsPath)) {
        return $null
    }

    $zipFiles = Get-ChildItem "$docsPath\*.zip" -File | Where-Object { $_.Name -match '-(\d+\.\d+\.\d+)\.zip$' }

    if ($zipFiles.Count -eq 0) {
        return $null
    }

    $versions = $zipFiles | ForEach-Object {
        if ($_.Name -match '-(\d+\.\d+\.\d+)\.zip$') {
            [Version]$matches[1]
        }
    } | Sort-Object -Descending

    return $versions[0].ToString()
}

function Increment-Version($version) {
    $v = [Version]$version
    return "$($v.Major).$($v.Minor).$($v.Build + 1)"
}

function Update-KodiFile($path, $old, $new) {
    if (Test-Path $path) {
        $content = Get-Content $path -Raw
        $updated = $content -replace $old, $new

        if ($content -ne $updated) {
            $updated = $updated.Trim()
            [System.IO.File]::WriteAllText($path, $updated, $Utf8NoBOM)
            Write-Host "  [+] Updated: $path" -ForegroundColor Gray
        } else {
            Write-Host "  [i] No changes needed: $path" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  [!] Warning: Path not found - $path" -ForegroundColor Yellow
    }
}

function Write-MD5($targetFile, $md5Path) {
    if (Test-Path $targetFile) {
        $hash = (Get-FileHash $targetFile -Algorithm MD5).Hash.ToLower()
        [System.IO.File]::WriteAllText($md5Path, "$hash  $(Split-Path $targetFile -Leaf)", $Utf8NoBOM)
        Write-Host "  [+] Created: $(Split-Path $md5Path -Leaf)" -ForegroundColor Gray
    } else {
        Write-Host "  [!] Warning: File not found - $targetFile" -ForegroundColor Yellow
    }
}

function Update-Plugin($oldVersion, $newVersion) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Updating Plugin: $oldVersion -> $newVersion" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    $OldRefEscaped = [regex]::Escape($oldVersion)

    # File paths for plugin
    $xmlPaths = @(
        "$baseDir\plugin.video.aiostreams\addon.xml",
        "$baseDir\docs\plugin.video.aiostreams\addon.xml",
        "$baseDir\docs\repository.aiostreams\zips\addons.xml",
        "$baseDir\docs\index.html"
    )

    $zipDest1 = "$baseDir\docs\repository.aiostreams\zips\plugin.video.aiostreams\plugin.video.aiostreams-$newVersion.zip"
    $zipDest2 = "$baseDir\docs\plugin.video.aiostreams\plugin.video.aiostreams-$newVersion.zip"

    # Update version numbers
    Write-Host "`n[1/4] Updating version numbers..." -ForegroundColor Cyan
    foreach ($xml in $xmlPaths) {
        Update-KodiFile $xml $OldRefEscaped $newVersion
    }

    # Create ZIP files
    Write-Host "`n[2/4] Building plugin ZIP files..." -ForegroundColor Cyan
    Build-PluginZip $zipDest1 "$baseDir\plugin.video.aiostreams"
    Build-PluginZip $zipDest2 "$baseDir\plugin.video.aiostreams"

    # Generate checksums
    Write-Host "`n[3/4] Generating MD5 checksums..." -ForegroundColor Cyan
    Write-MD5 "$baseDir\docs\repository.aiostreams-1.0.0.zip" "$baseDir\docs\repository.aiostreams-1.0.0.zip.md5"
    Write-MD5 "$baseDir\docs\repository.aiostreams\zips\repository.aiostreams-1.0.0.zip" "$baseDir\docs\repository.aiostreams\zips\repository.aiostreams-1.0.0.zip.md5"
    Write-MD5 $zipDest1 "$zipDest1.md5"
    Write-MD5 "$baseDir\docs\repository.aiostreams\zips\addons.xml" "$baseDir\docs\repository.aiostreams\zips\addons.xml.md5"
    Write-MD5 $zipDest2 "$zipDest2.md5"

    # Cleanup old version
    Write-Host "`n[4/4] Checking for old version files..." -ForegroundColor Cyan
    $oldZipPath1 = "$baseDir\docs\repository.aiostreams\zips\plugin.video.aiostreams\plugin.video.aiostreams-$oldVersion.zip"
    $oldZipPath2 = "$baseDir\docs\plugin.video.aiostreams\plugin.video.aiostreams-$oldVersion.zip"

    $foundOldFiles = (Test-Path $oldZipPath1) -or (Test-Path $oldZipPath2)

    if ($foundOldFiles) {
        $cleanup = Read-Host "Found old plugin version $oldVersion. Delete old ZIP files? (y/n)"
        if ($cleanup -eq "y" -or $cleanup -eq "Y") {
            if (Test-Path $oldZipPath1) {
                Remove-Item $oldZipPath1 -Force
                Remove-Item "$oldZipPath1.md5" -Force -ErrorAction SilentlyContinue
                Write-Host "  [+] Deleted: $oldZipPath1" -ForegroundColor Gray
            }
            if (Test-Path $oldZipPath2) {
                Remove-Item $oldZipPath2 -Force
                Remove-Item "$oldZipPath2.md5" -Force -ErrorAction SilentlyContinue
                Write-Host "  [+] Deleted: $oldZipPath2" -ForegroundColor Gray
            }
        } else {
            Write-Host "  [i] Keeping old version files" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  [i] No old version files found" -ForegroundColor DarkGray
    }

    Write-Host "`n[+] Plugin update complete: $newVersion" -ForegroundColor Green
}

function Build-PluginZip($destination, $sourceDir) {
    $destDir = Split-Path $destination
    if (!(Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }

    if (Test-Path $destination) { Remove-Item $destination -Force }
    $zipArchive = [System.IO.Compression.ZipFile]::Open($destination, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        # Add addon.xml FIRST (Critical for Kodi)
        $entryName = "plugin.video.aiostreams/addon.xml"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, "$sourceDir\addon.xml", $entryName)
        # Add all other files
        $files = Get-ChildItem $sourceDir -Recurse | Where-Object { $_.Name -ne "addon.xml" -and !$_.PSIsContainer }
        foreach ($file in $files) {
            $relativePath = $file.FullName.Substring($sourceDir.Length + 1).Replace("\", "/")
            $entryName = "plugin.video.aiostreams/$relativePath"
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file.FullName, $entryName)
        }
    } finally { $zipArchive.Dispose() }

    $zipSize = (Get-Item $destination).Length
    $zipSizeKB = [math]::Round($zipSize / 1KB, 2)
    Write-Host "  [+] Created: $destination (${zipSizeKB} KB)" -ForegroundColor Gray
}

function Update-Skin($oldVersion, $newVersion) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Updating Skin: $oldVersion -> $newVersion" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    $OldRefEscaped = [regex]::Escape($oldVersion)

    # File paths for skin
    $xmlPaths = @(
        "$baseDir\skin.AIODI\addon.xml",
        "$baseDir\docs\skin.aiodi\addon.xml",
        "$baseDir\docs\repository.aiostreams\zips\addons.xml"
    )

    $zipDestRepo = "$baseDir\docs\repository.aiostreams\zips\skin.aiodi\skin.aiodi-$newVersion.zip"
    $zipDestDocs = "$baseDir\docs\skin.aiodi\skin.aiodi-$newVersion.zip"

    # Update version numbers
    Write-Host "`n[1/4] Updating version numbers..." -ForegroundColor Cyan
    foreach ($xml in $xmlPaths) {
        Update-KodiFile $xml $OldRefEscaped $newVersion
    }

    # Create ZIP files
    Write-Host "`n[2/4] Building skin ZIP file..." -ForegroundColor Cyan
    Build-SkinZip $zipDestRepo "$baseDir\skin.AIODI"
    Write-Host "  [+] Copying ZIP to docs/skin.aiodi/" -ForegroundColor Gray
    Copy-Item $zipDestRepo $zipDestDocs -Force

    # Generate checksums
    Write-Host "`n[3/4] Generating MD5 checksums..." -ForegroundColor Cyan
    Write-MD5 $zipDestRepo "$zipDestRepo.md5"
    Write-MD5 $zipDestDocs "$zipDestDocs.md5"
    Write-MD5 "$baseDir\docs\repository.aiostreams\zips\addons.xml" "$baseDir\docs\repository.aiostreams\zips\addons.xml.md5"

    # Cleanup old version
    Write-Host "`n[4/4] Checking for old version files..." -ForegroundColor Cyan
    $oldZipPathRepo = "$baseDir\docs\repository.aiostreams\zips\skin.aiodi\skin.aiodi-$oldVersion.zip"
    $oldZipPathDocs = "$baseDir\docs\skin.aiodi\skin.aiodi-$oldVersion.zip"

    $foundOldFiles = (Test-Path $oldZipPathRepo) -or (Test-Path $oldZipPathDocs)

    if ($foundOldFiles) {
        $cleanup = Read-Host "Found old skin version $oldVersion. Delete old ZIP files? (y/n)"
        if ($cleanup -eq "y" -or $cleanup -eq "Y") {
            if (Test-Path $oldZipPathRepo) {
                Remove-Item $oldZipPathRepo -Force
                Remove-Item "$oldZipPathRepo.md5" -Force -ErrorAction SilentlyContinue
                Write-Host "  [+] Deleted: $oldZipPathRepo" -ForegroundColor Gray
            }
            if (Test-Path $oldZipPathDocs) {
                Remove-Item $oldZipPathDocs -Force
                Remove-Item "$oldZipPathDocs.md5" -Force -ErrorAction SilentlyContinue
                Write-Host "  [+] Deleted: $oldZipPathDocs" -ForegroundColor Gray
            }
        } else {
            Write-Host "  [i] Keeping old version files" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  [i] No old version files found" -ForegroundColor DarkGray
    }

    Write-Host "`n[+] Skin update complete: $newVersion" -ForegroundColor Green
}

function Build-SkinZip($destination, $sourceDir) {
    $destDir = Split-Path $destination
    if (!(Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    if (Test-Path $destination) { Remove-Item $destination -Force }

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
        }

        # Add all other files except excluded ones
        $files = Get-ChildItem $sourceDir -Recurse | Where-Object {
            $_.Name -ne "addon.xml" -and
            !$_.PSIsContainer -and
            $_.Name -notmatch $excludePattern
        }

        foreach ($file in $files) {
            $relativePath = $file.FullName.Substring($sourceDir.Length + 1).Replace("\", "/")
            $entryName = "skin.aiodi/$relativePath"
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file.FullName, $entryName)
        }

    } finally {
        $zipArchive.Dispose()
    }

    $zipSize = (Get-Item $destination).Length
    $zipSizeKB = [math]::Round($zipSize / 1KB, 2)
    Write-Host "  [+] Created: $destination (${zipSizeKB} KB)" -ForegroundColor Green
}

# Main Script
Clear-Host
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AIOStreams Repository Update Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Detect current versions
Write-Host "`nDetecting current versions..." -ForegroundColor Yellow

$pluginVersion = Get-LatestVersion "$baseDir\docs\plugin.video.aiostreams"
$skinVersion = Get-LatestVersion "$baseDir\docs\skin.aiodi"

if ($pluginVersion) {
    Write-Host "  Plugin current version: $pluginVersion" -ForegroundColor White
} else {
    Write-Host "  Plugin version: Not found" -ForegroundColor DarkGray
}

if ($skinVersion) {
    Write-Host "  Skin current version: $skinVersion" -ForegroundColor White
} else {
    Write-Host "  Skin version: Not found" -ForegroundColor DarkGray
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "What would you like to update?" -ForegroundColor Yellow
Write-Host "  1. Plugin only" -ForegroundColor White
Write-Host "  2. Skin only" -ForegroundColor White
Write-Host "  3. Both plugin and skin" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

$choice = Read-Host "`nEnter your choice (1, 2, or 3)"

switch ($choice) {
    "1" {
        if (!$pluginVersion) {
            Write-Host "`n[!] Error: Could not detect plugin version. Please check docs/plugin.video.aiostreams/" -ForegroundColor Red
            exit
        }
        $newPluginVersion = Increment-Version $pluginVersion
        Write-Host "`nPlugin will be updated: $pluginVersion -> $newPluginVersion" -ForegroundColor Yellow
        $confirm = Read-Host "Continue? (y/n)"
        if ($confirm -eq "y" -or $confirm -eq "Y") {
            Update-Plugin $pluginVersion $newPluginVersion
        } else {
            Write-Host "`n[i] Update cancelled" -ForegroundColor DarkGray
        }
    }
    "2" {
        if (!$skinVersion) {
            Write-Host "`n[!] Error: Could not detect skin version. Please check docs/skin.aiodi/" -ForegroundColor Red
            exit
        }
        $newSkinVersion = Increment-Version $skinVersion
        Write-Host "`nSkin will be updated: $skinVersion -> $newSkinVersion" -ForegroundColor Yellow
        $confirm = Read-Host "Continue? (y/n)"
        if ($confirm -eq "y" -or $confirm -eq "Y") {
            Update-Skin $skinVersion $newSkinVersion
        } else {
            Write-Host "`n[i] Update cancelled" -ForegroundColor DarkGray
        }
    }
    "3" {
        $canProceed = $true

        if (!$pluginVersion) {
            Write-Host "`n[!] Error: Could not detect plugin version" -ForegroundColor Red
            $canProceed = $false
        }
        if (!$skinVersion) {
            Write-Host "[!] Error: Could not detect skin version" -ForegroundColor Red
            $canProceed = $false
        }

        if (!$canProceed) {
            Write-Host "`nPlease check docs folder for version detection issues" -ForegroundColor Yellow
            exit
        }

        $newPluginVersion = Increment-Version $pluginVersion
        $newSkinVersion = Increment-Version $skinVersion

        Write-Host "`nUpdates planned:" -ForegroundColor Yellow
        Write-Host "  Plugin: $pluginVersion -> $newPluginVersion" -ForegroundColor White
        Write-Host "  Skin: $skinVersion -> $newSkinVersion" -ForegroundColor White

        $confirm = Read-Host "`nContinue? (y/n)"
        if ($confirm -eq "y" -or $confirm -eq "Y") {
            Update-Plugin $pluginVersion $newPluginVersion
            Update-Skin $skinVersion $newSkinVersion
        } else {
            Write-Host "`n[i] Update cancelled" -ForegroundColor DarkGray
        }
    }
    default {
        Write-Host "`n[!] Invalid choice. Exiting." -ForegroundColor Red
        exit
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "[+] Update process complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Review changes in Git" -ForegroundColor White
Write-Host "  2. Test the new ZIP files in Kodi" -ForegroundColor White
Write-Host "  3. Commit and push changes" -ForegroundColor White
Write-Host ""
