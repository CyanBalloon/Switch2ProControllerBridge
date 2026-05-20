@echo off
cd /d "%~dp0"
echo Installing build dependencies...
python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

taskkill /IM Switch2Bridge.exe /F >nul 2>&1

echo Building Tk onefile exe...
python -m PyInstaller Switch2Bridge-tk.spec --noconfirm --clean
if errorlevel 1 exit /b 1

if not exist "dist\Switch2Bridge.exe" (
  echo Build failed: dist\Switch2Bridge.exe not found
  exit /b 1
)

echo.
echo Done: dist\Switch2Bridge.exe
echo Run from anywhere. ViGEmBus required on target PC.
pause
