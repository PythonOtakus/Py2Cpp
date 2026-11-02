@echo off
REM C2→C3: link thin reseed against c2_thin, emit c3_thin, compare markers.
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call scripts\_init_msvc.bat
if errorlevel 1 exit /b 1

set "C2=compiler\stages\stage1\c2_thin"
set "C3=compiler\stages\stage1\c3_thin"
set "BIN=compiler\stages\stage1\bin"
if not exist "%BIN%" mkdir "%BIN%"
set "DRV=compiler\stages\driver"
if not exist "%C2%\mid\emit_cpp.cpp" (
  echo FAIL missing %C2% — run paw_stage1_c1_link.bat first
  exit /b 1
)
if not exist "%C3%" mkdir "%C3%"

echo === cl+link c2_thin_reseed_run ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%C2% ^
  /Fe:%BIN%\c2_thin_reseed_run.exe ^
  %DRV%\c1_thin_reseed_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c2 thin reseed link
  exit /b 1
)

echo === run c2→c3 thin reseed ===
"%BIN%\c2_thin_reseed_run.exe" --out %C3% ^
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
  echo FAIL c2→c3 thin reseed run
  exit /b 1
)

python scripts\paw_thin_reseed_compare.py %C2% %C3%
if errorlevel 1 (
  echo FAIL c2/c3 compare
  exit /b 1
)

echo === cl+link c2_thin vertical smoke/span/parser ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%C2% ^
  /Fe:%BIN%\c2_span_run.exe ^
  %DRV%\c1_emit_span_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c2 span link
  exit /b 1
)
"%BIN%\c2_span_run.exe"
if errorlevel 1 (
  echo FAIL c2 span run
  exit /b 1
)

cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Igenerated\runtime /Ithird_party\sqlite /I%C2% ^
  /Fe:%BIN%\c2_parser_run.exe ^
  %DRV%\c1_emit_parser_main.cpp ^
  /link /STACK:8388608 generated\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL c2 parser link
  exit /b 1
)
"%BIN%\c2_parser_run.exe"
if errorlevel 1 (
  echo FAIL c2 parser run
  exit /b 1
)

echo OK C2→C3 thin reseed + C2 span/parser vertical
exit /b 0
