"""为所有自定义类分配 ``__id__`` / ``__class_id__``（各继承树根内唯一整型）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def _skip_class_id(info: ClassInfo) -> bool:
  return (
    info.is_protocol
    or info.is_mixin
    or info.is_descriptor
    or info.is_annotation
    or info.is_refcount
    or info.is_boxing
    or info.is_enum
    or info.is_union
    or info.is_variant_mixin
  )


def _inheritance_root(info: ClassInfo, tr: Translator) -> str:
  for base_name in info.bases:
    base_info = tr.classes.get(base_name)
    if base_info is None or base_info.is_protocol:
      continue
    return _inheritance_root(base_info, tr)
  return info.name


def _ordered_custom_classes(tr: Translator) -> list[ClassInfo]:
  out: list[ClassInfo] = []
  seen: set[str] = set()
  for module_path in tr.module_order:
    tree = tr.module_asts.get(module_path)
    if tree is None:
      continue
    for node in tree.body:
      if not isinstance(node, ast.ClassDef):
        continue
      info = tr.classes.get(node.name)
      if info is None or info.module_path != module_path:
        continue
      if _skip_class_id(info):
        continue
      if info.name in seen:
        continue
      seen.add(info.name)
      out.append(info)
  return out


def expand_class_id(tr: Translator) -> None:
  counters: dict[str, int] = {}
  for info in _ordered_custom_classes(tr):
    if info.inject_type_id:
      raise ValueError(f"{info.name}: 勿手写 ``__id__`` / ``__class_id__``（译器自动注入）")
    if "__id__" in info.static_properties or "__id__" in info.methods:
      raise ValueError(f"{info.name}: 勿手写 ``__id__``（译器自动注入）")
    if "__class_id__" in info.properties or "__class_id__" in info.methods:
      raise ValueError(f"{info.name}: 勿手写 ``__class_id__``（译器自动注入）")
    root = _inheritance_root(info, tr)
    info.class_id_root = root
    next_id = counters.get(root, 0) + 1
    counters[root] = next_id
    info.class_id = next_id
    info.inject_type_id = True
