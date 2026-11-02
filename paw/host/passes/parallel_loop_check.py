"""``prange`` 循环体静态约束（数据竞争 / OpenMP 合法子集）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..emit.prange_emit import is_prange_call_with_bindings

if TYPE_CHECKING:
  from ..translator import Translator


def check_parallel_loops(tr: Translator) -> None:
  for module_path, tree in tr.module_asts.items():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    bindings = tr.module_import_bindings.get(module_path, {})
    for node in ast.walk(tree):
      if not isinstance(node, ast.For):
        continue
      if not is_prange_call_with_bindings(node.iter, bindings):
        continue
      _check_prange_for(node, bindings)


def _check_prange_for(node: ast.For, bindings: dict) -> None:
  if getattr(node, "is_async", False):
    raise SyntaxError("prange 不支持 async for")
  for inner in ast.walk(node):
    if inner is node:
      continue
    if isinstance(inner, ast.For) and is_prange_call_with_bindings(inner.iter, bindings):
      raise SyntaxError("prange 暂不支持嵌套 prange")
    if isinstance(inner, ast.Break):
      raise SyntaxError("prange 循环体内禁止 break")
