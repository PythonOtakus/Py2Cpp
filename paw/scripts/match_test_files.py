"""列出 ``tests/**/test_*.paw`` 中匹配模式的相对路径（供 ``build.bat`` / ``run.bat``）。"""
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "tests"


def _is_fail(path: Path) -> bool:
  return path.name.endswith("_fail.paw")


def main(argv: list[str]) -> int:
  if not argv:
    print(
      "用法: match_test_files.py PATTERN [PATTERN ...]\n"
      "  子串匹配路径/文件名，或\n"
      "  含 * ?: fnmatch，如 lang\\test_*variadic*.paw",
      file=sys.stderr,
    )
    return 2
  patterns = argv
  found: list[Path] = []
  for path in TEST_DIR.rglob("test_*.paw"):
    if "fail" in path.parts or "perf" in path.parts or "gpu" in path.parts:
      continue
    if _is_fail(path):
      continue
    found.append(path)
  out: list[str] = []
  for path in sorted(found, key=lambda p: str(p).lower()):
    rel = str(path.relative_to(TEST_DIR)).replace("/", "\\")
    name = path.name
    hit = False
    for pat in patterns:
      if any(ch in pat for ch in "*?"):
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
          hit = True
          break
      else:
        needle = pat.replace("/", "\\").lower()
        if needle in rel.lower() or needle in name.lower():
          hit = True
          break
    if hit:
      out.append(rel)
  for line in out:
    print(line)
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
