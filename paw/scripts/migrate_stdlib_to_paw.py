"""将 ``py2cpp/**/*.py`` 转为 Paw 表面语法并重命名为 ``.paw``。

用法（仓库根）::
  python scripts/migrate_stdlib_to_paw.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.legacy_to_paw import legacy_to_paw
from compiler.py.frontend.surface_rewrite import rewrite_paw_to_legacy


def _roundtrip_ok(original: str, paw: str) -> tuple[bool, str]:
  import ast

  try:
    legacy = rewrite_paw_to_legacy(paw)
    ast.parse(legacy)
    ast.parse(paw)  # Paw 表面本身未必被 CPython 接受；仅保证 rewrite 可解析
  except SyntaxError as exc:
    # paw 含软关键字时 CPython 可能失败；只要求 legacy 可解析
    try:
      ast.parse(legacy)
    except Exception as exc2:
      return False, f"legacy syntax: {exc2}"
    return True, ""
  except Exception as exc:
    return False, f"rewrite: {exc}"
  _ = original
  return True, ""


def migrate_file(path: Path, *, dry_run: bool) -> str:
  src = path.read_text(encoding="utf-8").replace("\ufeff", "")
  paw = legacy_to_paw(src)
  ok, err = _roundtrip_ok(src, paw)
  if not ok:
    return f"FAIL {path}: {err}"
  dest = path.with_suffix(".paw")
  if dry_run:
    return f"OK   {path} -> {dest.name} (dry-run, {len(paw)} bytes)"
  dest.write_text(paw, encoding="utf-8", newline="\n")
  if dest.resolve() != path.resolve():
    path.unlink()
  return f"OK   {path} -> {dest.name}"


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument(
    "--root",
    type=Path,
    default=ROOT / "py2cpp",
    help="仅迁移该目录下 .py（默认 py2cpp/）",
  )
  ns = ap.parse_args()
  root: Path = ns.root.resolve()
  files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
  if not files:
    print(f"no .py under {root}")
    return 1
  fails = 0
  for p in files:
    msg = migrate_file(p, dry_run=ns.dry_run)
    print(msg)
    if msg.startswith("FAIL"):
      fails += 1
  print(f"done: {len(files)} files, {fails} failed")
  return 1 if fails else 0


if __name__ == "__main__":
  raise SystemExit(main())
