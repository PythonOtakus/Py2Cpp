"""Phase 7：删除 ir.py 中 is_cpp_* / cpp_*_elem 薄包装，正文改用 type_pred / type_extract。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IR = ROOT / "src" / "analysis" / "ir.py"

PRED_RENAME = {
  "is_cpp_delegate_type": "is_delegate_type",
  "is_cpp_callable_type": "is_callable_type",
  "is_cpp_py_callable_type": "is_py_callable_type",
  "is_cpp_py_generator_type": "is_py_generator_type",
  "is_cpp_concrete_generator_type": "is_concrete_generator_type",
  "is_cpp_py_coroutine_type": "is_py_coroutine_type",
  "is_cpp_concrete_coroutine_type": "is_concrete_coroutine_type",
  "is_cpp_py_async_generator_type": "is_py_async_generator_type",
  "is_cpp_py_iterable_type": "is_py_iterable_type",
  "is_cpp_erased_protocol_storage_type": "is_erased_protocol_storage_type",
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
  "is_cpp_heap_array_type": "is_heap_array_type",
  "is_cpp_char_heap_array_type": "is_char_heap_array_type",
  "is_cpp_byte_heap_array_type": "is_byte_heap_array_type",
  "is_cpp_char_stack_array_type": "is_char_stack_array_type",
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
  "is_cpp_invokable_type": "is_invokable_type",
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

REMOVE_FUNCS = set(PRED_RENAME) | set(EXTRACT_RENAME) - {"is_cpp_invokable_type"}


def _remove_top_level_func(text: str, name: str) -> str:
  pat = rf"^def {re.escape(name)}\("
  m = re.search(pat, text, re.MULTILINE)
  if not m:
    return text
  start = m.start()
  rest = text[m.end() :]
  nxt = re.search(r"^def ", rest, re.MULTILINE)
  end = m.end() + (nxt.start() if nxt else len(rest))
  chunk = text[start:end]
  if name in EXTRACT_RENAME and "from .type_extract import" in chunk:
    pass
  elif name in PRED_RENAME and "from .type_pred import" in chunk:
    pass
  elif name == "is_cpp_invokable_type":
    pass
  elif name.startswith("cpp_py_") and "template_fixed_inners" in chunk:
    pass
  else:
    return text
  return text[:start] + text[end:]


def main() -> int:
  text = IR.read_text(encoding="utf-8")
  for name in sorted(REMOVE_FUNCS, key=len, reverse=True):
    text = _remove_top_level_func(text, name)
  all_rename = {**PRED_RENAME, **EXTRACT_RENAME}
  for old, new in sorted(all_rename.items(), key=lambda x: -len(x[0])):
    text = re.sub(rf"\b{re.escape(old)}\b", new, text)
  text = text.replace("def is_invokable_type(", "def is_invokable_type(", 1)
  IR.write_text(text, encoding="utf-8")
  print(f"cleaned {IR}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
