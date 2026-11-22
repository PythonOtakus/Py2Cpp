# Wrapper: rebuild fat lib without Python (delegates to .bat; needs vcvars).
$ErrorActionPreference = "Stop"
$bat = Join-Path $PSScriptRoot "paw_runtime_nopy.bat"
& cmd /c "`"$bat`""
exit $LASTEXITCODE
