"""``@abstract`` 纯虚方法译期约束（桩体、抽象类 ``new()``）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import (
  ClassInfo,
  has_named_decorator,
  is_abstract_method_body,
  strip_type_annotation_markers,
)
from ..translation_error import TranslationError, location_from_node
from .strict_style import _Violation, _iter_class_methods, _resolve_inherited_method

if TYPE_CHECKING:
  from ..translator import Translator


def _skip_class_for_abstract(info: ClassInfo) -> bool:
  return (
    info.is_protocol
    or info.is_descriptor
    or info.is_annotation
    or info.is_enum
    or info.is_union
    or info.is_refcount
    or info.is_boxing
  )


def unresolved_abstract_method_names(tr: Translator, info: ClassInfo) -> frozenset[str]:
  """类上仍未落地的纯虚方法名（含自基类继承且未具体实现者）。"""
  if _skip_class_for_abstract(info):
    return frozenset()
  pending: set[str] = set()
  for base_name in info.bases:
    base_info = tr.classes.get(base_name)
    if base_info is None:
      continue
    pending |= set(unresolved_abstract_method_names(tr, base_info))
  for method in info.methods.values():
    name = method.name
    if name == "__init__":
      continue
    if has_named_decorator(method, "abstract"):
      pending.add(name)
    elif name in pending:
      pending.discard(name)
  return frozenset(pending)


def class_is_abstract(tr: Translator, info: ClassInfo) -> bool:
  return bool(unresolved_abstract_method_names(tr, info))


def _class_name_from_ann(ann: ast.expr | None) -> str | None:
  if ann is None:
    return None
  stripped = strip_type_annotation_markers(ann)
  if isinstance(stripped, ast.Name):
    return stripped.id
  return None


def _is_new_call(expr: ast.expr | None) -> bool:
  return (
    isinstance(expr, ast.Call)
    and isinstance(expr.func, ast.Name)
    and expr.func.id == "new"
  )


def _check_abstract_method_bodies(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    for method in _iter_class_methods(info):
      if not has_named_decorator(method, "abstract"):
        continue
      if method.name == "__init__":
        violations.append(
          _Violation(
            "abstract",
            "``__init__`` 不可标 ``@abstract``",
            method,
            module_path,
          )
        )
        continue
      if not is_abstract_method_body(method.body):
        violations.append(
          _Violation(
            "abstract",
            "``@abstract`` 方法体须仅写 ``...``（可有 docstring；勿 ``pass``）",
            method,
            module_path,
          )
        )


def _check_abstract_override_base(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    for method in _iter_class_methods(info):
      if not has_named_decorator(method, "abstract"):
        continue
      if not has_named_decorator(method, "override"):
        continue
      inherited = _resolve_inherited_method(tr, info, method.name)
      if inherited is None:
        violations.append(
          _Violation(
            "abstract",
            f"``@abstract`` + ``@override`` 的 ``{info.name}.{method.name}`` 须覆盖基类虚/纯虚方法",
            method,
            module_path,
          )
        )
        continue
      _base_info, base_method = inherited
      if not (
        has_named_decorator(base_method, "abstract")
        or has_named_decorator(base_method, "virtual")
      ):
        violations.append(
          _Violation(
            "abstract",
            f"``@abstract`` + ``@override`` 须覆盖 ``@virtual``/``@abstract`` 基类方法 "
            f"（``{_base_info.name}.{method.name}`` 未标）",
            method,
            module_path,
          )
        )


def _check_abstract_class_instantiation(
  tr: Translator,
  module_path: str,
  violations: list[_Violation],
) -> None:
  tree = tr.module_asts.get(module_path)
  if tree is None:
    return
  for node in ast.walk(tree):
    if not isinstance(node, ast.AnnAssign) or node.value is None:
      continue
    if not _is_new_call(node.value):
      continue
    cls_name = _class_name_from_ann(node.annotation)
    if cls_name is None:
      continue
    info = tr.classes.get(cls_name)
    if info is None or info.module_path != module_path:
      continue
    if not class_is_abstract(tr, info):
      continue
    pending = unresolved_abstract_method_names(tr, info)
    detail = "、".join(f"``{n}``" for n in sorted(pending))
    violations.append(
      _Violation(
        "abstract",
        f"不可 ``new()`` 实例化仍含纯虚方法的类 ``{cls_name}``（{detail}）",
        node,
        module_path,
      )
    )


def check_abstract_rules(tr: Translator) -> None:
  violations: list[_Violation] = []
  for module_path in tr.module_asts:
    _check_abstract_method_bodies(tr, module_path, violations)
    _check_abstract_override_base(tr, module_path, violations)
    _check_abstract_class_instantiation(tr, module_path, violations)
  if not violations:
    return
  parts: list[str] = [f"发现 {len(violations)} 处 ``@abstract`` 规则违规："]
  first_loc = None
  for v in violations:
    loc = location_from_node(tr, v.node, module_path=v.module_path)
    prefix = loc.prefix() if loc is not None else "?"
    parts.append(f"  {prefix}: {v.message}")
    if first_loc is None and loc is not None:
      first_loc = loc
  raise TranslationError("\n".join(parts), location=first_loc)
