# 1. Version Inputs
$OLDREF = Read-Host "Enter the Old Version"
$NEWREF = Read-Host "Enter the New Version"

# Paths
$addonXmlPath = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\plugin.video.aiostreams\addon.xml"
$repoXmlPath  = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\repo\addons.xml"
$sourceDir    = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\plugin.video.aiostreams"
$zipPath      = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\repo\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"

$OldRefEscaped = [regex]::Escape($OLDREF)
$Utf8NoBOM = New-Object System.Text.UTF8Encoding $false

# 2. Update XMLs with NO-BOM Encoding
Write-Host "Updating XML files (UTF-8 No-BOM)..." -ForegroundColor Cyan
$content1 = (Get-Content $addonXmlPath) -replace $OldRefEscaped, $NEWREF
$content2 = (Get-Content $repoXmlPath)  -replace $OldRefEscaped, $NEWREF

[System.IO.File]::WriteAllLines($addonXmlPath, $content1, $Utf8NoBOM)
[System.IO.File]::WriteAllLines($repoXmlPath, $content2, $Utf8NoBOM)

# 3. Create ZIP using .NET (Kodi Compatible)
Write-Host "Creating zip..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
# The '$true' at the end ensures the 'plugin.video.aiostreams' folder is the root inside the ZIP
[System.IO.Compression.ZipFile]::CreateFromDirectory($sourceDir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)

# 4. Generate MD5 Hashes (Clean strings, no newlines)
Write-Host "Generating MD5 hashes..." -ForegroundColor Cyan

$repoHash = (Get-FileHash $repoXmlPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$repoXmlPath.md5", $repoHash)

$zipHash = (Get-FileHash $zipPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$zipPath.md5", $zipHash)

Write-Host "Done! Please 'Check for updates' in your Kodi Repo settings." -ForegroundColor Green