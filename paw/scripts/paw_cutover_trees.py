"""硬切：``tests/**/*.py`` → ``.paw``；``ffi/**/*.pyi``（及 zeus/ffi）→ ``.paw``。

对测试走 legacy_to_paw + method/property 表面迁移；对 FFI 仅 method 表面
（``@native``→``native``，保留 ``@native_name``）。

用法（仓库根）::

  python scripts/paw_cutover_trees.py --dry-run
  python scripts/paw_cutover_trees.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util

from compiler.py.frontend.legacy_to_paw import legacy_to_paw


def _load(name: str, path: Path):
  spec = importlib.util.spec_from_file_location(name, path)
  assert spec and spec.loader
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod


_method = _load("paw_migrate_method_surface", ROOT / "scripts" / "paw_migrate_method_surface.py")
_prop = _load(
  "paw_migrate_property_ref_surface",
  ROOT / "scripts" / "paw_migrate_property_ref_surface.py",
)
migrate_methods = _method.migrate
migrate_props = _prop.migrate


def _transform_test(src: str) -> tuple[str, list[str]]:
  warns: list[str] = []
  s = legacy_to_paw(src)
  s, w1 = migrate_methods(s)
  warns.extend(w1)
  s = migrate_props(s)
  return s, warns


def _transform_ffi(src: str) -> tuple[str, list[str]]:
  return migrate_methods(src)


def _cut_tree(
  *,
  root: Path,
  pattern: str,
  new_suffix: str,
  transform,
  dry_run: bool,
) -> tuple[int, int, list[str]]:
  ok = fail = 0
  notes: list[str] = []
  files = sorted(root.rglob(pattern))
  for path in files:
    if not path.is_file():
      continue
    # 已有同 stem 的目标后缀则跳过源（避免双文件）
    dest = path.with_suffix(new_suffix)
    if dest.exists() and dest.resolve() != path.resolve():
      notes.append(f"SKIP exists {dest.relative_to(ROOT)}")
      if not dry_run:
        path.unlink()
      ok += 1
      continue
    text = path.read_text(encoding="utf-8").replace("\ufeff", "")
    try:
      new, warns = transform(text)
    except Exception as exc:  # noqa: BLE001
      notes.append(f"FAIL {path.relative_to(ROOT)}: {exc}")
      fail += 1
      continue
    for w in warns:
      notes.append(f"WARN {path.relative_to(ROOT)}: {w}")
    if dry_run:
      if new != text or path.suffix != new_suffix:
        notes.append(f"DRY {path.relative_to(ROOT)} -> {dest.name} (+{len(new)-len(text)}B)")
      ok += 1
      continue
    dest.write_text(new, encoding="utf-8", newline="\n")
    if dest.resolve() != path.resolve():
      path.unlink()
    ok += 1
  return ok, fail, notes


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument("--skip-test", action="store_true")
  ap.add_argument("--skip-ffi", action="store_true")
  args = ap.parse_args()
  total_fail = 0

  if not args.skip_test:
    ok, fail, notes = _cut_tree(
      root=ROOT / "tests",
      pattern="*.py",
      new_suffix=".paw",
      transform=_transform_test,
      dry_run=args.dry_run,
    )
    print(f"[test] ok={ok} fail={fail}")
    for n in notes[:40]:
      print(" ", n)
    if len(notes) > 40:
      print(f"  ... +{len(notes) - 40} more")
    total_fail += fail

  if not args.skip_ffi:
    for ffi_root in (ROOT / "ffi", ROOT / "zeus" / "ffi"):
      if not ffi_root.is_dir():
        continue
      ok, fail, notes = _cut_tree(
        root=ffi_root,
        pattern="*.pyi",
        new_suffix=".paw",
        transform=_transform_ffi,
        dry_run=args.dry_run,
      )
      rel = ffi_root.relative_to(ROOT)
      print(f"[{rel}] ok={ok} fail={fail}")
      for n in notes[:20]:
        print(" ", n)
      total_fail += fail

  return 1 if total_fail else 0


if __name__ == "__main__":
  raise SystemExit(main())
