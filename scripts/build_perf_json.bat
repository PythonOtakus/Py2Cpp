@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=python"
set "EXTRA=%*"

call "%~dp0_init_msvc.bat"
if errorlevel 1 (
  echo NOTE: MSVC not auto-configured. Run from "x64 Native Tools Command Prompt" if link fails.
  echo.
)

echo === bootstrap: py2cpp runtime ===
%PY% main.py py2cpp\__init__.py -o generated --no-main
if errorlevel 1 exit /b 1
call "%~dp0_clean_obj.bat" "%CD%\generated\runtime" "py2cpp" --global-py2cpp

echo === parallel compile JSON tests ===
%PY% scripts\parallel_build.py files --root test stdlib\serde\test_json.py perf\test_json_serde.py perf\test_json_dump_perf.py perf\test_json_document_perf.py %EXTRA%
if errorlevel 1 exit /b 1

echo.
echo === Py2Cpp JSON serde perf ===
generated\test\perf\test_json_serde.exe
if errorlevel 1 exit /b 1
echo.
echo === dumps vs dump(StringIO) ===
generated\test\perf\test_json_dump_perf.exe
if errorlevel 1 exit /b 1
echo.
echo === JsonDocument vs full RMW ===
generated\test\perf\test_json_document_perf.exe
if errorlevel 1 exit /b 1
echo.
echo === CPython baseline ===
%PY% scripts\compare_json_perf.py
call "%~dp0_gen_compile_commands.bat"
exit /b 0
