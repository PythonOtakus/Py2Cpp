@echo off
REM Regenerates generated/runtime from py2cpp/__init__.py.
REM Skip translate when py2cpp/templates/src/ffi are unchanged (see bootstrap_stamp).
REM Idempotent within one cmd process via PY2CPP_RUNTIME_BOOTSTRAPPED.
REM Optional args (e.g. --debug) are forwarded to main.py.
REM PY2CPP_FORCE_BOOTSTRAP=1 forces a full translate.
if defined PY2CPP_RUNTIME_BOOTSTRAPPED exit /b 0
if not defined PY set "PY=python"

%PY% -c "import sys" 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

set "BS_DEBUG="
for %%A in (%*) do if /I "%%~A"=="--debug" set "BS_DEBUG=--debug"

if defined PY2CPP_FORCE_BOOTSTRAP goto do_translate

%PY% -c "from src.codegen.bootstrap_stamp import should_skip_translate; import sys; raise SystemExit(0 if should_skip_translate(debug='--debug' in sys.argv) else 1)" %BS_DEBUG%
if errorlevel 1 goto do_translate
echo bootstrap: skip translate ^(inputs unchanged^)
goto after_translate

:do_translate
echo === bootstrap: py2cpp runtime ===
call "%~dp0_build_timing.bat" start
%PY% main.py py2cpp\__init__.py -o generated --no-main %*
if errorlevel 1 (
  echo ERROR: failed to translate py2cpp runtime.
  exit /b 1
)
%PY% -c "from src.codegen.bootstrap_stamp import write_stamp; import sys; write_stamp(debug='--debug' in sys.argv)" %BS_DEBUG%
call "%~dp0_build_timing.bat" end translate "bootstrap py2cpp runtime"

:after_translate

REM 胖库：默认编 py2cpp_runtime.lib（PY2CPP_HEADER_ONLY=1 跳过）
if /I not "%PY2CPP_HEADER_ONLY%"=="1" (
  echo === bootstrap: py2cpp_runtime.lib ===
  call "%~dp0_build_timing.bat" start
  %PY% -c "from pathlib import Path; from src.compile import ensure_runtime_fat_lib; r=ensure_runtime_fat_lib(Path('generated/runtime')); print(r.stderr or r.stdout or ('ok: '+str(r.artifact))); raise SystemExit(0 if r.ok else 1)"
  if errorlevel 1 (
    echo ERROR: failed to build py2cpp_runtime.lib
    exit /b 1
  )
  call "%~dp0_build_timing.bat" end compile "bootstrap py2cpp_runtime.lib"
)

call "%~dp0_clean_obj.bat" "%CD%\generated\runtime" "py2cpp" --global-py2cpp
echo.
set "PY2CPP_RUNTIME_BOOTSTRAPPED=1"
exit /b 0
