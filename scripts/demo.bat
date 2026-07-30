@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "SCRIPT_DIR=%%~fI\"
set "ROOT=%SCRIPT_DIR%.."
cd /d "%ROOT%"

set "PY=python"
set "MATCH_PY=%CD%\scripts\match_demo_files.py"
set "EX_DIR=%CD%\examples"
set "GEN_DIR=%CD%\generated\examples"
set "COUNT=0"
set "FAILED="
set "MATCHED=0"

if "%~1"=="" goto Usage

set "PAT_ARGS="
set "EXTRA="
:ParseArgs
if "%~1"=="" goto AfterParse
echo %~1| findstr /R "^-" >nul && goto CollectExtra
set "PAT_ARGS=!PAT_ARGS! "%~1""
shift
goto ParseArgs

:CollectExtra
set "EXTRA=!EXTRA! %~1"
shift
goto ParseArgs

:AfterParse
if not defined PAT_ARGS goto Usage

echo [py2cpp] demo patterns:!PAT_ARGS!
if defined EXTRA echo [py2cpp] main.py extra:!EXTRA!
echo.

%PY% -c "import sys" 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

call "%SCRIPT_DIR%_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Run from "x64 Native Tools Command Prompt" if link fails.
  echo.
)

call "%SCRIPT_DIR%_bootstrap_runtime.bat"
if errorlevel 1 exit /b 1


for /f "usebackq delims=" %%R in (`%PY% "%MATCH_PY%"!PAT_ARGS!`) do (
  set "MATCHED=1"
  call :DemoOne "%%R"
)

if !MATCHED! equ 0 (
  echo ERROR: no examples\**\*.py matched patterns:!PAT_ARGS!
  goto NoMatch
)

if defined FAILED (
  echo FAILED demos:!FAILED!
  exit /b 1
)

echo All !COUNT! matched demo(s) built and ran successfully.
exit /b 0

:DemoOne
set "REL=%~1"
set "SRC=examples\!REL!"
if not exist "%SRC%" (
  echo ERROR: not found: %SRC%
  set "FAILED=!FAILED! %SRC%(missing)"
  exit /b 0
)
set /a COUNT+=1
echo === demo examples\!REL! ===
set "EXE=!GEN_DIR!\!REL:.py=.exe!"
set "OBJDIR=!GEN_DIR!\%%~p1"
call "%SCRIPT_DIR%_build_timing.bat" start
%PY% main.py "examples\!REL!" -o generated -c --compiler cl --exe "!EXE!" !EXTRA!
set "BUILD_ERR=!ERRORLEVEL!"
call "%SCRIPT_DIR%_build_timing.bat" end "examples\!REL!"
call "%SCRIPT_DIR%_clean_obj.bat" "!OBJDIR!" %%~n1
if !BUILD_ERR! neq 0 (
  set "FAILED=!FAILED! !REL!(build)"
  echo.
  exit /b 0
)
if not exist "!EXE!" (
  echo WARNING: exe not found: !EXE!
  set "FAILED=!FAILED! !REL!(no exe)"
  echo.
  exit /b 0
)
echo run: !EXE!
"!EXE!"
set "RUN_ERR=!ERRORLEVEL!"
if !RUN_ERR! neq 0 (
  set "FAILED=!FAILED! !REL!(exit !RUN_ERR!)"
) else (
  echo OK: !EXE!
)
echo.
exit /b 0

:NoMatch
echo   PATTERN   Substring match on examples path/name, or fnmatch if * ? present
goto Usage

:Usage
echo.
echo(Usage: demo PATTERN [PATTERN ...] [main.py flags]
echo.
echo(  PATTERN   Substring match on examples path/name, or fnmatch if * ? present
echo(  Examples:
echo(    demo panel
echo(    demo *ui*
echo(    demo ui_panel_demo.py
echo.
exit /b 1
