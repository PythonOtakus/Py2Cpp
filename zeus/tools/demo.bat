@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "TOOLS_DIR=%~dp0"
set "ZEUS_ROOT=%TOOLS_DIR%.."
for %%I in ("%ZEUS_ROOT%") do set "ZEUS_ROOT=%%~fI"
set "PAW_ROOT=%ZEUS_ROOT%\..\paw"
set "MONOREPO_ROOT=%ZEUS_ROOT%\.."
cd /d "%PAW_ROOT%"

set "PY=python"
if not defined PY2CPP_RUNTIME_INC set "PY2CPP_RUNTIME_INC=%PAW_ROOT%\out\runtime"
set "SQLITE_INC=%PAW_ROOT%\third_party\sqlite"
set "ZEUS_OUT=%ZEUS_ROOT%\out"
set "ZEUS_RUNTIME_INC=%ZEUS_OUT%\runtime"
set "DEMO_PY=%ZEUS_ROOT%\samples\jump\source\jump_demo.py"
set "OUT_DEMO=%ZEUS_OUT%"
set "TP=%ZEUS_ROOT%\engine\thirdparty"

call "%PAW_ROOT%\tools\_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Use x64 Native Tools Prompt if link fails.
)

call "%TOOLS_DIR%setup_deps.bat"
if errorlevel 1 exit /b 1

if not exist "%PY2CPP_RUNTIME_INC%\paw\minimal.h" (
  echo [zeus] bootstrapping repo out\runtime ...
  call "%PAW_ROOT%\tools\_bootstrap_runtime.bat"
  if errorlevel 1 exit /b 1
)

set "GLFW_INC=%TP%\glfw\include"
set "GLFW_LIB=%TP%\glfw\lib-vc2022"
set "GLFW_LINK=glfw3dll.lib"
if not exist "%GLFW_LIB%\glfw3dll.lib" (
  if exist "%TP%\glfw\lib-static-ucrt\glfw3.lib" (
    set "GLFW_LIB=%TP%\glfw\lib-static-ucrt"
    set "GLFW_LINK=glfw3.lib"
  ) else (
    echo ERROR: glfw lib not found under engine\thirdparty\glfw
    exit /b 1
  )
)

mkdir "%ZEUS_OUT%" 2>nul

echo === [zeus] translate jump_demo ===
%PY% main.py "%DEMO_PY%" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile jump_demo ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" /I"%GLFW_INC%" ^
  "%OUT_DEMO%\jump_demo.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  /Fe:"%OUT_DEMO%\jump_demo.exe" ^
  /link /STACK:8388608 /LIBPATH:"%GLFW_LIB%" %GLFW_LINK% opengl32.lib user32.lib gdi32.lib shell32.lib
if errorlevel 1 exit /b 1

if exist "%GLFW_LIB%\glfw3.dll" (
  copy /Y "%GLFW_LIB%\glfw3.dll" "%OUT_DEMO%\glfw3.dll" >nul
)

echo === [zeus] launch jump_demo ===
start "" /D "%MONOREPO_ROOT%" "%OUT_DEMO%\jump_demo.exe"
exit /b 0
