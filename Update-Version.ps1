# 1. Inputs
$OLDREF = Read-Host "Enter the Old Version"
$NEWREF = Read-Host "Enter the New Version"

# Paths
$baseDir      = "C:\Users\jon_s\OneDrive\Documents\GitHub\AIOStreamsKODI"
$pluginDir    = "$baseDir\plugin.video.aiostreams"
$repoDir      = "$baseDir\docs"
$indexFile    = "$repoDir\index.html"
$zipPath      = "$repoDir\plugin.video.aiostreams\plugin.video.aiostreams-$NEWREF.zip"

$OldRefEscaped = [regex]::Escape($OLDREF)
$Utf8NoBOM = New-Object System.Text.UTF8Encoding($false)

# Load the required .NET Assemblies
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

# 2. Update XMLs and index.html with Sanitization
Write-Host "Updating and Sanitizing Files..." -ForegroundColor Cyan
function Update-KodiFile($path, $old, $new) {
    if (Test-Path $path) {
        $content = Get-Content $path -Raw
        $content = $content -replace $old, $new
        $content = $content.Trim()
        [System.IO.File]::WriteAllText($path, $content, $Utf8NoBOM)
        Write-Host "  Updated: $(Split-Path $path -Leaf)" -ForegroundColor Gray
    }
}

Update-KodiFile "$pluginDir\addon.xml" $OldRefEscaped $NEWREF
Update-KodiFile "$repoDir\addons.xml" $OldRefEscaped $NEWREF
# New: Update the version numbers in your index.html links
Update-KodiFile $indexFile $OldRefEscaped $NEWREF

# 3. Create ZIP with addon.xml as the FIRST entry
Write-Host "Building ZIP with priority ordering..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$zipArchive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

try {
    # A. Add addon.xml FIRST
    $entryName = "plugin.video.aiostreams/addon.xml"
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, "$pluginDir\addon.xml", $entryName)

    # B. Add all other files
    $files = Get-ChildItem $pluginDir -Recurse | Where-Object { $_.Name -ne "addon.xml" -and !$_.PSIsContainer }
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($pluginDir.Length + 1).Replace("\", "/")
        $entryName = "plugin.video.aiostreams/$relativePath"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipArchive, $file.FullName, $entryName)
    }
}
finally {
    $zipArchive.Dispose()
}

# 4. Hashing
Write-Host "Generating MD5..." -ForegroundColor Cyan
$repoHash = (Get-FileHash "$repoDir\addons.xml" -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$repoDir\addons.xml.md5", $repoHash)

$zipHash = (Get-FileHash $zipPath -Algorithm MD5).Hash.ToLower()
[System.IO.File]::WriteAllText("$zipPath.md5", $zipHash)

Write-Host "Success! Version $NEWREF deployed with updated index.html." -ForegroundColor Green