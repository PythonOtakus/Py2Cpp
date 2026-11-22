@echo off
REM Compile+run repo-root main.paw via Paw native bootstrap (c1_test_main).
REM Keeps only main.cpp + main.exe in the repo root; all other intermediates are removed.
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "REPO=%CD%"
set "PAW=%REPO%\paw"

if not exist "%REPO%\main.paw" (
  echo FAIL missing %REPO%\main.paw
  exit /b 1
)

call "%PAW%\tools\_init_msvc.bat"
if errorlevel 1 (
  echo FAIL MSVC not configured. Run from "x64 Native Tools Command Prompt" or install VS C++ tools.
  exit /b 1
)

if not exist "%PAW%\out\runtime\lib\py2cpp_runtime.lib" (
  echo FAIL need %PAW%\out\runtime\lib\py2cpp_runtime.lib
  echo        one-time: cd paw ^& tools\_bootstrap_runtime.bat
  exit /b 1
)

if not exist "%PAW%\compiler\stages\stage1\c2_native\mid\emit_cpp.cpp" (
  echo === bootstrap native self-host ===
  pushd "%PAW%"
  call tools\paw_native_self_host.bat
  set "RC=!ERRORLEVEL!"
  popd
  if not "!RC!"=="0" exit /b !RC!
)

set "BIN=%PAW%\compiler\stages\stage1\bin"
if not exist "%BIN%" mkdir "%BIN%"
set "C1=%BIN%\c1_test_main.exe"

if not exist "%C1%" (
  echo === link c1_test_main ===
  pushd "%PAW%"
  cl /nologo /std:c++17 /EHsc /utf-8 ^
    /Iout\runtime /Ithird_party\sqlite /Icompiler\stages\stage1\c2_native ^
    /Fe:"%C1%" ^
    compiler\stages\driver\c1_test_main.cpp ^
    /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
  set "RC=!ERRORLEVEL!"
  popd
  if not "!RC!"=="0" exit /b !RC!
  del /q "%BIN%\c1_test_main.obj" 2>nul
  del /q "%BIN%\c1_test_main.exe.manifest" 2>nul
)

REM Stage under a tests/.../test_*.paw path so mid-emit treats it as a global-main entry.
set "STAGE=%PAW%\out\_root_main"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\tests\root" >nul
copy /Y "%REPO%\main.paw" "%STAGE%\tests\root\test_main.paw" >nul
if errorlevel 1 (
  echo FAIL copy main.paw to stage
  exit /b 1
)

echo === native emit main.paw ===
"%C1%" --out "%STAGE%\out" "%STAGE%\tests\root\test_main.paw"
if errorlevel 1 (
  echo FAIL native emit
  if exist "%STAGE%" rmdir /s /q "%STAGE%"
  exit /b 1
)

set "EMITH=%STAGE%\out\tests\root\test_main.h"
set "EMITCPP=%STAGE%\out\tests\root\test_main.cpp"
if not exist "%EMITH%" (
  echo FAIL missing %EMITH%
  if exist "%STAGE%" rmdir /s /q "%STAGE%"
  exit /b 1
)
if not exist "%EMITCPP%" (
  echo FAIL missing %EMITCPP%
  if exist "%STAGE%" rmdir /s /q "%STAGE%"
  exit /b 1
)

REM Amalgamate .h into a single root main.cpp (no leftover .h).
echo === write %REPO%\main.cpp ===
powershell -NoProfile -Command ^
  "$h = Get-Content -LiteralPath $env:EMITH -Raw;" ^
  "$c = Get-Content -LiteralPath $env:EMITCPP -Raw;" ^
  "$nl = [Environment]::NewLine;" ^
  "$h = [regex]::Replace($h, '(?m)^// seed mid_emit -[^\r\n]*\r?\n', '');" ^
  "$h = [regex]::Replace($h, '(?ms)^#ifndef\s+\w+\s*\r?\n#define\s+\w+\s*\r?\n', '');" ^
  "$h = [regex]::Replace($h, '(?ms)\r?\n#endif\s*//[^\r\n]*\s*\z', '');" ^
  "$h = $h.TrimEnd() + $nl + $nl;" ^
  "$c = [regex]::Replace($c, '(?m)^#include\s+\"test_main\.h\"\s*\r?\n', [string]$h);" ^
  "$c = [regex]::Replace($c, '(?m)^// seed mid_emit -[^\r\n]*\r?\n', '// emitted from main.paw (Paw native bootstrap)' + $nl);" ^
  "$utf8 = New-Object System.Text.UTF8Encoding $false;" ^
  "[System.IO.File]::WriteAllText((Join-Path $env:REPO 'main.cpp'), $c, $utf8)"
if errorlevel 1 (
  echo FAIL amalgamate main.cpp
  if exist "%STAGE%" rmdir /s /q "%STAGE%"
  exit /b 1
)

echo === cl main.cpp ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%PAW%\out\runtime" /I"%PAW%\third_party\sqlite" ^
  /Fe:"%REPO%\main.exe" ^
  /Fo:"%STAGE%\main.obj" ^
  "%REPO%\main.cpp" ^
  /link /STACK:8388608 "%PAW%\out\runtime\lib\py2cpp_runtime.lib"
set "RC=%ERRORLEVEL%"

REM Drop every intermediate; keep only root main.cpp + main.exe.
del /q "%REPO%\main.obj" 2>nul
del /q "%REPO%\main.exe.manifest" 2>nul
del /q "%REPO%\main.ilk" 2>nul
del /q "%REPO%\main.pdb" 2>nul
del /q "%REPO%\vc*.pdb" 2>nul
if exist "%STAGE%" rmdir /s /q "%STAGE%"

if not "%RC%"=="0" (
  echo FAIL compile main.cpp
  exit /b %RC%
)

echo === run main.exe ===
"%REPO%\main.exe"
exit /b %ERRORLEVEL%
