"""含 ``__move__`` 的类自动注入 ``__moved__`` 字段，并剥除手写初始化/赋值。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, cpp_ident, cpp_param
from ..analysis.type_emit import clear_field_ann_ast, field_ann_ast, write_field_ann_ast

if TYPE_CHECKING:
  from ..translator import Translator

MOVE_STATE_FIELD = "__moved__"
_LEGACY_MOVE_FIELD = "moved"


def _class_has_move(info: ClassInfo) -> bool:
  if info.is_uncopyable:
    return False
  return info.has_move or "__move__" in info.methods


def _is_self_bool_false_init(stmt: ast.stmt, attr: str) -> bool:
  if not isinstance(stmt, ast.AnnAssign):
    return False
  if not isinstance(stmt.target, ast.Attribute):
    return False
  if not (
    isinstance(stmt.target.value, ast.Name)
    and stmt.target.value.id == "self"
    and stmt.target.attr == attr
  ):
    return False
  val = stmt.value
  return isinstance(val, ast.Constant) and val.value is False


def _is_move_state_bool_assign(stmt: ast.stmt) -> bool:
  """``x.__moved__ = True/False``（``x`` 为任意形参名或 ``self``）。"""
  if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
    return False
  t = stmt.targets[0]
  if not isinstance(t, ast.Attribute) or not isinstance(t.value, ast.Name):
    return False
  if t.attr not in (MOVE_STATE_FIELD, _LEGACY_MOVE_FIELD):
    return False
  val = stmt.value
  return isinstance(val, ast.Constant) and isinstance(val.value, bool)


def _strip_move_state_assigns(body: list[ast.stmt]) -> list[ast.stmt]:
  return [stmt for stmt in body if not _is_move_state_bool_assign(stmt)]


def _strip_handwritten_move_init(info: ClassInfo) -> None:
  for init in info.inits:
    init.body = [
      stmt
      for stmt in init.body
      if not _is_self_bool_false_init(stmt, _LEGACY_MOVE_FIELD)
      and not _is_self_bool_false_init(stmt, MOVE_STATE_FIELD)
    ]


def _strip_handwritten_move_assigns(info: ClassInfo) -> None:
  for init in info.inits:
    init.body = _strip_move_state_assigns(init.body)
  for method in info.methods.values():
    method.body = _strip_move_state_assigns(method.body)


def move_state_other_param(method: ast.FunctionDef) -> str | None:
  """``__move__`` 的第一个非 ``self`` 形参名。"""
  for arg in method.args.args:
    if arg.arg != "self":
      return arg.arg
  return None


def emit_move_state_prologue_lines(info: ClassInfo, method: ast.FunctionDef) -> list[str]:
  """``__init__`` / ``__copy__`` / ``__move__`` 开头：``this->__moved__ = false``。"""
  if MOVE_STATE_FIELD not in info.fields:
    return []
  if method.name not in ("__init__", "__copy__", "__move__"):
    return []
  return [f"this->{MOVE_STATE_FIELD} = false;"]


def emit_move_state_epilogue_lines(info: ClassInfo, method: ast.FunctionDef) -> list[str]:
  """``__move__`` 结尾：移动源 ``other->__moved__ = true``。"""
  if MOVE_STATE_FIELD not in info.fields or method.name != "__move__":
    return []
  other = move_state_other_param(method)
  if other is None:
    return []
  return [f"{cpp_param(other)}.{MOVE_STATE_FIELD} = true;"]


def ensure_move_state_field(info: ClassInfo) -> None:
  """登记 ``PyBool __moved__``；将遗留字段名 ``moved`` 统一为 ``__moved__``。"""
  if not _class_has_move(info):
    return
  if _LEGACY_MOVE_FIELD in info.fields:
    idx = info.fields.index(_LEGACY_MOVE_FIELD)
    info.fields[idx] = MOVE_STATE_FIELD
    ann = field_ann_ast(info, _LEGACY_MOVE_FIELD)
    clear_field_ann_ast(info, _LEGACY_MOVE_FIELD)
    if ann is not None:
      write_field_ann_ast(info, MOVE_STATE_FIELD, ann)
    from ..analysis.type_emit import write_field_storage

    node = info.field_type_nodes.pop(_LEGACY_MOVE_FIELD, None)
    if node is not None:
      write_field_storage(info, MOVE_STATE_FIELD, node)
    else:
      write_field_storage(info, _LEGACY_MOVE_FIELD, None)
      info.field_types.pop(_LEGACY_MOVE_FIELD, None)
    info.field_defaults.pop(_LEGACY_MOVE_FIELD, None)
  if MOVE_STATE_FIELD not in info.fields:
    info.fields.insert(0, MOVE_STATE_FIELD)
  from ..analysis.type_emit import field_storage_cpp, write_field_storage
  from ..analysis.type_node import TypeNode

  if not field_storage_cpp(info, MOVE_STATE_FIELD):
    write_field_storage(info, MOVE_STATE_FIELD, TypeNode.scalar(cpp_ident("bool")))


def expand_move_state(tr: Translator) -> None:
  for info in tr.classes.values():
    if not _class_has_move(info):
      continue
    _strip_handwritten_move_init(info)
    _strip_handwritten_move_assigns(info)
    ensure_move_state_field(info)
