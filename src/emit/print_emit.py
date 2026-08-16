"""``print()`` 语句 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.imports import resolve_ctor_cpp_type
from ..analysis.ir import cpp_ident, quote_cpp_string
from .fstring_emit import emit_format_expr, plan_joined_str

if TYPE_CHECKING:
  from ..translator import Translator


def escape_printf_literal(text: str) -> str:
  return text.replace("%", "%%")


def parse_print_keywords(node: ast.Call) -> tuple[str, str, bool]:
  sep = " "
  end = "\n"
  flush = False
  for keyword in node.keywords:
    match keyword.arg:
      case "sep":
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
          sep = keyword.value.value
        else:
          raise NotImplementedError("print(sep=...) requires string literal")
      case "end":
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
          end = keyword.value.value
        else:
          raise NotImplementedError("print(end=...) requires string literal")
      case "flush":
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
          flush = keyword.value.value
        else:
          raise NotImplementedError("print(flush=...) requires bool literal")
      case "file":
        raise NotImplementedError("print(file=...) is not supported")
      case _:
        raise NotImplementedError(f"print() keyword {keyword.arg!r}")
  return sep, end, flush


def printf_arg_cstr(pystr_expr: str) -> str:
  return f"{cpp_ident('str')}::PrintfArg({pystr_expr}).data"


def str_literal_for_print(tr: Translator, node: ast.expr) -> str | None:
  if not isinstance(node, ast.Call) or len(node.args) != 1:
    return None
  if not isinstance(node.func, ast.Name):
    return None
  if resolve_ctor_cpp_type(tr, node.func.id) != cpp_ident("str"):
    return None
  arg0 = node.args[0]
  if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
    return quote_cpp_string(arg0.value)
  return None


def plan_print_arg(tr: Translator, node: ast.expr) -> tuple[str, list[str], list[str]]:
  prep: list[str] = []
  if isinstance(node, ast.Constant) and isinstance(node.value, str):
    return "%s", [quote_cpp_string(node.value)], prep
  if isinstance(node, ast.JoinedStr):
    plan = plan_joined_str(tr, node)
    if plan.literal_only:
      return plan.fmt, [], prep
    expr = emit_format_expr(tr, plan)
    return "%s", [printf_arg_cstr(expr)], prep
  lit = str_literal_for_print(tr, node)
  if lit is not None:
    return "%s", [lit], prep
  s = tr._emit_str_expr(node)
  return "%s", [printf_arg_cstr(s)], prep


def emit_printf(
  tr: Translator,
  fmt: str,
  args: list[str],
  prep: list[str],
  *,
  flush: bool,
) -> None:
  for line in prep:
    tr.write_line(line)
  if args:
    tr.write_line(f"printf({quote_cpp_string(fmt)}, {', '.join(args)});")
  else:
    tr.write_line(f"printf({quote_cpp_string(fmt)});")
  if flush:
    tr.write_line("fflush(_py2cpp_c_stdout());")


def emit_print(tr: Translator, node: ast.Call) -> None:
  if tr.debug:
    label = tr._debug_call_label(node).replace("\\", "\\\\").replace('"', '\\"')
    tr.write_line(f'_py2cpp_debug_call("{label}");')
  sep, end, flush = parse_print_keywords(node)
  if not node.args:
    emit_printf(tr, escape_printf_literal(end), [], [], flush=flush)
    return
  if (
    len(node.args) == 1
    and isinstance(node.args[0], ast.Constant)
    and isinstance(node.args[0].value, str)
  ):
    text = node.args[0].value + end
    emit_printf(tr, escape_printf_literal(text), [], [], flush=flush)
    return
  fmt_parts: list[str] = []
  printf_args: list[str] = []
  prep: list[str] = []
  for i, arg in enumerate(node.args):
    if i > 0:
      fmt_parts.append(escape_printf_literal(sep))
    spec, arg_exprs, arg_prep = plan_print_arg(tr, arg)
    fmt_parts.append(spec)
    printf_args.extend(arg_exprs)
    prep.extend(arg_prep)
  fmt_parts.append(escape_printf_literal(end))
  emit_printf(tr, "".join(fmt_parts), printf_args, prep, flush=flush)
