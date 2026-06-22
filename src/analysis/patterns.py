"""译器命名 helper（字面量表见 ``constant.language``）。"""
from __future__ import annotations

from ..constant.language import (
  CPP_KEYWORDS,
  CPP_PARAM_RENAME,
  DUNDER_METHODS,
  RESERVED,
)

_temp_id = 0


def temp_name(prefix: str = "tmp") -> str:
  """译器生成的 C++ 临时局部名（``__`` 前缀 + 单调编号，避免与用户局部名冲突）。"""
  global _temp_id
  leaf = prefix.lstrip("_") or "tmp"
  name = f"__{leaf}{_temp_id}"
  _temp_id += 1
  return name


def py2cpp_emit_symbol(*parts: str) -> str:
  """命名空间级译器辅助符号（``__py2cpp_{…}``，如 peel struct、``type if`` picker）。"""
  body = "_".join(p.strip("_") for p in parts if p)
  return f"__py2cpp_{body}"


def auto_template_type_param_name(leaf: str, *, reserved: set[str]) -> str:
  """译器自动补全的 C++ 模板类型形参名（``__`` 前缀，避免与 Win 宏 / ``Args`` 等冲突）。"""
  norm = leaf.lstrip("_") or "T"
  base = f"__{norm}"
  name = base
  suffix = 0
  while name in reserved:
    suffix += 1
    name = f"{base}{suffix}"
  return name


def escape_cpp_param(name: str) -> str:
  """Python 形参/局部名 → 合法 C++ 标识符。"""
  if name in CPP_PARAM_RENAME:
    return CPP_PARAM_RENAME[name]
  if name in CPP_KEYWORDS:
    return f"{name}_"
  return name


def property_getter_method_for(attr: str) -> str:
  """``@property`` / 描述符读：``{attr}__get()``（dunder 如 ``__id__`` → ``__id____get``，不合并下划线）。"""
  return f"{attr}__get"


def property_setter_method_for(attr: str) -> str:
  """``@property`` / 描述符写：``{attr}__set(…)``（dunder 同理，如 ``__id____set``）。"""
  return f"{attr}__set"


def property_postsetter_method_for(attr: str) -> str:
  """``@property.postsetter``：``{attr}__postset(…)``（dunder 同理）。"""
  return f"{attr}__postset"


def property_storage_field_for(attr: str) -> str:
  """``self.__value__`` / ``@property`` 存储：``{attr}__value``（dunder 如 ``__foo__`` → ``__foo____value``）。"""
  return f"{attr}__value"
