"""``inline_range``：译期完全展开循环体（无 ``for`` / ``range`` 残留）。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from .match_case import _clone_body_replace_names, _simplify_const_ifs
from .static_reflect import _const_compare_result, fold_static_reflect_tree

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo

INLINE_RANGE = "inlineRange"

_INLINE_RANGE_ERR = (
  "inline_range 参数须为外层 inline_range 循环变量、@const、字面量"
  "及其任意一元/二元嵌套"
)


def _const_int_expr(value: ast.expr | None) -> int | None:
  if isinstance(value, ast.Constant) and isinstance(value.value, int):
    return value.value
  if (
    isinstance(value, ast.UnaryOp)
    and isinstance(value.op, ast.USub)
    and isinstance(value.operand, ast.Constant)
    and isinstance(value.operand.value, int)
  ):
    return -value.operand.value
  return None


def _host_static_field_int(host: ClassInfo, field: str) -> int | None:
  """宿主 ``@const`` / 类体字面量静态字段 → 整型；未知则 ``None``。"""
  for stmt in host.node.body:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
      continue
    target = stmt.targets[0]
    if isinstance(target, ast.Name) and target.id == field:
      return _const_int_expr(stmt.value)
  static = host.static_class_fields.get(field)
  if static is not None and static.value is not None:
    return _const_int_expr(static.value)
  return None


def _bound_to_ast(bound: int | ast.expr) -> ast.expr:
  if isinstance(bound, ast.expr):
    return copy.deepcopy(bound)
  return ast.Constant(value=bound)


def _binop_int(op: ast.operator, left: int, right: int) -> int | None:
  if isinstance(op, ast.Add):
    return left + right
  if isinstance(op, ast.Sub):
    return left - right
  if isinstance(op, ast.Mult):
    return left * right
  if isinstance(op, ast.FloorDiv):
    if right == 0:
      return None
    return left // right
  return None


def _parse_inline_range_bound(
  expr: ast.expr,
  host: ClassInfo,
  subst: dict[str, int],
) -> int | ast.expr | None:
  """已展开循环变量、``@const``、字面量及其一元/二元嵌套 → 编译期 ``int`` 或保留 ``ast.expr``。"""
  lit = _const_int_expr(expr)
  if lit is not None:
    return lit
  if isinstance(expr, ast.Name):
    if expr.id in subst:
      return subst[expr.id]
    return _host_static_field_int(host, expr.id)
  if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
    if expr.value.id == "Self":
      return _host_static_field_int(host, expr.attr)
  if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub):
    inner = _parse_inline_range_bound(expr.operand, host, subst)
    if inner is None:
      return None
    if isinstance(inner, int):
      return -inner
    return ast.UnaryOp(op=ast.USub(), operand=_bound_to_ast(inner))
  if isinstance(expr, ast.BinOp):
    left = _parse_inline_range_bound(expr.left, host, subst)
    right = _parse_inline_range_bound(expr.right, host, subst)
    if left is None or right is None:
      return None
    if isinstance(left, int) and isinstance(right, int):
      return _binop_int(expr.op, left, right)
    return ast.BinOp(
      left=_bound_to_ast(left),
      op=expr.op,
      right=_bound_to_ast(right),
    )
  return None


def is_inline_range_call(node: ast.expr) -> bool:
  return _is_inline_range_call(node)


def _is_inline_range_call(node: ast.expr) -> bool:
  return (
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == INLINE_RANGE
    and not node.keywords
  )


def _inline_range_bounds(
  call: ast.Call,
  host: ClassInfo,
  subst: dict[str, int],
) -> tuple[int | ast.expr, int | ast.expr, int | ast.expr] | None:
  """``inline_range(stop)`` / ``(start, stop)`` / ``(start, stop, step)`` → 边界三元组。"""
  match call.args:
    case [stop]:
      start_v: int | ast.expr = 0
      stop_v = _parse_inline_range_bound(stop, host, subst)
      step_v: int | ast.expr = 1
    case [start, stop]:
      start_v = _parse_inline_range_bound(start, host, subst)
      stop_v = _parse_inline_range_bound(stop, host, subst)
      step_v = 1
    case [start, stop, step]:
      start_v = _parse_inline_range_bound(start, host, subst)
      stop_v = _parse_inline_range_bound(stop, host, subst)
      step_v = _parse_inline_range_bound(step, host, subst)
    case _:
      return None
  if start_v is None or stop_v is None or step_v is None:
    return None
  return start_v, stop_v, step_v


def _compile_time_indices(
  start: int | ast.expr,
  stop: int | ast.expr,
  step: int | ast.expr,
  *,
  lineno: int = 0,
) -> list[int]:
  if not all(isinstance(x, int) for x in (start, stop, step)):
    raise NotImplementedError(f"{lineno}: {_INLINE_RANGE_ERR}")
  assert isinstance(start, int)
  assert isinstance(stop, int)
  assert isinstance(step, int)
  if step == 0:
    raise NotImplementedError(f"{lineno}: inline_range step 不可为 0")
  return list(range(start, stop, step))


_INLINE_RANGE_LOOP_CTRL_ERR = "inline_range 循环体不支持 break/continue"


class _BreakContinueFinder(ast.NodeVisitor):
  found: bool = False

  def visit_Break(self, node: ast.Break) -> None:
    self.found = True

  def visit_Continue(self, node: ast.Continue) -> None:
    self.found = True


def _subst_renames(subst: dict[str, int]) -> dict[str, ast.expr]:
  return {name: ast.Constant(value=val) for name, val in subst.items()}


def _fold_if_test(
  test: ast.expr,
  host: ClassInfo,
  subst: dict[str, int],
) -> ast.expr:
  """``inline_range`` 展开后，用 ``subst`` 折叠 ``if`` 条件（如 ``r != k``）。"""
  if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
    left = _parse_inline_range_bound(test.left, host, subst)
    right = _parse_inline_range_bound(test.comparators[0], host, subst)
    if isinstance(left, int) and isinstance(right, int):
      folded = _const_compare_result(
        ast.Constant(value=left),
        test.ops[0],
        ast.Constant(value=right),
      )
      if folded is not None:
        return ast.Constant(value=folded)
  if subst:
    renames = _subst_renames(subst)

    class _Renamer(ast.NodeTransformer):
      def visit_Name(self, node: ast.Name) -> ast.expr:
        if isinstance(node.ctx, ast.Load) and node.id in renames:
          return copy.deepcopy(renames[node.id])
        return node

    folded = fold_static_reflect_tree(_Renamer().visit(copy.deepcopy(test)))
    if isinstance(folded, ast.Constant) and isinstance(folded.value, bool):
      return folded
  return test


def _reject_break_continue(body: list[ast.stmt], *, lineno: int) -> None:
  finder = _BreakContinueFinder()
  for stmt in body:
    finder.visit(stmt)
  if finder.found:
    raise NotImplementedError(f"{lineno}: {_INLINE_RANGE_LOOP_CTRL_ERR}")


def _unroll_inline_range_for(
  node: ast.For,
  host: ClassInfo,
  subst: dict[str, int],
) -> list[ast.stmt]:
  if node.orelse:
    raise NotImplementedError("inline_range 不支持 for-else")
  if not isinstance(node.target, ast.Name):
    lineno = getattr(node, "lineno", 0) or 0
    raise NotImplementedError(f"{lineno}: inline_range for-loop 目标须为简单变量名")
  lineno = getattr(node, "lineno", 0) or 0
  _reject_break_continue(node.body, lineno=lineno)
  bounds = _inline_range_bounds(node.iter, host, subst)
  if bounds is None:
    lineno = getattr(node, "lineno", 0) or 0
    raise NotImplementedError(f"{lineno}: {_INLINE_RANGE_ERR}")
  start, stop, step = bounds
  indices = _compile_time_indices(start, stop, step, lineno=lineno)
  var = node.target.id
  out: list[ast.stmt] = []
  for idx in indices:
    new_subst = {**subst, var: idx}
    cloned = _clone_body_replace_names(node.body, _subst_renames(new_subst))
    out.extend(_flatten_body(cloned, host, new_subst))
  return out


def _flatten_body(
  body: list[ast.stmt],
  host: ClassInfo,
  subst: dict[str, int],
) -> list[ast.stmt]:
  out: list[ast.stmt] = []
  for stmt in body:
    out.extend(_flatten_stmt(stmt, host, subst))
  return out


def _flatten_stmt(
  stmt: ast.stmt,
  host: ClassInfo,
  subst: dict[str, int],
) -> list[ast.stmt]:
  if isinstance(stmt, ast.For) and _is_inline_range_call(stmt.iter):
    return _unroll_inline_range_for(stmt, host, subst)
  if isinstance(stmt, ast.For):
    out = copy.deepcopy(stmt)
    out.body = _flatten_body(stmt.body, host, subst)
    if stmt.orelse:
      out.orelse = _flatten_body(stmt.orelse, host, subst)
    ast.fix_missing_locations(out)
    return [out]
  if isinstance(stmt, ast.If):
    out = copy.deepcopy(stmt)
    out.body = _flatten_body(stmt.body, host, subst)
    out.orelse = _flatten_body(stmt.orelse, host, subst)
    out.test = _fold_if_test(out.test, host, subst)
    ast.fix_missing_locations(out)
    return _simplify_const_ifs([out])
  if isinstance(stmt, ast.While):
    out = copy.deepcopy(stmt)
    out.body = _flatten_body(stmt.body, host, subst)
    if stmt.orelse:
      out.orelse = _flatten_body(stmt.orelse, host, subst)
    ast.fix_missing_locations(out)
    return [out]
  if isinstance(stmt, ast.With):
    out = copy.deepcopy(stmt)
    out.body = _flatten_body(stmt.body, host, subst)
    ast.fix_missing_locations(out)
    return [out]
  if isinstance(stmt, ast.Try):
    out = copy.deepcopy(stmt)
    out.body = _flatten_body(stmt.body, host, subst)
    for handler in out.handlers:
      handler.body = _flatten_body(handler.body, host, subst)
    if out.finalbody:
      out.finalbody = _flatten_body(out.finalbody, host, subst)
    ast.fix_missing_locations(out)
    return [out]
  return [stmt]


def expand_inline_range(method: ast.FunctionDef, host: ClassInfo) -> ast.FunctionDef:
  """``for i in inline_range(…)`` → 按编译期边界展开循环体（无 ``for`` 残留）。"""
  out = copy.deepcopy(method)
  out.body = _simplify_const_ifs(_flatten_body(method.body, host, {}))
  ast.fix_missing_locations(out)
  return out
