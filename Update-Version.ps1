# 1. Inputs
$OLDREF = Read-Host "Enter the Old Version"
$NEWREF = Read-Host "Enter the New Version"

# Paths
$baseDir      = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"
$pluginDir    = "$baseDir\plugin.video.aiostreams"
$repoDir      = "$baseDir\repo"
$stagingDir   = "$env:TEMP\kodi_build"
$zipName      = "plugin.video.aiostreams-$NEWREF.zip"
$zipPath      = "$repoDir\plugin.video.aiostreams\$zipName"

$OldRefEscaped = [regex]::Escape($OLDREF)

# 2. Update XML files (Pre-Staging)
Write-Host "Cleaning and Updating XMLs..." -ForegroundColor Cyan
function Update-KodiXML($path, $old, $new) {
    $content = Get-Content $path -Raw
    $content = $content -replace $old, $new
    # Force UTF8 without BOM using .NET to ensure no Line 0 errors
    [System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))
}

Update-KodiXML "$pluginDir\addon.xml" $OldRefEscaped $NEWREF
Update-KodiXML "$repoDir\addons.xml" $OldRefEscaped $NEWREF

# 3. Create ZIP with Precise Structure
Write-Host "Building ZIP..." -ForegroundColor Cyan
if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path "$stagingDir\plugin.video.aiostreams" | Out-Null

# Copy files to staging folder
Copy-Item -Path "$pluginDir\*" -Destination "$stagingDir\plugin.video.aiostreams" -Recurse

# Zip the staging folder
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stagingDir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

# 4. MD5 Hashes
Write-Host "Hashing..." -ForegroundColor Cyan
function Write-KodiMD5($targetPath) {
    $hash = (Get-FileHash $targetPath -Algorithm MD5).Hash.ToLower()
    [System.IO.File]::WriteAllText("$targetPath.md5", $hash)
}

Write-KodiMD5 "$repoDir\addons.xml"
Write-KodiMD5 $zipPath

Remove-Item $stagingDir -Recurse -Force
Write-Host "Success! Created $zipName" -ForegroundColor Green