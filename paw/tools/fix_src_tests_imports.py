"""Fix ``from paw import …`` in src/tests embedded sources."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_TESTS = ROOT / "src" / "tests"
PAT = re.compile(
  r"^(\s*)from paw import (?!\\*)(.+)$",
  re.MULTILINE,
)


def main() -> None:
  n = 0
  for path in sorted(SRC_TESTS.glob("test_*.py")):
    text = path.read_text(encoding="utf-8")
    new = PAT.sub(r"\1from paw import *", text)
    if new != text:
      path.write_text(new, encoding="utf-8")
      n += 1
      print(path.relative_to(ROOT))
  print(f"updated {n} files")


if __name__ == "__main__":
  main()
