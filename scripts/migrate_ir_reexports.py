"""Phase 8a：ir 谓词/提取 re-export → 直引 type_pred / type_extract。"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

PRED = {
  "is_array_type", "is_byte_type", "is_bytes_type", "is_callable_type",
  "is_char_heap_array_type", "is_char_type", "is_concrete_coroutine_type",
  "is_concrete_generator_type", "is_container_type", "is_delegate_type",
  "is_deque_type", "is_dict_type", "is_erased_protocol_storage_type",
  "is_float64_type", "is_float_type", "is_frozenlist_type", "is_frozendict_type",
  "is_frozenset_type", "is_heap_array_type", "is_int64_type", "is_int_type",
  "is_list_type", "is_optional_type", "is_py_async_generator_type",
  "is_py_callable_type", "is_py_coroutine_type", "is_py_generator_type",
  "is_refcount_type", "is_set_type", "is_span_type", "is_stack_array_type",
  "is_str_type", "is_tuple_type", "is_uint64_type", "is_uint_type",
  "is_uintptr_type", "is_long_type",
}
EXTRACT = {
  "async_generator_type_args", "coroutine_type_args", "dict_type_args",
  "frozendict_type_args", "generator_type_args", "list_elem_type",
  "optional_inner_type", "refcount_inner_type",
}


def _sibling(module: str, sibling: str) -> str:
  if module.endswith(".ir"):
    return module[:-2] + sibling
  return module.replace(".ir", f".{sibling}")


class ImportRewriter(ast.NodeTransformer):
  def __init__(self) -> None:
    self.pending: list[ast.stmt] = []

  def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom | None:
    if not node.module or not node.module.endswith(".ir"):
      return node
    pred: list[str] = []
    extr: list[str] = []
    rest: list[str] = []
    for alias in node.names:
      n = alias.name
      if n in PRED:
        pred.append(n)
      elif n in EXTRACT:
        extr.append(n)
      else:
        rest.append(n)
    if not pred and not extr:
      return node
    if pred:
      self.pending.append(
        ast.ImportFrom(
          module=_sibling(node.module, "type_pred"),
          names=[ast.alias(name=n) for n in pred],
          level=node.level,
        )
      )
    if extr:
      self.pending.append(
        ast.ImportFrom(
          module=_sibling(node.module, "type_extract"),
          names=[ast.alias(name=n) for n in extr],
          level=node.level,
        )
      )
    if rest:
      return ast.ImportFrom(
        module=node.module,
        names=[ast.alias(name=n) for n in rest],
        level=node.level,
      )
    return None


def rewrite_imports(source: str) -> tuple[str, bool]:
  try:
    tree = ast.parse(source)
  except SyntaxError:
    return source, False
  rw = ImportRewriter()
  new_body: list[ast.stmt] = []
  changed = False
  for stmt in tree.body:
    rw.pending = []
    if isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.module.endswith(".ir"):
      res = rw.visit(stmt)
      if rw.pending or res is None:
        changed = True
      new_body.extend(rw.pending)
      if res is not None:
        new_body.append(res)
    else:
      new_body.append(stmt)
  if not changed:
    return source, False
  tree.body = new_body
  ast.fix_missing_locations(tree)
  return ast.unparse(tree) + "\n", True


def main() -> int:
  changed: list[Path] = []
  for p in SRC.rglob("*.py"):
    if p.name == "ir.py" and "analysis" in p.parts:
      continue
    text = p.read_text(encoding="utf-8")
    new_text, ok = rewrite_imports(text)
    if ok:
      p.write_text(new_text, encoding="utf-8")
      changed.append(p)
  print(f"updated {len(changed)} files")
  return 0


if __name__ == "__main__":
  sys.exit(main())
