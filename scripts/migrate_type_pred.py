"""Phase 7：is_cpp_* / cpp_*_elem → type_pred / type_extract。"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

PRED_RENAME = {
  "is_cpp_list_type": "is_list_type",
  "is_cpp_dict_type": "is_dict_type",
  "is_cpp_set_type": "is_set_type",
  "is_cpp_frozenset_type": "is_frozenset_type",
  "is_cpp_frozenlist_type": "is_frozenlist_type",
  "is_cpp_frozendict_type": "is_frozendict_type",
  "is_cpp_deque_type": "is_deque_type",
  "is_cpp_tuple_type": "is_tuple_type",
  "is_cpp_counter_type": "is_counter_type",
  "is_cpp_chunk_deque_type": "is_chunk_deque_type",
  "is_cpp_container_type": "is_container_type",
  "is_cpp_array_type": "is_array_type",
  "is_cpp_span_type": "is_span_type",
  "is_cpp_stack_array_type": "is_stack_array_type",
  "is_cpp_option_type": "is_optional_type",
  "is_cpp_str_type": "is_str_type",
  "is_cpp_bytes_type": "is_bytes_type",
  "is_cpp_char_type": "is_char_type",
  "is_cpp_byte_type": "is_byte_type",
  "is_cpp_int_type": "is_int_type",
  "is_cpp_int64_type": "is_int64_type",
  "is_cpp_uint_type": "is_uint_type",
  "is_cpp_uint64_type": "is_uint64_type",
  "is_cpp_uintptr_type": "is_uintptr_type",
  "is_cpp_long_type": "is_long_type",
  "is_cpp_float_type": "is_float_type",
  "is_cpp_float64_type": "is_float64_type",
  "is_cpp_scalar_int_type": "is_scalar_int_type",
  "is_cpp_scalar_float_type": "is_scalar_float_type",
  "is_cpp_refcount_type": "is_refcount_type",
  "is_cpp_py_callable_type": "is_py_callable_type",
  "is_cpp_py_generator_type": "is_py_generator_type",
  "is_cpp_py_coroutine_type": "is_py_coroutine_type",
  "is_cpp_py_async_generator_type": "is_py_async_generator_type",
  "is_cpp_py_iterable_type": "is_py_iterable_type",
  "is_cpp_concrete_generator_type": "is_concrete_generator_type",
  "is_cpp_concrete_coroutine_type": "is_concrete_coroutine_type",
  "is_cpp_erased_protocol_storage_type": "is_erased_protocol_storage_type",
  "is_cpp_callable_type": "is_callable_type",
  "is_cpp_delegate_type": "is_delegate_type",
}

EXTRACT_RENAME = {
  "cpp_list_elem_type": "list_elem_type",
  "cpp_dict_type_args": "dict_type_args",
  "cpp_set_elem_type": "set_elem_type",
  "cpp_deque_elem_type": "deque_elem_type",
  "cpp_chunk_deque_elem_type": "chunk_deque_elem_type",
  "cpp_option_inner_type": "optional_inner_type",
  "cpp_refcount_inner_type": "refcount_inner_type",
  "cpp_py_iterable_elem_type": "iterable_elem_type",
  "cpp_frozenset_elem_type": "frozenset_elem_type",
  "cpp_frozenlist_elem_type": "frozenlist_elem_type",
  "cpp_frozendict_type_args": "frozendict_type_args",
  "cpp_py_generator_type_args": "generator_type_args",
  "cpp_py_coroutine_type_args": "coroutine_type_args",
  "cpp_py_async_generator_type_args": "async_generator_type_args",
}

ALL_RENAME = {**PRED_RENAME, **EXTRACT_RENAME}
PRED_NAMES = set(PRED_RENAME.values())
EXTRACT_NAMES = set(EXTRACT_RENAME.values())
SKIP = {SRC / "analysis" / "ir.py", Path(__file__).resolve()}


def _rename_text(text: str) -> str:
  for old, new in sorted(ALL_RENAME.items(), key=lambda x: -len(x[0])):
    text = re.sub(rf"\b{re.escape(old)}\b", new, text)
  return text


def _ir_to_sibling(module: str, sibling: str) -> str:
  if module.endswith(".ir"):
    return module[:-2] + sibling
  return module.replace(".ir", f".{sibling}")


class ImportRewriter(ast.NodeTransformer):
  def __init__(self) -> None:
    self.new_imports: list[ast.stmt] = []

  def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom | None:
    if not node.module or not node.module.endswith(".ir"):
      return node
    pred: list[str] = []
    extr: list[str] = []
    rest: list[str] = []
    for alias in node.names:
      name = alias.name
      if name in PRED_NAMES:
        pred.append(name)
      elif name in EXTRACT_NAMES:
        extr.append(name)
      else:
        rest.append(name)
    out: list[ast.stmt] = []
    if pred:
      out.append(
        ast.ImportFrom(
          module=_ir_to_sibling(node.module, "type_pred"),
          names=[ast.alias(name=n) for n in pred],
          level=node.level,
        )
      )
    if extr:
      out.append(
        ast.ImportFrom(
          module=_ir_to_sibling(node.module, "type_extract"),
          names=[ast.alias(name=n) for n in extr],
          level=node.level,
        )
      )
    if rest:
      out.append(
        ast.ImportFrom(
          module=node.module,
          names=[ast.alias(name=n) for n in rest],
          level=node.level,
        )
      )
    self.new_imports.extend(out)
    return None


def rewrite_imports(source: str) -> str:
  try:
    tree = ast.parse(source)
  except SyntaxError:
    return source
  rw = ImportRewriter()
  new_body: list[ast.stmt] = []
  for stmt in tree.body:
    if isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.module.endswith(".ir"):
      rw.visit(stmt)
      new_body.extend(rw.new_imports)
      rw.new_imports = []
    else:
      new_body.append(stmt)
  if not rw.new_imports and new_body == tree.body:
    return source
  tree.body = new_body
  ast.fix_missing_locations(tree)
  return ast.unparse(tree) + "\n"


def migrate_file(path: Path) -> bool:
  if path.resolve() in SKIP:
    return False
  text = path.read_text(encoding="utf-8")
  if not any(re.search(rf"\b{re.escape(k)}\b", text) for k in ALL_RENAME):
    return False
  text = _rename_text(text)
  text = rewrite_imports(text)
  path.write_text(text, encoding="utf-8")
  return True


def main() -> int:
  changed = [p for p in SRC.rglob("*.py") if migrate_file(p)]
  print(f"updated {len(changed)} files")
  return 0


if __name__ == "__main__":
  sys.exit(main())
