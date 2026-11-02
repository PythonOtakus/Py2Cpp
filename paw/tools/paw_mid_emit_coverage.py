#!/usr/bin/env python3
"""统计 ``paw/**/*.paw`` 的 ``can_emit_mid`` 覆盖与阻塞原因。

用法::

  python tools/paw_mid_emit_coverage.py
  python tools/paw_mid_emit_coverage.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.syntax_nodes import OpaqueStmtSyntax
from compiler.py.mid.emit_cpp import can_emit_mid
from compiler.py.mid.structure import class_needs_rewrite as _class_needs_rewrite
from compiler.py.mid.structure import opaque_needs_rewrite as _opaque_needs_rewrite
from compiler.py.mid.nodes import MidClass, MidFunction, MidOpaque
from host.frontend.api import clear_parse_cache, parse_module_file


def _head(src: str) -> str:
  line = src.strip().split("\n", 1)[0].strip()
  if not line:
    return ""
  return line.split()[0] if line.split() else line[:40]


def _doc_or_import(src: str) -> bool:
  s = src.strip()
  return (
    not s
    or s.startswith("#")
    or s.startswith('"""')
    or s.startswith("'''")
    or s.startswith("from ")
    or s.startswith("import ")
  )


def classify(mid) -> list[str]:
  tags: list[str] = []
  for it in mid.items:
    if isinstance(it, MidClass) and _class_needs_rewrite(it):
      tags.append("class_rewrite")
      for o in it.opaque_members:
        if _opaque_needs_rewrite(o):
          tags.append(f"opaque_mem:{_head(o)}")
          break
    if isinstance(it, MidOpaque) and not _doc_or_import(it.source):
      tags.append(f"mod_opaque:{_head(it.source)}")
    if isinstance(it, MidFunction):
      for s in it.body:
        if isinstance(s, OpaqueStmtSyntax):
          tags.append(f"fn_opaque:{_head(s.source)}")
          break
    if isinstance(it, MidClass):
      for meth in it.methods:
        for s in meth.body:
          if isinstance(s, OpaqueStmtSyntax):
            tags.append(f"meth_opaque:{_head(s.source)}")
            break
        else:
          continue
        break
  return tags or ["unknown"]


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--json", action="store_true")
  ap.add_argument(
    "--root",
    type=Path,
    default=ROOT / "lib" / "paw",
    help="扫描根目录（默认 py2cpp）",
  )
  args = ap.parse_args()
  clear_parse_cache()
  files = sorted(args.root.rglob("*.paw"))
  ok = 0
  reasons: Counter[str] = Counter()
  examples: dict[str, str] = {}
  for path in files:
    m = parse_module_file(path)
    if m.mid_emit_ok or (m.mid is not None and can_emit_mid(m.mid)):
      ok += 1
      continue
    tags = classify(m.mid) if m.mid is not None else ["parse_fail"]
    key = ",".join(tags[:3])
    reasons[key] += 1
    examples.setdefault(key, str(path.relative_to(ROOT)).replace("\\", "/"))
  total = len(files)
  report = {
    "root": str(args.root.relative_to(ROOT)).replace("\\", "/"),
    "total": total,
    "mid_ok": ok,
    "mid_fail": total - ok,
    "pct": round(100.0 * ok / total, 1) if total else 0.0,
    "top_reasons": [
      {"count": c, "reason": k, "example": examples[k]}
      for k, c in reasons.most_common(25)
    ],
  }
  if args.json:
    print(json.dumps(report, ensure_ascii=False, indent=2))
  else:
    print(
      f"{report['root']}: mid_ok={ok}/{total} ({report['pct']}%)  fail={total - ok}"
    )
    for row in report["top_reasons"]:
      print(f"  {row['count']:3d}  {row['reason']}  eg={row['example']}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
