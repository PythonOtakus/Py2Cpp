"""C++ 模板类型前缀 ``PyList<`` 等：由 ``@native_name`` + ``constant/stdlib_classes`` 覆盖推导。"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from ...constant.stdlib_classes import CPP_TEMPLATE_PREFIX_OVERRIDES
from .paths import stdlib_module_paths


def _native_name_from_class(node: ast.ClassDef) -> str | None:
  for deco in node.decorator_list:
    match deco:
      case ast.Call(func=ast.Name(id="native_name"), args=[ast.Constant(value=cpp)]):
        if isinstance(cpp, str):
          if "*" in cpp:
            return cpp.replace("*", node.name)
          return cpp
      case ast.Name(id="native_name"):
        pass
  return None


def _scan_native_names(path: Path) -> dict[str, str]:
  out: dict[str, str] = {}
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  for node in tree.body:
    if not isinstance(node, ast.ClassDef):
      continue
    cpp = _native_name_from_class(node)
    if cpp:
      out[node.name] = cpp
  return out


@lru_cache(maxsize=1)
def load_cpp_template_type_prefixes() -> dict[str, str]:
  """Python 类名 → ``CppName<``（供 ``is_cpp_*_type`` / ``cpp_*_elem_type``）。"""
  out = dict(CPP_TEMPLATE_PREFIX_OVERRIDES)
  for path in stdlib_module_paths():
    for py_name, cpp_name in _scan_native_names(path).items():
      out.setdefault(py_name, f"{cpp_name}<")
  return out


def cpp_template_type_prefix(py_class: str) -> str | None:
  return load_cpp_template_type_prefixes().get(py_class)
