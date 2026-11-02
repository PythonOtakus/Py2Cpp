"""``for i in prange(...)`` → OpenMP ``parallel for``（无 OpenMP 时降级为 ``range`` 原生 ``for``）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from ..constant.parallel import CONCUR_PARALLEL_MODULE, PRANGE_SCHEDULES
from ..analysis.ir import cpp_ident
from .loops_emit import emit_native_range_loop, emit_native_range_loop_from_call

if TYPE_CHECKING:
  from ..translator import Translator


@dataclass(frozen=True)
class PrangeSpec:
  start_s: str
  stop_s: str
  step_s: str
  schedule: str
  num_threads_s: str | None
  chunksize_s: str | None
  th_const: int | None
  th_s: str
  reductions: tuple[tuple[str, str], ...]


_REDUCTION_OP_MAP: dict[type, str] = {
  ast.Add: "+",
  ast.Sub: "-",
  ast.Mult: "*",
  ast.BitAnd: "&",
  ast.BitOr: "|",
  ast.BitXor: "^",
}


def is_prange_call(tr: Translator, node: ast.expr) -> bool:
  bindings = tr._effective_import_bindings()
  return is_prange_call_with_bindings(node, bindings)


def is_prange_call_with_bindings(
  node: ast.expr,
  bindings: dict,
) -> bool:
  if not isinstance(node, ast.Call):
    return False
  if not isinstance(node.func, ast.Name) or node.func.id != "prange":
    return False
  binding = bindings.get("prange")
  if binding is None:
    return False
  return (
    binding.module_path == CONCUR_PARALLEL_MODULE
    and binding.symbol == "prange"
    and binding.kind == "function"
  )


def _const_int(node: ast.expr) -> int | None:
  if isinstance(node, ast.Constant) and isinstance(node.value, int):
    return node.value
  return None


def _const_str(node: ast.expr) -> str | None:
  if isinstance(node, ast.Constant) and isinstance(node.value, str):
    return node.value
  return None


def _parse_positional(tr: Translator, call: ast.Call) -> tuple[str, str, str]:
  match call.args:
    case [stop]:
      return "0", tr.visit(stop), "1"
    case [start, stop]:
      return tr.visit(start), tr.visit(stop), "1"
    case [start, stop, step]:
      return tr.visit(start), tr.visit(stop), tr.visit(step)
    case _:
      raise NotImplementedError("prange 仅支持 1～3 个位置参数")


def _const_range_trip_count(call: ast.Call) -> int | None:
  match call.args:
    case [stop]:
      start_v: int = 0
      stop_v: int | None = _const_int(stop)
      step_v: int = 1
    case [start, stop]:
      start_v = _const_int(start)
      stop_v = _const_int(stop)
      step_v = 1
    case [start, stop, step]:
      start_v = _const_int(start)
      stop_v = _const_int(stop)
      step_v = _const_int(step)
    case _:
      return None
  if start_v is None or stop_v is None or step_v is None or step_v == 0:
    return None
  if step_v > 0:
    n: int = stop_v - start_v
    if n <= 0:
      return 0
    return (n + step_v - 1) // step_v
  n = start_v - stop_v
  if n <= 0:
    return 0
  return (n - step_v - 1) // (-step_v)


def _parse_keywords(
  tr: Translator, call: ast.Call,
) -> tuple[str, str | None, str | None, int | None, str]:
  schedule = "static"
  num_threads_s: str | None = None
  chunksize_s: str | None = None
  th_const: int | None = 0
  th_s: str = "0"
  for kw in call.keywords:
    if kw.arg is None:
      raise SyntaxError("prange 不支持 **kwargs")
    match kw.arg:
      case "schedule":
        s = _const_str(kw.value)
        if s is None or s not in PRANGE_SCHEDULES:
          raise SyntaxError(
            f"prange schedule 须为常量 {sorted(PRANGE_SCHEDULES)!r} 之一"
          )
        schedule = s
      case "num_threads":
        n = _const_int(kw.value)
        if n is not None:
          if n <= 0:
            num_threads_s = None
          else:
            num_threads_s = str(n)
        else:
          num_threads_s = tr.visit(kw.value)
      case "chunkSize":
        n = _const_int(kw.value)
        if n is not None:
          if n <= 0:
            chunksize_s = None
          else:
            chunksize_s = str(n)
        else:
          chunksize_s = tr.visit(kw.value)
      case "th":
        n = _const_int(kw.value)
        if n is not None:
          if n < 0:
            raise SyntaxError("prange th 须 >= 0")
          th_const = n
          th_s = str(n)
        else:
          th_const = None
          th_s = tr.visit(kw.value)
      case _:
        raise SyntaxError(f"prange 未知关键字 {kw.arg!r}")
  return schedule, num_threads_s, chunksize_s, th_const, th_s


def parse_prange_call(tr: Translator, call: ast.Call) -> PrangeSpec | None:
  if not is_prange_call(tr, call):
    return None
  start_s, stop_s, step_s = _parse_positional(tr, call)
  schedule, num_threads_s, chunksize_s, th_const, th_s = _parse_keywords(tr, call)
  return PrangeSpec(
    start_s,
    stop_s,
    step_s,
    schedule,
    num_threads_s,
    chunksize_s,
    th_const,
    th_s,
    collect_reductions(call, tr),
  )


def collect_reductions(call: ast.Call, tr: Translator) -> tuple[tuple[str, str], ...]:
  """自 ``for`` 体收集 ``name op= expr`` reduction（仅顶层语句）。"""
  for_node = _enclosing_for_with_iter(tr, call)
  if for_node is None:
    return ()
  reds: dict[str, str] = {}
  for stmt in for_node.body:
    _scan_reduction_stmt(stmt, reds)
  return tuple(sorted(reds.items()))


def _enclosing_for_with_iter(tr: Translator, call: ast.Call) -> ast.For | None:
  stack = getattr(tr, "_ast_node_stack", None)
  if not stack:
    return None
  for node in reversed(stack):
    if isinstance(node, ast.For) and node.iter is call:
      return node
  return None


def _scan_reduction_stmt(stmt: ast.stmt, reds: dict[str, str]) -> None:
  if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
    op = _REDUCTION_OP_MAP.get(type(stmt.op))
    if op is not None:
      prev = reds.get(stmt.target.id)
      if prev is not None and prev != op:
        raise SyntaxError(
          f"prange reduction：变量 {stmt.target.id!r} 不能同时使用 {prev!r} 与 {op!r}"
        )
      reds[stmt.target.id] = op


def _schedule_clause(spec: PrangeSpec) -> str:
  if spec.chunksize_s:
    return f"schedule({spec.schedule}, {spec.chunksize_s})"
  if spec.schedule == "static":
    return ""
  return f"schedule({spec.schedule})"


def _reduction_clause(reductions: tuple[tuple[str, str], ...]) -> str:
  if not reductions:
    return ""
  by_op: dict[str, list[str]] = {}
  for name, op in reductions:
    by_op.setdefault(op, []).append(name)
  parts: list[str] = []
  for op in sorted(by_op):
    names = ", ".join(sorted(by_op[op]))
    parts.append(f"reduction({op}:{names})")
  return " ".join(parts)


def _omp_pragma(spec: PrangeSpec) -> str:
  parts = ["parallel", "for"]
  sched = _schedule_clause(spec)
  if sched:
    parts.append(sched)
  if spec.num_threads_s:
    parts.append(f"num_threads({spec.num_threads_s})")
  red = _reduction_clause(spec.reductions)
  if red:
    parts.append(red)
  return "#pragma omp " + " ".join(parts)


def _parallel_mode(spec: PrangeSpec, iter_call: ast.Call) -> bool | None:
  """``True`` 恒并行；``False`` 恒串行；``None`` 须运行时 ``trip >= th`` 分支。"""
  if spec.th_const == 0:
    return True
  trip: int | None = _const_range_trip_count(iter_call)
  if spec.th_const is not None and trip is not None:
    return trip >= spec.th_const
  return None


def _prange_range_call(iter_call: ast.Call) -> ast.Call:
  return ast.Call(
    func=ast.Name(id="range", ctx=ast.Load()),
    args=list(iter_call.args),
    keywords=[],
  )


def emit_prange_trip_expr(tr: Translator, iter_call: ast.Call) -> str:
  """``len(range(*prange 位置参数))``；单参 ``prange(stop)`` 即 ``range(0, stop, 1)``，直接 ``stop``。"""
  match iter_call.args:
    case [stop]:
      return tr._visit_value_expr(stop)
    case _:
      from .loops_emit import emit_range_len_expr

      return emit_range_len_expr(tr, _prange_range_call(iter_call))


def _emit_openmp_range_loop(
  tr: Translator,
  name: str,
  spec: PrangeSpec,
  body: Callable[[], None],
  *,
  redeclare: bool,
) -> None:
  tr.uses_openmp = True
  pragma = _omp_pragma(spec)

  def _prefix() -> None:
    tr.write_line(pragma)

  emit_native_range_loop(
    tr,
    name,
    spec.start_s,
    spec.stop_s,
    spec.step_s,
    body,
    redeclare=redeclare,
    before_header=_prefix,
  )


def emit_prange_loop_from_call(
  tr: Translator,
  name: str,
  iter_call: ast.Call,
  body: Callable[[], None],
) -> None:
  spec = parse_prange_call(tr, iter_call)
  if spec is None:
    raise NotImplementedError("prange for-loop")
  if not tr.openmp_enabled:
    emit_native_range_loop_from_call(tr, name, iter_call, body)
    return
  from ..translator import NameContext

  redeclare = not (
    tr.scope is not None and tr.scope.vars.get(name) == NameContext.Variable
  )
  mode = _parallel_mode(spec, iter_call)
  if mode is False:
    emit_native_range_loop_from_call(tr, name, iter_call, body)
    return
  if mode is True:
    _emit_openmp_range_loop(tr, name, spec, body, redeclare=redeclare)
    return
  trip_s: str = emit_prange_trip_expr(tr, iter_call)
  with tr._use_block(f"if ({trip_s} >= {spec.th_s})"):
    _emit_openmp_range_loop(tr, name, spec, body, redeclare=redeclare)
  with tr._use_block("else"):
    emit_native_range_loop_from_call(tr, name, iter_call, body)


def emit_prange_for(tr: Translator, node: ast.For) -> None:
  match node.target:
    case ast.Name(id=name):
      with tr._loop_with_else(node.orelse):
        emit_prange_loop_from_call(
          tr, name, node.iter, lambda: tr._emit_body(node.body),
        )
    case _:
      raise NotImplementedError("prange for-loop 目标须为简单变量名")
