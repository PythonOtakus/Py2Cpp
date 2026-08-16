"""C++ 模板类型前缀 ``PyList<`` 等：由 ``@native_name`` / 默认 ``Py`` 前缀 + overrides 推导。"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from ...constant.language import default_py_class_cpp_name
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


def _class_cpp_prefix(node: ast.ClassDef) -> str:
  cpp = _native_name_from_class(node)
  if cpp is None:
    cpp = default_py_class_cpp_name(node.name)
  return f"{cpp}<"


@lru_cache(maxsize=1)
def load_cpp_template_type_prefixes() -> dict[str, str]:
  """Python 类名 → ``CppName<``（供 ``is_cpp_*_type`` / ``cpp_*_elem_type``）。"""
  out = dict(CPP_TEMPLATE_PREFIX_OVERRIDES)
  for path in stdlib_module_paths():
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
      if not isinstance(node, ast.ClassDef):
        continue
      # 有类型参数或显式 ``@native_name`` 的容器类
      if getattr(node, "type_params", None) or _native_name_from_class(node):
        out.setdefault(node.name, _class_cpp_prefix(node))
  return out


def cpp_template_type_prefix(py_class: str) -> str | None:
  return load_cpp_template_type_prefixes().get(py_class)
