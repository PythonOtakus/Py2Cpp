"""``PyTuple<…>`` 多目标解包：前缀非负 ``get<N>``、后缀负 ``get<-N>``、``*_`` 丢弃中间。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from ..translator import Translator


@dataclass(frozen=True)
class PyTupleUnpackSlot:
  target: ast.expr | None
  get_index: int | None = None
  slice_start: int | None = None
  slice_stop: int | None = None


def unpack_target_is_discard(target: ast.expr) -> bool:
  match target:
    case ast.Name(id="_"):
      return True
    case ast.Starred(value=ast.Name(id="_")):
      return True
    case _:
      return False


def split_tuple_unpack_layout(
  elts: list[ast.expr],
) -> tuple[list[ast.expr], ast.Starred | None, list[ast.expr]]:
  star_idx: int | None = None
  for i, elt in enumerate(elts):
    if isinstance(elt, ast.Starred):
      if star_idx is not None:
        raise NotImplementedError("元组解包仅允许一个 ``*``")
      star_idx = i
  if star_idx is None:
    return list(elts), None, []
  return elts[:star_idx], elts[star_idx], elts[star_idx + 1 :]


def pytuple_unpack_slots(
  elts: list[ast.expr],
  *,
  arity: int,
) -> list[PyTupleUnpackSlot]:
  prefix, star, suffix = split_tuple_unpack_layout(elts)
  suffix_count = len(suffix)
  prefix_count = len(prefix)
  if star is None:
    if prefix_count != arity:
      raise NotImplementedError(
        f"``PyTuple`` 定长解包须 {arity} 个目标，当前 {prefix_count} 个；"
        "未用槽位写 ``_`` 或 ``*_`` 丢弃中间段"
      )
    slots: list[PyTupleUnpackSlot] = []
    for i, tgt in enumerate(prefix):
      if unpack_target_is_discard(tgt):
        continue
      slots.append(PyTupleUnpackSlot(target=tgt, get_index=i))
    return slots
  if prefix_count + suffix_count > arity:
    raise NotImplementedError(
      f"``PyTuple`` 解包目标过多：定长 {arity}，前缀 {prefix_count} + 后缀 {suffix_count}"
    )
  if star is not None and not isinstance(star.value, ast.Name):
    raise NotImplementedError("``PyTuple`` 解包 ``*`` 目标须为名称")
  slots = []
  for i, tgt in enumerate(prefix):
    if unpack_target_is_discard(tgt):
      continue
    slots.append(PyTupleUnpackSlot(target=tgt, get_index=i))
  if star is not None and star.value.id != "_":
    slice_start = prefix_count
    slice_stop = arity - suffix_count
    slots.append(
      PyTupleUnpackSlot(
        target=star.value,
        slice_start=slice_start,
        slice_stop=slice_stop,
      )
    )
  for j, tgt in enumerate(suffix):
    if unpack_target_is_discard(tgt):
      continue
    slots.append(PyTupleUnpackSlot(target=tgt, get_index=-(suffix_count - j)))
  return slots

def tuple_unpack_bound_names(elts: list[ast.expr]) -> list[str]:
  names: list[str] = []
  for elt in elts:
    match elt:
      case ast.Name(id=name) if name != "_":
        names.append(name)
      case ast.Starred(value=ast.Name(id=name)) if name != "_":
        names.append(name)
      case _:
        pass
  return names


def emit_pytuple_unpack_assignments(
  tr: "Translator",
  value: str,
  elts: list[ast.expr],
  types: list[str],
) -> None:
  from ..translator import temp_name
  from .parallel_assign_emit import emit_parallel_assign_targets

  unpack_tmp = temp_name("pytuple_unpack")
  tr.write_line(f"auto {unpack_tmp} = {value};")
  slots = pytuple_unpack_slots(elts, arity=len(types))
  temps: list[str] = []
  targets: list[ast.expr] = []
  for slot in slots:
    assert slot.target is not None
    tmp = temp_name("par")
    if slot.slice_start is not None:
      assert slot.slice_stop is not None
      mid_types = types[slot.slice_start : slot.slice_stop]
      if mid_types:
        cpp_type = f"PyTuple<{', '.join(mid_types)}>"
      else:
        cpp_type = "PyTuple<>"
      tr.write_line(
        f"{cpp_type} {tmp} = {unpack_tmp}.template "
        f"get_slice<{slot.slice_start}, {slot.slice_stop}>();"
      )
    else:
      idx = slot.get_index
      assert idx is not None
      et = types[idx] if idx >= 0 else types[len(types) + idx]
      tr.write_line(f"{et} {tmp} = {unpack_tmp}.template get<{idx}>();")
    temps.append(tmp)
    targets.append(slot.target)
  emit_parallel_assign_targets(tr, targets, temps)
