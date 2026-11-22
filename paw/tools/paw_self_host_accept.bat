@echo off
REM Compiler self-host acceptance (no Python after one-time runtime bootstrap):
REM   1) fat lib present (or PY2CPP_RUNTIME_NOPY rebuild)
REM   2) paw_native_self_host  (c2_native ≡ c3_native)
REM   3) paw_native_template_expand  (production templates 0 SKIP)
setlocal
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

if not exist "out\runtime\lib\py2cpp_runtime.lib" (
  if exist "out\runtime\paw\minimal.h" (
    echo === accept: nopy rebuild fat lib ===
    call tools\paw_runtime_nopy.bat
    if errorlevel 1 exit /b 1
  ) else (
    echo FAIL need out\runtime — one-time: tools\_bootstrap_runtime.bat
    exit /b 1
  )
)

echo === accept: native self-host ===
call tools\paw_native_self_host.bat
if errorlevel 1 exit /b 1

echo === accept: native template expand ===
call tools\paw_native_template_expand.bat
if errorlevel 1 exit /b 1

echo OK paw_self_host_accept
exit /b 0
