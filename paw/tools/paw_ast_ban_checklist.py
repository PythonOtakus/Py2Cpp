"""生产路径禁止 ``ast`` 依赖检查清单（N0）。

扫描 ``host/`` / ``compiler/`` 中仍引用 ``ast.parse`` / ``import ast`` 的位置，
并区分：允许（legacy adapter / materialize / 测试）与禁止（业务热路径）。

用法::

  python tools/paw_ast_ban_checklist.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 允许保留 ast 的路径前缀（相对仓库根，posix）
ALLOW_PREFIXES = (
  "src/frontend/cpython_adapter.py",
  "src/frontend/api.py",  # LEGACY dialect + 过渡 materialize 消费方
  "src/frontend/legacy_lowering.py",  # 已废弃，仅对照
  "compiler/py/mid/ast_from_mid.py",  # Mid→AST 直构（passes 未迁完前仍产 ast）
  "compiler/py/frontend/surface_rewrite.py",  # 离线工具
  "compiler/py/frontend/legacy_to_paw.py",
  "src/tests/",
  "tests/",
)

# 热路径高风险（应随 N3/N4 清零）
HOT_GLOBS = (
  "src/translator.py",
  "src/passes/",
  "src/emit/",
  "src/analysis/",
  "src/codegen/",
)


def _rel(p: Path) -> str:
  return p.relative_to(ROOT).as_posix()


def _allowed(rel: str) -> bool:
  for pref in ALLOW_PREFIXES:
    if rel == pref or rel.startswith(pref):
      return True
  return False


def main() -> int:
  pat_import = re.compile(r"^\s*import\s+ast\b|^\s*from\s+ast\s+import\b", re.M)
  pat_parse = re.compile(r"\bast\.parse\b")
  hits_import: list[str] = []
  hits_parse: list[str] = []
  hot_parse: list[str] = []

  for base in (ROOT / "src", ROOT / "compiler"):
    if not base.is_dir():
      continue
    for p in base.rglob("*.py"):
      if "__pycache__" in p.parts:
        continue
      rel = _rel(p)
      text = p.read_text(encoding="utf-8", errors="replace")
      if pat_import.search(text):
        hits_import.append(rel)
      if pat_parse.search(text):
        hits_parse.append(rel)
        if any(rel == h or rel.startswith(h) for h in HOT_GLOBS) and not _allowed(rel):
          hot_parse.append(rel)

  print("=== Paw ast ban checklist ===")
  print(f"import ast: {len(hits_import)} files")
  print(f"ast.parse:  {len(hits_parse)} files")
  print(f"hot-path ast.parse (migration debt): {len(hot_parse)}")
  for rel in sorted(set(hot_parse))[:40]:
    print(f"  DEBT  {rel}")
  if len(hot_parse) > 40:
    print(f"  ... +{len(hot_parse) - 40} more")

  print("\nAllowed prefixes:")
  for a in ALLOW_PREFIXES:
    print(f"  OK    {a}")

  print("\nProduction Paw path must NOT call rewrite_paw_to_legacy / paw_source_to_ast.")
  # 硬检：api.py 不得再 import surface_rewrite
  api = (ROOT / "src/frontend/api.py").read_text(encoding="utf-8")
  if "rewrite_paw_to_legacy" in api or "paw_source_to_ast" in api:
    print("FAIL: host/frontend/api.py still references rewrite bridge")
    return 1
  print("OK: host/frontend/api.py has no rewrite bridge")
  return 0


if __name__ == "__main__":
  sys.exit(main())
