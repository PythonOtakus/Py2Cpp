@echo off
REM Rebuild out\runtime\lib\py2cpp_runtime.lib without Python.
REM Requires prior translated sources under out\runtime (one-time bootstrap).
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

if not exist "out\runtime\paw\minimal.h" (
  echo FAIL missing out\runtime\paw\minimal.h — one-time Python bootstrap required
  exit /b 1
)

set "RT=%CD%\out\runtime"
set "LIBDIR=%RT%\lib"
set "OBJDIR=%LIBDIR%\obj"
set "OUTLIB=%LIBDIR%\py2cpp_runtime.lib"
if not exist "%OBJDIR%" mkdir "%OBJDIR%"

set "INC=/I%RT%"
if exist "third_party\sqlite" set "INC=%INC% /I%CD%\third_party\sqlite"

set "RSP=%OBJDIR%\nopy_objs.rsp"
if exist "%RSP%" del /q "%RSP%"
set /a COUNT=0
set "FAIL=0"

echo === nopy fat lib: compile library TUs ===
for /r "%RT%\paw" %%F in (*.cpp) do (
  set "CPP=%%~fF"
  set "INL=%%~dpnF.inl"
  if exist "!INL!" (
    set "REL=!CPP!"
    set "REL=!REL:%RT%\paw\=!"
    set "REL=!REL:.cpp=!"
    set "STEM=!REL:\=__!"
    set "OBJ=%OBJDIR%\!STEM!.obj"
    cl /nologo /EHsc /utf-8 /std:c++14 /c /DSQLITE_THREADSAFE=1 /DSQLITE_OMIT_LOAD_EXTENSION=1 %INC% /Fo"!OBJ!" "!CPP!"
    if errorlevel 1 (
      echo FAIL compile !CPP!
      set "FAIL=1"
    ) else (
      echo "!OBJ!">> "%RSP%"
      set /a COUNT+=1
    )
  )
)

if "%FAIL%"=="1" (
  echo FAIL nopy object compile
  exit /b 1
)
if %COUNT%==0 (
  echo FAIL no library .cpp+.inl under out\runtime\paw
  exit /b 1
)

echo === nopy fat lib: lib.exe ^(%COUNT% objs^) ===
lib /nologo /OUT:"%OUTLIB%" @"%RSP%"
if errorlevel 1 (
  echo FAIL nopy lib.exe
  exit /b 1
)
if not exist "%OUTLIB%" (
  echo FAIL missing %OUTLIB%
  exit /b 1
)
echo OK nopy py2cpp_runtime.lib ^(%COUNT% objs^)
exit /b 0
