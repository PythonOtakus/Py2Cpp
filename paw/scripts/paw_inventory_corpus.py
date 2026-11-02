"""刷新 Paw P0 语料计数（stdout 表格；供 docs/paw/baseline.md 对照）。"""
from __future__ import annotations

from pathlib import Path


def main() -> int:
  root = Path(__file__).resolve().parent.parent
  rows = [
    ("stdlib", list((root / "paw").rglob("*.paw")) + list((root / "paw").rglob("*.py"))),
    (
      "tests",
      [
        p
        for p in (root / "tests").rglob("test_*.py")
        if "_fail" not in p.name and "fail" not in p.parts and "perf" not in p.parts
      ],
    ),
    ("fails", list((root / "tests").rglob("*_fail.py"))),
    (
      "examples",
      list((root / "examples").rglob("*.py")) if (root / "examples").is_dir() else [],
    ),
    ("ffi", list((root / "ffi").rglob("*.pyi")) if (root / "ffi").is_dir() else []),
    (
      "paw_preview",
      [root / "lexer_preview.paw"] if (root / "lexer_preview.paw").is_file() else [],
    ),
    (
      "paw_tests",
      list((root / "tests").rglob("test_*.paw")) if (root / "tests").is_dir() else [],
    ),
  ]
  print("| 集合 | 数量 |")
  print("|---|---:|")
  for name, files in rows:
    print(f"| {name} | {len(files)} |")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
