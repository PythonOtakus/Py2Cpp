@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PY=python"
where python >nul 2>&1
if errorlevel 1 set "PY=py -3"

"%PY%" --version >nul 2>&1
if errorlevel 1 goto NoPython

"%PY%" scripts\stat_lines.py %*
exit /b %ERRORLEVEL%

:NoPython
echo ERROR: Python not found. Install Python 3.10+ or ensure python/py is on PATH.
exit /b 1
