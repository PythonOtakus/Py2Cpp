#!/usr/bin/env python3
"""将 ``templates/**`` 中 A/B 系统头 ``#include`` 改为 ``#include "ffi/…"``。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.constant.template_ffi_includes import (  # noqa: E402
  ffi_include_for_system_header,
  normalize_system_header,
)
from src.codegen.expand_py2cpp_template import template_root  # noqa: E402

_INCLUDE_LINE = re.compile(
  r'^([ \t]*#[ \t]*include[ \t]*)([<"])([^>"]+)([>"])(.*)$'
)


def migrate_file(path: Path) -> int:
  text = path.read_text(encoding="utf-8")
  lines = text.splitlines(keepends=True)
  n = 0
  out: list[str] = []
  for line in lines:
    m = _INCLUDE_LINE.match(line.rstrip("\r\n"))
    if not m:
      out.append(line)
      continue
    prefix, qopen, header, qclose, suffix = m.groups()
    mapped = ffi_include_for_system_header(header)
    if mapped is None:
      out.append(line)
      continue
    # 已是 ffi / 已是目标 C++ 头则跳过
    hn = normalize_system_header(header)
    if hn.startswith("ffi/") or hn == normalize_system_header(mapped):
      out.append(line)
      continue
    nl = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    # C→C++ 包装（cstdint 等）用尖括号；ffi 中转用引号
    if mapped.startswith("ffi/"):
      new_line = f'{prefix}"{mapped}"{suffix}{nl}'
    else:
      new_line = f"{prefix}<{mapped}>{suffix}{nl}"
    if new_line != line:
      n += 1
    out.append(new_line)
  if n:
    path.write_text("".join(out), encoding="utf-8", newline="")
  return n


def main() -> int:
  root = template_root().resolve()
  total = 0
  files = 0
  for path in sorted(root.rglob("*")):
    if not path.is_file() or path.suffix not in (".h", ".inl"):
      continue
    rel = path.relative_to(root).as_posix()
    if rel.startswith("~macro/"):
      continue
    n = migrate_file(path)
    if n:
      files += 1
      total += n
      print(f"  {rel}: {n} include(s)")
  print(f"migrated {total} includes in {files} files")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
