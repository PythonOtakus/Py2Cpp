"""从标准库 Python 源 AST 扫描 ``@native_name``。"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from ...constant.stdlib_classes import (
  HOST_BOUND_ITERATOR_VIEW_EXCLUDE_PY,
  HOST_BOUND_ITERATOR_VIEW_EXTRA_CPP,
)
from ...constant.iterator_patterns import HOST_BOUND_ITERATOR_VIEW_SUFFIXES
from ..ir import cpp_ident, decorator_string_arg, has_named_decorator
from .builtin_stubs import function_cpp_rename
from .paths import (
  PY2CPP,
  header_for_module_path,
  module_path_for_py,
  stdlib_module_paths,
)


def _scan_native_names(path: Path) -> dict[str, str]:
  out: dict[str, str] = {}
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  for node in tree.body:
    if not isinstance(node, ast.ClassDef):
      continue
    if not has_named_decorator(node, "native_name"):
      continue
    cpp = decorator_string_arg(node, "native_name")
    if not cpp:
      continue
    out[node.name] = cpp
  return out


@lru_cache(maxsize=1)
def load_package_root_native_names() -> dict[str, str]:
  return _scan_native_names(PY2CPP / "builtins.py")


@lru_cache(maxsize=1)
def load_stdlib_native_names() -> dict[str, str]:
  out: dict[str, str] = {}
  for path in stdlib_module_paths():
    out.update(_scan_native_names(path))
  return out


@lru_cache(maxsize=1)
def load_stdlib_exception_types() -> frozenset[str]:
  """``py2cpp/core/exceptions.py`` 中异常类名（``raise X`` → ``cpp_exception_ctor``）。"""
  path = PY2CPP / "core" / "exceptions.py"
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  return frozenset(
    node.name for node in tree.body if isinstance(node, ast.ClassDef)
  )


@lru_cache(maxsize=1)
def load_native_cpp_base_headers() -> dict[str, str]:
  """``@native_name`` C++ 基名 → ``#include`` 路径（无 ``ClassInfo`` 时 ``type_deps`` 用）。"""
  out: dict[str, str] = {}
  for path in stdlib_module_paths():
    module_path = module_path_for_py(path)
    header = header_for_module_path(module_path)
    for _py, cpp in _scan_native_names(path).items():
      out[cpp] = header
  return out


def _scan_function_cpp_renames(path: Path) -> dict[tuple[str, str], str]:
  out: dict[tuple[str, str], str] = {}
  module_path = module_path_for_py(path)
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  for node in tree.body:
    if not isinstance(node, ast.FunctionDef):
      continue
    cpp = function_cpp_rename(node)
    if cpp is None:
      continue
    out[(module_path, node.name)] = cpp
  return out


@lru_cache(maxsize=1)
def load_module_function_cpp_renames() -> dict[tuple[str, str], str]:
  out: dict[tuple[str, str], str] = {}
  for path in stdlib_module_paths():
    out.update(_scan_function_cpp_renames(path))
  return out


def lookup_module_function_cpp_name(module_path: str, func_name: str) -> str | None:
  norm = module_path.replace("\\", "/")
  return load_module_function_cpp_renames().get((norm, func_name))


def _is_host_bound_iterator_view_py_name(py_name: str) -> bool:
  if py_name in HOST_BOUND_ITERATOR_VIEW_EXCLUDE_PY:
    return False
  return any(py_name.endswith(suffix) for suffix in HOST_BOUND_ITERATOR_VIEW_SUFFIXES)


@lru_cache(maxsize=1)
def load_stdlib_class_names() -> frozenset[str]:
  """标准库全部类名（含无 ``@native_name`` 的默认 ``Py`` 前缀类）。"""
  names: set[str] = set()
  for path in stdlib_module_paths():
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
      if isinstance(node, ast.ClassDef):
        names.add(node.name)
  return frozenset(names)


@lru_cache(maxsize=1)
def load_host_bound_iterator_view_cpp_bases() -> frozenset[str]:
  """``new(host)`` / ``ListIterator[T](lst)`` 走 ``_emit_list_iterator_ctor_inner`` 的 C++ 基名。"""
  names: set[str] = set(HOST_BOUND_ITERATOR_VIEW_EXTRA_CPP)
  for py_name in load_stdlib_class_names():
    if _is_host_bound_iterator_view_py_name(py_name):
      names.add(cpp_ident(py_name))
  return frozenset(names)
