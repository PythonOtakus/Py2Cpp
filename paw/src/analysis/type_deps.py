"""从 C++ 类型文本推导 ``#include``（替代 ``INCLUDE_RULES`` 子串表）。"""
from __future__ import annotations

from .stubs.class_stubs import load_native_cpp_base_headers
from .ir import (
  ClassInfo,
  class_info_for_cpp_type,
  cpp_template_base_and_args,
  strip_cpp_type_qualifiers,
)

from ..constant.primitive_headers import PRIMITIVE_HEADER_MAP


def header_for_module(module_path: str) -> str:
  return f"{module_path}.h"


def _is_skippable_atom(cpp_type: str) -> bool:
  if not cpp_type:
    return True
  if cpp_type == "void":
    return True
  if len(cpp_type) >= 2 and cpp_type[0] == "T" and cpp_type[1:].isdigit():
    return True
  return False


def _header_for_class(info: ClassInfo) -> str:
  return header_for_module(info.module_path)


def _collect_base_dep(
  base: str,
  classes: dict[str, ClassInfo],
  own_header: str,
  out: list[str],
) -> None:
  if base == "PyCallable":
    from ..constant.stdlib_layout import stdlib_header_include

    # ``str.h`` 前置声明 PyCallable，避免 str → delegate → list → str 的头环。
    if own_header == stdlib_header_include("text/str"):
      return
    header = stdlib_header_include("core/delegate")
    if header != own_header and header not in out:
      out.append(header)
    return
  # 标量优先于包根 ``char``/``byte`` 等 ``TYPE_MARKER`` 的 ``ClassInfo``（否则误拉 ``py2cpp.h``）。
  header = PRIMITIVE_HEADER_MAP.get(base)
  if header is None:
    header = load_native_cpp_base_headers().get(base)
  if header is not None:
    if header != own_header and header not in out:
      out.append(header)
    return
  info = class_info_for_cpp_type(base, classes)
  if info is not None:
    header = _header_for_class(info)
    if header != own_header and header not in out:
      out.append(header)


def collect_type_header_deps(
  cpp_type: str,
  own_header: str,
  classes: dict[str, ClassInfo],
) -> list[str]:
  """从单段 C++ 类型文本收集依赖头（含模板实参递归）。"""
  out: list[str] = []
  _collect_type_header_deps_into(cpp_type, own_header, classes, out)
  return out


def _collect_type_header_deps_into(
  cpp_type: str,
  own_header: str,
  classes: dict[str, ClassInfo],
  out: list[str],
) -> None:
  t = strip_cpp_type_qualifiers(cpp_type.strip())
  if _is_skippable_atom(t):
    return
  parsed = cpp_template_base_and_args(t)
  if parsed is not None:
    base, args = parsed
    _collect_base_dep(base, classes, own_header, out)
    for arg in args:
      _collect_type_header_deps_into(arg, own_header, classes, out)
    return
  _collect_base_dep(t, classes, own_header, out)
