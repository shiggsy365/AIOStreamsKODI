# 1. Ask for Version inputs
$OLDREF = Read-Host "Enter the Old Version (e.g., 3.21.22)"
$NEWREF = Read-Host "Enter the New Version (e.g., 3.21.23)"

# Define Paths
$addonXmlPath = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\plugin.video.aiostreams\addon.xml"
$repoXmlPath  = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\repo\addons.xml"
$sourceDir    = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\plugin.video.aiostreams"
$zipPath      = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI\repo\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"

# Escape dots in OLDREF for Regex replacement
$OldRefEscaped = [regex]::Escape($OLDREF)

# 2. Replace versions with Kodi-compatible encoding (No BOM)
Write-Host "Updating XML files..." -ForegroundColor Cyan
$content1 = (Get-Content $addonXmlPath) -replace $OldRefEscaped, $NEWREF
$content2 = (Get-Content $repoXmlPath)  -replace $OldRefEscaped, $NEWREF

[System.IO.File]::WriteAllLines($addonXmlPath, $content1)
[System.IO.File]::WriteAllLines($repoXmlPath, $content2)

# 3. Create the ZIP file (Using .NET for better compatibility)
Write-Host "Creating zip via .NET..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($sourceDir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)

# 4. Generate MD5 (Ensure no extra spaces or newlines)
Write-Host "Generating MD5 hashes..." -ForegroundColor Cyan
$repoHash = (Get-FileHash $repoXmlPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$repoXmlPath.md5", $repoHash)

$zipHash = (Get-FileHash $zipPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$zipPath.md5", $zipHash)

Write-Host "Process Complete!" -ForegroundColor Green