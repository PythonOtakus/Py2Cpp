"""``a, b = b, a + 1`` / ``xs[i], xs[j] = xs[j], xs[i]`` 并行多目标赋值。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import strip_cpp_type_qualifiers

if TYPE_CHECKING:
  from ..translator import Translator


def emit_parallel_assign_targets(
  tr: "Translator", target_elts: list[ast.expr], value_exprs: list[str],
) -> None:
  """将已求值的 ``value_exprs[i]`` 写入 ``target_elts[i]``（顺序赋值）。"""
  for tgt, val in zip(target_elts, value_exprs):
    tr._emit_assign(tgt, val)


def emit_parallel_tuple_assign(
  tr: "Translator",
  target_elts: list[ast.expr],
  value_elts: list[ast.expr],
) -> None:
  """右值各元素先求值到临时变量，再写入左值（避免交换/自引用别名）。"""
  from ..translator import temp_name

  temps: list[str] = []
  for ve in value_elts:
    et = strip_cpp_type_qualifiers(tr._infer_expr_cpp_type(ve) or "auto")
    val = tr._visit_value_for_type(ve, et)
    tmp = temp_name("par")
    tr.write_line(f"{et} {tmp} = {val};")
    temps.append(tmp)
  emit_parallel_assign_targets(tr, target_elts, temps)


def try_emit_parallel_tuple_assign(
  tr: "Translator",
  target_elts: list[ast.expr],
  value_elts: list[ast.expr],
) -> bool:
  if len(target_elts) != len(value_elts):
    return False
  emit_parallel_tuple_assign(tr, target_elts, value_elts)
  return True
