$ErrorActionPreference = "Stop"
$exe = $env:PY2CPP_TMPL_EXE
$out = $env:PY2CPP_TMPL_OUT
if (-not $exe -or -not (Test-Path -LiteralPath $exe)) {
  Write-Host "FAIL missing expander exe"
  exit 1
}
if (-not $out) {
  Write-Host "FAIL missing out dir"
  exit 1
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
$ok = 0
$skipTest = 0
Get-ChildItem -Path "templates" -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring((Resolve-Path "templates").Path.Length).TrimStart('\','/')
  $text = Get-Content -Raw -LiteralPath $_.FullName -ErrorAction SilentlyContinue
  if ($null -eq $text) { return }
  if ($text -notmatch "PY2CPP_") { return }
  $dest = Join-Path $out $_.Name
  & $exe --in $_.FullName --out $dest
  $code = $LASTEXITCODE
  $isTest = $rel -match '(^|[/\\])~test([/\\]|$)'
  if ($code -eq 3) {
    if ($isTest) {
      $skipTest++
    } else {
      Write-Host ("FAIL production template still needs host EXEC/def: " + $_.FullName)
      exit 1
    }
  } elseif ($code -ne 0) {
    Write-Host ("FAIL " + $_.FullName)
    exit 1
  } else {
    $ok++
  }
}
Write-Host ("OK native frozen templates expanded=$ok skipped_test_host=$skipTest")
exit 0
