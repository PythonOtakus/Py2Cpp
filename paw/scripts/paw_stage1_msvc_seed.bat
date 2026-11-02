@echo off
REM stage1 seed MidIR 产物 MSVC 竖切（自举 C0→stage1 可编译门闩）
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call scripts\_init_msvc.bat
if errorlevel 1 (
  echo FAIL: MSVC not found
  exit /b 1
)
python scripts\paw_bootstrap_stages.py emit-seed
if errorlevel 1 exit /b 1

set "OUT=compiler\stages\stage1"
set "SEED=%OUT%\compiler\seed"
set "INC=/Igenerated\runtime /Ithird_party\sqlite /I%OUT%"
set "CFLAGS=/nologo /std:c++17 /EHsc /c !INC!"

for %%M in (span_tokens diagnostic source_manager lexer parser syntax_nodes mid_emit check) do (
  echo === cl stage1 %%M.cpp ===
  cl !CFLAGS! /Fo%SEED%\%%M.obj %SEED%\%%M.cpp
  if errorlevel 1 (
    echo FAIL stage1 %%M
    exit /b 1
  )
)

echo OK stage1 seed MSVC accept 6/6
exit /b 0
