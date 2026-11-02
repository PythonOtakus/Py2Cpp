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
set "ENG_SRC=%ZEUS_ROOT%\engine\source"
set "TESTS=%ENG_SRC%\zeus\programs\tests"
set "OUT_TESTS=%ZEUS_OUT%\zeus\programs\tests"
set "TP=%ZEUS_ROOT%\engine\thirdparty"

call "%PAW_ROOT%\tools\_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Use x64 Native Tools Prompt if link fails.
)

call "%TOOLS_DIR%setup_deps.bat"
if errorlevel 1 exit /b 1

echo [zeus] bootstrapping repo out\runtime ...
call "%PAW_ROOT%\tools\_bootstrap_runtime.bat"
if errorlevel 1 exit /b 1

set "PY2CPP_RUNTIME_LINK="
if /I not "%PY2CPP_HEADER_ONLY%"=="1" (
  set "PY2CPP_RUNTIME_LINK="%PY2CPP_RUNTIME_INC%\lib\py2cpp_runtime.lib""
  if not exist "%PY2CPP_RUNTIME_INC%\lib\py2cpp_runtime.lib" (
    echo ERROR: py2cpp_runtime.lib was not generated.
    exit /b 1
  )
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

echo === [zeus] translate test_runtime ===
%PY% main.py "%TESTS%\test_runtime.py" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile test_runtime ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%OUT_TESTS%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%OUT_TESTS%\test_runtime.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%OUT_TESTS%\test_runtime.exe" /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_runtime ===
"%OUT_TESTS%\test_runtime.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_render ===
%PY% main.py "%TESTS%\test_render.py" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile test_render ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%OUT_TESTS%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" /I"%GLFW_INC%" ^
  "%OUT_TESTS%\test_render.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%OUT_TESTS%\test_render.exe" ^
  /link /STACK:8388608 /LIBPATH:"%GLFW_LIB%" %GLFW_LINK% opengl32.lib user32.lib gdi32.lib shell32.lib
if errorlevel 1 exit /b 1

if exist "%GLFW_LIB%\glfw3.dll" (
  copy /Y "%GLFW_LIB%\glfw3.dll" "%OUT_TESTS%\glfw3.dll" >nul
)

echo === [zeus] run test_render ===
"%OUT_TESTS%\test_render.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_editor_smoke ===
%PY% main.py "%TESTS%\test_editor_smoke.py" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile test_editor_smoke ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%OUT_TESTS%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" /I"%GLFW_INC%" ^
  "%OUT_TESTS%\test_editor_smoke.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%OUT_TESTS%\test_editor_smoke.exe" ^
  /link /STACK:33554432 /LIBPATH:"%GLFW_LIB%" %GLFW_LINK% opengl32.lib user32.lib gdi32.lib gdiplus.lib comdlg32.lib ole32.lib shell32.lib
if errorlevel 1 exit /b 1
if exist "%GLFW_LIB%\glfw3.dll" (
  copy /Y "%GLFW_LIB%\glfw3.dll" "%OUT_TESTS%\glfw3.dll" >nul
)

echo === [zeus] run test_editor_smoke ===
"%OUT_TESTS%\test_editor_smoke.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_commands ===
%PY% main.py "%TESTS%\test_commands.py" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile test_commands ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%OUT_TESTS%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%OUT_TESTS%\test_commands.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%OUT_TESTS%\test_commands.exe" ^
  /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_commands ===
"%OUT_TESTS%\test_commands.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_jump ===
%PY% main.py "%TESTS%\test_jump.py" -o "%ZEUS_OUT%" --no-strict
if errorlevel 1 exit /b 1

echo === [zeus] compile test_jump ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_OUT%" /I"%OUT_TESTS%" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%OUT_TESTS%\test_jump.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%OUT_TESTS%\test_jump.exe" ^
  /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_jump ===
"%OUT_TESTS%\test_jump.exe"
if errorlevel 1 exit /b 1

echo.
echo [zeus] ALL GREEN
exit /b 0
