@echo off
REM MidIR seed emit + MSVC compile
REM Accept gate: all 6 seed modules (nested ns compiler::paw::*)
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call scripts\_init_msvc.bat
if errorlevel 1 (
  echo FAIL: MSVC not found
  exit /b 1
)
python scripts\paw_mid_emit_seed.py
if errorlevel 1 exit /b 1

set "OUT=generated\mid_emit_seed"
set "SEED=%OUT%\compiler\seed"
set "INC=/Igenerated\runtime /Ithird_party\sqlite /I%OUT%"
set "CFLAGS=/nologo /std:c++17 /EHsc /c !INC!"

for %%M in (span_tokens diagnostic source_manager lexer parser syntax_nodes mid_emit check) do (
  echo === cl %%M.cpp ===
  cl !CFLAGS! /Fo%SEED%\%%M.obj %SEED%\%%M.cpp
  if errorlevel 1 (
    echo FAIL %%M
    exit /b 1
  )
)

echo OK mid-emit seed MSVC accept 6/6
exit /b 0
