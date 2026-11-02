@echo off
setlocal EnableExtensions
set "ZEUS_ROOT=%~dp0"
set "MONOREPO_ROOT=%ZEUS_ROOT%.."
set "PAW_ROOT=%MONOREPO_ROOT%\paw"
cd /d "%PAW_ROOT%"
set "ZEUS_FFI=%ZEUS_ROOT%ffi"
set "GLFW_H=%ZEUS_ROOT%third_party\glfw\include\GLFW\glfw3.h"
set "GLFW_INC=%ZEUS_ROOT%third_party\glfw\include"

set "CHECK="
set "TARGET=all"
:parse
if "%~1"=="" goto run
if /I "%~1"=="--check" (
  set "CHECK=--check"
  shift
  goto parse
)
if /I "%~1"=="glfw" (
  set "TARGET=glfw"
  shift
  goto parse
)
if /I "%~1"=="gl" (
  set "TARGET=gl"
  shift
  goto parse
)
if /I "%~1"=="all" (
  set "TARGET=all"
  shift
  goto parse
)
echo Usage: zeus\ffi.bat [all^|glfw^|gl] [--check]
echo   Regenerates zeus\ffi\glfw\glfw3.pyi and/or zeus\ffi\gl\gl.pyi via scripts\gen_c_ffi.py
echo   GLFW: zeus\third_party\glfw\include\GLFW\glfw3.h  ^(+ GLFW_INCLUDE_NONE^)
echo   GL:   Windows Kits um\gl\GL.h  ^(bare name `gl`^)
exit /b 1

:run
if not exist "%GLFW_H%" (
  echo ERROR: missing "%GLFW_H%" — run zeus\setup_deps.bat first
  exit /b 1
)

if "%TARGET%"=="gl" goto do_gl
if "%TARGET%"=="all" goto do_glfw
if "%TARGET%"=="glfw" goto do_glfw
goto done

:do_glfw
echo === generate zeus\ffi\glfw\glfw3.pyi ===
python scripts\gen_c_ffi.py "%GLFW_H%" --out "%ZEUS_FFI%\glfw\glfw3.pyi" --no-include-deps --clang-arg=-I%GLFW_INC% --clang-arg=-DGLFW_INCLUDE_NONE --clang-arg=--target=x86_64-pc-windows-msvc %CHECK%
if errorlevel 1 exit /b %ERRORLEVEL%
if "%TARGET%"=="glfw" goto done

:do_gl
echo === generate zeus\ffi\gl\gl.pyi ===
python scripts\gen_c_ffi.py gl --out "%ZEUS_FFI%\gl\gl.pyi" --no-include-deps %CHECK%
if errorlevel 1 exit /b %ERRORLEVEL%

:done
echo OK: zeus FFI pyi up to date
exit /b 0
