"""按 ``__int__`` < ``__float__`` < ``__complex__`` 为数字类型注入默认转换（向下兼容）。

- 三者均未实现：不注入
- 缺 ``__float__`` 且有 ``__int__``：``__float__`` 经 ``int(self)`` 转 ``float``
- 缺 ``__complex__`` 且有 ``__float__``：``__complex__`` 经 ``float(self)`` 后 ``new(r, 0)``
- 缺 ``__complex__`` 且无 ``__float__`` 但有 ``__int__``：``__complex__`` 经 ``int(self)`` 后 ``new(n, 0)``

须在 ``expand_mixins`` 之后、``SemanticAnalyzer`` 之前调用（与 ``expand_default_bool`` 同级）。
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
    or info.is_native
    or info.is_union
    or info.is_enum
    or info.name == "str"
  )


def _self_expr() -> ast.Name:
  return ast.Name(id="self", ctx=ast.Load())


def _builtin_call(name: str, *args: ast.expr) -> ast.Call:
  node = ast.Call(
    func=ast.Name(id=name, ctx=ast.Load()),
    args=list(args),
  )
  ast.fix_missing_locations(node)
  return node


def _float_from_int_body() -> list[ast.stmt]:
  return [
    ast.Return(
      value=_builtin_call("float", _builtin_call("int", _self_expr())),
    ),
  ]


def _complex_from_float_body() -> list[ast.stmt]:
  return [
    ast.Return(
      value=ast.Call(
        func=ast.Name(id="new", ctx=ast.Load()),
        args=[
          _builtin_call("float", _self_expr()),
          ast.Constant(value=0),
        ],
      ),
    ),
  ]


def _complex_from_int_body() -> list[ast.stmt]:
  return [
    ast.Return(
      value=ast.Call(
        func=ast.Name(id="new", ctx=ast.Load()),
        args=[
          _builtin_call("int", _self_expr()),
          ast.Constant(value=0),
        ],
      ),
    ),
  ]


def _assign(name: str, ann: str, value: ast.expr) -> ast.AnnAssign:
  node = ast.AnnAssign(
    target=ast.Name(id=name, ctx=ast.Store()),
    annotation=ast.Name(id=ann, ctx=ast.Load()),
    value=value,
    simple=1,
  )
  ast.fix_missing_locations(node)
  return node


def _return_name(name: str) -> ast.Return:
  node = ast.Return(value=ast.Name(id=name, ctx=ast.Load()))
  ast.fix_missing_locations(node)
  return node


def _make_method(name: str, ret_ann: str, body: list[ast.stmt]) -> ast.FunctionDef:
  fn = ast.FunctionDef(
    name=name,
    args=ast.arguments(
      posonlyargs=[],
      args=[ast.arg(arg="self")],
      kwonlyargs=[],
      kw_defaults=[],
      defaults=[],
      kwarg=None,
    ),
    body=body,
    decorator_list=[copy.deepcopy(_IMMUTABLE_DEC)],
    returns=ast.Name(id=ret_ann, ctx=ast.Load()),
    type_params=[],
  )
  ast.fix_missing_locations(fn)
  return fn


def _inject_method(info, method: ast.FunctionDef) -> None:
  info.node.body.append(method)
  info.methods[method.name] = method
  ast.fix_missing_locations(info.node)


def expand_default_numeric_convert(tr: Translator) -> None:
  for info in tr.classes.values():
    if _skip_class(info):
      continue
    has_int = "__int__" in info.methods
    has_float = "__float__" in info.methods
    has_complex = "__complex__" in info.methods
    if not has_int and not has_float and not has_complex:
      continue
    if not has_float and has_int:
      _inject_method(info, _make_method("__float__", "float", _float_from_int_body()))
      has_float = True
    if not has_complex:
      if has_float:
        _inject_method(
          info,
          _make_method("__complex__", "complex", _complex_from_float_body()),
        )
      elif has_int:
        _inject_method(
          info,
          _make_method("__complex__", "complex", _complex_from_int_body()),
        )
