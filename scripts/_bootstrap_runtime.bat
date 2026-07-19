@echo off
REM Regenerates generated/runtime from py2cpp/__init__.py.
REM Idempotent within one cmd process via PY2CPP_RUNTIME_BOOTSTRAPPED.
REM Optional args (e.g. --debug) are forwarded to main.py.
if defined PY2CPP_RUNTIME_BOOTSTRAPPED exit /b 0
if not defined PY set "PY=python"

%PY% -c "import sys" 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

echo === bootstrap: py2cpp runtime ===
call "%~dp0_build_timing.bat" start
%PY% main.py py2cpp\__init__.py -o generated --no-main %*
if errorlevel 1 (
  echo ERROR: failed to translate py2cpp runtime.
  exit /b 1
)
call "%~dp0_build_timing.bat" end translate "bootstrap py2cpp runtime"
call "%~dp0_clean_obj.bat" "%CD%\generated\runtime" "py2cpp" --global-py2cpp
echo.
set "PY2CPP_RUNTIME_BOOTSTRAPPED=1"
exit /b 0
