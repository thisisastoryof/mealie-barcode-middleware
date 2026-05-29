# Download Tabler v1.4.0 CSS/JS from jsDelivr for offline vendoring.
# Also downloads Inter variable font.
# Run from repo root: .\scripts\download-tabler.ps1

$version = "1.4.0"
$outDir = Join-Path $PSScriptRoot "..\app\static\vendor\tabler"
$interDir = Join-Path $PSScriptRoot "..\app\static\vendor\inter"

Write-Host "Downloading Tabler @tabler/core@$version from jsDelivr..."

# Ensure output dirs exist
New-Item -ItemType Directory -Path (Join-Path $outDir "css") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $outDir "js") -Force | Out-Null
New-Item -ItemType Directory -Path $interDir -Force | Out-Null

$cssUrl = "https://cdn.jsdelivr.net/npm/@tabler/core@$version/dist/css/tabler.min.css"
$jsUrl  = "https://cdn.jsdelivr.net/npm/@tabler/core@$version/dist/js/tabler.min.js"

Invoke-WebRequest -Uri $cssUrl -OutFile (Join-Path $outDir "css\tabler.min.css")
Write-Host "  -> css/tabler.min.css"

Invoke-WebRequest -Uri $jsUrl -OutFile (Join-Path $outDir "js\tabler.min.js")
Write-Host "  -> js/tabler.min.js"

# Download Inter variable font
$interUrl = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
$interZip = Join-Path $PSScriptRoot "inter.zip"
Write-Host "Downloading Inter font..."
Invoke-WebRequest -Uri $interUrl -OutFile $interZip
$extractDir = Join-Path $PSScriptRoot "inter_temp"
Expand-Archive -Path $interZip -DestinationPath $extractDir -Force
$woff2 = Get-ChildItem $extractDir -Recurse -Filter "InterVariable.woff2" | Select-Object -First 1
Copy-Item $woff2.FullName (Join-Path $interDir "InterVariable.woff2")
Remove-Item $interZip -Force
Remove-Item $extractDir -Recurse -Force
Write-Host "  -> inter/InterVariable.woff2"

Write-Host "Done! Tabler $version + Inter font files are in: app/static/vendor/"
