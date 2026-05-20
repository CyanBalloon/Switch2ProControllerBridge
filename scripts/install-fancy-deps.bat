@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Switch 2 Bridge - Fancy dependencies
echo Folder: %CD%
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH", then run this script again.
  pause
  exit /b 1
)

set "PY="
if exist python_version.txt (
  set /p WANT_VER=<python_version.txt
  echo Release expects Python %WANT_VER%
  for /f "delims=" %%P in ('where python 2^>nul') do (
    "%%P" -c "import sys; raise SystemExit(0 if '%WANT_VER%'==f'{sys.version_info.major}.{sys.version_info.minor}' else 1)" 2>nul
    if not errorlevel 1 (
      set "PY=%%P"
      goto :gotpy
    )
  )
  echo.
  echo WARNING: No Python %WANT_VER% found on PATH.
  echo Install that version, or the Fancy .exe may not start.
  echo Continuing with the first python on PATH...
  echo.
)

for /f "delims=" %%P in ('where python 2^>nul') do (
  set "PY=%%P"
  goto :gotpy
)

:gotpy
if not defined PY (
  echo Could not resolve python.exe.
  pause
  exit /b 1
)

echo Using: %PY%
"%PY%" -c "import sys; print('Version:', sys.version)"
echo.

echo Installing packages (this may take several minutes)...
"%PY%" -m pip install --no-cache-dir --upgrade pip
"%PY%" -m pip install --no-cache-dir -r requirements-fancy.txt
if errorlevel 1 (
  echo.
  echo pip install FAILED. Fix errors above and run this script again.
  pause
  exit /b 1
)

echo.
echo Verifying imports...
"%PY%" -c "import importlib; mods=['bleak','vgamepad','pystray','PIL','PySide6.QtWebEngineWidgets']; [importlib.import_module(m) for m in mods]; print('All imports OK.')"
if errorlevel 1 (
  echo.
  echo Import verification FAILED.
  echo Try: "%PY%" -m pip install --no-cache-dir -r requirements-fancy.txt
  echo Or clear cache: "%PY%" -m pip cache purge
  pause
  exit /b 1
)

echo.
echo Done. You can now run Switch2Bridge.exe
pause
exit /b 0
