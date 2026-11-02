"""MRO 闭集扫描（``@enum.mro`` / ``@union.mro`` 共用）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator

_DEFAULT_EXCLUDE = frozenset({"BaseExceptionGroup", "ExceptionGroup"})


def is_subclass_of(info: ClassInfo, base_name: str, tr: Translator) -> bool:
  if base_name in info.bases:
    return True
  for base in info.bases:
    base_info = tr.classes.get(base)
    if base_info is not None and is_subclass_of(base_info, base_name, tr):
      return True
  return False


def collect_mro_classes(
  tr: Translator,
  base_name: str,
  enum_module: str,
  *,
  exclude: frozenset[str] = _DEFAULT_EXCLUDE,
) -> list[str]:
  if tr.classes.get(base_name) is None:
    raise ValueError(f"MRO 闭集: 未知基类 {base_name!r}")
  out: list[str] = []
  seen: set[str] = set()
  tree = tr.module_asts.get(enum_module)
  if tree is None:
    return out
  for node in tree.body:
    if not isinstance(node, ast.ClassDef):
      continue
    info = tr.classes.get(node.name)
    if info is None or info.module_path != enum_module:
      continue
    if info.name in seen or info.name == base_name:
      continue
    if info.name in exclude:
      continue
    if info.is_enum or info.is_union or info.is_protocol:
      continue
    if not is_subclass_of(info, base_name, tr):
      continue
    if info.class_id is None:
      raise ValueError(f"{info.name}: MRO 闭集扫描前须先 expand_class_id")
    seen.add(info.name)
    out.append(info.name)
  return out


def mark_mro_base_polymorphic_class_id(tr: Translator, base_name: str) -> None:
  """``@enum.mro`` / ``@union.mro`` 基类：``of(e)`` 经基类引用须动态 ``__class_id__``。"""
  base_info = tr.classes.get(base_name)
  if base_info is not None:
    base_info.force_virtual_class_id = True
