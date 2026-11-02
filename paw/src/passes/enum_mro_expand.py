"""``@enum.mro`` + ``class E(base=…)``：MRO 闭集枚举 + 手动特殊成员。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  EnumMemberInfo,
  class_base_name,
  has_enum_mro_decorator,
  parse_enum_mro_base,
)
from .class_id import _skip_class_id
from .enum_expand import _clear_enum_class_body, _parse_enum_assignments, _parse_int_value

if TYPE_CHECKING:
  from ..translator import Translator

from .mro_closure import collect_mro_classes, mark_mro_base_polymorphic_class_id, is_subclass_of as _is_subclass_of


def _resolve_enum_mro_members(
  owner: str,
  own_specs: list[tuple[str, ast.expr | None]],
  inherited: list[EnumMemberInfo],
  inherited_classes: dict[str, str],
  auto_class_names: list[str],
  tr: Translator,
) -> tuple[list[EnumMemberInfo], dict[str, str]]:
  members: list[EnumMemberInfo] = list(inherited)
  member_classes: dict[str, str] = dict(inherited_classes)
  seen_names = {m.name for m in members}
  used_values = {m.value for m in members}
  auto_set = set(auto_class_names)

  for name, val_node in own_specs:
    if name in seen_names:
      raise ValueError(f"{owner}: 成员 {name} 重复")
    seen_names.add(name)
    if name in auto_set:
      cls_info = tr.classes.get(name)
      if cls_info is None or cls_info.class_id is None:
        raise ValueError(f"{owner}.{name}: 无 class_id")
      value = cls_info.class_id if val_node is None else _parse_int_value(val_node, owner, name)
      member_classes[name] = name
    elif val_node is None:
      if not members:
        raise ValueError(f"{owner}.{name}: ... 不能作为首个成员（无起始值）")
      value = members[-1].value + 1
      while value in used_values:
        value += 1
    else:
      value = _parse_int_value(val_node, owner, name)
    if value in used_values:
      raise ValueError(f"{owner}.{name}: 枚举值 {value} 与已有成员或 __id__ 冲突")
    used_values.add(value)
    members.append(EnumMemberInfo(name, value))

  if not members:
    raise ValueError(f"{owner}: @enum.mro 至少须有一个成员")
  return members, member_classes


def _parse_enum_mro_layout(tr: Translator, info: ClassInfo) -> None:
  parent_name: str | None = None
  for base in info.node.bases:
    name = class_base_name(base)
    if name is None:
      raise ValueError(f"{info.name}: @enum.mro 仅支持单继承其它 @enum.mro")
    parent = tr.classes.get(name)
    if parent is None or not parent.is_enum_mro:
      raise ValueError(f"{info.name}: 基类 {name} 须为 @enum.mro")
    if parent_name is not None:
      raise ValueError(f"{info.name}: @enum.mro 仅支持单继承")
    parent_name = name

  inherited: list[EnumMemberInfo] = []
  inherited_classes: dict[str, str] = {}
  if parent_name is not None:
    if parse_enum_mro_base(info.node) is not None:
      raise ValueError(f"{info.name}: 子 @enum.mro 勿写 base=，继承父枚举闭集")
    parent = tr.classes[parent_name]
    base_name = parent.enum_mro_base
    if base_name is None:
      raise ValueError(f"{info.name}: 父枚举 {parent_name} 缺少 enum_mro_base")
    inherited = list(parent.enum_members)
    inherited_classes = dict(parent.enum_mro_member_classes)
    info.enum_underlying_cpp = parent.enum_underlying_cpp
    info.enum_parent = parent_name
  else:
    base_name = parse_enum_mro_base(info.node)
    if base_name is None:
      raise ValueError(
        f"{info.name}: @enum.mro 须 ``class {info.name}(base=ClassName):``"
      )
    info.enum_parent = None
    info.enum_underlying_cpp = "PyInt"

  info.enum_mro_base = base_name
  mark_mro_base_polymorphic_class_id(tr, base_name)

  own_specs = _parse_enum_assignments(info.node)
  manual_names = {name for name, _ in own_specs}
  auto_names = collect_mro_classes(tr, base_name, info.module_path)
  if parent_name is not None:
    covered = set(inherited_classes.values())
    auto_names = [n for n in auto_names if n not in covered]
  for cls_name in auto_names:
    if cls_name not in manual_names:
      own_specs.append((cls_name, None))

  members, member_classes = _resolve_enum_mro_members(
    info.name,
    own_specs,
    inherited,
    inherited_classes,
    auto_names,
    tr,
  )
  info.enum_members = members
  info.enum_mro_member_classes = member_classes
  info.enum_is_flag = False


def expand_enum_mro(tr: Translator) -> None:
  for info in tr.classes.values():
    if not has_enum_mro_decorator(info.node):
      continue
    info.is_enum = True
    info.is_enum_mro = True
    _parse_enum_mro_layout(tr, info)
    _clear_enum_class_body(info)
