# Build portable Switch2Bridge package for Windows.
# Output: dist\Switch2Bridge\Switch2Bridge.exe
# Zip that folder and distribute — users can extract and run from any location.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Write-Host "Building (PyInstaller onedir)..."
python -m PyInstaller Switch2Bridge.spec --noconfirm --clean

$OutDir = Join-Path $Root "dist\Switch2Bridge"
$ZipPath = Join-Path $Root "dist\Switch2Bridge-win64.zip"

if (-not (Test-Path (Join-Path $OutDir "Switch2Bridge.exe"))) {
    Write-Error "Build failed: Switch2Bridge.exe not found in $OutDir"
}

Write-Host "Creating zip: $ZipPath"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $OutDir -DestinationPath $ZipPath

Write-Host ""
Write-Host "Done."
Write-Host "  Run:  $OutDir\Switch2Bridge.exe"
Write-Host "  Zip:  $ZipPath"
Write-Host ""
Write-Host "Note: ViGEmBus must be installed on the target PC (one-time):"
Write-Host "  https://github.com/nefarius/ViGEmBus/releases/latest"
