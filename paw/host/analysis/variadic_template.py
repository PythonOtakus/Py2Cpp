"""``def f[*Args](*args: Args)`` / ``def g[*Ts](*args)`` — C++ 形参包（与 ``*args: T[:]`` 区分）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import ast

from .patterns import auto_template_type_param_name
from .ir import strip_type_annotation_markers

if TYPE_CHECKING:
  from .analyzer import TypeChecker


@dataclass(frozen=True)
class VariadicTemplateInfo:
  pack_name: str
  param_name: str


def parse_function_type_params(
  func: ast.FunctionDef,
) -> tuple[list[str], tuple[str, ...], str | None]:
  """PEP 695 函数头：调用形参、``_U = …`` 捕获形参、至多一个 ``TypeVarTuple``。"""
  from .ir import typevar_default_is_capture

  regular: list[str] = []
  capture: list[str] = []
  typevar_tuple: str | None = None
  for p in getattr(func, "type_params", None) or ():
    if isinstance(p, ast.TypeVar):
      dv = getattr(p, "default_value", None)
      if typevar_default_is_capture(dv):
        capture.append(p.name)
      else:
        regular.append(p.name)
    elif isinstance(p, ast.TypeVarTuple):
      if typevar_tuple is not None:
        raise NotImplementedError("函数头至多一个 TypeVarTuple 形参包")
      typevar_tuple = p.name
  return regular, tuple(capture), typevar_tuple


_VARARG_PACK_AUTO_LEAF = "Ts"


def _vararg_pack_type_param_name(param_name: str, *, reserved: set[str]) -> str:
  """无注解 ``*args`` 自动形参包：固定 ``__Ts``（与形参名无关；与头内用户 ``Ts`` 等区分）。"""
  _ = param_name
  return auto_template_type_param_name(_VARARG_PACK_AUTO_LEAF, reserved=reserved)


def typevar_tuple_names_for_emit(
  func_ft: "FuncTypeParams",
  variadic_template: VariadicTemplateInfo | None,
) -> list[str]:
  """``template<typename...>`` 中须声明的 TypeVarTuple 名（去重、保序）。"""
  names: list[str] = []
  if func_ft.typevar_tuple:
    names.append(func_ft.typevar_tuple)
  if variadic_template is not None:
    pack = variadic_template.pack_name
    if pack not in names:
      names.append(pack)
  return names


def resolve_variadic_template(
  func: ast.FunctionDef,
  *,
  class_type_params: list[str] | None = None,
  class_typevar_tuple: str | None = None,
) -> VariadicTemplateInfo | None:
  """形参包：显式 ``*args: HeaderTuple`` 复用函数/类头 TypeVarTuple；无注解 ``*args`` 另增一包。"""
  _ = class_type_params
  va = func.args.vararg
  if va is None:
    return None
  if func.args.kwonlyargs:
    raise NotImplementedError("暂不支持 *args 后的仅关键字形参")
  regular, _capture, header_tuple = parse_function_type_params(func)
  if header_tuple is None and class_typevar_tuple is not None:
    header_tuple = class_typevar_tuple
  reserved = set(regular)
  if header_tuple is not None:
    reserved.add(header_tuple)
  if va.annotation is None:
    pack = _vararg_pack_type_param_name(va.arg, reserved=reserved)
    return VariadicTemplateInfo(pack_name=pack, param_name=va.arg)
  ann = strip_type_annotation_markers(va.annotation)
  if isinstance(ann, ast.Subscript) and isinstance(ann.slice, ast.Slice):
    return None
  if header_tuple is None:
    raise NotImplementedError(
      "``*args: …`` 带注解的可变参数包须配合函数头 ``TypeVarTuple``（如 ``def f[*Ts](*args: Ts)``）",
    )
  if not isinstance(ann, ast.Name) or ann.id != header_tuple:
    raise NotImplementedError(
      f"``*{va.arg}: …`` 须写 ``*{va.arg}: {header_tuple}``（与函数头 TypeVarTuple 同名）；"
      f"无注解 ``*{va.arg}`` 则自动另增形参包类型参数（勿写 ``*{header_tuple}``）",
    )
  return VariadicTemplateInfo(pack_name=header_tuple, param_name=va.arg)


def typevar_tuple_pack_from_type_node(
  node: ast.expr | None,
  typevar_tuple_names: frozenset[str] | set[str],
) -> str | None:
  """``(*Ts,)`` / ``tuple[*Ts]`` → 形参包名 ``Ts``（须在 ``typevar_tuple_names`` 内）。"""
  if node is None or not typevar_tuple_names:
    return None
  core = strip_type_annotation_markers(node)
  starred: ast.expr | None = None
  if isinstance(core, ast.Tuple) and len(core.elts) == 1:
    e0 = core.elts[0]
    if isinstance(e0, ast.Starred):
      starred = e0.value
  elif (
    isinstance(core, ast.Subscript)
    and isinstance(core.value, ast.Name)
    and core.value.id == "tuple"
    and isinstance(core.slice, ast.Tuple)
    and len(core.slice.elts) == 1
  ):
    e0 = core.slice.elts[0]
    if isinstance(e0, ast.Starred):
      starred = e0.value
  if isinstance(starred, ast.Name) and starred.id in typevar_tuple_names:
    return starred.id
  return None


def cpp_typevar_tuple_as_pytuple(pack_name: str) -> str:
  from .ir import cpp_ident

  return f"{cpp_ident('tuple')}<{pack_name}...>"


if TYPE_CHECKING:
  from .ir import FuncTypeParams  # noqa: F401
