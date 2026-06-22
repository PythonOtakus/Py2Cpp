"""分析 ``Iterable`` 形参 + ``for param in …`` 循环体，供 genexp 调用点内联。"""
from __future__ import annotations

import ast
from dataclasses import dataclass

from ..analysis.ir import protocol_param_template_from_annotation
from ..translation_error import TranslationError, location_from_node
from ..translator import Translator


@dataclass(frozen=True)
class GenexpInlinePlan:
  """可内联的 ``for iterable_param`` 单遍循环 + prelude/return。"""

  iterable_param: str
  loop_var: str
  prelude: tuple[ast.stmt, ...]
  loop_body: tuple[ast.stmt, ...]
  return_stmt: ast.Return


def literal_iterable_param_names(func: ast.FunctionDef) -> dict[str, str | None]:
  """形参注解字面 ``Iterable`` / ``Iterable[T]`` → ``{名: 元素形参名或 None}``。"""
  out: dict[str, str | None] = {}
  for arg in func.args.args:
    if arg.arg in ("self", "cls"):
      continue
    if arg.annotation is None:
      continue
    parsed = protocol_param_template_from_annotation(arg.annotation)
    if parsed is not None and parsed[0] == "Iterable":
      out[arg.arg] = parsed[1]
  return out


def analyze_genexp_inline_body(
  tr: Translator,
  func: ast.FunctionDef,
  iterable_param: str,
  *,
  site: ast.AST,
) -> GenexpInlinePlan:
  body = _strip_docstring(func.body)
  for_idx: int | None = None
  for_loop: ast.For | None = None
  for i, stmt in enumerate(body):
    if not isinstance(stmt, ast.For):
      continue
    if for_idx is not None:
      raise TranslationError(
        f"genexp 内联要求函数体仅含单个 ``for {iterable_param}`` 循环",
        location=location_from_node(tr, stmt),
      )
    if not isinstance(stmt.iter, ast.Name) or stmt.iter.id != iterable_param:
      raise TranslationError(
        f"genexp 内联要求 ``for … in {iterable_param}``",
        location=location_from_node(tr, stmt),
      )
    if not isinstance(stmt.target, ast.Name):
      raise TranslationError(
        "genexp 内联的 for 目标须为简单变量名",
        location=location_from_node(tr, stmt.target),
      )
    if stmt.orelse:
      raise TranslationError("genexp 内联不支持 for-else", location=location_from_node(tr, stmt))
    for_idx = i
    for_loop = stmt

  if for_loop is None or for_idx is None:
    raise TranslationError(
      f"genexp 内联要求函数体含 ``for … in {iterable_param}``",
      location=location_from_node(tr, site),
    )

  tail = body[for_idx + 1 :]
  if len(tail) != 1 or not isinstance(tail[0], ast.Return):
    raise TranslationError(
      "genexp 内联要求 for 循环后仅一条 return",
      location=location_from_node(tr, site),
    )

  prelude = tuple(body[:for_idx])
  loop_var = for_loop.target.id
  _check_param_not_used_outside_for(
    tr, prelude + tuple(for_loop.body) + tuple(tail), iterable_param, for_loop,
  )
  return GenexpInlinePlan(
    iterable_param=iterable_param,
    loop_var=loop_var,
    prelude=prelude,
    loop_body=tuple(for_loop.body),
    return_stmt=tail[0],
  )


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
  if body and isinstance(body[0], ast.Expr):
    val = body[0].value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
      return body[1:]
  return body


def _check_param_not_used_outside_for(
  tr: Translator,
  stmts: tuple[ast.stmt, ...],
  param: str,
  for_loop: ast.For,
) -> None:
  for stmt in stmts:
    for node in ast.walk(stmt):
      if isinstance(node, ast.Name) and node.id == param:
        if id(node) == id(for_loop.iter) or (
          isinstance(node.ctx, ast.Load) and _name_in_expr(node, for_loop.iter)
        ):
          continue
        raise TranslationError(
          f"genexp 内联要求形参 {param!r} 仅出现在对应 for 的迭代对象上",
          location=location_from_node(tr, node),
        )


def _name_in_expr(name: ast.Name, expr: ast.expr) -> bool:
  for node in ast.walk(expr):
    if isinstance(node, ast.Name) and node.id == name.id:
      return True
  return False
