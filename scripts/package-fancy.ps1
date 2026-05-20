# Package Fancy app for distribution (deps installed by user via pip, not bundled).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$OutDir = Join-Path $Root "dist\Switch2Bridge-Fancy"
$ZipPath = Join-Path $Root "dist\Switch2Bridge-Fancy.zip"

if (Test-Path $OutDir) {
    Remove-Item $OutDir -Recurse -Force
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$CopyItems = @(
    "main.py",
    "gui.py",
    "bridge",
    "ui",
    "requirements.txt",
    "requirements-fancy.txt"
)

foreach ($item in $CopyItems) {
    $src = Join-Path $Root $item
    if (-not (Test-Path $src)) {
        Write-Error "Missing: $src"
    }
    Copy-Item -Path $src -Destination (Join-Path $OutDir $item) -Recurse -Force
}

$InstallTxt = @"
Switch 2 Bridge (Fancy UI)
============================

Prerequisites on this PC:
  1. Python 3.11 or newer (python.org) - check "Add to PATH"
  2. ViGEmBus driver: https://github.com/nefarius/ViGEmBus/releases/latest

First run:
  Double-click Run.bat
  (installs Python packages via pip, then starts the app)

Manual install:
  pip install -r requirements-fancy.txt
  pythonw main.py --fancy

Reskin: edit files in the ui\ folder (index.html, styles.css, app.js).

Logs: logs\bridge.log (next to this folder)
"@

Set-Content -Path (Join-Path $OutDir "INSTALL.txt") -Value $InstallTxt -Encoding UTF8

$RunBat = @"
@echo off
cd /d "%~dp0"
where python >nul 2>&1 || (
  echo.
  echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)
echo Installing Python packages (bleak, vgamepad, PySide6, ...)...
python -m pip install -r requirements-fancy.txt
if errorlevel 1 (
  echo.
  echo pip install failed. See INSTALL.txt
  pause
  exit /b 1
)
echo Starting Switch 2 Bridge...
start "" pythonw main.py --fancy
"@

Set-Content -Path (Join-Path $OutDir "Run.bat") -Value $RunBat -Encoding ASCII

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path $OutDir -DestinationPath $ZipPath -Force

$zipMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "Done:"
Write-Host "  Folder: $OutDir"
Write-Host "  Zip:    $ZipPath  ($zipMb MB)"
Write-Host ""
Write-Host "End users need Python + pip install; only app source is packaged."
Write-Host "For a standalone .exe without Python, use build-lite.bat instead."
