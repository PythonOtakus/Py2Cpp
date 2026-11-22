@echo off
REM 自举编译器驱动正向 tests（列表 ≡ parallel_build._list_all_tests）
REM 译码：c1_test_main.exe；调度：paw_native_parallel_build.py
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

if not exist "out\runtime\lib\py2cpp_runtime.lib" (
  echo FAIL need out\runtime\lib\py2cpp_runtime.lib
  exit /b 1
)
if not exist "compiler\stages\stage1\c2_native\mid\emit_cpp.cpp" (
  call tools\paw_native_self_host.bat
  if errorlevel 1 exit /b 1
)

set "BIN=compiler\stages\stage1\bin"
if not exist "%BIN%" mkdir "%BIN%"

echo === link c1_test_main ===
if exist "%BIN%\c1_test_main.exe" del /f /q "%BIN%\c1_test_main.exe" 2>nul
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Iout\runtime /Ithird_party\sqlite /Icompiler\stages\stage1\c2_native ^
  /Fe:%BIN%\c1_test_main.exe ^
  compiler\stages\driver\c1_test_main.cpp ^
  /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 exit /b 1

set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

echo === native parallel tests ===
"%PY%" tools\paw_native_parallel_build.py %*
exit /b %ERRORLEVEL%
