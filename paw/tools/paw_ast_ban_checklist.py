"""生产路径禁止 stdlib ``ast`` 直接导入 / ``eval`` / ``exec`` 依赖检查清单。

扫描 ``host/`` / ``compiler/``：
- 禁止源码 ``import ast`` / ``from ast import``（含 ``import ast as …``）
- 允许过渡期 ``import host.tree_nodes as ast``（AST-shaped IR facade）
- 热路径禁止 ``ast.parse`` / ``eval(`` / ``exec(``
- ``host.tree_nodes`` 是唯一允许经 ``importlib`` 加载 stdlib ``ast`` 的地方

**Zero-AST Phase 5**：
- ``IMPORT_AST_ALLOW_*`` 为空（goal: 0 import-ast debt）
- ``rg "import ast|from ast import" host compiler`` 应为空

用法::

  python tools/paw_ast_ban_checklist.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Zero-AST Phase 5：不再允许任何 stdlib ``import ast`` / ``from ast import``。
# 过渡 IR：``import host.tree_nodes as ast``（checklist 不 FAIL）。
# ---------------------------------------------------------------------------
IMPORT_AST_ALLOW_PREFIXES: tuple[str, ...] = ()
IMPORT_AST_ALLOW_FILES: frozenset[str] = frozenset()

# 允许保留 ast.parse / _stdlib_parse 的路径前缀（相对 Paw 工程根，posix）
# Phase 4：已删 cpython_adapter / ir_to_ast / legacy_lowering / ast_from_mid
# Phase 5：桥接仍可能调用 ``ast._stdlib_parse``（tree_nodes 对 ``parse`` 抛错）
ALLOW_PREFIXES = (
  "compiler/py/mid/tree_from_mid.py",  # Mid→AST 过渡桥（stubs / method bridge）
  "compiler/py/mid/_syntax_to_ast.py",
  "compiler/py/passes/",
  "compiler/py/frontend/surface_rewrite.py",  # 离线工具
  "compiler/py/frontend/legacy_to_paw.py",
  "host/tools/",
  "host/tests/",
  "tests/",
  "host/tree_nodes.py",
)

# 热路径高风险（应清零）
HOT_GLOBS = (
  "host/translator.py",
  "host/passes/",
  "host/emit/",
  "host/analysis/",
  "host/codegen/",
)

# codegen 模板求值器允许出现文字 “eval”/“exec” 作为 API 名说明，但禁止调用内建
CODEGEN_EVAL_ALLOW = (
  "host/codegen/template_eval.py",
  "host/codegen/template_profile.py",
  "host/codegen/expand_py2cpp_template.py",
)


def _rel(p: Path) -> str:
  return p.relative_to(ROOT).as_posix()


def _allowed(rel: str) -> bool:
  for pref in ALLOW_PREFIXES:
    if rel == pref or rel.startswith(pref):
      return True
  return False


def _import_ast_allowed(rel: str) -> bool:
  if rel in IMPORT_AST_ALLOW_FILES:
    return True
  for pref in IMPORT_AST_ALLOW_PREFIXES:
    if rel == pref or rel.startswith(pref):
      return True
  return False


def _strip_comments_and_strings(text: str) -> str:
  """粗去掉 # 行注释与三引号/普通字符串，降低文档误报。"""
  text = re.sub(r'(?s)""".*?"""', '""', text)
  text = re.sub(r"(?s)'''.*?'''", "''", text)
  text = re.sub(r"#.*?$", "", text, flags=re.M)
  return text


def main() -> int:
  # 仅匹配真正导入 stdlib ast 的语句（不含 host.tree_nodes）
  pat_import = re.compile(
    r"^\s*import\s+ast\b|^\s*from\s+ast\s+import\b",
    re.M,
  )
  pat_parse = re.compile(r"\bast\.parse\b|\bast\._stdlib_parse\b")
  # 内建 eval/exec 调用（排除方法名 eval_echo 等）
  pat_eval = re.compile(r"(?<![\w.])eval\s*\(")
  pat_exec = re.compile(r"(?<![\w.])exec\s*\(")
  hits_import: list[str] = []
  hits_parse: list[str] = []
  hot_parse: list[str] = []
  hot_eval_exec: list[str] = []
  import_debt: list[str] = []
  tree_nodes_hits = 0

  for base in (ROOT / "host", ROOT / "compiler"):
    if not base.is_dir():
      continue
    for p in base.rglob("*.py"):
      if "__pycache__" in p.parts:
        continue
      rel = _rel(p)
      raw = p.read_text(encoding="utf-8", errors="replace")
      text = _strip_comments_and_strings(raw)
      if "import host.tree_nodes as ast" in raw or "from host.tree_nodes import" in raw:
        tree_nodes_hits += 1
      if pat_import.search(raw):
        hits_import.append(rel)
        if not _import_ast_allowed(rel):
          import_debt.append(rel)
      if pat_parse.search(text):
        hits_parse.append(rel)
        if any(rel == h or rel.startswith(h) for h in HOT_GLOBS) and not _allowed(rel):
          hot_parse.append(rel)
      if (pat_eval.search(text) or pat_exec.search(text)) and not _allowed(rel):
        if any(rel == h or rel.startswith(h) for h in HOT_GLOBS):
          if rel not in CODEGEN_EVAL_ALLOW:
            hot_eval_exec.append(rel)

  print("=== Paw ast ban checklist (Zero-AST Phase 5) ===")
  print(f"import ast (stdlib): {len(hits_import)} files")
  print(f"host.tree_nodes facade imports: {tree_nodes_hits} files")
  print(f"ast.parse / _stdlib_parse: {len(hits_parse)} files")
  print(f"hot-path ast.parse (migration debt): {len(hot_parse)}")
  for rel in sorted(set(hot_parse))[:40]:
    print(f"  DEBT  {rel}")
  if len(hot_parse) > 40:
    print(f"  ... +{len(hot_parse) - 40} more")
  print(f"hot-path eval/exec calls: {len(hot_eval_exec)}")
  for rel in sorted(set(hot_eval_exec))[:20]:
    print(f"  DEBT  {rel}")

  print("\nstdlib import-ast outside ALLOW (ALLOW must stay empty):")
  if not import_debt:
    print("  (none)")
  else:
    for rel in sorted(set(import_debt))[:40]:
      print(f"  FAIL  {rel}")
    if len(set(import_debt)) > 40:
      print(f"  ... +{len(set(import_debt)) - 40} more")

  if IMPORT_AST_ALLOW_PREFIXES or IMPORT_AST_ALLOW_FILES:
    print("\nAllowed import-ast prefixes/files (must be empty in Phase 5):")
    for a in IMPORT_AST_ALLOW_PREFIXES:
      print(f"  OK    {a}")
    for a in sorted(IMPORT_AST_ALLOW_FILES):
      print(f"  OK    {a}")
  else:
    print("\nIMPORT_AST_ALLOW_* is empty (goal met for allow-list)")

  print("\nAllowed ast.parse / _stdlib_parse prefixes:")
  for a in ALLOW_PREFIXES:
    print(f"  OK    {a}")

  print("\nProduction Paw path must NOT call rewrite_paw_to_legacy / paw_source_to_ast.")
  api_path = ROOT / "host/frontend/api.py"
  if not api_path.is_file():
    print(f"FAIL: missing {api_path.relative_to(ROOT).as_posix()}")
    return 1
  api = api_path.read_text(encoding="utf-8")
  if "rewrite_paw_to_legacy" in api or "paw_source_to_ast" in api:
    print("FAIL: host/frontend/api.py still references rewrite bridge")
    return 1
  print("OK: host/frontend/api.py has no rewrite bridge")

  # Phase 4：已删 LEGACY / 桥文件不得再出现
  for gone in (
    "host/frontend/cpython_adapter.py",
    "host/frontend/ir_to_ast.py",
    "host/frontend/legacy_lowering.py",
    "compiler/py/mid/ast_from_mid.py",
  ):
    if (ROOT / gone).is_file():
      print(f"FAIL: deleted bridge still present: {gone}")
      return 1
  print("OK: Phase 4 deleted LEGACY / ast_from_mid bridges absent")

  tn = ROOT / "host/tree_nodes.py"
  if not tn.is_file():
    print("FAIL: missing host/tree_nodes.py (Phase 5 facade)")
    return 1
  tn_src = tn.read_text(encoding="utf-8")
  if not re.search(r'importlib\.import_module\(\s*["\']ast["\']\s*\)', tn_src):
    print("FAIL: host/tree_nodes.py must load stdlib via importlib.import_module(\"ast\")")
    return 1
  if pat_import.search(tn_src):
    print("FAIL: host/tree_nodes.py must not use direct import-ast statements")
    return 1
  print("OK: host/tree_nodes.py is the sole importlib(\"ast\") loader")

  failed = False
  if IMPORT_AST_ALLOW_PREFIXES or IMPORT_AST_ALLOW_FILES:
    print("\nFAIL: IMPORT_AST_ALLOW_* must be empty (Phase 5)")
    failed = True

  if hot_parse or hot_eval_exec:
    print(
      f"\nFAIL: hot-path debt remaining "
      f"(ast.parse={len(set(hot_parse))}, eval/exec={len(set(hot_eval_exec))})"
    )
    failed = True
  else:
    print("\nOK: hot-path ast.parse / eval / exec debt is 0")

  if import_debt or hits_import:
    print(
      f"\nFAIL: stdlib import-ast remaining "
      f"({len(set(hits_import))} files) — migrate to host.tree_nodes"
    )
    failed = True
  else:
    print("OK: zero stdlib import-ast (goal: 0); tree_nodes facade allowed")

  return 1 if failed else 0


if __name__ == "__main__":
  sys.exit(main())
