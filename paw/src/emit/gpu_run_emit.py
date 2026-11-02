"""GPU ``run`` / ``@GpuDeviceMeta`` 函数体 → 标量 C++ 表达式。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_ident
from ..translation_error import raise_translation_error

if TYPE_CHECKING:
  from ..translator import Translator

_BINOP_MAP: dict[type, str] = {
  ast.Add: "+",
  ast.Sub: "-",
  ast.Mult: "*",
  ast.Div: "/",
  ast.Mod: "%",
  ast.Pow: "**",
  ast.LShift: "<<",
  ast.RShift: ">>",
  ast.BitOr: "|",
  ast.BitXor: "^",
  ast.BitAnd: "&",
  ast.FloorDiv: "/",
}

_CMPOP_MAP: dict[type, str] = {
  ast.Eq: "==",
  ast.NotEq: "!=",
  ast.Lt: "<",
  ast.LtE: "<=",
  ast.Gt: ">",
  ast.GtE: ">=",
}

_BOOLOP_MAP: dict[type, str] = {
  ast.And: "&&",
  ast.Or: "||",
}

_UNARYOP_MAP: dict[type, str] = {
  ast.UAdd: "+",
  ast.USub: "-",
  ast.Not: "!",
  ast.Invert: "~",
}


def _member_cpp(tr: Translator, info, self_cpp: str, attr: str) -> str:
  if info is not None:
    return f"{self_cpp}.{tr._member_cpp_name(info, attr)}"
  return f"{self_cpp}.{attr}"


def emit_rewritten_expr(
  tr: Translator,
  expr: ast.expr,
  *,
  self_name: str,
  self_cpp: str,
  host_info,
  param_map: dict[str, str],
  device_funcs: dict[str, str],
) -> str:
  match expr:
    case ast.Constant(value=v):
      return tr._visit_value_expr(ast.Constant(value=v))
    case ast.Name(id=name):
      if name in param_map:
        return param_map[name]
      if name in device_funcs:
        return device_funcs[name]
      raise_translation_error(tr, expr, f"GPU 表达式未知标识符 `{name}`")
    case ast.Attribute(value=ast.Name(id=sname), attr=attr):
      if sname == self_name:
        return _member_cpp(tr, host_info, self_cpp, attr)
      raise_translation_error(tr, expr, f"GPU 表达式不支持属性 `{sname}.{attr}`")
    case ast.Call(func=ast.Name(id=fname), args=args):
      if fname not in device_funcs:
        raise_translation_error(tr, expr, f"GPU 仅可调用 `@GpuDeviceMeta` 函数 `{fname}`")
      arg_cpp = ", ".join(
        emit_rewritten_expr(
          tr, a, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
        )
        for a in args
      )
      return f"{device_funcs[fname]}({arg_cpp})"
    case ast.UnaryOp(op=op, operand=operand):
      op_s = _UNARYOP_MAP.get(type(op))
      if op_s is None:
        raise_translation_error(tr, expr, "GPU 表达式不支持该一元运算")
      inner = emit_rewritten_expr(
        tr,
        operand,
        self_name=self_name,
        self_cpp=self_cpp,
        host_info=host_info,
        param_map=param_map,
        device_funcs=device_funcs,
      )
      if isinstance(op, ast.Not):
        return f"(!({inner}))"
      return f"({op_s}({inner}))"
    case ast.BinOp(left=left, op=op, right=right):
      op_s = _BINOP_MAP.get(type(op))
      if op_s is None:
        raise_translation_error(tr, expr, "GPU 表达式不支持该二元运算")
      l = emit_rewritten_expr(
        tr, left, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      r = emit_rewritten_expr(
        tr, right, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      return f"(({l}) {op_s} ({r}))"
    case ast.BoolOp(op=op, values=values):
      op_s = _BOOLOP_MAP.get(type(op))
      if op_s is None or len(values) < 2:
        raise_translation_error(tr, expr, "GPU 表达式不支持该逻辑运算")
      parts = [
        emit_rewritten_expr(
          tr, v, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
        )
        for v in values
      ]
      return f"({f' {op_s} '.join(f'({p})' for p in parts)})"
    case ast.Compare(left=left, ops=ops, comparators=comps):
      cur = emit_rewritten_expr(
        tr, left, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      out: list[str] = [cur]
      for op, comp in zip(ops, comps, strict=True):
        op_s = _CMPOP_MAP.get(type(op))
        if op_s is None:
          raise_translation_error(tr, expr, "GPU 表达式不支持该比较运算")
        nxt = emit_rewritten_expr(
          tr, comp, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
        )
        out.append(f"{op_s} ({nxt})")
      return f"({' '.join(out)})"
    case ast.IfExp(test=test, body=body, orelse=orelse):
      t = emit_rewritten_expr(
        tr, test, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      b = emit_rewritten_expr(
        tr, body, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      e = emit_rewritten_expr(
        tr, orelse, self_name=self_name, self_cpp=self_cpp, host_info=host_info, param_map=param_map, device_funcs=device_funcs
      )
      return f"(({t}) ? ({b}) : ({e}))"
    case _:
      raise_translation_error(tr, expr, f"GPU 表达式不支持 {type(expr).__name__}")


def emit_gpu_scalar_result(
  tr: Translator,
  body: list[ast.stmt],
  *,
  self_name: str,
  self_cpp: str,
  host_info,
  param_map: dict[str, str],
  device_funcs: dict[str, str],
  node: ast.AST | None = None,
) -> str:
  if not body:
    raise_translation_error(tr, node, "GPU 函数体为空")

  def emit_stmts(stmts: list[ast.stmt]) -> str:
    if not stmts:
      raise_translation_error(tr, node, "GPU 函数体须以 `return` 结束")
    stmt = stmts[0]
    if isinstance(stmt, ast.Return):
      if stmt.value is None:
        raise_translation_error(tr, stmt, "GPU `run` 须有返回值")
      return emit_rewritten_expr(
        tr,
        stmt.value,
        self_name=self_name,
        self_cpp=self_cpp,
        host_info=host_info,
        param_map=param_map,
        device_funcs=device_funcs,
      )
    if isinstance(stmt, ast.If):
      test = emit_rewritten_expr(
        tr,
        stmt.test,
        self_name=self_name,
        self_cpp=self_cpp,
        host_info=host_info,
        param_map=param_map,
        device_funcs=device_funcs,
      )
      then_cpp = emit_stmts(stmt.body)
      if stmt.orelse:
        else_cpp = emit_stmts(stmt.orelse)
      else:
        else_cpp = emit_stmts(stmts[1:])
      return f"(({test}) ? ({then_cpp}) : ({else_cpp}))"
    raise_translation_error(tr, stmt, f"GPU 函数体不支持语句 {type(stmt).__name__}")

  return emit_stmts(body)


def gpu_device_cpp_name(module_path: str, func_name: str) -> str:
  safe = func_name.replace(".", "_")
  mod = module_path.replace("/", "_").replace("\\", "_")
  return cpp_ident(f"_gpu_dev_{mod}_{safe}")
