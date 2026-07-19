@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"
set "EXTRA=%*"

echo [py2cpp] Build all test\**\test_*.py ^(skip test\fail\, test\perf\, *_fail.py^)
echo   Parallel compile via scripts\parallel_build.py ^(default 16, PY2CPP_BUILD_JOBS / --jobs N / --seq^)
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

call "%~dp0_bootstrap_runtime.bat"
if errorlevel 1 exit /b 1

%PY% scripts\parallel_build.py all %EXTRA%
set "RC=%ERRORLEVEL%"
call "%~dp0_build_timing.bat" end "build_all"
call "%~dp0_gen_compile_commands.bat"
exit /b %RC%
