"""``@final`` 类/方法/字段译期约束（继承、覆盖、``__init__`` 外赋值）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, has_named_decorator
from ..translation_error import TranslationError, location_from_node
from .strict_style import _Violation, _iter_class_methods, _resolve_inherited_method

if TYPE_CHECKING:
  from ..translator import Translator


def _self_final_field_name(node: ast.stmt, final_fields: frozenset[str]) -> str | None:
  if isinstance(node, ast.Assign):
    if len(node.targets) != 1:
      return None
    tgt = node.targets[0]
  elif isinstance(node, ast.AnnAssign):
    tgt = node.target
  else:
    return None
  if not isinstance(tgt, ast.Attribute):
    return None
  if not isinstance(tgt.value, ast.Name) or tgt.value.id != "self":
    return None
  if tgt.attr not in final_fields:
    return None
  return tgt.attr


def _check_final_class_inheritance(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    for base_name in info.bases:
      base_info = tr.classes.get(base_name)
      if base_info is None or not base_info.is_final:
        continue
      violations.append(
        _Violation(
          "final",
          f"不可继承 ``@final`` 类 ``{base_info.name}``",
          info.node,
          module_path,
        )
      )


def _check_final_method_override(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    for method in _iter_class_methods(info):
      if method.name == "__init__":
        continue
      inherited = _resolve_inherited_method(tr, info, method.name)
      if inherited is None:
        continue
      base_info, base_method = inherited
      if not has_named_decorator(base_method, "final"):
        continue
      violations.append(
        _Violation(
          "final",
          f"不可覆盖 ``@final`` 方法 ``{base_info.name}.{method.name}``",
          method,
          module_path,
        )
      )


def _check_final_field_assignments(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  for info in tr.classes.values():
    if info.module_path != module_path or not info.final_fields:
      continue
    final = frozenset(info.final_fields)
    for method in _iter_class_methods(info):
      if method.name == "__init__":
        continue
      for stmt in ast.walk(method):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
          continue
        if stmt is method:
          continue
        field = _self_final_field_name(stmt, final)
        if field is None:
          continue
        violations.append(
          _Violation(
            "final",
            f"``@final`` 字段 ``{field}`` 仅可在 ``__init__`` 中初始化",
            stmt,
            module_path,
          )
        )


def check_final_rules(tr: Translator) -> None:
  violations: list[_Violation] = []
  for module_path in tr.module_asts:
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    _check_final_class_inheritance(tr, module_path, violations)
    _check_final_method_override(tr, module_path, violations)
    _check_final_field_assignments(tr, module_path, violations)
  if not violations:
    return
  parts: list[str] = [f"发现 {len(violations)} 处 ``@final`` 规则违规："]
  first_loc = None
  for v in violations:
    loc = location_from_node(tr, v.node, module_path=v.module_path)
    prefix = loc.prefix() if loc is not None else "?"
    parts.append(f"  {prefix}: {v.message}")
    if first_loc is None and loc is not None:
      first_loc = loc
  raise TranslationError("\n".join(parts), location=first_loc)
