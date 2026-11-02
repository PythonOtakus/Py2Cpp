@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"
for %%I in ("%ROOT%..") do set "MONO=%%~fI"
set "ZEUS=%MONO%\zeus"

echo [paw] clean: minimal release prep
echo   keep paw root: .gitattributes .gitignore .clangd compile_flags.txt main.py README.md LICENSE *.bat
echo   remove other paw root files / out / generated / templates\~macro / .cache / _test_temp
echo   remove zeus out/generated/.cache + all __pycache__ under paw and zeus
echo.

set "N_ROOT=0"
for %%F in ("%ROOT%*") do (
  if exist "%%F\" (
    REM skip subdirectories at paw root
  ) else (
    set "KEEP=0"
    if /i "%%~nxF"==".gitattributes" set "KEEP=1"
    if /i "%%~nxF"==".gitignore" set "KEEP=1"
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

if exist "%ROOT%out" (
  echo rmdir /s /q out
  rmdir /s /q "%ROOT%out" 2>nul
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

for %%F in ("%ROOT%compile_commands.json" "%ROOT%compile_flags.txt.bak") do (
  if exist "%%~F" (
    echo del "%%~nxF"
    del /f /q "%%~F" 2>nul
  )
)

rem Zeus local/out state; keep engine/samples/tools/docs/icons/saved and tracked thirdparty.
if exist "%ZEUS%\" (
  for %%D in ("%ZEUS%\out" "%ZEUS%\generated" "%ZEUS%\templates\~macro" "%ZEUS%\.cache" "%ZEUS%\_test_temp") do (
    if exist "%%~D\" (
      echo rmdir /s /q "%%~D"
      rmdir /s /q "%%~D" 2>nul
    )
  )
  for %%F in ("%ZEUS%\compile_commands.json" "%ZEUS%\compile_flags.txt") do (
    if exist "%%~F" (
      echo del "%%~F"
      del /f /q "%%~F" 2>nul
    )
  )
)

set "N_CACHE=0"
for %%R in ("%ROOT%" "%ZEUS%") do (
  if exist "%%~R\" (
    for /d /r "%%~R" %%D in (__pycache__) do (
      if exist "%%D\" (
        echo rmdir /s /q "%%D"
        rmdir /s /q "%%D" 2>nul
        set /a N_CACHE+=1
      )
    )
  )
)

echo.
echo done: !N_ROOT! paw root file(s) removed; !N_CACHE! __pycache__ dir(s); paw and zeus generated state cleared
exit /b 0
