"""为未实现 ``__bool__`` 的用户类注入默认 ``__bool__``（``@immutable``）。

- 无 ``__len__``：``return True``（对齐 ``py2cpp.object.object``）
- 有 ``__len__``：``return len(self) > 0``
- 跳过 ``@protocol`` / ``@mixin`` / ``@descriptor`` / ``@refcount`` / ``@boxing`` 等

须在 ``expand_mixins`` **之后**调用，否则宿主尚未混入 mixin 的 ``__bool__`` / ``__len__``，
会误注入 ``return True`` 并挡住 mixin 方法（如 ``set`` / ``frozenset``）。
"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator

_IMMUTABLE_DEC = ast.Name(id="immutable", ctx=ast.Load())


def _has_immutable_decorator(node: ast.FunctionDef) -> bool:
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == "immutable":
      return True
    if (
      isinstance(dec, ast.Call)
      and isinstance(dec.func, ast.Name)
      and dec.func.id == "immutable"
    ):
      return True
  return False


def _skip_class(info) -> bool:
  return (
    info.is_protocol
    or info.is_mixin
    or info.is_descriptor
    or info.is_annotation
    or info.is_refcount
    or info.is_boxing
    or info.is_native
    or info.name == "str"
    or _has_class_type_if_head(info)
  )


def _has_class_type_if_head(info) -> bool:
  """类体首条为 ``if T is …`` 时由 ``class_type_if`` 分派，勿注入默认 ``__bool__``。"""
  if not info.type_params or info.is_protocol or info.is_enum or info.is_union:
    return False
  from .type_if import _looks_like_type_if_head, _strip_docstring

  body = _strip_docstring(info.node.body)
  if not body or not isinstance(body[0], ast.If):
    return False
  return _looks_like_type_if_head(body[0].test, set(info.type_params))


def _bool_body(*, use_len: bool) -> list[ast.stmt]:
  if use_len:
    value = ast.Compare(
      left=ast.Call(
        func=ast.Name(id="len", ctx=ast.Load()),
        args=[ast.Name(id="self", ctx=ast.Load())],
      ),
      ops=[ast.Gt()],
      comparators=[ast.Constant(value=0)],
    )
  else:
    value = ast.Constant(value=True)
  ret = ast.Return(value=value)
  ast.fix_missing_locations(ret)
  return [ret]


def _make_bool_method(*, use_len: bool) -> ast.FunctionDef:
  fn = ast.FunctionDef(
    name="__bool__",
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=_bool_body(use_len=use_len),
    decorator_list=[copy.deepcopy(_IMMUTABLE_DEC)],
    returns=ast.Name(id="bool", ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def expand_default_bool(tr: Translator) -> None:
  for info in tr.classes.values():
    if _skip_class(info) or info.is_union or info.is_enum:
      continue
    if "__bool__" in info.methods:
      continue
    len_m = info.methods.get("__len__")
    use_len = len_m is not None and _has_immutable_decorator(len_m)
    method = _make_bool_method(use_len=use_len)
    info.node.body.append(method)
    info.methods["__bool__"] = method
    ast.fix_missing_locations(info.node)
