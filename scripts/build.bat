@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"

if "%~1"=="" goto Usage

call "%~dp0_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Run from "x64 Native Tools Command Prompt" if link fails.
  echo.
)

call "%~dp0_bootstrap_runtime.bat"
if errorlevel 1 exit /b 1

echo [py2cpp] build patterns: %*
echo.

%PY% scripts\parallel_build.py match %*
set "RC=%ERRORLEVEL%"
call "%~dp0_gen_compile_commands.bat"
if %RC% neq 0 goto Fail
exit /b 0

:Fail
call "%~dp0_gen_compile_commands.bat"
exit /b %RC%

:Usage
echo.
echo(Usage: build PATTERN [PATTERN ...] [--jobs N] [--seq] [main.py flags]
echo.
echo(  PATTERN   Substring match on test path/name, or fnmatch if * ? present
echo(  --jobs N  Parallel compile ^(default: 16, or PY2CPP_BUILD_JOBS^)
echo(  --seq     Force serial compile
echo(  Examples:
echo(    build vararg
echo(    build *vararg* --jobs 8
echo(    build lang\test_variadic* --seq
echo.
exit /b 1
