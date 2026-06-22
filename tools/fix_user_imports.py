"""Normalize non-stdlib modules to ``from py2cpp import *``."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [ROOT / "test", ROOT / "examples"]
PY2CPP_IMPORT = re.compile(r"^from py2cpp import .+$")


def fix_file(path: Path) -> bool:
  text = path.read_text(encoding="utf-8")
  lines = text.splitlines(keepends=True)
  out: list[str] = []
  i = 0
  changed = False
  while i < len(lines):
    line = lines[i]
    if line.startswith('"""') or line.startswith("'''"):
      quote = line[:3]
      out.append(line)
      if line.count(quote) >= 2 and line.strip().endswith(quote):
        i += 1
        continue
      i += 1
      while i < len(lines):
        out.append(lines[i])
        if quote in lines[i]:
          i += 1
          break
        i += 1
      continue
    if line.startswith("from __future__"):
      out.append(line)
      i += 1
      continue
    break
  while i < len(lines) and lines[i].strip() == "":
    out.append(lines[i])
    i += 1
  has_star = "from py2cpp import *" in text
  new_lines: list[str] = []
  while i < len(lines):
    line = lines[i]
    if PY2CPP_IMPORT.match(line.rstrip("\n")) and "import *" not in line:
      changed = True
      i += 1
      continue
    new_lines.append(line)
    i += 1
  if not has_star:
    out.append("from py2cpp import *\n")
    changed = True
  out.extend(new_lines)
  if changed:
    path.write_text("".join(out), encoding="utf-8")
  return changed


def main() -> None:
  n = 0
  for base in DIRS:
    if not base.is_dir():
      continue
    for path in sorted(base.rglob("*.py")):
      if fix_file(path):
        n += 1
        print(path.relative_to(ROOT))
  print(f"updated {n} files")


if __name__ == "__main__":
  main()
