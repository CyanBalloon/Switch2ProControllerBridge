@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Run from repo: scripts\   or beside Switch2Bridge.exe in dist (copy this file if needed)
set "ROOT=%CD%"
if exist "%~dp0..\requirements-fancy.txt" set "ROOT=%~dp0.."
if exist "%ROOT%\requirements-fancy.txt" (
  set "REQ=%ROOT%\requirements-fancy.txt"
) else if exist "%CD%\requirements-fancy.txt" (
  set "REQ=%CD%\requirements-fancy.txt"
) else (
  echo requirements-fancy.txt not found.
  echo Run from the project folder or copy this script next to that file.
  pause
  exit /b 1
)

echo Switch 2 Bridge - Uninstall Fancy dependencies
echo Requirements: %REQ%
echo.

set "PY="

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

if exist "%ROOT%\python_version.txt" (
  set /p WANT_VER=<"%ROOT%\python_version.txt"
  echo Looking for Python %WANT_VER%...
  for /f "delims=" %%P in ('where python 2^>nul') do (
    "%%P" -c "import sys; raise SystemExit(0 if '%WANT_VER%'==f'{sys.version_info.major}.{sys.version_info.minor}' else 1)" 2>nul
    if not errorlevel 1 (
      set "PY=%%P"
      goto :gotpy
    )
  )
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
echo This removes packages listed in requirements-fancy.txt
echo (bleak, vgamepad, pystray, Pillow, PySide6, ...).
echo.
echo Close Switch 2 Bridge / any game using the virtual controller first.
echo.
set /p CONFIRM=Continue? [y/N] 
if /i not "%CONFIRM%"=="y" (
  echo Cancelled.
  pause
  exit /b 0
)

echo.
echo Stopping Switch 2 Bridge and related Python processes...
taskkill /IM Switch2Bridge.exe /F >nul 2>&1
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -in @('python.exe','pythonw.exe')) -and ($_.CommandLine -match 'Switch2Bridge|main\.py|frozen_fancy|switch2') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo Waiting for file locks to clear...
timeout /t 3 /nobreak >nul

echo Clearing pip wheel cache for vgamepad (avoids install errors later)...
"%PY%" -m pip cache remove vgamepad >nul 2>&1

echo.
echo Uninstalling (vgamepad last — its DLL is often locked while the app runs)...
set "FAILED=0"

call :uninstall PySide6
call :uninstall PySide6-Essentials
call :uninstall PySide6-Addons
call :uninstall shiboken6
call :uninstall bleak
call :uninstall pystray
call :uninstall Pillow
call :uninstall vgamepad

if "%FAILED%"=="1" (
  echo.
  echo Some packages could not be removed. Usually something still has the app open.
  echo - Close Switch2Bridge.exe and any game using the Xbox pad
  echo - Close other Python windows, then run this script again
  echo - Or reboot, then run this script again
  echo.
) else (
  echo.
  echo All listed packages removed.
)

echo.
echo Done. Run Switch2Bridge.exe to test first-time install again.
pause
exit /b 0

:uninstall
"%PY%" -m pip uninstall -y %1 >nul 2>&1
if errorlevel 1 (
  echo   %1 - retry after wait...
  timeout /t 2 /nobreak >nul
  "%PY%" -m pip uninstall -y %1
  if errorlevel 1 (
    echo   %1 - FAILED ^(file may be in use^)
    set "FAILED=1"
  ) else (
    echo   %1 - removed
  )
) else (
  echo   %1 - removed
)
exit /b 0
