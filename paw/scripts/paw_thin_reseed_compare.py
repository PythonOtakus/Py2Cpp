"""Compare host thin c1_emit vs C2 thin-reseed for key API markers (not byte-identical)."""
from __future__ import annotations

import sys
from pathlib import Path

MARKERS: dict[str, list[str]] = {
  "frontend/source.h": ["class PySourceSpan", "class PySourceManager", "makeSpan("],
  "frontend/source.cpp": ["makeSpan(", "this->_files"],
  "frontend/tokens.h": ["enum class PyTokenKindEnum", "class PyToken"],
  "frontend/diagnostic.h": ["class PyDiagnostic", "formatDiagnostic("],
  "frontend/diagnostic.cpp": ["makeDiagnostic(", "formatDiagnostic("],
  "frontend/lexer.h": ["class PyLexer", "tokenize("],
  "frontend/lexer.cpp": ["tokenize(", "while (true)"],
  "frontend/parser.h": ["parseSource(", "_appendClass("],
  "frontend/parser.cpp": ["_appendClass(", "parseSource("],
  "passes/check.h": ["checkOk("],
  "mid/emit_cpp.h": ["emitEnum(", "emitModuleHeader(", "emitModuleCpp("],
  "mid/emit_cpp.cpp": ["_emitStmtSeq(", "emitModuleHeader(", "emitModuleCpp("],
}


def main() -> int:
  if len(sys.argv) != 3:
    print("usage: paw_thin_reseed_compare.py C1_EMIT_DIR C2_THIN_DIR", flush=True)
    return 2
  c1 = Path(sys.argv[1])
  c2 = Path(sys.argv[2])
  failed = 0
  for rel, needles in MARKERS.items():
    p1 = c1 / rel
    p2 = c2 / rel
    if not p2.is_file():
      print(f"FAIL missing C2 {rel}", flush=True)
      failed += 1
      continue
    text = p2.read_text(encoding="utf-8", errors="replace")
    for n in needles:
      if n not in text:
        print(f"FAIL {rel} missing marker {n!r}", flush=True)
        failed += 1
    # Presence in C1 is advisory (nested layout may differ slightly).
    if p1.is_file():
      t1 = p1.read_text(encoding="utf-8", errors="replace")
      ratio = (len(text) + 1) / (len(t1) + 1)
      if ratio < 0.5:
        print(
          f"FAIL {rel} C2 too small vs C1 ({len(text)}/{len(t1)} ratio={ratio:.2f})",
          flush=True,
        )
        failed += 1
      else:
        print(f"OK {rel} markers+size C2={len(text)} C1={len(t1)}", flush=True)
    else:
      print(f"OK {rel} markers (no C1 twin)", flush=True)
  if failed:
    print(f"FAIL thin-reseed compare failures={failed}", flush=True)
    return 1
  print("OK thin-reseed compare", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
