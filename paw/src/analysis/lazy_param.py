"""``T @lazy`` / ``T @ref @lazy`` 形参：惰性实参 supplier（``PyCallable<V>``）。"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass

from .ir import (
  _matmult_marker_name,
  is_ref_type_annotation,
  iter_matmult_marker_names,
  strip_descriptor_type_annotation,
  strip_type_annotation_markers,
)


def is_lazy_type_annotation(ann: ast.expr | None) -> bool:
  """``V @lazy`` / ``V @ref @lazy``（``lazy`` 为最外层 ``MatMult`` 标记）。"""
  return _matmult_marker_name(ann, "lazy")


def strip_lazy_type_annotation(ann: ast.expr | None) -> ast.expr | None:
  if ann is None or not is_lazy_type_annotation(ann):
    return copy.deepcopy(ann) if ann is not None else None
  return copy.deepcopy(ann.left)


def lazy_param_inner_annotation(ann: ast.expr | None) -> ast.expr | None:
  """去掉最外层 ``@lazy``，保留 ``V`` / ``V @ref`` 等。"""
  if ann is None:
    return None
  return strip_lazy_type_annotation(ann)


def lazy_param_has_ref(ann: ast.expr | None) -> bool:
  inner = lazy_param_inner_annotation(ann)
  return is_ref_type_annotation(inner) or (
    inner is not None and "ref" in iter_matmult_marker_names(inner)
  )


def lazy_param_value_annotation(ann: ast.expr | None) -> ast.expr | None:
  """``@lazy`` / ``@ref`` 剥除后的底层类型（供 storage；不含 ``@ref``）。"""
  inner = lazy_param_inner_annotation(ann)
  if inner is None:
    return None
  out = strip_descriptor_type_annotation(inner)
  return strip_type_annotation_markers(out) or out


def lazy_supplier_cpp_type(value_cpp: str) -> str:
  base = value_cpp.rstrip("&").strip()
  return f"PyCallable<{base}>"


def lazy_supplier_is_none_expr(supplier_cpp: str) -> str:
  return f"({supplier_cpp}._func == nullptr)"


def lazy_supplier_invoke_expr(supplier_cpp: str, value_cpp: str) -> str:
  return f"{supplier_cpp}.__call__()"


@dataclass(frozen=True)
class LazyParamInfo:
  """函数/方法形参 ``name: T @lazy`` 的编译期元数据。"""

  value_cpp_type: str
  supplier_cpp_type: str
  materialized_ref: bool = False
  default_expr: ast.expr | None = None
