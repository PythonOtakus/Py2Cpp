@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"
set "EXTRA=%*"

echo [py2cpp] Negative compile tests: test\fail\test_*_fail.py ^(expect FAILURE^)
echo   Parallel via scripts\parallel_build.py fail %EXTRA%
echo.

%PY% -c "import sys" 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

call "%~dp0_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Run from "x64 Native Tools Command Prompt" if link fails.
  echo.
)

%PY% scripts\parallel_build.py fail %EXTRA%
set "RC=%ERRORLEVEL%"
call "%~dp0_gen_compile_commands.bat"
exit /b %RC%
