@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
python package.py %*
exit /b %ERRORLEVEL%
