@echo off
setlocal EnableExtensions
chcp 65001 >nul
if not defined PY set "PY=python"
if not defined ROOT set "ROOT=%~dp0.."
cd /d "%ROOT%"

if not exist "%ROOT%\generated\runtime\py2cpp\minimal.h" (
  exit /b 0
)

echo === clangd: regenerate compile_commands.json ===
%PY% scripts\gen_compile_commands.py
if errorlevel 1 (
  echo NOTE: gen_compile_commands failed ^(clangd IDE only; MSVC build unaffected^).
)
exit /b 0
