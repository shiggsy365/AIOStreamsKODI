# 1. Inputs
$OLDREF = Read-Host "Enter the Old Version"
$NEWREF = Read-Host "Enter the New Version"

# Paths
$baseDir      = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"
$pluginDir    = "$baseDir\plugin.video.aiostreams"
$repoDir      = "$baseDir\repo"
$zipPath      = "$repoDir\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"

$OldRefEscaped = [regex]::Escape($OLDREF)
$Utf8NoBOM = New-Object System.Text.UTF8Encoding($false)

# Load the required .NET Assemblies
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

# 2. Update XMLs with Sanitization (Removes leading spaces/bom)
Write-Host "Updating and Sanitizing XMLs..." -ForegroundColor Cyan
function Update-KodiXML($path, $old, $new) {
    $content = Get-Content $path -Raw
    $content = $content -replace $old, $new
    # Trim leading whitespace/newlines that cause 'Line 0' errors
    $content = $content.Trim()
    [System.IO.File]::WriteAllText($path, $content, $Utf8NoBOM)
}
Update-KodiXML "$pluginDir\addon.xml" $OldRefEscaped $NEWREF
Update-KodiXML "$repoDir\addons.xml" $OldRefEscaped $NEWREF

# 3. Create ZIP with addon.xml as the FIRST entry
Write-Host "Building ZIP with priority ordering..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

# Open ZIP in 'Create' mode
$zipArchive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

try {
    # A. Add addon.xml FIRST (Critical for Kodi VFS)
    $entryName = "plugin.video.aiostreams/addon.xml"
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, "$pluginDir\addon.xml", $entryName)

    # B. Add all other files
    $files = Get-ChildItem $pluginDir -Recurse | Where-Object { $_.Name -ne "addon.xml" -and !$_.PSIsContainer }
    foreach ($file in $files) {
        # Calculate relative path and force forward slashes
        $relativePath = $file.FullName.Substring($pluginDir.Length + 1).Replace("\", "/")
        $entryName = "plugin.video.aiostreams/$relativePath"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file.FullName, $entryName)
    }
}
finally {
    # Close the ZIP file properly
    $zipArchive.Dispose()
}

# 4. Hashing
Write-Host "Generating MD5..." -ForegroundColor Cyan
$repoHash = (Get-FileHash "$repoDir\addons.xml" -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$repoDir\addons.xml.md5", $repoHash)

$zipHash = (Get-FileHash $zipPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$zipPath.md5", $zipHash)

Write-Host "Success! Version $NEWREF deployed with priority file ordering." -ForegroundColor Green