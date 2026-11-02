"""``@union.mro`` + ``class U(base=…)``：MRO 闭集 union + 嵌套 ``Enum``。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  EnumMemberInfo,
  UnionVariantInfo,
  has_named_decorator,
  has_union_mro_decorator,
  parse_enum_mro_base,
)
from .enum_expand import _clear_enum_class_body, _parse_enum_assignments, _parse_int_value
from .mro_closure import collect_mro_classes, mark_mro_base_polymorphic_class_id
from .union_expand import _build_nested_variant, _is_variant_class

if TYPE_CHECKING:
  from ..translator import Translator

_UNION_MRO_FIELD = "value"


def union_enum_member_names(info: ClassInfo) -> frozenset[str]:
  return frozenset(m.name for m in info.union_enum_members)


def _resolve_union_enum_members(
  owner: str,
  auto_class_names: list[str],
  tr: Translator,
) -> tuple[list[EnumMemberInfo], dict[str, str]]:
  """嵌套 ``Enum`` 成员仅来自 MRO 闭集（``__id__``）；类体赋值见 ``_collect_union_mro_static_fields``。"""
  members: list[EnumMemberInfo] = []
  member_classes: dict[str, str] = {}
  used_values: set[int] = set()

  for cls_name in auto_class_names:
    cls_info = tr.classes.get(cls_name)
    if cls_info is None or cls_info.class_id is None:
      raise ValueError(f"{owner}.{cls_name}: 无 class_id")
    value = cls_info.class_id
    if value in used_values:
      raise ValueError(f"{owner}.{cls_name}: 枚举值 {value} 与已有成员冲突")
    used_values.add(value)
    member_classes[cls_name] = cls_name
    members.append(EnumMemberInfo(cls_name, value))

  if not members:
    raise ValueError(f"{owner}: @union.mro 至少须有一个 Enum 成员")
  return members, member_classes


def _append_union_mro_body_variants(
  tr: Translator,
  info: ClassInfo,
  auto_names: list[str],
  variants: list[UnionVariantInfo],
  enum_members: list[EnumMemberInfo],
  used_values: set[int],
) -> None:
  """类体 ``@variant``（非 MRO）：unit 无赋值时枚举值自 -1 递减；否则须单个整型常量赋值。"""
  auto_set = set(auto_names)
  seen = {v.name for v in variants}
  next_auto_neg = -1

  for stmt in info.node.body:
    if not isinstance(stmt, ast.ClassDef) or not _is_variant_class(stmt):
      continue
    if stmt.name in auto_set:
      raise ValueError(
        f"{info.name}.{stmt.name}: 与 MRO 类型同名；MRO 变体由闭集自动生成",
      )
    if stmt.name in seen:
      raise ValueError(f"{info.name}: 重复变体 {stmt.name}")
    seen.add(stmt.name)
    variant = _build_nested_variant(tr, info, stmt)
    variants.append(variant)

    manual = _parse_enum_assignments(stmt)
    if manual:
      if len(manual) != 1:
        raise ValueError(
          f"{info.name}.{stmt.name}: @variant 枚举值须至多一个 ``name = 整型`` 赋值",
        )
      _ename, val_node = manual[0]
      if val_node is None:
        raise ValueError(f"{info.name}.{stmt.name}: 枚举值须为整型常量")
      value = _parse_int_value(val_node, info.name, stmt.name)
    elif variant.is_unit:
      value = next_auto_neg
      next_auto_neg -= 1
    else:
      raise ValueError(
        f"{info.name}.{stmt.name}: 带字段 @variant 须显式 ``name = 整型`` 枚举值",
      )
    if value in used_values:
      raise ValueError(f"{info.name}.{stmt.name}: 枚举值 {value} 冲突")
    used_values.add(value)
    enum_members.append(EnumMemberInfo(stmt.name, value))


def _collect_union_mro_static_fields(info: ClassInfo) -> None:
  """类体 ``name = 编译期常量`` → ``static const``，非嵌套 ``Enum`` 成员。"""
  info.static_class_fields.clear()
  for stmt in info.node.body:
    if isinstance(stmt, ast.Assign):
      info._field_from_class_assign(stmt)


def _validate_union_mro_static_fields(info: ClassInfo, auto_class_names: list[str]) -> None:
  auto_set = set(auto_class_names)
  variant_names = {
    stmt.name
    for stmt in info.node.body
    if isinstance(stmt, ast.ClassDef) and _is_variant_class(stmt)
  }
  for name in info.static_class_fields:
    if name in auto_set or name in variant_names:
      raise ValueError(
        f"{info.name}.{name}: 类体赋值须为静态字段；MRO / @variant 同名请改用 ``@variant class {name}``",
      )


def _clear_union_mro_class_body(info: ClassInfo) -> None:
  _clear_enum_class_body(info)
  _collect_union_mro_static_fields(info)


def _parse_union_mro_layout(tr: Translator, info: ClassInfo) -> None:
  base_name = parse_enum_mro_base(info.node)
  if base_name is None:
    raise ValueError(
      f"{info.name}: @union.mro 须 ``class {info.name}(base=ClassName):``",
    )
  info.union_mro_base = base_name
  mark_mro_base_polymorphic_class_id(tr, base_name)
  info.union_enum_underlying_cpp = "PyInt"

  auto_names = collect_mro_classes(tr, base_name, info.module_path)
  enum_members, member_classes = _resolve_union_enum_members(
    info.name,
    auto_names,
    tr,
  )
  used_values = {m.value for m in enum_members}
  variants: list[UnionVariantInfo] = []
  for cls_name in auto_names:
    variants.append(
      UnionVariantInfo(
        name=cls_name,
        fields=[_UNION_MRO_FIELD],
        field_annotations={_UNION_MRO_FIELD: ast.Name(id=cls_name, ctx=ast.Load())},
      ),
    )
  _append_union_mro_body_variants(
    tr, info, auto_names, variants, enum_members, used_values,
  )
  info.union_enum_members = enum_members
  info.union_mro_member_classes = member_classes
  info.union_variants = variants
  info.union_family_names = frozenset({info.name})


def expand_union_mro(tr: Translator) -> None:
  for info in tr.classes.values():
    if not has_union_mro_decorator(info.node):
      continue
    if has_named_decorator(info.node, "boxing") or has_named_decorator(info.node, "refcount"):
      raise ValueError(f"{info.name}: @union.mro 与 @boxing / @refcount 互斥")
    info.is_union = True
    info.is_union_mro = True
    info.is_copyable = True
    _parse_union_mro_layout(tr, info)
    _clear_union_mro_class_body(info)
    _validate_union_mro_static_fields(info, list(info.union_mro_member_classes))
