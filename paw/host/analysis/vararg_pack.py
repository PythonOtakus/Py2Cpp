"""``*args: T[:]`` — 整包译为 ``PyArray<T>``（与单形参 ``T[:]`` 相同）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import ast

from .ir import cpp_array_elem_type, cpp_array_ndim
from .type_pred import is_array_type

if TYPE_CHECKING:
  from .analyzer import TypeChecker


@dataclass(frozen=True)
class VarargPackInfo:
  param_name: str
  cpp_type: str

  @property
  def elem_cpp_type(self) -> str | None:
    return cpp_array_elem_type(self.cpp_type)


def resolve_vararg_pack(
  types: "TypeChecker",
  func: ast.FunctionDef,
  *,
  class_type_params: list[str] | None = None,
  class_typevar_tuple: str | None = None,
  self_class: str | None = None,
) -> VarargPackInfo | None:
  from .variadic_template import resolve_variadic_template

  if (
    resolve_variadic_template(
      func,
      class_type_params=class_type_params,
      class_typevar_tuple=class_typevar_tuple,
    )
    is not None
  ):
    return None
  va = func.args.vararg
  if va is None:
    return None
  if func.args.kwonlyargs:
    raise NotImplementedError("暂不支持 *args 后的仅关键字形参")
  if not va.annotation:
    return None
  from .ir import FuncTypeParams

  tparams = set(class_type_params or []) | set(
    FuncTypeParams.collect(func).template_names
  )
  ann_cpp = types.parse_type(
    va.annotation, tparams, self_class=self_class,
  )
  if not is_array_type(ann_cpp) or cpp_array_ndim(ann_cpp) != 1:
    raise NotImplementedError(
      f"可变参数 {va.arg} 须注解为 T[:]（堆一维数组），得到 {ann_cpp!r}",
    )
  return VarargPackInfo(param_name=va.arg, cpp_type=ann_cpp)
