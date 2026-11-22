@echo off
REM 自举入口（唯一真相源）：用宿主 host/ 直译 compiler/paw/**/*.paw → stage1。
REM 不再经过 compiler/py/mid/emit_cpp.py 种子轨（已归档为历史参考）。
REM
REM 产物：compiler\stages\stage1\compiler\paw\<rel>.{h,cpp}
REM      + compiler\stages\stage1\bin\c1_seed_driver.exe（原生 C1）
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

if not exist "out\runtime\lib\py2cpp_runtime.lib" (
  call tools\_bootstrap_runtime.bat
  if errorlevel 1 exit /b 1
)

set "OUT=compiler\stages\stage1"
set "BIN=%OUT%\bin"
set "DRV=compiler\stages\driver"
set "C1DRV=%BIN%\c1_seed_driver.exe"

echo === host emit compiler/paw/**/*.paw → %OUT% ===
python tools\paw_seed_emit_host.py --out "%OUT%"
if errorlevel 1 (
  echo FAIL host seed emit
  exit /b 1
)

if not exist "%BIN%" mkdir "%BIN%"
if not exist "%OUT%\compiler\paw\mid\emit_cpp.h" (
  echo FAIL missing %OUT%\compiler\paw\mid\emit_cpp.h
  exit /b 1
)

echo === cl+link c1_seed_driver.exe ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Iout\runtime /Ithird_party\sqlite /I%OUT% ^
  /Fe:%C1DRV% ^
  %DRV%\c1_seed_driver.cpp ^
  /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_seed_driver link
  exit /b 1
)

echo === run c1_seed_driver --smoke ===
"%C1DRV%" --smoke
if errorlevel 1 (
  echo FAIL c1_seed_driver smoke
  exit /b 1
)

echo OK host-seeded c1_seed_driver
exit /b 0
