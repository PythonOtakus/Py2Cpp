#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
n = 0
for p in (ROOT / "ffi").rglob("*.pyi"):
  t = p.read_text(encoding="utf-8")
  t2 = re.sub(r"\bc_str\b", "CStr", t)
  if t2 != t:
    p.write_text(t2, encoding="utf-8", newline="\n")
    n += 1
    print(p.relative_to(ROOT))
print(f"updated {n} files")
