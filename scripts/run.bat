@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"
set "MATCH_PY=%CD%\scripts\match_test_files.py"
set "GEN_DIR=%CD%\generated\test"
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

echo [py2cpp] run patterns:!PAT_ARGS!
if defined EXTRA echo NOTE: ignoring main.py flags:!EXTRA!
echo.

%PY% -c "import sys" 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

for /f "usebackq delims=" %%R in (`%PY% "%MATCH_PY%"!PAT_ARGS!`) do (
  set "MATCHED=1"
  call :RunOneTest "%%R"
)

if !MATCHED! equ 0 (
  echo ERROR: no test\**\test_*.py matched patterns:!PAT_ARGS!
  goto NoMatch
)

if defined FAILED (
  echo FAILED runs:!FAILED!
  exit /b 1
)

echo All !COUNT! matched test(s) passed.
exit /b 0

:RunOneTest
set "REL=%~1"
set "SRC=test\!REL!"
if not exist "%SRC%" (
  echo ERROR: not found: %SRC%
  set "FAILED=!FAILED! %SRC%(missing)"
  exit /b 0
)
set "EXE=!GEN_DIR!\!REL:.py=.exe!"
set /a COUNT+=1
echo === run test\!REL! ===
if not exist "!EXE!" (
  echo ERROR: exe not found: !EXE! ^(run build first^)
  set "FAILED=!FAILED! !REL!(no exe)"
  echo.
  exit /b 0
)
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
echo   PATTERN   Substring match on test path/name, or fnmatch if * ? present
goto Usage

:Usage
echo.
echo(Usage: run PATTERN [PATTERN ...]
echo.
echo(  PATTERN   Same as build.bat; runs generated\test\...\test_*.exe only
echo(  Examples:
echo(    run vararg
echo(    run *vararg*
echo(    run lang\test_variadic*
echo(    run variadic vararg
echo(    run lang\test_variadic_template.py
echo.
exit /b 1
