@echo off
setlocal EnableExtensions
chcp 65001 >nul
call "%~dp0plugins\py2cpp-pyml\package.bat" %*
exit /b %ERRORLEVEL%
