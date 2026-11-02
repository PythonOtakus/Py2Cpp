@echo off
REM C1 vertical: emit stage1 seed Mid, amalgamate-compile c1_seed_driver,
REM smoke + self-parse + thin mid_emit to stage1\c1_emit.
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call scripts\_init_msvc.bat
if errorlevel 1 (
  echo FAIL: MSVC not found
  exit /b 1
)

if not exist "generated\runtime\lib\py2cpp_runtime.lib" (
  call scripts\_bootstrap_runtime.bat
  if errorlevel 1 exit /b 1
)

python scripts\paw_bootstrap_stages.py emit-seed stage1
if errorlevel 1 exit /b 1

set "OUT=compiler\stages\stage1"
set "BIN=%OUT%\bin"
set "DRV=compiler\stages\driver"
set "EMIT=%OUT%\c1_emit"
set "INC=/Igenerated\runtime /Ithird_party\sqlite /I%OUT%"

if not exist "%BIN%" mkdir "%BIN%"
if not exist "%EMIT%" mkdir "%EMIT%"

echo === cl+link c1_seed_driver.exe ===
cl /nologo /std:c++17 /EHsc /utf-8 !INC! ^
  /Fe:%BIN%\c1_seed_driver.exe ^
  %DRV%\c1_seed_driver.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_seed_driver link
  exit /b 1
)

echo === run c1_seed_driver --smoke ===
"%BIN%\c1_seed_driver.exe" --smoke
if errorlevel 1 (
  echo FAIL c1_seed_driver smoke
  exit /b 1
)

echo === run c1_seed_driver self-parse seed *.paw ===
"%BIN%\c1_seed_driver.exe" ^
  compiler\paw\frontend\source.paw ^
  compiler\paw\frontend\tokens.paw ^
  compiler\paw\frontend\diagnostic.paw ^
  compiler\paw\frontend\syntax_nodes.paw ^
  compiler\paw\frontend\lexer.paw ^
  compiler\paw\frontend\parser.paw ^
  compiler\paw\mid\emit_cpp.paw ^
  compiler\paw\passes\check.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver self-parse
  exit /b 1
)

echo === run c1_seed_driver --emit-out vertical ===
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% --smoke
if errorlevel 1 (
  echo FAIL c1_seed_driver emit smoke
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\source.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit source
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\tokens.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit tokens
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\diagnostic.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit diagnostic
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\syntax_nodes.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit syntax_nodes
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\passes\check.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit check
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\lexer.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit lexer
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\frontend\parser.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit parser
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\hir\nodes.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit hir/nodes
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\mid\nodes.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit mid/nodes
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\mid\emit_cpp.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit emit_cpp
  exit /b 1
)
"%BIN%\c1_seed_driver.exe" --emit-out %EMIT% compiler\paw\sema\bind.paw
if errorlevel 1 (
  echo FAIL c1_seed_driver emit bind
  exit /b 1
)
if not exist "%EMIT%\frontend\smoke.h" (
  echo FAIL missing %EMIT%\frontend\smoke.h
  exit /b 1
)
if not exist "%EMIT%\frontend\source.h" (
  echo FAIL missing %EMIT%\frontend\source.h
  exit /b 1
)
if not exist "%EMIT%\frontend\tokens.h" (
  echo FAIL missing %EMIT%\frontend\tokens.h
  exit /b 1
)
if not exist "%EMIT%\frontend\diagnostic.h" (
  echo FAIL missing %EMIT%\frontend\diagnostic.h
  exit /b 1
)
if not exist "%EMIT%\frontend\syntax_nodes.h" (
  echo FAIL missing %EMIT%\frontend\syntax_nodes.h
  exit /b 1
)
if not exist "%EMIT%\passes\check.h" (
  echo FAIL missing %EMIT%\passes\check.h
  exit /b 1
)
if not exist "%EMIT%\frontend\lexer.h" (
  echo FAIL missing %EMIT%\frontend\lexer.h
  exit /b 1
)
if not exist "%EMIT%\frontend\parser.h" (
  echo FAIL missing %EMIT%\frontend\parser.h
  exit /b 1
)
if not exist "%EMIT%\hir\nodes.h" (
  echo FAIL missing %EMIT%\hir\nodes.h
  exit /b 1
)
if not exist "%EMIT%\mid\nodes.h" (
  echo FAIL missing %EMIT%\mid\nodes.h
  exit /b 1
)
if not exist "%EMIT%\mid\emit_cpp.h" (
  echo FAIL missing %EMIT%\mid\emit_cpp.h
  exit /b 1
)
if not exist "%EMIT%\sema\bind.h" (
  echo FAIL missing %EMIT%\sema\bind.h
  exit /b 1
)

echo === cl+link c1_emit smoke run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_smoke_run.exe ^
  %DRV%\c1_emit_smoke_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit smoke link
  exit /b 1
)
"%BIN%\c1_emit_smoke_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit smoke run
  exit /b 1
)

echo === cl+link c1_emit span_tokens run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_span_run.exe ^
  %DRV%\c1_emit_span_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit span link
  exit /b 1
)
"%BIN%\c1_emit_span_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit span run
  exit /b 1
)

echo === cl+link c1_emit diagnostic run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_diag_run.exe ^
  %DRV%\c1_emit_diag_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit diag link
  exit /b 1
)
"%BIN%\c1_emit_diag_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit diag run
  exit /b 1
)

echo === cl+link c1_emit check run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_check_run.exe ^
  %DRV%\c1_emit_check_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit check link
  exit /b 1
)
"%BIN%\c1_emit_check_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit check run
  exit /b 1
)

echo === cl+link c1_emit source_manager run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_srcmgr_run.exe ^
  %DRV%\c1_emit_srcmgr_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit srcmgr link
  exit /b 1
)
"%BIN%\c1_emit_srcmgr_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit srcmgr run
  exit /b 1
)

echo === cl+link c1_emit lexer run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_lexer_run.exe ^
  %DRV%\c1_emit_lexer_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit lexer link
  exit /b 1
)
"%BIN%\c1_emit_lexer_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit lexer run
  exit /b 1
)

echo === cl+link c1_emit parser run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_parser_run.exe ^
  %DRV%\c1_emit_parser_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit parser link
  exit /b 1
)
"%BIN%\c1_emit_parser_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit parser run
  exit /b 1
)

echo === c1_seed_driver --emit-enum-dump (D4+ Mid emit_cpp.emitEnum) ===
"%BIN%\c1_seed_driver.exe" --emit-enum-dump
if errorlevel 1 (
  echo FAIL c1_seed_driver emit-enum-dump
  exit /b 1
)

echo === cl+link c1_emit thin emit_cpp run (D5 parse→emit) ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_thin_emitcpp_run.exe ^
  %DRV%\c1_emit_thin_emitcpp_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit thin emit_cpp link
  exit /b 1
)
if not exist "%EMIT%\mid" mkdir "%EMIT%\mid"
"%BIN%\c1_emit_thin_emitcpp_run.exe" --write-out %EMIT% --fixture compiler\stages\fixtures\fixture_foo.paw
if errorlevel 1 (
  echo FAIL c1_emit thin emit_cpp run
  exit /b 1
)
if not exist "%EMIT%\mid\fixture_foo.h" (
  echo FAIL missing %EMIT%\mid\fixture_foo.h
  exit /b 1
)

echo === cl+link c1_emit thin fixture_foo run (parse→emit) ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_emit_thin_foo_run.exe ^
  %DRV%\c1_emit_thin_foo_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1_emit thin fixture_foo link
  exit /b 1
)
"%BIN%\c1_emit_thin_foo_run.exe"
if errorlevel 1 (
  echo FAIL c1_emit thin fixture_foo run
  exit /b 1
)

echo === cl+link c1 thin reseed (C1→C2 gate) ===
set "C2=%OUT%\c2_thin"
if not exist "%C2%" mkdir "%C2%"
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%EMIT% ^
  /Fe:%BIN%\c1_thin_reseed_run.exe ^
  %DRV%\c1_thin_reseed_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c1 thin reseed link
  exit /b 1
)
"%BIN%\c1_thin_reseed_run.exe" --out %C2% ^
  compiler\paw\frontend\source.paw ^
  compiler\paw\frontend\tokens.paw ^
  compiler\paw\frontend\diagnostic.paw ^
  compiler\paw\frontend\syntax_nodes.paw ^
  compiler\paw\frontend\lexer.paw ^
  compiler\paw\frontend\parser.paw ^
  compiler\paw\frontend\param_parse.paw ^
  compiler\paw\frontend\stmt_parse.paw ^
  compiler\paw\frontend\type_parse.paw ^
  compiler\paw\frontend\surface_rewrite.paw ^
  compiler\paw\frontend\legacy_to_paw.paw ^
  compiler\paw\passes\check.paw ^
  compiler\paw\passes\apply_mid_decls.paw ^
  compiler\paw\hir\nodes.paw ^
  compiler\paw\mid\nodes.paw ^
  compiler\paw\mid\structure.paw ^
  compiler\paw\mid\ast_from_mid.paw ^
  compiler\paw\sema\bind.paw ^
  compiler\paw\mid\emit_cpp.paw
if errorlevel 1 (
  echo FAIL c1 thin reseed run
  exit /b 1
)
python scripts\paw_thin_reseed_compare.py %EMIT% %C2%
if errorlevel 1 (
  echo FAIL thin reseed compare
  exit /b 1
)

echo === compare-host-thin (host Mid vs c1_emit soft-skip) ===
python scripts\paw_bootstrap_stages.py compare-host-thin
if errorlevel 1 (
  echo FAIL compare-host-thin
  exit /b 1
)

echo === paw_dual_compare (D0+D1+D2+D4+) ===
python scripts\paw_dual_compare.py
if errorlevel 1 (
  echo FAIL paw_dual_compare
  exit /b 1
)

echo === C2→C3 thin reseed vertical ===
call scripts\paw_c2_c3_thin_reseed.bat
if errorlevel 1 (
  echo FAIL C2→C3 thin reseed
  exit /b 1
)

echo OK stage1 C1→C2→C3 thin seed self-host gate + dual
exit /b 0
