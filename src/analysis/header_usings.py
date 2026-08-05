"""从 ``ClassInfo`` / ``#include`` 推导模块 ``using``（替代 ``_RUNTIME_HEADER_USINGS``）。"""
from __future__ import annotations

from .ir import TYPE_MARKER_CLASSES, ClassInfo
from .module_namespace import namespace_qualifier_for_module
from .type_deps import header_for_module
from ..constant.stdlib_layout import RUNTIME_PKG, stdlib_header_include


def header_include_for_module(module_path: str) -> str:
  if module_path == RUNTIME_PKG:
    return stdlib_header_include(RUNTIME_PKG)
  return header_for_module(module_path)


def _skip_class_for_header_using(info: ClassInfo) -> bool:
  if info.is_descriptor or info.is_mixin or info.is_annotation or info.is_protocol:
    return True
  if info.outer_class is not None and info.outer_class.is_union:
    return True
  if info.name in TYPE_MARKER_CLASSES:
    return True
  return False


def build_header_usings_index(
  classes: dict[str, ClassInfo],
) -> dict[str, list[tuple[str, str]]]:
  """``include 路径`` → ``[(namespace_qualifier, cpp_symbol), …]``。"""
  buckets: dict[str, list[tuple[str, str]]] = {}
  for info in classes.values():
    if _skip_class_for_header_using(info):
      continue
    ns = namespace_qualifier_for_module(info.module_path)
    if not ns:
      continue
    pair = (ns, info.cpp_name())
    h = header_include_for_module(info.module_path)
    buckets.setdefault(h, []).append(pair)
  index: dict[str, list[tuple[str, str]]] = {}
  for h, pairs in buckets.items():
    seen: set[tuple[str, str]] = set()
    uniq: list[tuple[str, str]] = []
    for pair in pairs:
      if pair in seen:
        continue
      seen.add(pair)
      uniq.append(pair)
    uniq.sort(key=lambda item: item[1])
    index[h] = uniq
  return index


def usings_for_headers(
  headers: list[str],
  index: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, str]]:
  seen: set[tuple[str, str]] = set()
  out: list[tuple[str, str]] = []
  for inc in headers:
    for pair in index.get(inc, ()):
      if pair in seen:
        continue
      seen.add(pair)
      out.append(pair)
  return out
