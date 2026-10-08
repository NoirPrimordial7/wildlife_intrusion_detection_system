@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch.py %*
    if errorlevel 1 goto failed
    exit /b 0
)
for %%V in (3.12 3.11 3.10) do (
    py -%%V -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 (
        py -%%V launch.py %*
        if errorlevel 1 goto failed
        exit /b 0
    )
)
python -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12); assert sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 (
    python launch.py %*
    if errorlevel 1 goto failed
    exit /b 0
)
echo Install 64-bit Python 3.12 from python.org and select Add Python to PATH.
echo Then double-click START.bat again. See QUICKSTART.md.
:failed
echo.
echo VanRakshak could not start. The error is shown above.
pause
exit /b 1
