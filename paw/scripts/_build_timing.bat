@echo off
REM Wall-clock timer for build_*.bat
REM Usage: end translate label  OR  end compile label  OR  end label (defaults to compile)
if not defined PY set "PY=python"
if /i "%~1"=="start" (
  for /f "usebackq delims=" %%t in (`%PY% "%~dp0_build_timing.py" start`) do set "BUILD_T0=%%t"
  exit /b 0
)
if /i "%~1"=="end" (
  if /i "%~2"=="translate" (
    %PY% "%~dp0_build_timing.py" end "%~3" translate
    exit /b 0
  )
  if /i "%~2"=="compile" (
    %PY% "%~dp0_build_timing.py" end "%~3" compile
    exit /b 0
  )
  %PY% "%~dp0_build_timing.py" end "%~2" build
  exit /b 0
)
echo ERROR: _build_timing.bat: use start or end [translate^|compile] label
exit /b 1
