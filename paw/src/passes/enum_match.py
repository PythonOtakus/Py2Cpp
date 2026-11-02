"""``match`` 中 ``Enum.MEMBER`` 模式；``MatchOr`` 仅逻辑或，**不**表示 Flag 位运算。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo
from .enum_expand import enum_member_names


def _parse_enum_attr(node: ast.expr) -> tuple[str, str] | None:
  if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
    return node.value.id, node.attr
  return None


def _parse_enum_or_value(node: ast.expr) -> tuple[str, list[str]] | None:
  """``Cls.A | Cls.B`` 或 ``Cls.A`` → ``(类名, [成员名, …])``。"""
  if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
    left = _parse_enum_or_value(node.left)
    right = _parse_enum_or_value(node.right)
    if left is None or right is None or left[0] != right[0]:
      return None
    return left[0], left[1] + right[1]
  hit = _parse_enum_attr(node)
  if hit is None:
    return None
  return hit[0], [hit[1]]


def _enum_match_condition(
  info: ClassInfo,
  member_names: list[str],
  subject_expr: str,
) -> str:
  """单成员精确相等；多成员（仅 ``MatchValue`` 内 ``BinOp`` 才可能）为 ``==`` 逻辑或。"""
  cpp = info.cpp_name()
  if len(member_names) == 1:
    return f"({subject_expr} == {cpp}::{member_names[0]})"
  parts = [f"({subject_expr} == {cpp}::{m})" for m in member_names]
  return "(" + " || ".join(parts) + ")"


def _enum_members_from_match_value(
  pattern: ast.MatchValue,
) -> tuple[str, list[str]] | None:
  return _parse_enum_or_value(pattern.value)


def enum_or_pattern_to_match(
  pattern: ast.MatchOr,
  *,
  subject_expr: str,
  classes: dict[str, ClassInfo],
):
  """``case E.A | E.B``（``MatchOr`` 各支为 ``MatchValue``）。"""
  from .match_case import PatternMatch

  cls_name: str | None = None
  member_names: list[str] = []
  for branch in pattern.patterns:
    if not isinstance(branch, ast.MatchValue):
      return None
    hit = _enum_members_from_match_value(branch)
    if hit is None:
      return None
    if cls_name is None:
      cls_name = hit[0]
    elif cls_name != hit[0]:
      return None
    member_names.extend(hit[1])
  if cls_name is None:
    return None
  info = classes.get(cls_name)
  if info is None or not info.is_enum:
    return None
  known = enum_member_names(info)
  for m in member_names:
    if m not in known:
      raise ValueError(f"{cls_name}: match 模式未知成员 {m}")
  return PatternMatch(
    condition=_enum_match_condition(info, member_names, subject_expr),
  )


def enum_pattern_to_match(
  pattern: ast.MatchValue,
  *,
  subject_expr: str,
  classes: dict[str, ClassInfo],
):
  from .match_case import PatternMatch
  parsed = _enum_members_from_match_value(pattern)
  if parsed is None:
    return None
  cls_name, member_names = parsed
  info = classes.get(cls_name)
  if info is None or not info.is_enum:
    return None
  known = enum_member_names(info)
  for m in member_names:
    if m not in known:
      raise ValueError(f"{cls_name}: match 模式未知成员 {m}")
  return PatternMatch(
    condition=_enum_match_condition(info, member_names, subject_expr),
  )
