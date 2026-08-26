@echo off
setlocal EnableExtensions
chcp 65001 >nul
call "%~dp0plugins\py2cpp-architect\package.bat" %*
exit /b %ERRORLEVEL%
