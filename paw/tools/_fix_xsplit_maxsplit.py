#!/usr/bin/env python3
"""xSplit/xRSplit → 全小写；xSplitLines/xsplitlines → xsplitLines；maxsplit → maxSplit。

不改 ``src/`` 内 CPython ``re.split(..., maxsplit=)``。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

METHOD_MAP = [
  ("xSplitLines", "xsplitLines"),
  ("xsplitlines", "xsplitLines"),
  ("xRSplit", "xrsplit"),
  ("xSplit", "xsplit"),
]

DIRS = ("py2cpp", "test", "examples", "docs", "templates", ".cursor", "scripts", "tools")
EXTS = {".py", ".md", ".inl", ".h", ".cpp", ".txt"}


def transform(text: str, *, allow_maxsplit: bool) -> str:
  for old, new in METHOD_MAP:
    text = re.sub(rf"\b{re.escape(old)}\b", new, text)
  if allow_maxsplit:
    text = re.sub(r"\bmaxsplit\b", "maxSplit", text)
  return text


def main() -> None:
  n = 0
  for d in DIRS:
    base = ROOT / d
    if not base.exists():
      continue
    for path in base.rglob("*"):
      if not path.is_file() or path.suffix.lower() not in EXTS:
        continue
      if "node_modules" in path.parts or "generated" in path.parts:
        continue
      if path.name == "_fix_xsplit_maxsplit.py":
        continue
      raw = path.read_text(encoding="utf-8")
      new = transform(raw, allow_maxsplit=True)
      if new != raw:
        path.write_text(new, encoding="utf-8", newline="\n")
        print(path.relative_to(ROOT))
        n += 1

  src = ROOT / "src"
  if src.exists():
    for path in src.rglob("*"):
      if not path.is_file() or path.suffix.lower() not in EXTS:
        continue
      raw = path.read_text(encoding="utf-8")
      new = transform(raw, allow_maxsplit=False)
      if new != raw:
        path.write_text(new, encoding="utf-8", newline="\n")
        print(path.relative_to(ROOT))
        n += 1

  print(f"updated {n} files")


if __name__ == "__main__":
  main()
