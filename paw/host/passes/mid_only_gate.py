"""Host Mid-only gate（``host-pass-mid``）。

``compiler/paw/**`` 在 ``PY2CPP_MID_PRIMARY`` 默认开启时走薄 Mid emit，
不经 ``tree_from_mid`` 骨架、不 ``ensure_methods_bridged_from_mid``。

stdlib / 用户模块仍经 ``host.tree_nodes`` facade + ClassInfo host emit
（须 ``tree_from_mid`` 骨架供 union.mro 等）；完整去掉 facade 需逐 pass 迁 Mid。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator


def is_mid_only_module(translator: Translator, module_path: str) -> bool:
  """薄生产 / Mid-primary seed：passes 应只读写 ``module_mids``。"""
  check = getattr(translator, "_module_mid_thin_production", None)
  if callable(check):
    return bool(check(module_path))
  return False
