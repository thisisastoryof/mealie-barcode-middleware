# Download Tabler v1.4.0 CSS/JS from jsDelivr for offline vendoring.
# Run from repo root: .\scripts\download-tabler.ps1

$version = "1.4.0"
$outDir = Join-Path $PSScriptRoot "..\app\static\vendor\tabler"

Write-Host "Downloading Tabler @tabler/core@$version from jsDelivr..."

# Ensure output dirs exist
New-Item -ItemType Directory -Path (Join-Path $outDir "css") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $outDir "js") -Force | Out-Null

$cssUrl = "https://cdn.jsdelivr.net/npm/@tabler/core@$version/dist/css/tabler.min.css"
$jsUrl  = "https://cdn.jsdelivr.net/npm/@tabler/core@$version/dist/js/tabler.min.js"

Invoke-WebRequest -Uri $cssUrl -OutFile (Join-Path $outDir "css\tabler.min.css")
Write-Host "  -> css/tabler.min.css"

Invoke-WebRequest -Uri $jsUrl -OutFile (Join-Path $outDir "js\tabler.min.js")
Write-Host "  -> js/tabler.min.js"

Write-Host "Done! Tabler $version files are in: $outDir"
