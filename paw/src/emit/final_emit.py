"""``T @final`` → C++ ``const`` 成员与构造初始化列表。"""
from __future__ import annotations

import ast

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


def emit_self_init_delegate_suffix(
  tr: "Translator",
  info: ClassInfo,
  method,
  forward: ast.Call,
) -> str:
  """``self.__init__(...)`` 单句转发 → C++ 委托构造 ``: Class(args)``。"""
  if emit_final_ctor_init_suffix(tr, info, method):
    raise NotImplementedError(
      "self.__init__(...) 转发重载与 @final 成员构造初始化列表暂不可同用",
    )
  from .call_emit import emit_call_args

  if tr._method_def_for_call(info, "__init__", forward) is None:
    raise NotImplementedError("self.__init__(...) 须转发到同类已声明的 __init__ 重载")
  param_types = tr._ordered_method_param_cpp_types(info, "__init__", call=forward)
  args = emit_call_args(tr, forward, param_cpp_types=param_types)
  return f" : {info.cpp_name()}({args})"
