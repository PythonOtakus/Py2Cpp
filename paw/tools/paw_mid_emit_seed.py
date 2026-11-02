"""对 compiler/paw/**/*.paw 尝试 MidIR→C++ 直 emit（绕过 materialize）。

用法（仓库根）::
  python tools/paw_mid_emit_seed.py
  python tools/paw_mid_emit_seed.py --out out/mid_emit_seed

产物布局：``{out}/compiler/paw/{frontend|mid|passes}/…``，
命名空间与模块路径一致。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module
from compiler.py.sema.bind import bind_module, lower_to_mid


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", type=Path, default=ROOT / "out" / "mid_emit_seed")
  args = ap.parse_args()
  seed = ROOT / "compiler" / "paw"
  ok_n = skip_n = 0
  for path in sorted(p for p in seed.rglob("*.paw") if p.is_file()):
    src = path.read_text(encoding="utf-8")
    toks = Lexer(src, FileId(0)).tokenize()
    syntax = parse_tokens(toks, src)
    rel = path.relative_to(ROOT).with_suffix("").as_posix()
    hir = bind_module(syntax, path=rel)
    mid = lower_to_mid(hir)
    if not can_emit_mid(mid):
      print(f"SKIP {rel} (not mid-emit capable)")
      skip_n += 1
      continue
    pkg_out = (args.out.joinpath(*rel.split("/"))).parent
    h, c = emit_mid_module(mid, out_dir=pkg_out, module_path=rel)
    print(f"OK   {rel} -> {h.relative_to(ROOT)} , {c.name}")
    ok_n += 1
  print(f"done: emit={ok_n} skip={skip_n}")
  return 0 if ok_n else 1


if __name__ == "__main__":
  raise SystemExit(main())
