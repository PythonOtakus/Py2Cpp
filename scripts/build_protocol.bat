@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"
set "EXE_OK=%CD%\generated\test\lang\test_protocol.exe"

echo [py2cpp] Protocol constraint compile tests
echo   OK:   test\lang\test_protocol.py
echo   FAIL: test\fail\test_*_fail.py via scripts\build_fail.bat
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

echo === expect compile OK ===
call "%~dp0_build_timing.bat" start
%PY% main.py test\lang\test_protocol.py -o generated -c --compiler cl --exe "%EXE_OK%" %*
set BUILD_ERR=%ERRORLEVEL%
call "%~dp0_build_timing.bat" end "test\lang\test_protocol.py"
call "%~dp0_clean_obj.bat" "%CD%\generated\test\lang" "test_protocol"
if %BUILD_ERR% neq 0 goto :FailOk

echo.
call "%~dp0build_fail.bat" %*
if errorlevel 1 exit /b 1

echo.
echo OK: valid type compiled; invalid types rejected at compile time.
call "%~dp0_gen_compile_commands.bat"
exit /b 0

:FailOk
echo.
echo FAILED: test\lang\test_protocol.py should compile ^(protocol constraints satisfied^).
exit /b 1
