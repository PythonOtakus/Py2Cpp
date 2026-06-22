"""One-off: split py2cpp/__init__.py -> builtins.py + slim __init__.py; update stdlib imports."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY2CPP = ROOT / "py2cpp"

EXTRA_IMPORTS: dict[str, list[str]] = {
  "text/bytes.py": ["from .str import str"],
  "util/arena.py": ["from .list import list"],
  "text/string_mixin.py": ["from ..core.protocols import Generator"],
}


def expected_builtins_line(rel: str) -> str:
  parts = rel.replace("\\", "/").split("/")
  hops = len(parts) - 1
  prefix = "." * (hops + 1)
  return f"from {prefix}builtins import *"


def split_init() -> None:
  init = (PY2CPP / "__init__.py").read_text(encoding="utf-8")
  marker = "from .core import *"
  idx = init.index(marker)
  header = init[:idx]
  tail = init[idx:]
  body_lines: list[str] = []
  started = False
  for line in header.splitlines():
    if line.startswith("class char:") or line.startswith("type int64"):
      started = True
    if started:
      body_lines.append(line)
  builtins_doc = (
    '"""py2cpp 内建：类型标记、内存 API、装饰器桩、new/len/print 等。\n\n'
    "由 ``py2cpp/__init__.py`` 再导出；标准库子模块须 ``from ..builtins import *``（深度见编码规范 S27）。\n"
    '"""\n'
    "from __future__ import annotations\n\n"
    "# py2cpp: strict-off\n\n"
  )
  (PY2CPP / "builtins.py").write_text(
    builtins_doc + "\n".join(body_lines) + "\n",
    encoding="utf-8",
  )
  new_init = (
    '"""py2cpp 标准库包根：自 ``builtins`` 与域子包再导出（见 ``builtins.py``）。\n\n'
    "``from py2cpp import *`` 拉入 ``list``/``str``/``dict`` 等；``io`` 须 ``from py2cpp.io import open, StringIO``。\n"
    '"""\n'
    "from .builtins import *\n"
    + tail
  )
  (PY2CPP / "__init__.py").write_text(new_init, encoding="utf-8")


def update_stdlib_file(path: Path) -> None:
  rel = str(path.relative_to(PY2CPP)).replace("\\", "/")
  if rel in ("__init__.py", "builtins.py"):
    return
  text = path.read_text(encoding="utf-8")
  lines = text.splitlines(keepends=True)
  new_lines: list[str] = []
  i = 0
  # docstring / future imports
  while i < len(lines):
    line = lines[i]
    if line.startswith('"""') or line.startswith("'''"):
      quote = line[:3]
      new_lines.append(line)
      if line.count(quote) >= 2 and line.strip().endswith(quote):
        i += 1
        break
      i += 1
      while i < len(lines):
        new_lines.append(lines[i])
        if quote in lines[i]:
          i += 1
          break
        i += 1
      continue
    if line.startswith("from __future__"):
      new_lines.append(line)
      i += 1
      continue
    break
  # skip blank lines before imports
  while i < len(lines) and lines[i].strip() == "":
    new_lines.append(lines[i])
    i += 1
  expected = expected_builtins_line(rel)
  new_lines.append(expected + "\n")
  extras = EXTRA_IMPORTS.get(rel, [])
  for ex in extras:
    new_lines.append(ex + "\n")
  parent_import = re.compile(r"^from (\.\.+)\s+import\s+")
  while i < len(lines):
    line = lines[i]
    if parent_import.match(line.rstrip("\n")) and "builtins" not in line:
      i += 1
      continue
    new_lines.append(line)
    i += 1
  path.write_text("".join(new_lines), encoding="utf-8")


def main() -> None:
  split_init()
  for path in sorted(PY2CPP.rglob("*.py")):
    update_stdlib_file(path)
  print("done")


if __name__ == "__main__":
  main()
