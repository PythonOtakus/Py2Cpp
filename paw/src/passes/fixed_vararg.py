"""``*axis: T[:Self._dim-1]`` — ``@mixin`` 注入时展开为 ``__arg_axis0``、``__arg_axis1`` …"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import stack_slice_dim_from_ast

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo


def _fixed_vararg_pack_length(
  annotation: ast.expr,
  host: ClassInfo,
) -> tuple[ast.expr, int] | None:
  """``T[:N]`` / ``T[:Self._dim-1]`` 定长栈切片注解 → ``(元素类型 AST, 长度)``。"""
  if not isinstance(annotation, ast.Subscript):
    return None
  if not isinstance(annotation.slice, ast.Slice):
    return None
  dim = stack_slice_dim_from_ast(annotation.slice, host)
  if dim is None:
    return None
  offset, length = dim
  if offset != 0 or length <= 0:
    return None
  return copy.deepcopy(annotation.value), length


def method_has_fixed_vararg(method: ast.FunctionDef) -> bool:
  va = method.args.vararg
  return va is not None and va.annotation is not None


def expand_fixed_vararg(
  method: ast.FunctionDef,
  host: ClassInfo,
) -> ast.FunctionDef | None:
  """``*pack: T[:N]`` → ``__arg_{pack}0`` … ``__arg_{pack}{N-1}``；``pack[i]`` → ``[…][i]``。"""
  va = method.args.vararg
  if va is None or va.annotation is None:
    return None
  parsed = _fixed_vararg_pack_length(va.annotation, host)
  if parsed is None:
    return None
  elem_ann, count = parsed
  pack_name = va.arg
  param_names = [f"__arg_{pack_name}{i}" for i in range(count)]

  out = copy.deepcopy(method)
  out.args.vararg = None
  expanded_args = [
    ast.arg(arg=pname, annotation=copy.deepcopy(elem_ann))
    for pname in param_names
  ]
  out.args.args = expanded_args + out.args.args
  if out.args.kwonlyargs:
    out.args.args = out.args.args + out.args.kwonlyargs
    out.args.defaults = list(out.args.defaults) + list(out.args.kw_defaults)
    out.args.kwonlyargs = []
    out.args.kw_defaults = []

  rewriter = _FixedVarargSubscriptRewriter(pack_name, param_names)
  out.body = [rewriter.visit(stmt) for stmt in out.body]
  ast.fix_missing_locations(out)
  return out


class _FixedVarargSubscriptRewriter(ast.NodeTransformer):
  def __init__(self, pack_name: str, param_names: list[str]) -> None:
    self.pack_name = pack_name
    self.param_names = param_names

  def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
    self.generic_visit(node)
    if isinstance(node.value, ast.Name) and node.value.id == self.pack_name:
      return ast.Subscript(
        value=ast.List(
          elts=[ast.Name(id=n, ctx=ast.Load()) for n in self.param_names],
          ctx=ast.Load(),
        ),
        slice=node.slice,
        ctx=node.ctx,
      )
    return node
