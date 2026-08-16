"""迭代器 / 视图类与宿主容器的字段、形参指针类型（``analyzer`` 用）。"""
from __future__ import annotations

import re
from functools import lru_cache

from ...constant.stdlib_classes import (
  ECS_QUERY_CLASS,
  ECS_QUERY_OWNER_FIELDS,
  ECS_QUERY_OWNER_PARAMS,
  ITERATOR_CTOR_SELF_AS_THIS,
)
from ...constant.iterator_patterns import HOST_BOUND_ITERATOR_VIEW_SUFFIXES
from ..ir import cpp_ident, cpp_template_type

_PASCAL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_PASCAL_2 = re.compile(r"([a-z0-9])([A-Z])")


def pascal_to_snake_iter_name(name: str) -> str:
  """``ListIterator`` → ``list_iterator``；``FrozenDictKeysView`` → ``frozendict_keys_view``。"""
  if "_" in name:
    return name
  for py, pas in (
    ("frozendict", "FrozenDict"),
    ("frozenlist", "FrozenList"),
    ("frozenset", "FrozenSet"),
  ):
    if name.startswith(pas):
      rest = name[len(pas) :]
      if not rest:
        return py
      rest_snake = _PASCAL_2.sub(
        r"\1_\2", _PASCAL_1.sub(r"\1_\2", rest)
      ).lower()
      return f"{py}_{rest_snake}" if rest_snake else py
  return _PASCAL_2.sub(r"\1_\2", _PASCAL_1.sub(r"\1_\2", name)).lower()


@lru_cache(maxsize=1)
def load_frozendict_host_bound_class_names() -> frozenset[str]:
  """``FrozenDict*`` / 旧 ``frozendict_*`` 迭代器与 view（``_dct`` 为 ``const frozendict*``）。"""
  from .class_stubs import load_stdlib_native_names

  names: set[str] = set()
  for py_name in load_stdlib_native_names():
    sn = pascal_to_snake_iter_name(py_name)
    if not sn.startswith("frozendict_"):
      continue
    if any(sn.endswith(suffix) for suffix in HOST_BOUND_ITERATOR_VIEW_SUFFIXES):
      names.add(py_name)
  return frozenset(names)


def iterator_ctor_self_expr(host_class: str) -> str:
  """宿主 ``new(self)`` / ``__iter__`` 时传给迭代器构造的 ``self`` 表达式。"""
  if host_class in ITERATOR_CTOR_SELF_AS_THIS or host_class.startswith(
    ("frozendict", "FrozenDict")
  ):
    return "this"
  return "*this"


def dict_like_host_py_name(class_name: str) -> str | None:
  sn = pascal_to_snake_iter_name(class_name)
  if sn.startswith("frozendict_"):
    return "frozendict"
  if sn.startswith("dict_"):
    return "dict"
  return None


def _stem_to_host(stem: str) -> str | None:
  for suffix in ("_key_reverse", "_key", "_values", "_items"):
    if stem.endswith(suffix):
      return stem[: -len(suffix)] or None
  return stem or None


def iterator_owner_host_py_name(class_name: str) -> str | None:
  """``ListIterator`` → ``list``；``FrozenDictKeyIterator`` → ``frozendict``。"""
  if class_name == "ECSComponentTableIterator":
    return "ECSComponentTable"
  sn = pascal_to_snake_iter_name(class_name)
  if sn.endswith("_reverse_iterator"):
    return _stem_to_host(sn[: -len("_reverse_iterator")])
  if sn.endswith("_iterator"):
    return _stem_to_host(sn[: -len("_iterator")])
  return None


def _dq_owner_host_classes() -> frozenset[str]:
  return frozenset({"deque", "ChunkDeque"})


def host_owner_field_name(class_name: str) -> str | None:
  if class_name == ECS_QUERY_CLASS:
    return None
  sn = pascal_to_snake_iter_name(class_name)
  if sn.startswith("dict_"):
    return None
  if class_name in load_frozendict_host_bound_class_names():
    return "_dct"
  host = iterator_owner_host_py_name(class_name)
  if host in _dq_owner_host_classes():
    return "_dq"
  if host is not None:
    return "_owner"
  return None


def host_owner_param_name(class_name: str) -> str | None:
  if class_name == ECS_QUERY_CLASS:
    return None
  sn = pascal_to_snake_iter_name(class_name)
  if sn.startswith("dict_"):
    return None
  if class_name in load_frozendict_host_bound_class_names():
    return "dct"
  host = iterator_owner_host_py_name(class_name)
  if host in _dq_owner_host_classes():
    return "dq"
  if host is not None:
    return "owner"
  return None


def host_ptr_cpp_type(
  host_py: str,
  type_params: list[str],
  *,
  const: bool = True,
) -> str | None:
  """宿主容器指针 C++ 类型；无法推导时返回 ``None``。"""
  if host_py == "array" and type_params:
    return f"{type_params[0]}*"
  if host_py in ("dict", "frozendict") and len(type_params) >= 2:
    inner = cpp_template_type(host_py, f"{type_params[0]}, {type_params[1]}")
    prefix = "const " if const else ""
    return f"{prefix}{inner}*"
  if host_py in ("deque", "ChunkDeque") and type_params:
    return f"{cpp_ident(host_py)}<{type_params[0]}>*"
  if host_py in ("list", "frozenlist") and type_params:
    elem = type_params[0]
    cap = type_params[1] if len(type_params) >= 2 else "0"
    prefix = "const " if const else ""
    return f"{prefix}{cpp_ident(host_py)}<{elem}, {cap}>*"
  if type_params:
    prefix = "const " if const else ""
    return f"{prefix}{cpp_ident(host_py)}<{type_params[0]}>*"
  return None


def ecs_query_ptr_cpp_type(
  class_name: str,
  field_or_param: str,
  type_params: list[str],
) -> str | None:
  if class_name != ECS_QUERY_CLASS:
    return None
  idx = ECS_QUERY_OWNER_FIELDS.get(field_or_param)
  if idx is None:
    idx = ECS_QUERY_OWNER_PARAMS.get(field_or_param)
  if idx is None or len(type_params) <= idx:
    return None
  return f"const {cpp_ident('ECSComponentTable')}<{type_params[idx]}>*"
