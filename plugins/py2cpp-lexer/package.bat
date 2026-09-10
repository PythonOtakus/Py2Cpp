@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto TryLauncher
python "%~dp0package.py" %*
exit /b %ERRORLEVEL%

:TryLauncher
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto NoPython
py -3 "%~dp0package.py" %*
exit /b %ERRORLEVEL%

:NoPython
echo ERROR: Python 3.10+ not found. Ensure python or py is on PATH.
echo        VSIX packaging needs Python only (no npm).
exit /b 1
