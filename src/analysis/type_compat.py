"""C++ 类型字符串 ↔ TypeNode（Phase 0 过渡；新代码优先 AST → TypeNode）。"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .ir import (
  CPP_ARRAY2D_PREFIX,
  CPP_ARRAY3D_PREFIX,
  CPP_ARRAY_PREFIX,
  CPP_OPTIONAL_PREFIX,
  CPP_REFCount_PREFIX,
  CPP_SPAN2D_PREFIX,
  CPP_SPAN3D_PREFIX,
  CPP_SPAN_PREFIX,
  CPP_STACK_ARRAY2D_PREFIX,
  CPP_STACK_ARRAY3D_PREFIX,
  CPP_STACK_ARRAY_PREFIX,
  cpp_ident,
  cpp_template_base_and_args,
  cpp_template_inner_args,
  split_cpp_param_list,
  strip_cpp_ref,
)
from .type_node import TypeKind, TypeNode

if TYPE_CHECKING:
  from .ir import ClassInfo

_KNOWN_SCALARS = frozenset({
  "void",
  cpp_ident("int"),
  cpp_ident("int64"),
  cpp_ident("uint"),
  cpp_ident("uint64"),
  cpp_ident("uintptr"),
  cpp_ident("float"),
  cpp_ident("float64"),
  cpp_ident("bool"),
  cpp_ident("str"),
  cpp_ident("bytes"),
  cpp_ident("char"),
  cpp_ident("byte"),
  cpp_ident("PyNone"),
  cpp_ident("Never"),
  "c_str",
  "void*",
})


def _array_kind_for_prefix(prefix: str) -> str:
  return {
    CPP_ARRAY_PREFIX: "heap",
    CPP_ARRAY2D_PREFIX: "heap2d",
    CPP_ARRAY3D_PREFIX: "heap3d",
    CPP_STACK_ARRAY_PREFIX: "stack",
    CPP_STACK_ARRAY2D_PREFIX: "stack2d",
    CPP_STACK_ARRAY3D_PREFIX: "stack3d",
    CPP_SPAN_PREFIX: "span",
    CPP_SPAN2D_PREFIX: "span2d",
    CPP_SPAN3D_PREFIX: "span3d",
  }[prefix]


def _py_name_for_cpp_template_base(
  cpp_base: str,
  classes: dict[str, ClassInfo] | None,
) -> str:
  if not classes:
    return ""
  for info in classes.values():
    if info.cpp_name() == cpp_base:
      return info.name
  return ""


def type_node_from_cpp_string(
  cpp_type: str,
  *,
  classes: dict[str, ClassInfo] | None = None,
) -> TypeNode:
  """自 C++ 类型文本解析为 TypeNode（Phase 0/1 过渡 API）。"""
  raw = cpp_type.strip()
  if not raw:
    return TypeNode.void()
  if raw == "void":
    return TypeNode.void()
  if raw in (cpp_ident("Never"), "Never"):
    return TypeNode.never(cpp_ident("Never"))

  fn_m = re.match(r"^(.+?) \(\*\)\((.*)\)$", raw)
  if fn_m:
    ret = type_node_from_cpp_string(fn_m.group(1).strip(), classes=classes)
    arg_strs = split_cpp_param_list(fn_m.group(2))
    args = tuple(
      type_node_from_cpp_string(a, classes=classes) for a in arg_strs
    )
    return TypeNode.function_ptr(ret, *args)
  fn_void_m = re.match(r"^(.+?) \(\*\)\(\)$", raw)
  if fn_void_m:
    ret = type_node_from_cpp_string(fn_void_m.group(1).strip(), classes=classes)
    return TypeNode.function_ptr(ret)

  if raw.endswith("*"):
    return TypeNode.pointer(type_node_from_cpp_string(raw[:-1].strip(), classes=classes))

  if raw.endswith("&"):
    return TypeNode.ref(type_node_from_cpp_string(raw[:-1].strip(), classes=classes))

  t = raw

  optional_inner = cpp_template_inner_args(t, CPP_OPTIONAL_PREFIX)
  if optional_inner is not None:
    return TypeNode.optional(
      type_node_from_cpp_string(optional_inner, classes=classes),
    )

  refcount_inner = cpp_template_inner_args(t, CPP_REFCount_PREFIX)
  if refcount_inner is not None:
    return TypeNode.refcount(
      type_node_from_cpp_string(refcount_inner, classes=classes),
    )

  for prefix in (
    CPP_ARRAY3D_PREFIX,
    CPP_ARRAY2D_PREFIX,
    CPP_ARRAY_PREFIX,
    CPP_STACK_ARRAY3D_PREFIX,
    CPP_STACK_ARRAY2D_PREFIX,
    CPP_STACK_ARRAY_PREFIX,
    CPP_SPAN3D_PREFIX,
    CPP_SPAN2D_PREFIX,
    CPP_SPAN_PREFIX,
  ):
    inner = cpp_template_inner_args(t, prefix)
    if inner is not None:
      return TypeNode.array(
        type_node_from_cpp_string(inner, classes=classes),
        kind=_array_kind_for_prefix(prefix),
      )

  parsed = cpp_template_base_and_args(t)
  if parsed is not None:
    base, arg_strs = parsed
    args = tuple(
      type_node_from_cpp_string(a, classes=classes) for a in arg_strs
    )
    py = _py_name_for_cpp_template_base(base, classes)
    return TypeNode.template(py, base, *args)

  if t in _KNOWN_SCALARS:
    return TypeNode.scalar(t)

  if classes:
    parsed = cpp_template_base_and_args(t)
    if parsed is not None:
      base, arg_strs = parsed
      for info in classes.values():
        if info.cpp_name() == base:
          args = tuple(
            type_node_from_cpp_string(a, classes=classes) for a in arg_strs
          )
          return TypeNode.template(info.name, base, *args)
    for info in classes.values():
      if info.cpp_name() == t:
        if info.type_params and not info.typevar_tuple:
          return TypeNode.template(info.name, info.cpp_name())
        return TypeNode.scalar(info.cpp_name())

  return TypeNode.type_param(t)


def type_node_to_cpp_string(node: TypeNode) -> str:
  """默认 CLASS_BODY 策略 render。"""
  from .type_render import CLASS_BODY

  return node.render(CLASS_BODY)


def split_cpp_template(cpp: str) -> tuple[str, list[str]]:
  """``PyList<PyInt>`` → ``(\"PyList\", [\"PyInt\"])``；统一模板拆分入口。"""
  parsed = cpp_template_base_and_args(strip_cpp_ref(cpp.strip()))
  if parsed is None:
    return cpp.strip(), []
  base, args = parsed
  return base, args
