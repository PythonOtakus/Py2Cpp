"""``new(类型/类名)`` 为非法表达式，任意上下文须在翻译期拒绝。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..translation_error import TranslationError, location_from_node
from ..analysis.ir import scalar_type_static_attr_from_expr

if TYPE_CHECKING:
  from ..translator import Translator

_MAKE_TYPE_ARG_MSG = (
  "new() 不得以类型或类名作为实参（如 new(list[int])、new(Box)）；"
  "类型由注解 ``x: T = new()`` 提供；"
  "请写 ``new()``、``new(n)`` 预分配或 ``new(字段=值…)``"
)

_BUILTIN_AND_CONTAINER_TYPE_NAMES = frozenset(
  {
    "int",
    "str",
    "bool",
    "float",
    "bytes",
    "char",
    "byte",
    "None",
    "Self",
    "object",
    "list",
    "dict",
    "set",
    "tuple",
    "deque",
    "frozenset",
    "frozenlist",
    "frozendict",
    "alloc",
    "allocArray",
    "allocRawArray",
    "ref",
    "view",
    "span",
    "utf8ptr",
    "utf16ptr",
  }
)


def _is_new_call(node: ast.Call) -> bool:
  return isinstance(node.func, ast.Name) and node.func.id == "new"


def _subscript_looks_like_type(tr: "Translator", node: ast.Subscript) -> bool:
  """``list[int]`` / ``T[:]`` 等类型下标；``obj[i]`` 运行时取下标不算。"""
  match node.value:
    case ast.Name(id=name):
      return name in _BUILTIN_AND_CONTAINER_TYPE_NAMES or name in tr.classes
    case ast.Attribute():
      return False
    case other:
      return _expr_looks_like_type(tr, other)


def _expr_looks_like_type(tr: "Translator", node: ast.expr) -> bool:
  """实参 AST 是否为类型/类名形式（非运行时值）。"""
  match node:
    case ast.Subscript() as sub:
      return _subscript_looks_like_type(tr, sub)
    case ast.BinOp(op=ast.BitOr()):
      return _expr_looks_like_type(tr, node.left) or _expr_looks_like_type(
        tr, node.right,
      )
    case ast.Name(id=name):
      if name in _BUILTIN_AND_CONTAINER_TYPE_NAMES:
        return True
      return name in tr.classes
    case ast.Attribute() as attr:
      if scalar_type_static_attr_from_expr(attr) is not None:
        return False
      value = attr.value
      if isinstance(value, ast.Name) and value.id == "typing":
        return True
      if isinstance(value, ast.Name) and value.id in tr.classes:
        info = tr.classes[value.id]
        if info.is_enum:
          return False
        if attr.attr in info.static_properties:
          return False
      return _expr_looks_like_type(tr, value)
    case _:
      return False


def validate_new_call_args(
  tr: "Translator",
  call: ast.Call,
  *,
  module_path: str | None = None,
) -> None:
  """``new`` 的位置/关键字实参不得为类型或类名表达式。"""
  if not _is_new_call(call):
    return
  for arg in call.args:
    if _expr_looks_like_type(tr, arg):
      loc = location_from_node(tr, call, module_path=module_path)
      raise TranslationError(_MAKE_TYPE_ARG_MSG, location=loc)
  for kw in call.keywords:
    if kw.value is not None and _expr_looks_like_type(tr, kw.value):
      loc = location_from_node(tr, call, module_path=module_path)
      raise TranslationError(_MAKE_TYPE_ARG_MSG, location=loc)


def check_new_type_arguments(tr: "Translator") -> None:
  for module_path, tree in tr.module_asts.items():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    for node in ast.walk(tree):
      if isinstance(node, ast.Call):
        validate_new_call_args(tr, node, module_path=module_path)
