@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python is required. Install Python 3 and try again.
  pause
  exit /b 1
)
powershell -NoProfile -Command "Start-Process -FilePath 'py' -ArgumentList '-3', 'web.py', '--launch' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden"
if errorlevel 1 (
  echo Could not open the application. Run: py web.py --launch
  pause
)
endlocal
