@echo off
REM Native emit+compile+run one tests/**/test_*.paw
REM Usage: tools\paw_native_build_one.bat tests\lang\test_empty_main.paw
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
if "%~1"=="" (
  echo usage: paw_native_build_one.bat tests\...\test_foo.paw
  exit /b 2
)
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
set "EXE=%BIN%\c1_test_main.exe"

if not exist "%EXE%" (
  echo === link c1_test_main ===
  cl /nologo /std:c++17 /EHsc /utf-8 ^
    /Iout\runtime /Ithird_party\sqlite /Icompiler\stages\stage1\c2_native ^
    /Fe:%EXE% ^
    compiler\stages\driver\c1_test_main.cpp ^
    /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
  if errorlevel 1 exit /b 1
) else (
  echo === reuse %EXE% ===
)

set "SRC=%~1"
echo === native emit %SRC% ===
"%EXE%" --out out %SRC%
if errorlevel 1 exit /b 1

powershell -NoProfile -Command ^
  "$s='%~1' -replace '\\','/'; if ($s -notmatch '(?i)^tests/') { exit 3 }; $rel=$s -replace '(?i)^tests/',''; $rel=$rel -replace '\.paw$','.cpp'; $p=Join-Path 'out/tests' $rel; if (-not (Test-Path -LiteralPath $p)) { Write-Host \"FAIL missing $p\"; exit 1 }; Write-Output $p" > "%TEMP%\paw_native_one_cpp.txt"
if errorlevel 1 exit /b 1
set /p OUTCPP=<"%TEMP%\paw_native_one_cpp.txt"
set "OUTEXE=%OUTCPP:.cpp=.exe%"

for %%I in ("%OUTCPP%") do set "OUTDIR=%%~dpI"
REM Amalgamate sibling helper.cpp into the test TU (avoid LNK2005 from dual paw headers).
powershell -NoProfile -Command ^
  "$main='%OUTCPP%' -replace '\\','/'; $dir=Split-Path -Parent $main; $mainFull=(Resolve-Path -LiteralPath $main).Path; Get-ChildItem -LiteralPath $dir -Filter '*.cpp' | Where-Object { $_.Name -notlike 'test_*' -and $_.FullName -ne $mainFull } | ForEach-Object { $inc='#include \"' + $_.Name + '\"'; $t=Get-Content -LiteralPath $main -Raw; if ($t -notmatch [regex]::Escape($inc)) { Add-Content -LiteralPath $main -Value (\"`r`n\" + $inc) } }"
if errorlevel 1 exit /b 1

echo === cl %OUTCPP% ===
REM Shared sqlite3.obj (same path as paw_native_parallel_build.py); build once if missing.
set "SQLITE_EXTRA="
set "SHARED_SQLITE=out\runtime\lib\sqlite3.obj"
if exist "third_party\sqlite\sqlite3.c" (
  if not exist "%SHARED_SQLITE%" (
    if not exist "out\runtime\lib" mkdir "out\runtime\lib"
    echo === cl shared sqlite3.obj ===
    cl /nologo /O2 /c /DSQLITE_THREADSAFE=1 /DSQLITE_OMIT_LOAD_EXTENSION=1 ^
      /Ithird_party\sqlite ^
      /Fo"%SHARED_SQLITE%" ^
      third_party\sqlite\sqlite3.c
    if errorlevel 1 exit /b 1
  )
  set "SQLITE_EXTRA=%SHARED_SQLITE%"
)
REM C++17：type_if 的 std::is_same_v / if constexpr
cl /nologo /EHsc /utf-8 /std:c++17 ^
  /Iout\runtime /Ithird_party\sqlite /I"%OUTDIR%." ^
  /Fe:%OUTEXE% ^
  "%OUTCPP%" ^
  /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib %SQLITE_EXTRA%
if errorlevel 1 exit /b 1

echo === run %OUTEXE% ===
"%OUTEXE%"
exit /b %ERRORLEVEL%
