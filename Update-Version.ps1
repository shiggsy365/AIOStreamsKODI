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

# 2. Replace versions in XML files
Write-Host "Updating XML files..." -ForegroundColor Cyan
(Get-Content $addonXmlPath) -replace $OldRefEscaped, $NEWREF | Set-Content $addonXmlPath
(Get-Content $repoXmlPath)  -replace $OldRefEscaped, $NEWREF | Set-Content $repoXmlPath

# 3. Create the ZIP file
Write-Host "Creating zip: plugin.video.aiostreams-$NEWREF.zip" -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force } # Remove existing zip if it exists
Compress-Archive -Path $sourceDir -DestinationPath $zipPath

# 4. Generate MD5 Hashes
Write-Host "Generating MD5 hashes..." -ForegroundColor Cyan

# Hash for repo/addons.xml
(Get-FileHash $repoXmlPath -Algorithm MD5).Hash.ToLower() | 
    Out-File -FilePath "$repoXmlPath.md5" -NoNewline -Encoding ascii

# Hash for the new ZIP file
(Get-FileHash $zipPath -Algorithm MD5).Hash.ToLower() | 
    Out-File -FilePath "$zipPath.md5" -NoNewline -Encoding ascii

Write-Host "Process Complete!" -ForegroundColor Green