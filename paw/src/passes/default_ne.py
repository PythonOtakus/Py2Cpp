"""为已实现 ``__eq__``、未写 ``__ne__`` 的类注入默认 ``__ne__``（``@immutable``）。

体为 ``return not (self == other)``（经 ``__eq__`` 取反，避免 ``self != other`` 递归）。

须在 ``expand_mixins`` **之后**、``SemanticAnalyzer`` **之前**调用。
"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

_IMMUTABLE_DEC = ast.Name(id="immutable", ctx=ast.Load())


def _skip_class(info) -> bool:
  return (
    info.is_protocol
    or info.is_mixin
    or info.is_descriptor
    or info.is_annotation
    or info.is_refcount
    or info.is_boxing
  )


def _eq_other_annotation(eq: ast.FunctionDef) -> ast.expr | None:
  args = eq.args.args
  if len(args) < 2:
    return None
  return copy.deepcopy(args[1].annotation)


def _decorators_like_eq(eq: ast.FunctionDef) -> list[ast.expr]:
  for dec in eq.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "immutable":
      return [copy.deepcopy(dec)]
    if (
      isinstance(dec, ast.Call)
      and isinstance(dec.func, ast.Name)
      and dec.func.id == "immutable"
    ):
      return [copy.deepcopy(dec)]
  return [copy.deepcopy(_IMMUTABLE_DEC)]


def _ne_body() -> list[ast.stmt]:
  value = ast.UnaryOp(
    op=ast.Not(),
    operand=ast.Compare(
      left=ast.Name(id="self", ctx=ast.Load()),
      ops=[ast.Eq()],
      comparators=[ast.Name(id="other", ctx=ast.Load())],
    ),
  )
  ret = ast.Return(value=value)
  ast.fix_missing_locations(ret)
  return [ret]


def _make_ne_method(eq: ast.FunctionDef) -> ast.FunctionDef:
  other_ann = _eq_other_annotation(eq)
  other_arg = ast.arg(arg="other", annotation=other_ann) if other_ann else ast.arg(arg="other")
  fn = ast.FunctionDef(
    name="__ne__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self"), other_arg],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=_ne_body(),
    decorator_list=_decorators_like_eq(eq),
    returns=ast.Name(id="bool", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def expand_default_ne(tr: Translator) -> None:
  for info in tr.classes.values():
    if _skip_class(info) or info.is_union or info.is_enum:
      continue
    if "__ne__" in info.methods:
      continue
    eq = info.methods.get("__eq__")
    if eq is None:
      continue
    if info.method_overloads.get("__eq__"):
      continue
    method = _make_ne_method(eq)
    info.node.body.append(method)
    info.methods["__ne__"] = method
    ast.fix_missing_locations(info.node)
