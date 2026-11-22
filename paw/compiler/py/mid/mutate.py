"""MidIR 就地变更助手（pass 回写 ``module_mids``）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .nodes import MidClass, MidFunction, MidModule

if TYPE_CHECKING:
  from typing import Any


def find_mid_class(mid: MidModule, name: str) -> MidClass | None:
  """在 ``MidModule.items`` 中按名查找 ``MidClass``。"""
  for item in mid.items:
    if isinstance(item, MidClass) and item.name == name:
      return item
  return None


def append_mid_method(mid_class: MidClass, fn: MidFunction) -> None:
  """将合成 ``MidFunction`` 挂到 ``MidClass.methods``（同名则替换）。"""
  methods = mid_class.methods
  for i, existing in enumerate(methods):
    if existing.name == fn.name:
      methods[i] = fn
      return
  methods.append(fn)


def replace_module_mid(tr: Any, module_path: str, mid: MidModule) -> None:
  """写入 / 覆盖 ``tr.module_mids[module_path]``。"""
  if not hasattr(tr, "module_mids") or tr.module_mids is None:
    tr.module_mids = {}
  tr.module_mids[module_path] = mid


def mid_class_for_info(tr: Any, info: Any) -> MidClass | None:
  """按 ``ClassInfo.module_path`` + ``name`` 取对应 ``MidClass``。"""
  name = getattr(info, "name", None)
  mp = getattr(info, "module_path", None)
  if not name:
    return None
  mids = getattr(tr, "module_mids", None) or {}
  if mp and mp in mids:
    found = find_mid_class(mids[mp], name)
    if found is not None:
      return found
  for mid in mids.values():
    found = find_mid_class(mid, name)
    if found is not None:
      return found
  return None
