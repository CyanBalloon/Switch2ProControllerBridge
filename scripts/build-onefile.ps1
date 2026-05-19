# Build a single Switch2Bridge.exe (large; see BUILD.md).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Get-Process Switch2Bridge -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Building onefile exe..."
python -m PyInstaller Switch2Bridge-onefile.spec --noconfirm --clean

$Exe = Join-Path $Root "dist\Switch2Bridge.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "Build failed: $Exe not found"
}

$mb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $Exe  ($mb MB)"
Write-Host "Note: Under 20 MB is not possible with the WebEngine UI."
