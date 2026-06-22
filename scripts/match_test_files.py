"""列出 ``test/**/test_*.py`` 中匹配模式的相对路径（供 ``build.bat`` / ``run.bat``）。"""
from __future__ import annotations

import fnmatch
import pathlib
import sys


def _skipped(path: pathlib.Path) -> bool:
  parts = path.parts
  if "fail" in parts or "perf" in parts:
    return True
  return path.name.endswith("_fail.py")


def _matches(rel: str, name: str, pattern: str) -> bool:
  pat = pattern.replace("/", "\\")
  if "*" in pat or "?" in pat:
    return fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(name, pat)
  low = pat.lower()
  return low in rel.lower() or low in name.lower()


def main(argv: list[str] | None = None) -> int:
  args = list(argv if argv is not None else sys.argv[1:])
  if not args:
    print(
      "用法: match_test_files.py PATTERN [PATTERN ...]\n"
      "  无通配符: 路径/文件名子串（不区分大小写），如 vararg\n"
      "  含 * ?: fnmatch，如 lang\\test_*variadic*.py",
      file=sys.stderr,
    )
    return 2
  root = pathlib.Path(__file__).resolve().parent.parent / "test"
  if not root.is_dir():
    print(f"ERROR: missing test dir: {root}", file=sys.stderr)
    return 2
  matched: list[str] = []
  seen: set[str] = set()
  for path in sorted(root.rglob("test_*.py")):
    if _skipped(path):
      continue
    rel = str(path.relative_to(root))
    name = path.name
    for pat in args:
      if _matches(rel, name, pat):
        if rel not in seen:
          seen.add(rel)
          matched.append(rel)
        break
  if not matched:
    return 1
  for rel in matched:
    print(rel)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
