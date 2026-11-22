@echo off
REM Native frozen template expand gate (BEGIN/ECHO/EVAL; no EXEC/def).
setlocal
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

set "OUT=compiler\stages\stage1"
set "BIN=%OUT%\bin"
set "C2=%OUT%\c2_native"
set "DRV=compiler\stages\driver"
set "TMPL_OUT=%OUT%\native_tmpl"

if not exist "%C2%\codegen\template_expand.cpp" (
  echo === need c2_native; run paw_native_self_host ===
  call tools\paw_native_self_host.bat
  if errorlevel 1 exit /b 1
)

if not exist "%BIN%" mkdir "%BIN%"
if exist "%TMPL_OUT%" rmdir /s /q "%TMPL_OUT%"
mkdir "%TMPL_OUT%"

echo === link c1_template_expand_main ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Iout\runtime /Ithird_party\sqlite /I%C2% ^
  /Fe:%BIN%\c1_template_expand_main.exe ^
  %DRV%\c1_template_expand_main.cpp ^
  /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL template expand link
  exit /b 1
)

echo === expand frozen-only templates under templates\ ===
set "PY2CPP_TMPL_EXE=%CD%\%BIN%\c1_template_expand_main.exe"
set "PY2CPP_TMPL_OUT=%CD%\%TMPL_OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -File tools\paw_native_template_expand.ps1
if errorlevel 1 exit /b 1
exit /b 0
