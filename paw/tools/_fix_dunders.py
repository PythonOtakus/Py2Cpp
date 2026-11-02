#!/usr/bin/env python3
"""修复误伤的 dunder：``__init`` → ``__init__``（批量改名脚本 bug）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DUNDER_STEMS = (
  "init", "del", "len", "getitem", "setitem", "delitem", "iter", "next",
  "contains", "bool", "str", "repr", "hash", "call", "enter", "exit",
  "aenter", "aexit", "await", "aiter", "anext", "copy", "move",
  "add", "sub", "mul", "rmul", "truediv", "floordiv", "mod", "neg", "pos",
  "cmp", "eq", "ne", "lt", "le", "gt", "ge", "setattr", "getattr", "delattr",
  "post_init", "moved",
)

# ``__postInit``（snake 误 camel）→ ``__post_init__``
BROKEN_CAMEL = {
  "__postInit": "__post_init__",
  "__postInit__": "__post_init__",
}

STEM_PAT = re.compile(
  r"\b__(" + "|".join(re.escape(s) for s in sorted(DUNDER_STEMS, key=len, reverse=True)) + r")(?!_)\b"
)


def fix_text(text: str) -> str:
  for bad, good in BROKEN_CAMEL.items():
    text = text.replace(bad, good)
  return STEM_PAT.sub(r"__\1__", text)


def main() -> int:
  roots = sys.argv[1:] or ["py2cpp/console"]
  n = 0
  for root in roots:
    base = ROOT / root
    files = [base] if base.is_file() else list(base.rglob("*.py"))
    for p in files:
      if not p.is_file():
        continue
      raw = p.read_text(encoding="utf-8")
      new = fix_text(raw)
      if new != raw:
        p.write_text(new, encoding="utf-8", newline="\n")
        n += 1
        print(f"fixed {p.relative_to(ROOT)}")
  print(f"files_fixed={n}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
