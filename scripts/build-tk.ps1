# Small single-file Switch2Bridge.exe (Tkinter, no Qt).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Get-Process Switch2Bridge -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Building Tk onefile exe..."
python -m PyInstaller Switch2Bridge-tk.spec --noconfirm --clean

$Exe = Join-Path $Root "dist\Switch2Bridge.exe"
if (-not (Test-Path $Exe)) { Write-Error "Build failed: $Exe not found" }

$mb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $Exe  ($mb MB)"
Write-Host "Run from anywhere. ViGEmBus required on target PC."
