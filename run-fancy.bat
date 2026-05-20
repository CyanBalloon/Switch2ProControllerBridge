@echo off
cd /d "%~dp0"
where python >nul 2>&1 || (
  echo Python not found on PATH.
  pause
  exit /b 1
)
python -m pip install --no-cache-dir -r requirements-fancy.txt
pythonw main.py --fancy
