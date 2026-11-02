#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = [
  "src/passes/generator_emit.py",
  "src/emit/try_emit.py",
  "src/passes/generators.py",
  "src/passes/serializable.py",
  "src/emit/copy_move_emit.py",
]
for rel in files:
  p = ROOT / rel
  t = p.read_text(encoding="utf-8")
  t2 = (
    t.replace(".copy_from(", ".copyFrom(")
    .replace(".copy_from_ptr(", ".copyFromPtr(")
    .replace(".copy_from_span(", ".copyFromSpan(")
    .replace("``copy_from``", "``copyFrom``")
    .replace('"copy_from"', '"copyFrom"')
  )
  if t2 != t:
    p.write_text(t2, encoding="utf-8", newline="\n")
    print(f"updated {rel}")
print("done")
