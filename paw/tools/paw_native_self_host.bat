@echo off
REM Native self-host loop (no Python after c1_seed_driver exists):
REM   1) Ensure C1 driver (may call stage1_c1_link once)
REM   2) C1 emits full compiler/paw corpus → c2_native
REM   3) Link C2 driver against c2_native
REM   4) C2 emits → c3_native
REM   5) Marker-compare c2≡c3
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
call tools\_init_msvc.bat
if errorlevel 1 exit /b 1

if not exist "out\runtime\lib\py2cpp_runtime.lib" (
  call tools\_bootstrap_runtime.bat
  if errorlevel 1 exit /b 1
)

set "OUT=compiler\stages\stage1"
set "BIN=%OUT%\bin"
set "DRV=compiler\stages\driver"
set "C1DRV=%BIN%\c1_seed_driver.exe"
set "C2=%OUT%\c2_native"
set "C3=%OUT%\c3_native"

if not exist "%C1DRV%" (
  echo === bootstrap C1 driver via paw_stage1_c1_link ===
  call tools\paw_stage1_c1_link.bat
  if errorlevel 1 exit /b 1
)

if not exist "%BIN%" mkdir "%BIN%"
if exist "%C2%" rmdir /s /q "%C2%"
if exist "%C3%" rmdir /s /q "%C3%"
mkdir "%C2%"
mkdir "%C3%"

set "CORPUS=compiler\paw\frontend\source.paw compiler\paw\frontend\tokens.paw compiler\paw\frontend\diagnostic.paw compiler\paw\frontend\syntax_nodes.paw compiler\paw\frontend\lexer.paw compiler\paw\frontend\parser.paw compiler\paw\frontend\param_parse.paw compiler\paw\frontend\stmt_parse.paw compiler\paw\frontend\type_parse.paw compiler\paw\frontend\surface_rewrite.paw compiler\paw\frontend\legacy_to_paw.paw compiler\paw\passes\check.paw compiler\paw\passes\apply_mid_decls.paw compiler\paw\hir\nodes.paw compiler\paw\mid\nodes.paw compiler\paw\mid\structure.paw compiler\paw\mid\mutate.paw compiler\paw\mid\tree_from_mid.paw compiler\paw\mid\_syntax_to_ast.paw compiler\paw\sema\bind.paw compiler\paw\mid\emit_cpp.paw compiler\paw\codegen\__init__.paw compiler\paw\codegen\template_profile.paw compiler\paw\codegen\template_eval.paw compiler\paw\codegen\template_expand.paw"

echo === C1 emit → c2_native ===
"%C1DRV%" --emit-out %C2% %CORPUS%
if errorlevel 1 (
  echo FAIL C1 native emit
  exit /b 1
)

echo === link C2 native reseed driver ===
cl /nologo /std:c++17 /EHsc /utf-8 ^
  /Iout\runtime /Ithird_party\sqlite /I%C2% ^
  /Fe:%BIN%\c2_native_reseed.exe ^
  %DRV%\c1_thin_reseed_main.cpp ^
  /link /STACK:8388608 out\runtime\lib\py2cpp_runtime.lib
if errorlevel 1 (
  echo FAIL C2 native link
  exit /b 1
)

echo === C2 emit → c3_native ===
"%BIN%\c2_native_reseed.exe" --out %C3% %CORPUS%
if errorlevel 1 (
  echo FAIL C2→C3 native emit
  exit /b 1
)

python tools\paw_thin_reseed_compare.py %C2% %C3%
if errorlevel 1 (
  echo FAIL c2_native/c3_native compare
  exit /b 1
)

echo OK paw_native_self_host c2_native≡c3_native
exit /b 0
