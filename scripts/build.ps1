# Fancy onefile .exe — app inside exe; pip packages from user's Python (same version).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Building for Python $PyVer (end users must pip install with the same version)"

Write-Host "Installing build tools..."
python -m pip install -r requirements-build.txt -q

Get-Process Switch2Bridge -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Building Fancy onefile exe..."
python -m PyInstaller Switch2Bridge-fancy.spec --noconfirm --clean

$Exe = Join-Path $Root "dist\Switch2Bridge.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "Build failed: $Exe not found"
}

Copy-Item (Join-Path $Root "requirements-fancy.txt") (Join-Path $Root "dist\requirements-fancy.txt") -Force
Copy-Item (Join-Path $Root "requirements.txt") (Join-Path $Root "dist\requirements.txt") -Force

$InstallDeps = @"
@echo off
cd /d "%~dp0"
where python >nul 2>&1 || (
  echo Install Python $PyVer from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m pip install -r requirements-fancy.txt
echo.
echo Done. Run Switch2Bridge.exe
pause
"@
Set-Content -Path (Join-Path $Root "dist\Install dependencies.bat") -Value $InstallDeps -Encoding ASCII

$mb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $Exe  ($mb MB)"
Write-Host ""
Write-Host "End users (Python $PyVer on PATH):"
Write-Host "  1. ViGEmBus driver"
Write-Host "  2. Install dependencies.bat  (once)"
Write-Host "  3. Switch2Bridge.exe"
Write-Host ""
Write-Host "No app/ folder is created. Only logs/ may appear beside the exe."
