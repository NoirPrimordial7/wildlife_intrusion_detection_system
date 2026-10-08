@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows_full.ps1" %*
if errorlevel 1 (
    echo.
    echo Setup failed. Read the error above or .setup\setup.log, then rerun SETUP.bat.
    pause
    exit /b 1
)
echo.
echo Setup complete. Double-click START.bat to open the app.
pause
exit /b 0
