"""``Proxy[T]`` 形式继承 ``T``、禁止 ``Proxy[Proxy[…]]``。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, class_base_name
from ..analysis.proxy import (
  PROXY_CLASS_NAME,
  is_nested_proxy_inner,
  is_proxy_class_info,
  proxy_inner_from_base_ast,
)
from ..translation_error import TranslationError, location_from_node
from .class_id import _ordered_custom_classes, _skip_class_id

if TYPE_CHECKING:
  from ..translator import Translator


def _proxy_class_info(tr: Translator) -> ClassInfo | None:
  for info in tr.classes.values():
    if info.name == PROXY_CLASS_NAME and info.module_path.replace("\\", "/").endswith(
      "core/proxy"
    ):
      return info
  return None


def expand_proxy(tr: Translator) -> None:
  proxy_info = _proxy_class_info(tr)
  if proxy_info is not None:
    proxy_info.is_proxy = True

  for info in _ordered_custom_classes(tr):
    if _skip_class_id(info):
      continue
    if is_proxy_class_info(info):
      continue
    node_bases: dict[str, ast.expr] = {}
    for base_ast in info.node.bases:
      name = class_base_name(base_ast)
      if name is not None:
        node_bases[name] = base_ast
    for base_name in info.bases:
      if base_name != PROXY_CLASS_NAME:
        continue
      base_ast = node_bases.get(base_name)
      if base_ast is None:
        continue
      inner = proxy_inner_from_base_ast(base_ast)
      if inner is not None and is_nested_proxy_inner(inner):
        loc = location_from_node(tr, base_ast, module_path=info.module_path)
        raise TranslationError(
          f"{info.name}: 禁止 ``Proxy[Proxy[…]]``（嵌套代理）",
          location=loc,
        )
      info.is_proxy_derived = True


def check_proxy_nested_type_args(tr: Translator) -> None:
  """``Proxy[Proxy[T]]`` 在类型注解中亦禁止。"""
  for module_path, tree in tr.module_asts.items():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(module_path):
      continue
    for node in ast.walk(tree):
      if not isinstance(node, ast.Subscript):
        continue
      if not (
        isinstance(node.value, ast.Name)
        and node.value.id == PROXY_CLASS_NAME
      ):
        continue
      inner = node.slice
      if is_nested_proxy_inner(inner):
        loc = location_from_node(tr, node, module_path=module_path)
        raise TranslationError(
          "禁止 ``Proxy[Proxy[…]]``（嵌套代理）",
          location=loc,
        )
