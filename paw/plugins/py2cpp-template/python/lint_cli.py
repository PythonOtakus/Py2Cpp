#!/usr/bin/env python3
"""Py2Cpp 模板 T* 规范 lint CLI（供 VS Code 扩展调用，输出 JSON）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root_from_script() -> Path:
  return Path(__file__).resolve().parents[3]


def _ensure_import_path(repo_root: Path) -> None:
  root = str(repo_root.resolve())
  if root not in sys.path:
    sys.path.insert(0, root)


def _template_rel_from_path(path: Path, repo_root: Path) -> str | None:
  templates = (repo_root / "templates").resolve()
  try:
    resolved = path.resolve()
  except OSError:
    return None
  if not str(resolved).startswith(str(templates)):
    return None
  return resolved.relative_to(templates).as_posix()


def _violation_to_dict(v, *, repo_root: Path) -> dict:
  from src.codegen.template_conventions import ViolationSeverity

  file_path = repo_root / "templates" / v.template_rel
  return {
    "rule": v.rule,
    "templateRel": v.template_rel,
    "line": v.lineno,
    "message": v.message,
    "severity": (
      "warning" if v.severity == ViolationSeverity.WARNING else "error"
    ),
    "file": str(file_path),
  }


def collect_violations(
  *,
  repo_root: Path,
  file_path: Path | None = None,
  include_warnings: bool = True,
) -> list[dict]:
  from src.codegen.template_conventions import (
    ViolationSeverity,
    clear_template_violations_cache,
    collect_template_violations,
  )

  clear_template_violations_cache()
  violations = collect_template_violations()
  if file_path is not None:
    rel = _template_rel_from_path(file_path, repo_root)
    if rel is None:
      return []
    violations = [v for v in violations if v.template_rel == rel]
  if not include_warnings:
    violations = [
      v for v in violations if v.severity != ViolationSeverity.WARNING
    ]
  return [_violation_to_dict(v, repo_root=repo_root) for v in violations]


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Py2Cpp template T* linter")
  parser.add_argument(
    "--repo",
    type=Path,
    default=None,
    help="Py2Cpp 仓库根（含 main.py 与 templates/）",
  )
  parser.add_argument(
    "--file",
    type=Path,
    default=None,
    help="仅 lint 该模板文件（须在 templates/ 下）",
  )
  parser.add_argument(
    "--json",
    action="store_true",
    help="输出 JSON（默认）",
  )
  parser.add_argument(
    "--no-warnings",
    action="store_true",
    help="不输出 warning 级违规",
  )
  args = parser.parse_args(argv)

  repo_root = args.repo or _repo_root_from_script()
  repo_root = repo_root.resolve()
  if not (repo_root / "main.py").is_file() or not (repo_root / "templates").is_dir():
    print(
      json.dumps({
        "ok": False,
        "error": f"无效的 Py2Cpp 仓库根: {repo_root}",
        "violations": [],
      }),
      file=sys.stdout,
    )
    return 2

  _ensure_import_path(repo_root)
  try:
    items = collect_violations(
      repo_root=repo_root,
      file_path=args.file,
      include_warnings=not args.no_warnings,
    )
  except Exception as exc:  # noqa: BLE001 — CLI 边界
    print(
      json.dumps({
        "ok": False,
        "error": str(exc),
        "violations": [],
      }),
      file=sys.stdout,
    )
    return 1

  print(json.dumps({
    "ok": True,
    "repoRoot": str(repo_root),
    "violations": items,
  }, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
