@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo [py2cpp] clean: minimal release prep
echo   keep root: .gitattributes .clangd compile_flags.txt main.py README.md *.bat
echo   remove other root files / generated / templates\~macro / .cache / all __pycache__
echo.

set "N_ROOT=0"
for %%F in ("%ROOT%*") do (
  if exist "%%F\" (
    REM skip subdirectories at repo root
  ) else (
    set "KEEP=0"
    if /i "%%~nxF"==".gitattributes" set "KEEP=1"
    if /i "%%~nxF"==".clangd" set "KEEP=1"
    if /i "%%~nxF"=="compile_flags.txt" set "KEEP=1"
    if /i "%%~nxF"=="main.py" set "KEEP=1"
    if /i "%%~nxF"=="README.md" set "KEEP=1"
    if /i "%%~nxF"=="LICENSE" set "KEEP=1"
    if /i "%%~xF"==".bat" set "KEEP=1"
    if !KEEP! equ 0 (
      echo del %%~nxF
      del /f /q "%%F" 2>nul
      set /a N_ROOT+=1
    )
  )
)

if exist "%ROOT%generated" (
  echo rmdir /s /q generated
  rmdir /s /q "%ROOT%generated" 2>nul
)

if exist "%ROOT%templates\~macro" (
  echo rmdir /s /q templates\~macro
  rmdir /s /q "%ROOT%templates\~macro" 2>nul
)

if exist "%ROOT%.cache" (
  echo rmdir /s /q .cache
  rmdir /s /q "%ROOT%.cache" 2>nul
)

if exist "%ROOT%_test_temp" (
  echo rmdir /s /q _test_temp
  rmdir /s /q "%ROOT%_test_temp" 2>nul
)

set "N_CACHE=0"
for /d /r "%ROOT%" %%D in (__pycache__) do (
  if exist "%%D\" (
    echo rmdir /s /q "%%D"
    rmdir /s /q "%%D" 2>nul
    set /a N_CACHE+=1
  )
)

echo.
echo done: !N_ROOT! root file(s) removed; !N_CACHE! __pycache__ dir(s); generated, templates\~macro, .cache and _test_temp cleared
exit /b 0
