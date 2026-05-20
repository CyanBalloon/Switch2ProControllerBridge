# Fancy onefile .exe — app inside exe; pip packages from user's Python (same version).

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot

Set-Location $Root



$PyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

Write-Host "Building for Python $PyVer (end users need this version installed)"



Write-Host "Installing build tools..."

python -m pip install -r requirements-build.txt -q



Set-Content -Path (Join-Path $Root "python_version.txt") -Value $PyVer -Encoding ASCII -NoNewline



Get-Process Switch2Bridge -ErrorAction SilentlyContinue | Stop-Process -Force



Write-Host "Building Fancy onefile exe..."

python -m PyInstaller Switch2Bridge-fancy.spec --noconfirm --clean



$Exe = Join-Path $Root "dist\Switch2Bridge.exe"

if (-not (Test-Path $Exe)) {

    Write-Error "Build failed: $Exe not found"

}



Copy-Item (Join-Path $Root "python_version.txt") (Join-Path $Root "dist\python_version.txt") -Force



$DebugBat = @"

@echo off

cd /d "%~dp0"

set PY=python

echo === Import test ===

"%PY%" -c "import importlib; mods=['bleak','vgamepad','pystray','PIL','PySide6.QtWebEngineWidgets']; [importlib.import_module(m) for m in mods]; print('OK')"

if errorlevel 1 pause & exit /b 1

echo.

echo === Starting Switch2Bridge.exe ===

Switch2Bridge.exe

echo Exit code: %ERRORLEVEL%

echo.

if exist logs\launcher.log (echo === logs\launcher.log === & type logs\launcher.log)

if exist logs\pip-install.log (echo. & echo === logs\pip-install.log === & type logs\pip-install.log)

if exist logs\bridge.log (echo. & echo === logs\bridge.log === & type logs\bridge.log)

pause

"@

Set-Content -Path (Join-Path $Root "dist\Run Fancy (debug).bat") -Value $DebugBat -Encoding ASCII



$mb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)

Write-Host ""

Write-Host "Done: $Exe  ($mb MB)"

Write-Host ""

Write-Host "Fancy release zip can contain only:"

Write-Host "  Switch2Bridge.exe"

Write-Host "  python_version.txt  (which Python to install)"

Write-Host ""

Write-Host "End users:"

Write-Host "  1. ViGEmBus driver"

Write-Host "  2. Python $PyVer on PATH (64-bit)"

Write-Host "  3. Run Switch2Bridge.exe (installs pip packages on first run)"

Write-Host ""

Write-Host "No app/ or logs/ folder is created beside the release exe."

