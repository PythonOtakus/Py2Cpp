"""``SignatureBuilder``：``__iter__`` / ``__reversed__`` 返回 C++ 类型（表驱动 + 少量特判）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...constant.iterator_returns import ITER_RETURN, REVERSED_RETURN
from ..ir import cpp_ident, cpp_iterator_type

if TYPE_CHECKING:
  from ..ir import ClassInfo


def _emit_from_table(
  info: ClassInfo,
  table: dict[str, tuple[str, int]],
) -> tuple[str, str] | None:
  spec = table.get(info.name)
  if spec is None:
    return None
  base, arity = spec
  if arity == 0:
    return cpp_ident(base), ""
  if arity == 1:
    if not info.type_params:
      return None
    return cpp_iterator_type(base, info.type_params[0]), ""
  if len(info.type_params) >= 2:
    return cpp_iterator_type(base, info.type_params[0], info.type_params[1]), ""
  return None


def iter_method_return_type(info: ClassInfo) -> tuple[str, str] | None:
  if info.seq_iterator_name:
    it = info.seq_iterator_name
    if info.type_params:
      return cpp_iterator_type(it, info.type_params[0]), ""
    return cpp_ident(it), ""

  hit = _emit_from_table(info, ITER_RETURN)
  if hit is not None:
    return hit

  if info.name == "tuple_iterator" and info.is_template():
    if info.typevar_tuple and not info.type_params:
      return f"{cpp_ident('tuple_iterator')}<{info.typevar_tuple}...>", ""
    if info.type_params:
      return cpp_iterator_type("tuple_iterator", info.type_params[0]), ""

  if info.name in ("tuple", "PyTuple") and info.is_template():
    if info.typevar_tuple and not info.type_params:
      return f"{cpp_ident('tuple_iterator')}<{info.typevar_tuple}...>", ""
    if info.type_params:
      return cpp_iterator_type("tuple_iterator", info.type_params[0]), ""

  if info.name == "zip_iterator" and len(info.type_params) >= 2:
    p = ", ".join(info.type_params)
    return f"{cpp_ident('zip_iterator')}<{p}>&", ""

  if info.name == "enumerate_iterator" and info.type_params:
    return f"{cpp_ident('enumerate_iterator')}<{info.type_params[0]}>&", ""

  return None


def reversed_method_return_type(info: ClassInfo) -> tuple[str, str] | None:
  return _emit_from_table(info, REVERSED_RETURN)
