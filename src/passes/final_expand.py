"""``T @final``：从 ``__init__`` 提取 ``self.f = …`` 供 C++ 构造初始化列表；类体默认进 ``final_ctor_inits``。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo
from ..translation_error import raise_translation_error

if TYPE_CHECKING:
  from ..translator import Translator


def _self_field_assign_value(node: ast.stmt, field: str) -> ast.expr | None:
  if isinstance(node, ast.Assign):
    if len(node.targets) != 1:
      return None
    tgt = node.targets[0]
    val = node.value
  elif isinstance(node, ast.AnnAssign):
    tgt = node.target
    val = node.value
    if val is None:
      return None
  else:
    return None
  if not isinstance(tgt, ast.Attribute):
    return None
  if not isinstance(tgt.value, ast.Name) or tgt.value.id != "self":
    return None
  if tgt.attr != field:
    return None
  return val


def _class_body_final_defaults(info: ClassInfo) -> dict[str, ast.expr]:
  out: dict[str, ast.expr] = {}
  for field in info.final_fields:
    if field in info.field_defaults:
      out[field] = copy.deepcopy(info.field_defaults.pop(field))
  return out


def _extract_final_inits_for_init(
  tr: Translator,
  info: ClassInfo,
  init: ast.FunctionDef,
  class_defaults: dict[str, ast.expr],
) -> None:
  local = copy.deepcopy(class_defaults)
  new_body: list[ast.stmt] = []
  for stmt in init.body:
    matched: str | None = None
    expr: ast.expr | None = None
    for field in info.final_fields:
      val = _self_field_assign_value(stmt, field)
      if val is not None:
        matched = field
        expr = val
        break
    if matched is None:
      new_body.append(stmt)
      continue
    if matched in local:
      raise_translation_error(
        tr,
        stmt,
        f"{info.name}.{matched}: ``@final`` 字段不可重复赋值",
      )
    local[matched] = copy.deepcopy(expr)
  init.body = new_body
  missing = info.final_fields - set(local)
  if missing:
    raise_translation_error(
      tr,
      init,
      f"{info.name}: ``@final`` 字段须初始化: {', '.join(sorted(missing))}",
    )
  info.final_ctor_inits_by_init[id(init)] = local


def expand_final_ctor_inits(tr: Translator) -> None:
  for info in tr.classes.values():
    if not info.final_fields:
      continue
    class_defaults = _class_body_final_defaults(info)
    if not info.inits:
      info.final_ctor_inits.update(class_defaults)
      missing = info.final_fields - set(info.final_ctor_inits)
      if missing:
        raise_translation_error(
          tr,
          info.node,
          f"{info.name}: ``@final`` 字段须类体默认值或 ``__init__`` 赋值: "
          f"{', '.join(sorted(missing))}",
        )
      continue
    for init in info.inits:
      _extract_final_inits_for_init(tr, info, init, class_defaults)
