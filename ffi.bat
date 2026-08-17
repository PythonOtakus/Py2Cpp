@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: ffi ^<header^> [options]
  echo   ffi windows
  echo   ffi windows --check
  echo   ffi stdio
  echo   ffi string
  echo   ffi third_party\sqlite\sqlite3.h
  echo   ffi third_party\sqlite\sqlite3.h --check
  echo.
  echo Defaults: windows -^> ffi\windows\windows.pyi ; CRT -^> ffi\crt\^<stem^>.pyi
  echo Options: --out PATH  --check  --include-deps / --no-include-deps  --clang-arg ARG
  echo See docs\c-ffi-pyi.md
  exit /b 1
)
python scripts\gen_c_ffi.py %*
exit /b %ERRORLEVEL%
