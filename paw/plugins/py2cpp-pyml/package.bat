@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PY=python"
where python >nul 2>&1
if errorlevel 1 set "PY=py -3"
where py >nul 2>&1
if errorlevel 1 if "%PY%"=="py -3" goto NoPython

"%PY%" --version >nul 2>&1
if errorlevel 1 goto NoPython

"%PY%" "%~dp0package.py" %*
exit /b %ERRORLEVEL%

:NoPython
echo ERROR: Python not found. Install Python 3.10+ and ensure python or py is on PATH.
echo        VSIX packaging needs Python only (no npm).
exit /b 1
