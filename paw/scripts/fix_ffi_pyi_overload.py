#!/usr/bin/env python3
"""给已生成的 ``ffi/**/*.pyi`` 补 ``@overload``（同名 pyi 函数组）。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNC_RE = re.compile(
  r"(?m)^(@native\n@native_name\(\"[^\"]+\"\)\ndef (pyi\w+)\([^)]*\)[^\n]*\n(?:  [^\n]*\n)*  \.\.\.\n)"
)


def fix(path: Path) -> int:
  text = path.read_text(encoding="utf-8")
  text2 = re.sub(r"(?m)^@overload\n(?=@native\n@native_name)", "", text)
  matches = list(FUNC_RE.finditer(text2))
  if not matches:
    return 0
  counts: dict[str, int] = {}
  for m in matches:
    counts[m.group(2)] = counts.get(m.group(2), 0) + 1
  if not any(c > 1 for c in counts.values()):
    if text2 != text:
      path.write_text(text2, encoding="utf-8", newline="\n")
    return 0
  out: list[str] = []
  last = 0
  n = 0
  for m in matches:
    out.append(text2[last : m.start()])
    if counts[m.group(2)] > 1:
      out.append("@overload\n")
      n += 1
    out.append(m.group(1))
    last = m.end()
  out.append(text2[last:])
  new = "".join(out)
  if new != text:
    path.write_text(new, encoding="utf-8", newline="\n")
  return n


def main() -> int:
  files = 0
  total = 0
  for p in sorted((ROOT / "ffi").rglob("*.pyi")):
    k = fix(p)
    if k:
      files += 1
      total += k
      print(f"  {p.relative_to(ROOT).as_posix()}: {k} overloaded defs")
  print(f"fixed {files} files, {total} defs")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
