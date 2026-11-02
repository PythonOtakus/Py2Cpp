"""``async def`` / ``await`` / ``async with``：脱糖为 ``yield from .__await__()``（对齐 Python 3.13）。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.patterns import temp_name
from ..translation_error import TranslationError, location_from_node

if TYPE_CHECKING:
  from ..translator import Translator

_YIELD_FROM_IN_ASYNC_MSG = "'yield from' inside async function"


def _await_as_yield_from(value: ast.expr) -> ast.YieldFrom:
  return ast.YieldFrom(
    value=ast.Call(
      func=ast.Attribute(
        value=copy.deepcopy(value),
        attr="__await__",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    ),
  )


def _fresh_async_with_ids() -> tuple[str, str]:
  return temp_name("awm"), temp_name("awe")


def _aenter_yield_from(mgr: ast.expr) -> ast.YieldFrom:
  return _await_as_yield_from(
    ast.Call(
      func=ast.Attribute(
        value=copy.deepcopy(mgr),
        attr="__aenter__",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    ),
  )


def _aexit_yield_from(mgr: ast.expr) -> ast.YieldFrom:
  return _await_as_yield_from(
    ast.Call(
      func=ast.Attribute(
        value=copy.deepcopy(mgr),
        attr="__aexit__",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    ),
  )


def _desugar_async_with_body(
  body: list[ast.stmt],
  mgr_ids: list[str],
) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in body:
    if isinstance(stmt, ast.Return):
      for mid in reversed(mgr_ids):
        out.append(ast.Expr(value=_aexit_yield_from(ast.Name(id=mid, ctx=ast.Load()))))
      out.extend(_desugar_stmt(stmt))
    elif isinstance(stmt, ast.If):
      out.append(
        ast.If(
          test=stmt.test,
          body=_desugar_async_with_body(stmt.body, mgr_ids),
          orelse=_desugar_async_with_body(stmt.orelse, mgr_ids),
        )
      )
    elif isinstance(stmt, ast.While):
      out.append(
        ast.While(
          test=stmt.test,
          body=_desugar_async_with_body(stmt.body, mgr_ids),
          orelse=_desugar_async_with_body(stmt.orelse, mgr_ids),
        )
      )
    elif isinstance(stmt, ast.AsyncFor):
      out.append(
        ast.AsyncFor(
          target=stmt.target,
          iter=stmt.iter,
          body=_desugar_async_with_body(stmt.body, mgr_ids),
          orelse=_desugar_async_with_body(stmt.orelse, mgr_ids),
        )
      )
    else:
      out.extend(_desugar_stmt(stmt))
  return out


def _desugar_async_with_items(
  items: list[ast.withitem],
  body: list[ast.stmt],
  mgr_ids: list[str] | None = None,
) -> list[ast.stmt]:
  """``async with`` → ``__aenter__``/``__aexit__`` 的 ``yield from ….__await__()``（无异常路径）。"""
  active = list(mgr_ids or [])
  if not items:
    mid = _desugar_async_with_body(body, active)
    if not _stmt_always_returns(body):
      mid.extend(
        ast.Expr(value=_aexit_yield_from(ast.Name(id=mgr, ctx=ast.Load())))
        for mgr in reversed(active)
      )
    return mid
  item = items[0]
  mgr_id, enter_id = _fresh_async_with_ids()
  mgr_ref = ast.Name(id=mgr_id, ctx=ast.Load())
  out: list[ast.stmt] = [
    ast.Assign(
      targets=[ast.Name(id=mgr_id, ctx=ast.Store())],
      value=item.context_expr,
    ),
    ast.Assign(
      targets=[ast.Name(id=enter_id, ctx=ast.Store())],
      value=_aenter_yield_from(mgr_ref),
    ),
  ]
  match item.optional_vars:
    case None:
      pass
    case ast.Name(id=name):
      out.append(
        ast.Assign(
          targets=[ast.Name(id=name, ctx=ast.Store())],
          value=ast.Name(id=enter_id, ctx=ast.Load()),
        ),
      )
    case _:
      raise NotImplementedError("async with ... as 仅支持简单变量名")
  active.append(mgr_id)
  return out + _desugar_async_with_items(items[1:], body, active)


def _stmt_always_returns(stmts: list[ast.stmt]) -> bool:
  if not stmts:
    return False
  last = stmts[-1]
  if isinstance(last, ast.Return):
    return True
  if isinstance(last, ast.If) and last.orelse:
    return _stmt_always_returns(last.body) and _stmt_always_returns(last.orelse)
  return False


class _AwaitExpr(ast.NodeTransformer):
  def visit_Await(self, node: ast.Await) -> ast.expr:
    return _await_as_yield_from(node.value)


def _desugar_stmt(stmt: ast.stmt) -> list[ast.stmt]:
  stmt = copy.deepcopy(stmt)
  match stmt:
    case ast.Return(value=ast.Await(value=v)):
      tmp = "_await_ret"
      return [
        ast.Assign(
          targets=[ast.Name(id=tmp, ctx=ast.Store())],
          value=_await_as_yield_from(v),
        ),
        ast.Return(value=ast.Name(id=tmp, ctx=ast.Load())),
      ]
    case ast.Expr(value=ast.Await(value=v)):
      return [ast.Expr(value=_await_as_yield_from(v))]
    case ast.If(test=test, body=body, orelse=orelse):
      return [
        ast.If(
          test=test,
          body=[s for st in body for s in _desugar_stmt(st)],
          orelse=[s for st in orelse for s in _desugar_stmt(st)],
        )
      ]
    case ast.While(test=test, body=body, orelse=orelse):
      return [
        ast.While(
          test=test,
          body=[s for st in body for s in _desugar_stmt(st)],
          orelse=[s for st in orelse for s in _desugar_stmt(st)],
        )
      ]
    case ast.AsyncWith(items=items, body=body):
      return _desugar_async_with_items(items, body)
    case ast.With(items=items, body=body) if getattr(stmt, "is_async", False):
      return _desugar_async_with_items(items, body)
    case ast.AsyncFor(target=target, iter=iter_, body=body, orelse=orelse):
      return [
        ast.AsyncFor(
          target=target,
          iter=iter_,
          body=[s for st in body for s in _desugar_stmt(st)],
          orelse=[s for st in orelse for s in _desugar_stmt(st)],
        )
      ]
    case ast.For(target=target, iter=iter_, body=body, orelse=orelse):
      new_for = ast.For(
        target=target,
        iter=iter_,
        body=[s for st in body for s in _desugar_stmt(st)],
        orelse=[s for st in orelse for s in _desugar_stmt(st)],
      )
      if getattr(stmt, "is_async", False):
        new_for.is_async = True
      return [new_for]
    case _:
      out = _AwaitExpr().visit(stmt)
      if isinstance(out, list):
        return out
      return [out]


def _compound_stmt_bodies(stmt: ast.stmt) -> list[list[ast.stmt]]:
  """复合语句内层表（不进入嵌套 ``def`` / ``class``）。"""
  out: list[list[ast.stmt]] = []
  if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
    out.append(stmt.body)
    if stmt.orelse:
      out.append(stmt.orelse)
  elif isinstance(stmt, (ast.With, ast.AsyncWith)):
    out.append(stmt.body)
  elif isinstance(stmt, (ast.Try, ast.TryStar)):
    for handler in stmt.handlers:
      out.append(handler.body)
    if stmt.orelse:
      out.append(stmt.orelse)
    if stmt.finalbody:
      out.append(stmt.finalbody)
  elif isinstance(stmt, ast.Match):
    for case in stmt.cases:
      out.append(case.body)
  return out


def _yield_from_in_async_scope(stmts: list[ast.stmt]) -> ast.YieldFrom | None:
  """``async def`` 直接作用域内的 ``yield from``（嵌套 ``def``/``class`` 内不计）。"""
  for stmt in stmts:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      continue
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.YieldFrom):
      return stmt.value
    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.YieldFrom):
      return stmt.value
    if (
      isinstance(stmt, ast.AnnAssign)
      and stmt.value is not None
      and isinstance(stmt.value, ast.YieldFrom)
    ):
      return stmt.value
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.YieldFrom):
      return stmt.value
    for inner in _compound_stmt_bodies(stmt):
      hit = _yield_from_in_async_scope(inner)
      if hit is not None:
        return hit
  return None


def _iter_async_defs(tree: ast.AST) -> list[ast.AsyncFunctionDef]:
  return [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]


def check_yield_from_in_async_def(tr: Translator) -> None:
  """Python 3.13：``async def`` 体内禁止用户手写 ``yield from``（``await`` 脱糖除外）。"""
  for module_path, tree in tr.module_asts.items():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    for async_fn in _iter_async_defs(tree):
      hit = _yield_from_in_async_scope(async_fn.body)
      if hit is not None:
        loc = location_from_node(tr, hit, module_path=module_path)
        raise TranslationError(_YIELD_FROM_IN_ASYNC_MSG, location=loc)


def desugar_await_body(body: list[ast.stmt]) -> list[ast.stmt]:
  global _async_with_serial
  _async_with_serial = 0
  out: list[ast.stmt] = []
  for stmt in body:
    out.extend(_desugar_stmt(stmt))
  return out


def async_def_to_function(node: ast.AsyncFunctionDef) -> ast.FunctionDef:
  """``async def`` → 普通 ``def``（体已脱糖 ``await``）。"""
  body = desugar_await_body(node.body)
  return ast.FunctionDef(
    name=node.name,
    args=node.args,
    body=body,
    decorator_list=node.decorator_list,
    returns=node.returns,
    type_params=getattr(node, "type_params", None) or [],
  )
