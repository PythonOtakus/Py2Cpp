"""``@enum``：整型 ``enum class``（``...`` 顺延、默认 ``int`` 底层、单继承其它 enum）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  EnumMemberInfo,
  class_base_name,
  cpp_ident,
  has_enum_mro_decorator,
  has_named_decorator,
)

if TYPE_CHECKING:
  from ..translator import Translator

_ENUM_SCALAR_BASES = frozenset({"int", "int64"})


def _is_ellipsis_expr(node: ast.expr | None) -> bool:
  if node is None:
    return False
  if isinstance(node, ast.Constant) and node.value is Ellipsis:
    return True
  return isinstance(node, ast.Name) and node.id == "..."


def _parse_enum_flag_option(node: ast.ClassDef) -> bool:
  """``@enum(flag=True)`` → Flag 式 ``...`` 顺延为下一个 2 的整数次幂（对齐 CPython ``enum.Flag``）。"""
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "enum":
      return False
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Name):
      continue
    if dec.func.id != "enum":
      continue
    for kw in dec.keywords:
      if kw.arg == "flag":
        if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, bool):
          raise ValueError(f"{node.name}: @enum(flag=…) 须为 bool 常量")
        return kw.value.value
  return False


def _parse_int_value(node: ast.expr, owner: str, member: str) -> int:
  if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
    node.value, bool,
  ):
    return node.value
  if (
    isinstance(node, ast.UnaryOp)
    and isinstance(node.op, ast.USub)
    and isinstance(node.operand, ast.Constant)
    and isinstance(node.operand.value, int)
    and not isinstance(node.operand.value, bool)
  ):
    return -node.operand.value
  raise ValueError(f"{owner}.{member}: 枚举值须为整型常量或 ...")


def _parse_enum_assignments(
  node: ast.ClassDef,
) -> list[tuple[str, ast.expr | None]]:
  """返回 ``(成员名, 值 AST 或 None 表示 ...)``。"""
  out: list[tuple[str, ast.expr | None]] = []
  for stmt in node.body:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
      continue
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Name):
      raise ValueError(f"{node.name}: 枚举成员须为简单赋值 ``name = v``")
    if _is_ellipsis_expr(stmt.value):
      out.append((tgt.id, None))
    else:
      out.append((tgt.id, stmt.value))
  return out


def _next_flag_value(members: list[EnumMemberInfo]) -> int:
  """对齐 CPython ``Flag._generate_next_value_``：取当前最大值的下一个 2 的幂。"""
  if not members:
    return 1
  last = max(m.value for m in members)
  if last == 0:
    return 1
  v = 1
  while v <= last:
    v <<= 1
  return v


def _resolve_enum_members(
  owner: str,
  own_specs: list[tuple[str, ast.expr | None]],
  inherited: list[EnumMemberInfo],
  *,
  is_flag: bool,
) -> list[EnumMemberInfo]:
  members: list[EnumMemberInfo] = list(inherited)
  seen = {m.name for m in members}
  for name, val_node in own_specs:
    if name in seen:
      raise ValueError(f"{owner}: 成员 {name} 重复")
    seen.add(name)
    if val_node is None:
      if is_flag:
        value = _next_flag_value(members)
      else:
        if not members:
          raise ValueError(f"{owner}.{name}: ... 不能作为首个成员（无起始值）")
        value = members[-1].value + 1
    else:
      value = _parse_int_value(val_node, owner, name)
    members.append(EnumMemberInfo(name, value))
  if not members:
    raise ValueError(f"{owner}: @enum 至少须有一个成员")
  return members


def _underlying_cpp_for_scalar(name: str) -> str:
  if name == "int64":
    return cpp_ident("int64")
  if name == "int":
    return cpp_ident("int")
  raise ValueError(f"不支持的枚举底层类型 {name!r}（仅 int / int64）")


def _parse_enum_layout(tr: Translator, info: ClassInfo) -> None:
  scalar_base: str | None = None
  parent_name: str | None = None
  for base in info.node.bases:
    name = class_base_name(base)
    if not name:
      raise ValueError(f"{info.name}: 非法 enum 基类 {ast.dump(base)}")
    if name in _ENUM_SCALAR_BASES:
      if scalar_base is not None or parent_name is not None:
        raise ValueError(f"{info.name}: 仅支持单继承（底层 int/int64 或一个 @enum）")
      scalar_base = name
      continue
    parent = tr.classes.get(name)
    if parent is None or not parent.is_enum:
      raise ValueError(f"{info.name}: 基类 {name} 须为 @enum 或 int/int64")
    if parent_name is not None or scalar_base is not None:
      raise ValueError(f"{info.name}: 仅支持单继承（底层 int/int64 或一个 @enum）")
    parent_name = name

  is_flag = _parse_enum_flag_option(info.node)
  if parent_name is not None:
    parent = tr.classes[parent_name]
    if not parent.enum_members:
      raise ValueError(f"{info.name}: 基类 {parent_name} 尚未展开")
    info.enum_underlying_cpp = parent.enum_underlying_cpp
    info.enum_parent = parent_name
    inherited = list(parent.enum_members)
    if parent.enum_is_flag:
      is_flag = True
  else:
    info.enum_parent = None
    info.enum_underlying_cpp = _underlying_cpp_for_scalar(scalar_base or "int")
    inherited = []

  info.enum_is_flag = is_flag
  own_specs = _parse_enum_assignments(info.node)
  info.enum_members = _resolve_enum_members(
    info.name, own_specs, inherited, is_flag=is_flag,
  )


def _clear_enum_class_body(info: ClassInfo) -> None:
  info.fields.clear()
  info.field_types.clear()
  info.field_type_nodes.clear()
  info.field_defaults.clear()
  info.field_annotations.clear()
  info.field_annotation_kwargs.clear()
  info.optional_fields.clear()
  info.methods.clear()
  info.method_sigs.clear()
  info.method_overloads.clear()
  info.method_overload_sigs.clear()
  info.inits.clear()
  info.init_sigs.clear()
  info.properties.clear()
  info.static_properties.clear()
  info.static_property_storage.clear()
  info.static_class_fields.clear()


def enum_member_names(info: ClassInfo) -> frozenset[str]:
  return frozenset(m.name for m in info.enum_members)


def expand_enum(tr: Translator) -> None:
  for info in tr.classes.values():
    if has_enum_mro_decorator(info.node):
      continue
    if not has_named_decorator(info.node, "enum"):
      continue
    info.is_enum = True
    _parse_enum_layout(tr, info)
    _clear_enum_class_body(info)
