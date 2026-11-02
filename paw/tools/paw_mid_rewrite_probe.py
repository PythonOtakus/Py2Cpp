"""Probe Mid rewrite coverage on paw frontend seeds."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PATHS = [
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "source.paw",
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "tokens.paw",
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "diagnostic.paw",
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "lexer.paw",
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "syntax_nodes.paw",
  ROOT / "compiler" / "lib" / "paw" / "frontend" / "parser.paw",
]


def main() -> int:
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import can_emit_mid
  from compiler.py.sema.bind import bind_module, lower_to_mid

  fail = 0
  for path in PATHS:
    src = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT).with_suffix("").as_posix()
    mid = lower_to_mid(
      bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=rel)
    )
    ok = can_emit_mid(mid)
    print(("OK " if ok else "FAIL"), rel)
    if not ok:
      fail = 1
  return fail


if __name__ == "__main__":
  raise SystemExit(main())
