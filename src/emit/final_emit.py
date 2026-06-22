"""``T @final`` → C++ ``const`` 成员与构造初始化列表。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


def final_inits_for_init(info: ClassInfo, init_id: int) -> dict[str, object]:
  by_init = info.final_ctor_inits_by_init
  if init_id in by_init:
    return by_init[init_id]
  return info.final_ctor_inits


def emit_final_ctor_init_suffix(
  tr: "Translator",
  info: ClassInfo,
  method,
) -> str:
  inits = final_inits_for_init(info, id(method))
  if not inits:
    return ""
  parts: list[str] = []
  for field in info.fields:
    if field not in inits:
      continue
    cpp = info.cpp_member_name(field)
    val = tr.visit(inits[field])
    parts.append(f"{cpp}({val})")
  if not parts:
    return ""
  return ": " + ", ".join(parts)
