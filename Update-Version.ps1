# 1. Inputs
$OLDREF = Read-Host "Enter the Old Version"
$NEWREF = Read-Host "Enter the New Version"

# Base Path
$baseDir = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"

# Updated Specific File Paths for Version Updates
$xmlPaths = @(
    "$baseDir\plugin.video.aiostreams\addon.xml",
    "$baseDir\docs\plugin.video.aiostreams\addon.xml",
    "$baseDir\docs\repository.aiostreams\zips\addons.xml",
    "$baseDir\docs\index.html"
)

# Updated Zip Destinations based on your new tree structure
# Path 1: Inside the nested plugin folder in zips
$zipDest1 = "$baseDir\docs\repository.aiostreams\zips\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"
# Path 2: Inside the docs plugin folder
$zipDest2 = "$baseDir\docs\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"

$OldRefEscaped = [regex]::Escape($OLDREF)
$Utf8NoBOM = New-Object System.Text.UTF8Encoding($false)

# Load Assemblies
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

# 2. Update Version Numbers in All Files
Write-Host "Updating version numbers in XMLs and HTML..." -ForegroundColor Cyan
function Update-KodiFile($path, $old, $new) {
    if (Test-Path $path) {
        $content = Get-Content $path -Raw
        $content = $content -replace $old, $new
        $content = $content.Trim()
        [System.IO.File]::WriteAllText($path, $content, $Utf8NoBOM)
        Write-Host "  Updated: $path" -ForegroundColor Gray
    } else {
        Write-Host "  Warning: Path not found - $path" -ForegroundColor Yellow
    }
}

foreach ($xml in $xmlPaths) { Update-KodiFile $xml $OldRefEscaped $NEWREF }

# 3. Create ZIP Files
Write-Host "Building ZIP files..." -ForegroundColor Cyan
function Build-KodiZip($destination, $sourceDir) {
    # Ensure the destination directory exists
    $destDir = Split-Path $destination
    if (!(Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force }
    
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
    Write-Host "  Created: $destination" -ForegroundColor Gray
}

Build-KodiZip $zipDest1 "$baseDir\plugin.video.aiostreams"
Build-KodiZip $zipDest2 "$baseDir\plugin.video.aiostreams"

# 4. Hashing / Checksums
Write-Host "Updating Checksums..." -ForegroundColor Cyan
function Write-MD5($targetFile, $md5Path) {
    if (Test-Path $targetFile) {
        $hash = (Get-FileHash $targetFile -Algorithm MD5).Hash.ToLower()
        [System.IO.File]::WriteAllText($md5Path, $hash)
        Write-Host "  Hash Created: $(Split-Path $md5Path -Leaf)" -ForegroundColor Gray
    }
}

# Updated MD5 targets to match your new structure
Write-MD5 "$baseDir\docs\repository.aiostreams-1.0.0.zip" "$baseDir\docs\repository.aiostreams-1.0.0.zip.md5"
Write-MD5 "$baseDir\docs\repository.aiostreams\zips\repository.aiostreams-1.0.0.zip" "$baseDir\docs\repository.aiostreams\zips\repository.aiostreams-1.0.0.zip.md5"
Write-MD5 $zipDest1 "$zipDest1.md5"
Write-MD5 "$baseDir\docs\repository.aiostreams\zips\addons.xml" "$baseDir\docs\repository.aiostreams\zips\addons.xml.md5"
Write-MD5 $zipDest2 "$zipDest2.md5"

Write-Host "`nSuccess! Version $NEWREF fully deployed to new paths." -ForegroundColor Green