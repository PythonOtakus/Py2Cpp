@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ZEUS_ROOT=%~dp0"
set "REPO_ROOT=%ZEUS_ROOT%.."
cd /d "%REPO_ROOT%"

set "PY=python"
if not defined PY2CPP_RUNTIME_INC set "PY2CPP_RUNTIME_INC=%REPO_ROOT%\generated\runtime"
set "SQLITE_INC=%REPO_ROOT%\third_party\sqlite"
set "ZEUS_RUNTIME_INC=%ZEUS_ROOT%generated\runtime"

call "%REPO_ROOT%\scripts\_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Use x64 Native Tools Prompt if link fails.
)

call "%ZEUS_ROOT%setup_deps.bat"
if errorlevel 1 exit /b 1

echo [zeus] bootstrapping repo generated\runtime ...
call "%REPO_ROOT%\scripts\_bootstrap_runtime.bat"
if errorlevel 1 exit /b 1

set "PY2CPP_RUNTIME_LINK="
if /I not "%PY2CPP_HEADER_ONLY%"=="1" (
  set "PY2CPP_RUNTIME_LINK="%PY2CPP_RUNTIME_INC%\lib\py2cpp_runtime.lib""
  if not exist "%PY2CPP_RUNTIME_INC%\lib\py2cpp_runtime.lib" (
    echo ERROR: py2cpp_runtime.lib was not generated.
    exit /b 1
  )
)

set "GLFW_INC=%ZEUS_ROOT%third_party\glfw\include"
set "GLFW_LIB=%ZEUS_ROOT%third_party\glfw\lib-vc2022"
set "GLFW_LINK=glfw3dll.lib"
if not exist "%GLFW_LIB%\glfw3dll.lib" (
  if exist "%ZEUS_ROOT%third_party\glfw\lib-static-ucrt\glfw3.lib" (
    set "GLFW_LIB=%ZEUS_ROOT%third_party\glfw\lib-static-ucrt"
    set "GLFW_LINK=glfw3.lib"
  ) else (
    echo ERROR: glfw lib not found under third_party\glfw
    exit /b 1
  )
)

mkdir "%ZEUS_ROOT%generated" 2>nul

echo === [zeus] translate test_runtime ===
%PY% main.py zeus\src\test_runtime.py -o zeus\generated
if errorlevel 1 exit /b 1

echo === [zeus] compile test_runtime ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_ROOT%generated" /I"%ZEUS_ROOT%generated\zeus\src" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%ZEUS_ROOT%generated\zeus\src\test_runtime.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%ZEUS_ROOT%generated\zeus\src\test_runtime.exe" /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_runtime ===
"%ZEUS_ROOT%generated\zeus\src\test_runtime.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_render ===
%PY% main.py zeus\src\test_render.py -o zeus\generated
if errorlevel 1 exit /b 1

echo === [zeus] compile test_render ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_ROOT%generated" /I"%ZEUS_ROOT%generated\zeus\src" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" /I"%GLFW_INC%" ^
  "%ZEUS_ROOT%generated\zeus\src\test_render.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%ZEUS_ROOT%generated\zeus\src\test_render.exe" ^
  /link /STACK:8388608 /LIBPATH:"%GLFW_LIB%" %GLFW_LINK% opengl32.lib user32.lib gdi32.lib shell32.lib
if errorlevel 1 exit /b 1

if exist "%GLFW_LIB%\glfw3.dll" (
  copy /Y "%GLFW_LIB%\glfw3.dll" "%ZEUS_ROOT%generated\zeus\src\glfw3.dll" >nul
)

echo === [zeus] run test_render ===
"%ZEUS_ROOT%generated\zeus\src\test_render.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_editor_smoke ===
%PY% main.py zeus\src\test_editor_smoke.py -o zeus\generated
if errorlevel 1 exit /b 1

echo === [zeus] compile test_editor_smoke ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_ROOT%generated" /I"%ZEUS_ROOT%generated\zeus\src" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" /I"%GLFW_INC%" ^
  "%ZEUS_ROOT%generated\zeus\src\test_editor_smoke.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%ZEUS_ROOT%generated\zeus\src\test_editor_smoke.exe" ^
  /link /STACK:33554432 /LIBPATH:"%GLFW_LIB%" %GLFW_LINK% opengl32.lib user32.lib gdi32.lib gdiplus.lib comdlg32.lib ole32.lib shell32.lib
if errorlevel 1 exit /b 1
if exist "%GLFW_LIB%\glfw3.dll" (
  copy /Y "%GLFW_LIB%\glfw3.dll" "%ZEUS_ROOT%generated\zeus\src\glfw3.dll" >nul
)

echo === [zeus] run test_editor_smoke ===
"%ZEUS_ROOT%generated\zeus\src\test_editor_smoke.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_commands ===
%PY% main.py zeus\src\test_commands.py -o zeus\generated
if errorlevel 1 exit /b 1

echo === [zeus] compile test_commands ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_ROOT%generated" /I"%ZEUS_ROOT%generated\zeus\src" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%ZEUS_ROOT%generated\zeus\src\test_commands.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%ZEUS_ROOT%generated\zeus\src\test_commands.exe" ^
  /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_commands ===
"%ZEUS_ROOT%generated\zeus\src\test_commands.exe"
if errorlevel 1 exit /b 1

echo === [zeus] translate test_jump ===
%PY% main.py zeus\src\test_jump.py -o zeus\generated
if errorlevel 1 exit /b 1

echo === [zeus] compile test_jump ===
cl /nologo /EHsc /utf-8 /std:c++14 ^
  /I"%ZEUS_ROOT%generated" /I"%ZEUS_ROOT%generated\zeus\src" /I"%ZEUS_RUNTIME_INC%" /I"%PY2CPP_RUNTIME_INC%" /I"%SQLITE_INC%" ^
  "%ZEUS_ROOT%generated\zeus\src\test_jump.cpp" ^
  "%SQLITE_INC%\sqlite3.c" ^
  %PY2CPP_RUNTIME_LINK% ^
  /Fe:"%ZEUS_ROOT%generated\zeus\src\test_jump.exe" ^
  /link /STACK:8388608
if errorlevel 1 exit /b 1

echo === [zeus] run test_jump ===
"%ZEUS_ROOT%generated\zeus\src\test_jump.exe"
if errorlevel 1 exit /b 1

echo.
echo [zeus] ALL GREEN
exit /b 0
