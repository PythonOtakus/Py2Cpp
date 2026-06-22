"""模块级 ``def`` 索引：``@overload`` 分组与普通实现分离。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .delegates import is_delegate_definition
from .ir import has_named_decorator
from ..constant.parallel import CONCUR_PARALLEL_MODULE, PRANGE_TRANSLATION_ONLY_FUNCS

if TYPE_CHECKING:
  from ..translator import Translator


def partition_module_functions_from_asts(
  tr: Translator,
  *,
  runtime_pkg: str,
  builtins_runtime_funcs: frozenset[str],
  translation_only_funcs: frozenset[str],
) -> None:
  """从 ``module_asts`` 重建 ``module_functions`` 与 ``module_function_overloads``。"""
  from ..passes.descriptor_signatures import is_descriptor_signature_helper

  from ..constant.stdlib_layout import RUNTIME_BUILTINS_MODULE, RUNTIME_PKG

  injected_helpers = [
    (mp, f) for mp, f in tr.module_functions if is_descriptor_signature_helper(f.name)
  ]
  overloads: dict[tuple[str, str], list[ast.FunctionDef]] = {}
  regular: list[tuple[str, ast.FunctionDef]] = []
  for module_path, tree in tr.module_asts.items():
    if tree is None:
      continue
    for node in tree.body:
      if not isinstance(node, ast.FunctionDef):
        continue
      if module_path in (runtime_pkg, RUNTIME_BUILTINS_MODULE):
        if node.name not in builtins_runtime_funcs:
          continue
        if has_named_decorator(node, "global_call"):
          continue
      if node.name in translation_only_funcs:
        continue
      if (
        module_path == CONCUR_PARALLEL_MODULE
        and node.name in PRANGE_TRANSLATION_ONLY_FUNCS
      ):
        continue
      if is_delegate_definition(node):
        continue
      if has_named_decorator(node, "overload"):
        overloads.setdefault((module_path, node.name), []).append(node)
      else:
        regular.append((module_path, node))
  tr.module_function_overloads = overloads
  tr.module_functions = regular
  seen = {id(f) for _, f in tr.module_functions}
  for mp, f in injected_helpers:
    if id(f) not in seen:
      tr.module_functions.append((mp, f))
      seen.add(id(f))
