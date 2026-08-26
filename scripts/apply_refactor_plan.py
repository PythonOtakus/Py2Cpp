#!/usr/bin/env python3
"""应用 RefactorPlan（``*.arch.json``；``rename_symbol`` / ``update_select_path``）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from src.tools.architect_plan import ApplyResult, PlanError, apply_plan, load_plan, validate_plan


def _print_result(result: ApplyResult) -> int:
  if result.errors:
    for err in result.errors:
      print(f"ERROR: {err}", file=sys.stderr)
    return 1
  if not result.changes:
    print("无变更", file=sys.stderr)
    return 1
  for ch in result.changes:
    diff = ch.diff
    if diff:
      print(diff, end="" if diff.endswith("\n") else "\n")
    else:
      print(f"unchanged: {ch.path}")
  return 0


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="应用 Py2Cpp RefactorPlan（*.arch.json）")
  parser.add_argument("plan", type=Path, help="RefactorPlan 路径（推荐 *.arch.json）")
  parser.add_argument(
    "--repo-root",
    type=Path,
    default=ROOT,
    help="仓库根（默认：含 main.py 的目录）",
  )
  mode = parser.add_mutually_exclusive_group(required=True)
  mode.add_argument("--check", action="store_true", help="校验并干跑，输出 unified diff")
  mode.add_argument("--apply", action="store_true", help="写回源文件")
  args = parser.parse_args(argv)

  repo_root = args.repo_root.resolve()
  if not (repo_root / "main.py").is_file():
    print(f"ERROR: 非 Py2Cpp 仓库根: {repo_root}", file=sys.stderr)
    return 1

  try:
    plan = load_plan(args.plan.resolve())
  except PlanError as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1

  if args.check:
    errors = validate_plan(plan, repo_root)
    if errors:
      for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
      return 1
    result = apply_plan(plan, repo_root, write=False)
    return _print_result(result)

  result = apply_plan(plan, repo_root, write=True)
  if result.errors:
    return _print_result(result)
  print(f"已应用 {len(result.changes)} 个文件变更")
  for ch in result.changes:
    print(f"  {ch.path.relative_to(repo_root)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
