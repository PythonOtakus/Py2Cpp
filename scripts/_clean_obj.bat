@echo off
REM Delete MSVC .obj files after link (local STEM only by default).
REM Usage: _clean_obj.bat DIR STEM [--global-py2cpp]
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "DIR=%~1"
set "STEM=%~2"
set "GLOBAL=%~3"
if "%GLOBAL%"=="--global-py2cpp" (
  for /r "%ROOT%\generated" %%O in (py2cpp.obj) do @del /q "%%O" 2>nul
  if exist "%ROOT%\py2cpp.obj" del /q "%ROOT%\py2cpp.obj" 2>nul
)
if "%STEM%"=="" exit /b 0
if not "%DIR%"=="" if exist "%DIR%\%STEM%.obj" del /q "%DIR%\%STEM%.obj" 2>nul
if exist "%ROOT%\%STEM%.obj" del /q "%ROOT%\%STEM%.obj" 2>nul
exit /b 0
