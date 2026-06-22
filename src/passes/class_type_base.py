"""为自定义类注入 ``type __base__``：实体基类或 ``void``（须在 ``expand_mixins`` 之后）。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from ..analysis.ir import TypeAliasInfo, class_base_name
from .class_id import _ordered_custom_classes, _skip_class_id

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def _is_non_entity_base(info: ClassInfo | None) -> bool:
  if info is None:
    return False
  from .mixins import is_mixin_class

  return (
    info.is_protocol
    or is_mixin_class(info)
    or info.is_annotation
  )


def _entity_base_ast(info: ClassInfo, tr: Translator) -> ast.expr | None:
  """``info.bases`` 中首个实体基类；``Proxy[T]`` 基展开为内层 ``T``。"""
  from ..analysis.proxy import PROXY_CLASS_NAME, proxy_inner_from_base_ast

  node_bases: dict[str, ast.expr] = {}
  for base_ast in info.node.bases:
    name = class_base_name(base_ast)
    if name is not None:
      node_bases[name] = base_ast
  for base_name in info.bases:
    bi = tr.classes.get(base_name)
    if _is_non_entity_base(bi):
      continue
    base_ast = node_bases.get(base_name)
    if base_ast is not None:
      if base_name == PROXY_CLASS_NAME or (bi is not None and getattr(bi, "is_proxy", False)):
        inner = proxy_inner_from_base_ast(base_ast)
        if inner is not None:
          return inner
      return copy.deepcopy(base_ast)
    return ast.Name(id=base_name, ctx=ast.Load())
  if getattr(info, "is_proxy", False) and info.type_params:
    return ast.Name(id=info.type_params[0], ctx=ast.Load())
  return None


def check_class_inheritance_bases(tr: Translator) -> None:
  """S30：全模块（含 ``test/fail/``）检查继承顺序与实体基类数量。"""
  from ..translation_error import TranslationError, location_from_node
  from .strict_style import _Violation, _check_s30_inheritance_bases

  violations: list[_Violation] = []
  for module_path in tr.module_asts:
    _check_s30_inheritance_bases(tr, module_path, violations)
  if not violations:
    return
  parts: list[str] = [f"发现 {len(violations)} 处继承规则违规（S30）："]
  first_loc = None
  for v in violations:
    loc = location_from_node(tr, v.node, module_path=v.module_path)
    prefix = loc.prefix() if loc is not None else "?"
    parts.append(f"  {prefix}: [{v.rule}] {v.message}")
    if first_loc is None and loc is not None:
      first_loc = loc
  raise TranslationError("\n".join(parts), location=first_loc)


def expand_class_type_base(tr: Translator) -> None:
  for info in _ordered_custom_classes(tr):
    if _skip_class_id(info):
      continue
    if "__base__" in info.type_aliases:
      raise ValueError(f"{info.name}: 勿手写 ``__base__``（译器自动注入）")
    entity_ast = _entity_base_ast(info, tr)
    value = entity_ast if entity_ast is not None else ast.Name(id="void", ctx=ast.Load())
    alias = TypeAliasInfo("__base__", value)
    info.type_alias_list.insert(0, alias)
    info.type_aliases["__base__"] = alias
    info.inject_type_base = True
