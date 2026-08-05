"""翻译中间表示（IR）：预处理阶段的结构化元数据。

本模块不依赖 AST 遍历逻辑，仅存放由 ``analyzer`` 填充、由 ``translator`` 消费的
数据类与工具函数。类型表达式结构化 IR 见 ``type_node`` / ``docs/type-node.md``。

主要类型
--------
- ``ClassInfo``：用户/标准库类的字段、方法、``@refcount`` 标记、预计算签名。
- ``MethodSig`` / ``FunctionSig``：C++ 声明与实现用的参数串、返回类型、文档行。
- ``ModuleAnalysis``：模块级 ``///`` 文档与 ``#include`` 依赖。
- ``FuncTypeParams``：无类型注解形参对应的模板参数 ``T0, T1, …``。
"""
from __future__ import annotations

import ast
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from .patterns import auto_template_type_param_name, escape_cpp_param, property_getter_method_for

from ..constant.language import CPP_RENAME
from ..constant.type_markers import TYPE_MARKER_CLASSES


def _cpp_tpl_prefix(py_class: str) -> str:
  from .stubs.template_prefix_stubs import load_cpp_template_type_prefixes

  return load_cpp_template_type_prefixes()[py_class]


# 翻译后 C++ 模板类型前缀（``@native_name`` + ``CPP_TEMPLATE_PREFIX_OVERRIDES``）
CPP_ARRAY_PREFIX = _cpp_tpl_prefix("array")
CPP_ARRAY2D_PREFIX = _cpp_tpl_prefix("array2d")
CPP_ARRAY3D_PREFIX = _cpp_tpl_prefix("array3d")
CPP_STACK_ARRAY_PREFIX = _cpp_tpl_prefix("stack_array")
CPP_STACK_ARRAY2D_PREFIX = _cpp_tpl_prefix("stack_array2d")
CPP_STACK_ARRAY3D_PREFIX = _cpp_tpl_prefix("stack_array3d")
CPP_SPAN_PREFIX = _cpp_tpl_prefix("span")
CPP_SPAN2D_PREFIX = _cpp_tpl_prefix("span2d")
CPP_SPAN3D_PREFIX = _cpp_tpl_prefix("span3d")
CPP_LIST_PREFIX = _cpp_tpl_prefix("list")
CPP_DICT_PREFIX = _cpp_tpl_prefix("dict")
CPP_SET_PREFIX = _cpp_tpl_prefix("set")
CPP_FROZENSET_PREFIX = _cpp_tpl_prefix("frozenset")
CPP_FROZENLIST_PREFIX = _cpp_tpl_prefix("frozenlist")
CPP_FROZENDICT_PREFIX = _cpp_tpl_prefix("frozendict")
CPP_DEQUE_PREFIX = _cpp_tpl_prefix("deque")
CPP_TUPLE_PREFIX = _cpp_tpl_prefix("tuple")
CPP_COUNTER_PREFIX = _cpp_tpl_prefix("Counter")
CPP_CHUNK_DEQUE_PREFIX = _cpp_tpl_prefix("ChunkDeque")
CPP_SLICE_PREFIX = _cpp_tpl_prefix("slice")
CPP_REFCount_PREFIX = _cpp_tpl_prefix("RefCount")
CPP_RESULT_PREFIX = _cpp_tpl_prefix("IterResult")
CPP_FAULT_RESULT_PREFIX = _cpp_tpl_prefix("Result")
CPP_OPTIONAL_PREFIX = _cpp_tpl_prefix("Optional")
CPP_PY_CALLABLE_PREFIX = "PyCallable<"
CPP_PY_GENERATOR_PREFIX = "PyGenerator<"
CPP_PY_COROUTINE_PREFIX = "PyCoroutine<"
CPP_PY_ASYNC_GENERATOR_PREFIX = "PyAsyncGenerator<"
CPP_PY_ITERABLE_PREFIX = "PyIterable<"


_type_pred_mod = None
_type_extract_mod = None


def _type_pred():
  global _type_pred_mod
  if _type_pred_mod is None:
    from . import type_pred as tp
    _type_pred_mod = tp
  return _type_pred_mod


def _type_extract():
  global _type_extract_mod
  if _type_extract_mod is None:
    from . import type_extract as te
    _type_extract_mod = te
  return _type_extract_mod

INT_FIELDS = frozenset({
  "_length", "_size", "_index", "_capacity", "_bucket",
  "_i", "_j", "_k",
  "_current", "_step", "_stop", "_start", "code", "first",
})


def collect_owned_fields_from_inits(
  inits: list[ast.FunctionDef],
) -> dict[str, tuple[str, str]]:
  """从各 ``__init__`` 中 ``self.f = alloc[...]()`` / ``allocArray[...](...)`` 收集需释放字段。"""
  owned: dict[str, tuple[str, str]] = {}
  for init in inits:
    for stmt in ast.walk(init):
      if not isinstance(stmt, ast.Assign):
        continue
      for target in stmt.targets:
        if not (
          isinstance(target, ast.Attribute)
          and isinstance(target.value, ast.Name)
          and target.value.id == "self"
        ):
          continue
        field = target.attr
        match stmt.value:
          case ast.Call(
            func=ast.Subscript(value=ast.Name(id="alloc"), slice=sl),
            args=[],
          ) if isinstance(sl, ast.Name):
            owned[field] = (sl.id, "free")
          case ast.Call(
            func=ast.Subscript(value=ast.Name(id="allocArray"), slice=sl),
            args=_,
          ) if isinstance(sl, ast.Name):
            owned[field] = (sl.id, "freeArray")
          case ast.Call(
            func=ast.Subscript(
              value=ast.Attribute(
                value=ast.Name(id=alloc_cls),
                attr=method,
              ),
              slice=sl,
            ),
            args=_,
          ) if alloc_cls == "Alloc" and method in (
            "alloc_array",
            "alloc_raw_array",
          ) and isinstance(sl, ast.Name):
            owned[field] = (sl.id, "freeArray")
  return owned


def collect_owned_array_sizes(
  inits: list[ast.FunctionDef],
) -> dict[str, int]:
  """``allocArray[T](n)`` 中 ``n`` 为整数字面量时记录元素个数。"""
  sizes: dict[str, int] = {}
  for init in inits:
    for stmt in ast.walk(init):
      if not isinstance(stmt, ast.Assign):
        continue
      for target in stmt.targets:
        if not (
          isinstance(target, ast.Attribute)
          and isinstance(target.value, ast.Name)
          and target.value.id == "self"
        ):
          continue
        field = target.attr
        match stmt.value:
          case ast.Call(
            func=ast.Subscript(value=ast.Name(id="allocArray"), slice=_),
            args=[ast.Constant(value=n)],
          ) if isinstance(n, int):
            sizes[field] = n
          case ast.Call(
            func=ast.Subscript(
              value=ast.Attribute(value=ast.Name(id=alloc_cls), attr=method),
              slice=_,
            ),
            args=[ast.Constant(value=n)],
          ) if alloc_cls == "Alloc" and method in (
            "alloc_array",
            "alloc_raw_array",
          ) and isinstance(n, int):
            sizes[field] = n
          case ast.Call(
            func=ast.Subscript(value=ast.Name(id="allocArray"), slice=_),
            args=[arg],
          ):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
              sizes[field] = arg.value
  return sizes


def codegen_file_header_lines(source_note: str, generated_at: str) -> list[str]:
  """生成 ``.h`` / ``.inl`` 等文件顶部的来源与生成时间注释行。"""
  return [
    f"// 由 py2cpp 根据 {source_note} 生成",
    f"// {generated_at}",
  ]


def cpp_type_rename(name: str) -> str | None:
  """Python 类型名 → C++ 名；无映射则 ``None``。"""
  from .stubs.class_stubs import load_stdlib_native_names

  ren = load_stdlib_native_names().get(name)
  if ren is not None:
    return ren
  if name in CPP_RENAME:
    return CPP_RENAME[name]
  return None


def cpp_ident(name: str) -> str:
  """Python 标识符 → C++ 标识符（``@native_name`` + 标量重命名表）。"""
  return cpp_type_rename(name) or name


def cpp_type_param_template_name(py_name: str) -> str:
  """PEP 695 类/函数形参在 C++ ``template<>`` 中的名字（``Element`` → ``_Element``）。"""
  if py_name.startswith("_"):
    return py_name
  return f"_{py_name}"


def is_type_param_forward_alias(
  alias: TypeAliasInfo,
  type_params: set[str] | frozenset[str],
) -> bool:
  """``type Element = T`` 且 ``T`` 为类形参 → 由 ``using Element = _Element`` 自动生成。"""
  if alias.member_constraint or alias.is_conditional:
    return False
  return isinstance(alias.value, ast.Name) and alias.value.id in type_params


_SCALAR_TYPE_STATIC_ATTR_CPP: dict[tuple[str, str], str] = {
  ("float", "Inf"): "PY2CPP_FLOAT_INF",
  ("float", "NaN"): "PY2CPP_FLOAT_NAN",
  ("float64", "Inf"): "PY2CPP_FLOAT64_INF",
  ("float64", "NaN"): "PY2CPP_FLOAT64_NAN",
  ("int", "Min"): "PY2CPP_INT_MIN",
  ("int", "Max"): "PY2CPP_INT_MAX",
  ("int64", "Min"): "PY2CPP_INT64_MIN",
  ("int64", "Max"): "PY2CPP_INT64_MAX",
  ("uint", "Min"): "PY2CPP_UINT_MIN",
  ("uint", "Max"): "PY2CPP_UINT_MAX",
  ("uint64", "Min"): "PY2CPP_UINT64_MIN",
  ("uint64", "Max"): "PY2CPP_UINT64_MAX",
  ("float", "Min"): "PY2CPP_FLOAT_MIN",
  ("float", "Max"): "PY2CPP_FLOAT_MAX",
  ("float64", "Min"): "PY2CPP_FLOAT64_MIN",
  ("float64", "Max"): "PY2CPP_FLOAT64_MAX",
}

_SCALAR_TYPE_STATIC_METHOD_CPP: dict[tuple[str, str], str] = {
  ("float", "isfinite"): "PY2CPP_ISFINITE_F({})",
  ("float", "isInf"): "PY2CPP_ISINF_F({})",
  ("float", "isNaN"): "PY2CPP_ISNAN_F({})",
  ("float64", "isfinite"): "PY2CPP_ISFINITE_F64({})",
  ("float64", "isInf"): "PY2CPP_ISINF_F64({})",
  ("float64", "isNaN"): "PY2CPP_ISNAN_F64({})",
}


def scalar_type_static_attr_cpp(type_name: str, attr: str) -> str | None:
  """``float.Inf`` / ``int.Min`` 等 → ``py_types.h`` 宏。"""
  return _SCALAR_TYPE_STATIC_ATTR_CPP.get((type_name, attr))


def scalar_type_static_attr_from_expr(node: ast.expr) -> str | None:
  """``int.Min`` 等 ``Attribute`` → ``py_types.h`` 宏。"""
  if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
    return scalar_type_static_attr_cpp(node.value.id, node.attr)
  return None


def scalar_type_static_method_cpp(
  type_name: str, method: str, arg_cpp: str,
) -> str | None:
  """``float64.isInf(x)`` 等 → ``py_types.h`` 宏调用。"""
  tpl = _SCALAR_TYPE_STATIC_METHOD_CPP.get((type_name, method))
  if tpl is None:
    return None
  return tpl.format(arg_cpp)


def delegate_base_name(cpp_type: str) -> str | None:
  """``Func<int>`` → ``Func``；非委托模板则 ``None``。"""
  if "<" not in cpp_type or not cpp_type.endswith(">"):
    return None
  return cpp_type.split("<", 1)[0].strip()


def cpp_make_py_generator_expr(erased_type: str, concrete_expr: str) -> str:
  args = _type_extract().generator_type_args(erased_type)
  if args is None:
    return f"makeGenerator({concrete_expr})"
  y, s, r = args
  return f"makeGenerator<{y}, {s}, {r}>({concrete_expr})"


def cpp_make_generator_expr(erased_type: str, concrete_expr: str) -> str:
  return cpp_make_py_generator_expr(erased_type, concrete_expr)


def cpp_make_py_coroutine_expr(erased_type: str, concrete_expr: str) -> str:
  args = _type_extract().coroutine_type_args(erased_type)
  if args is None:
    return f"makeCoroutine({concrete_expr})"
  y, s, r = args
  return f"makeCoroutine<{y}, {s}, {r}>({concrete_expr})"


def cpp_make_coroutine_expr(erased_type: str, concrete_expr: str) -> str:
  return cpp_make_py_coroutine_expr(erased_type, concrete_expr)


def cpp_make_py_async_generator_expr(erased_type: str, concrete_expr: str) -> str:
  args = _type_extract().async_generator_type_args(erased_type)
  if args is None:
    return f"makeAsyncGenerator({concrete_expr})"
  y, s = args
  return f"makeAsyncGenerator<{y}, {s}>({concrete_expr})"


def cpp_make_async_generator_expr(erased_type: str, concrete_expr: str) -> str:
  return cpp_make_py_async_generator_expr(erased_type, concrete_expr)


def cpp_make_erased_storage_expr(erased_type: str, concrete_expr: str) -> str:
  from .stubs.protocol_erase_stubs import cpp_make_erased_protocol_expr

  t = strip_cpp_type_qualifiers(erased_type)
  if _type_pred().is_py_generator_type(t):
    return cpp_make_generator_expr(t, concrete_expr)
  if _type_pred().is_py_coroutine_type(t):
    return cpp_make_coroutine_expr(t, concrete_expr)
  if _type_pred().is_py_async_generator_type(t):
    return cpp_make_async_generator_expr(t, concrete_expr)
  return cpp_make_erased_protocol_expr(t, concrete_expr)


def format_cpp_callable_var_decl(cpp_type: str, var_name: str) -> str | None:
  """``PyInt (*)(PyInt)`` + ``cb`` → ``PyInt (*cb)(PyInt)``（MSVC 可声明）。"""
  import re

  s = cpp_type.strip()
  m = re.match(r"^(.+?) \(\*\)\((.*)\)$", s)
  if m:
    return f"{m.group(1)} (*{var_name})({m.group(2)})"
  m = re.match(r"^(.+?) \(\*\)\(\)$", s)
  if m:
    return f"{m.group(1)} (*{var_name})()"
  return None


def format_callable_var_decl_from_node(node: "TypeNode", var_name: str) -> str | None:
  """``TypeNode.function_ptr`` → 带变量名的 C++ 形参声明。"""
  from .type_node import TypeKind
  from .type_render import CLASS_BODY

  if node.kind != TypeKind.FUNCTION_PTR or node.inner is None:
    return None
  ret = node.inner.render(CLASS_BODY)
  if not node.args:
    return f"{ret} (*{var_name})()"
  args = ", ".join(a.render(CLASS_BODY) for a in node.args)
  return f"{ret} (*{var_name})({args})"


def strip_cpp_type_qualifiers(cpp_type: str) -> str:
  """去掉前缀 ``const`` 与后缀 ``*`` / ``&``，便于识别 ``const PyList<T>*`` 等。"""
  t = cpp_type.strip()
  while True:
    changed = False
    if t.startswith("const "):
      t = t[6:].lstrip()
      changed = True
    if t.endswith("*"):
      t = t[:-1].rstrip()
      changed = True
    if t.endswith("&"):
      t = t[:-1].rstrip()
      changed = True
    if not changed:
      break
  return t


def cpp_tuple_element_types(cpp_type: str) -> list[str]:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not _type_pred().is_tuple_type(t):
    return []
  inner = t[len(CPP_TUPLE_PREFIX) : -1].strip()
  if not inner or inner.endswith("..."):
    return []
  return split_cpp_template_args(inner)


def cpp_tuple_arity(cpp_type: str) -> int | None:
  elems = cpp_tuple_element_types(cpp_type)
  if not elems and _type_pred().is_tuple_type(cpp_type):
    inner = strip_cpp_type_qualifiers(cpp_type)[len(CPP_TUPLE_PREFIX) : -1].strip()
    if not inner:
      return 0
    return None
  return len(elems)


def is_sequence_match_subject(cpp_type: str) -> bool:
  t = strip_cpp_type_qualifiers(cpp_type)
  return (
    _type_pred().is_list_type(t)
    or _type_pred().is_frozenlist_type(t)
    or _type_pred().is_deque_type(t)
    or _type_pred().is_str_type(t)
    or _type_pred().is_bytes_type(t)
    or _type_pred().is_tuple_type(t)
    or _type_pred().is_stack_array_type(t)
    or (_type_pred().is_array_type(t) and cpp_array_ndim(t) == 1)
    or _type_pred().is_span_type(t)
  )


def sequence_match_elem_cpp(cpp_type: str) -> str | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if _type_pred().is_list_type(t):
    return _type_extract().list_elem_type(t)
  if _type_pred().is_frozenlist_type(t):
    return _type_extract().frozenlist_elem_type(t)
  if _type_pred().is_deque_type(t):
    return _type_extract().deque_elem_type(t)
  if _type_pred().is_str_type(t):
    return cpp_ident("char")
  if _type_pred().is_bytes_type(t):
    return cpp_ident("byte")
  if _type_pred().is_tuple_type(t):
    elems = cpp_tuple_element_types(t)
    if len(elems) == 1:
      return elems[0]
    return None
  if _type_pred().is_stack_array_type(t):
    return cpp_stack_array_elem_type(t)
  if _type_pred().is_array_type(t) and cpp_array_ndim(t) == 1:
    return cpp_array_elem_type(t)
  if _type_pred().is_span_type(t):
    return cpp_span_elem_type(t)
  return None


def is_mapping_match_subject(cpp_type: str) -> bool:
  t = strip_cpp_type_qualifiers(cpp_type)
  return (
    _type_pred().is_dict_type(t)
    or _type_pred().is_frozendict_type(t)
    or _type_pred().is_counter_type(t)
  )


def mapping_match_key_value_cpp(cpp_type: str) -> tuple[str, str] | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if _type_pred().is_dict_type(t) or _type_pred().is_frozendict_type(t):
    inner = _type_extract().dict_type_args(t) or _type_extract().frozendict_type_args(t)
    if not inner:
      return None
    parts = split_cpp_template_args(inner)
    if len(parts) != 2:
      return None
    return parts[0], parts[1]
  if _type_pred().is_counter_type(t):
    inner = t[len(CPP_COUNTER_PREFIX) : -1].strip()
    parts = split_cpp_template_args(inner)
    if len(parts) < 1:
      return None
    key_t = parts[0]
    val_t = parts[1] if len(parts) > 1 else cpp_ident("int")
    return key_t, val_t
  return None


def cpp_array_ndim(cpp_type: str) -> int | None:
  t = cpp_type.strip()
  if t.startswith(CPP_ARRAY3D_PREFIX) and t.endswith(">"):
    return 3
  if t.startswith(CPP_ARRAY2D_PREFIX) and t.endswith(">"):
    return 2
  if t.startswith(CPP_ARRAY_PREFIX) and t.endswith(">"):
    return 1
  return None


def cpp_array_elem_type(cpp_type: str) -> str | None:
  for prefix in (CPP_ARRAY_PREFIX, CPP_ARRAY2D_PREFIX, CPP_ARRAY3D_PREFIX):
    inner = cpp_template_inner_args(cpp_type, prefix)
    if inner is not None:
      parts = split_cpp_template_args(inner)
      return parts[0].strip() if parts else None
  return None


def parse_slice_fixed_size(slice_node: ast.expr) -> int | None:
  """``T[:N]`` 中 ``N`` 为正整数字面量时返回 ``N``（栈定长数组）。

  注解 ``int[:10]`` 在 AST 中为 ``Slice(upper=Constant(10))``，非裸 ``Constant``。
  """
  match slice_node:
    case ast.Constant(value=n) if isinstance(n, int) and n > 0:
      return n
    case ast.Slice(upper=ast.Constant(value=n), lower=lo, step=step):
      if not isinstance(n, int) or n <= 0:
        return None
      if lo is not None and not (
        isinstance(lo, ast.Constant) and lo.value in (0, None)
      ):
        return None
      if step is not None and not (
        isinstance(step, ast.Constant) and step.value in (1, None)
      ):
        return None
      return n
    case _:
      return None


def parse_subslice_bounds(slice_node: ast.expr) -> tuple[int, int] | None:
  """``T[i:j]``（``i``、``j`` 为整数字面量，``step`` 缺省或 1）→ ``(offset, length)``。"""
  match slice_node:
    case ast.Slice(
      lower=ast.Constant(value=lo),
      upper=ast.Constant(value=hi),
      step=step,
    ):
      if not isinstance(lo, int) or not isinstance(hi, int):
        return None
      if step is not None and not (
        isinstance(step, ast.Constant) and step.value in (1, None)
      ):
        return None
      if hi <= lo:
        return None
      return (lo, hi - lo)
    case _:
      return None


def _slice_int_literal(node: ast.expr | None) -> int | None:
  if node is None:
    return None
  if isinstance(node, ast.Constant) and isinstance(node.value, int):
    return node.value
  if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
    inner = node.operand
    if isinstance(inner, ast.Constant) and isinstance(inner.value, int):
      return -inner.value
  return None


def parse_pytuple_slice_template_bounds(
  slice_node: ast.expr,
  *,
  arity: int,
) -> tuple[int, int] | None:
  """``PyTuple`` 定长切片 ``s[i:j]``（字面量界、``step`` 缺省或 1）→ ``get_slice<start, stop>`` 模板实参（半开区间，可含负索引）。"""
  match slice_node:
    case ast.Slice(lower=lo, upper=hi, step=step):
      if step is not None and not (
        isinstance(step, ast.Constant) and step.value in (1, None)
      ):
        return None
      if lo is None:
        start = 0
      else:
        start = _slice_int_literal(lo)
        if start is None:
          return None
      if hi is None:
        stop = arity
      else:
        stop = _slice_int_literal(hi)
        if stop is None:
          return None
      return (start, stop)
    case _:
      return None


def cpp_stack_array_type(
  elem_cpp: str,
  length: int | str,
  offset: int | str = 0,
) -> str:
  """``T[:N]`` / ``T[i:j]`` → ``PyStackArray<T, Length, Offset>``。"""
  if isinstance(length, str):
    length = f"(({length}) > 0 ? ({length}) : 0)"
  elif isinstance(length, int) and length <= 0:
    length = 0
  return f"{CPP_STACK_ARRAY_PREFIX}{elem_cpp}, {length}, {offset}>"


def cpp_stack_array2d_type(
  elem_cpp: str,
  rows: int,
  cols: int,
  row_off: int = 0,
  col_off: int = 0,
) -> str:
  """``T[:R, :C]`` / 子矩形 → ``PyStackArray2D<…>``。"""
  return (
    f"{CPP_STACK_ARRAY2D_PREFIX}{elem_cpp}, {rows}, {cols}, "
    f"{row_off}, {col_off}>"
  )


def cpp_stack_array3d_type(
  elem_cpp: str,
  d0: int,
  d1: int,
  d2: int,
  o0: int = 0,
  o1: int = 0,
  o2: int = 0,
) -> str:
  """``T[:D0, :D1, :D2]`` / 子块 → ``PyStackArray3D<…>``。"""
  return (
    f"{CPP_STACK_ARRAY3D_PREFIX}{elem_cpp}, {d0}, {d1}, {d2}, "
    f"{o0}, {o1}, {o2}>"
  )


def _parse_cpp_dim_offset_template(
  inner: str,
  num_dims: int,
) -> tuple[str, tuple[int, ...], tuple[int, ...]] | None:
  parts: list[str] = []
  depth = 0
  start = 0
  for i, ch in enumerate(inner):
    if ch == "<":
      depth += 1
    elif ch == ">":
      depth -= 1
    elif ch == "," and depth == 0:
      parts.append(inner[start:i].strip())
      start = i + 1
  parts.append(inner[start:].strip())
  need = 1 + num_dims * 2
  if len(parts) != need:
    return None
  elem = parts[0]
  dims: list[int] = []
  offs: list[int] = []
  for i in range(num_dims):
    ds = parts[1 + i].strip()
    os = parts[1 + num_dims + i].strip()
    if not ds.isdigit() or not os.isdigit():
      return None
    dim = int(ds)
    off = int(os)
    if dim <= 0:
      return None
    dims.append(dim)
    offs.append(off)
  return elem, tuple(dims), tuple(offs)


def parse_cpp_stack_array2d_type(
  cpp_type: str,
) -> tuple[str, int, int, int, int] | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_STACK_ARRAY2D_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_STACK_ARRAY2D_PREFIX) : -1]
  parsed = _parse_cpp_dim_offset_template(inner, 2)
  if parsed is None:
    return None
  elem, dims, offs = parsed
  return (elem, dims[0], dims[1], offs[0], offs[1])


def parse_cpp_stack_array3d_type(
  cpp_type: str,
) -> tuple[str, int, int, int, int, int, int] | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_STACK_ARRAY3D_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_STACK_ARRAY3D_PREFIX) : -1]
  parsed = _parse_cpp_dim_offset_template(inner, 3)
  if parsed is None:
    return None
  elem, dims, offs = parsed
  return (elem, dims[0], dims[1], dims[2], offs[0], offs[1], offs[2])


def cpp_stack_array_ndim(cpp_type: str) -> int | None:
  if parse_cpp_stack_array_type(cpp_type) is not None:
    return 1
  if parse_cpp_stack_array2d_type(cpp_type) is not None:
    return 2
  if parse_cpp_stack_array3d_type(cpp_type) is not None:
    return 3
  return None


def cpp_stack_array_elem_type_any(cpp_type: str) -> str | None:
  for parser in (
    parse_cpp_stack_array_type,
    parse_cpp_stack_array2d_type,
    parse_cpp_stack_array3d_type,
  ):
    parsed = parser(cpp_type)
    if parsed is not None:
      return parsed[0]
  return None


def cpp_span_type(elem_cpp: str) -> str:
  """``span[T]`` → ``PySpan<T>``。"""
  return f"{CPP_SPAN_PREFIX}{elem_cpp}>"


def cpp_span2d_type(elem_cpp: str) -> str:
  return f"{CPP_SPAN2D_PREFIX}{elem_cpp}>"


def cpp_span3d_type(elem_cpp: str) -> str:
  return f"{CPP_SPAN3D_PREFIX}{elem_cpp}>"


def parse_cpp_span2d_type(cpp_type: str) -> str | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_SPAN2D_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_SPAN2D_PREFIX) : -1].strip()
  return inner if inner else None


def parse_cpp_span3d_type(cpp_type: str) -> str | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_SPAN3D_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_SPAN3D_PREFIX) : -1].strip()
  return inner if inner else None


def cpp_span_ndim(cpp_type: str) -> int | None:
  if parse_cpp_span_type(cpp_type) is not None:
    return 1
  if parse_cpp_span2d_type(cpp_type) is not None:
    return 2
  if parse_cpp_span3d_type(cpp_type) is not None:
    return 3
  return None


def cpp_span_elem_type_any(cpp_type: str) -> str | None:
  for parser in (parse_cpp_span_type, parse_cpp_span2d_type, parse_cpp_span3d_type):
    elem = parser(cpp_type)
    if elem is not None:
      return elem
  return None


def _parse_cpp_length_offset_template(
  inner: str,
) -> tuple[str, int, int] | None:
  parts: list[str] = []
  depth = 0
  start = 0
  for i, ch in enumerate(inner):
    if ch == "<":
      depth += 1
    elif ch == ">":
      depth -= 1
    elif ch == "," and depth == 0:
      parts.append(inner[start:i].strip())
      start = i + 1
  parts.append(inner[start:].strip())
  if len(parts) == 2:
    elem = parts[0]
    length_s = parts[1]
    offset_s = "0"
  elif len(parts) == 3:
    elem = parts[0]
    length_s = parts[1]
    offset_s = parts[2]
  else:
    return None
  if not length_s.isdigit():
    return None
  length = int(length_s)
  if length <= 0:
    return None
  if not offset_s.isdigit():
    return None
  offset = int(offset_s)
  return (elem, length, offset)


def parse_cpp_stack_array_type(
  cpp_type: str,
) -> tuple[str, int, int] | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_STACK_ARRAY_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_STACK_ARRAY_PREFIX) : -1]
  return _parse_cpp_length_offset_template(inner)


def parse_cpp_span_type(cpp_type: str) -> str | None:
  t = strip_cpp_type_qualifiers(cpp_type)
  if not t.startswith(CPP_SPAN_PREFIX) or not t.endswith(">"):
    return None
  inner = t[len(CPP_SPAN_PREFIX) : -1].strip()
  return inner if inner else None


def cpp_stack_array_elem_type(cpp_type: str) -> str | None:
  return cpp_stack_array_elem_type_any(cpp_type)


def cpp_stack_array_size(cpp_type: str) -> int | None:
  """逻辑长度 ``Length``（``__len__`` / ``len``）。"""
  parsed = parse_cpp_stack_array_type(cpp_type)
  return parsed[1] if parsed is not None else None


def cpp_stack_array_offset(cpp_type: str) -> int | None:
  parsed = parse_cpp_stack_array_type(cpp_type)
  return parsed[2] if parsed is not None else None


def cpp_stack_array_iterator_type(cpp_type: str) -> str | None:
  """``PyStackArray<T, L, O>`` → ``PyStackArrayIterator<T, L, O>``。"""
  parsed = parse_cpp_stack_array_type(cpp_type)
  if parsed is None:
    return None
  elem, length, offset = parsed
  return f"PyStackArrayIterator<{elem}, {length}, {offset}>"


def cpp_span_elem_type(cpp_type: str) -> str | None:
  return cpp_span_elem_type_any(cpp_type)


def cpp_span_var_decl(cpp_type: str, name: str) -> str:
  elem = parse_cpp_span_type(cpp_type)
  if elem is None:
    return f"{cpp_type} {name}"
  return f"{cpp_span_type(elem)} {name}"


def cpp_stack_array_var_decl(cpp_type: str, name: str) -> str:
  parsed3 = parse_cpp_stack_array3d_type(cpp_type)
  if parsed3 is not None:
    elem, d0, d1, d2, o0, o1, o2 = parsed3
    return f"{cpp_stack_array3d_type(elem, d0, d1, d2, o0, o1, o2)} {name}"
  parsed2 = parse_cpp_stack_array2d_type(cpp_type)
  if parsed2 is not None:
    elem, rows, cols, row_off, col_off = parsed2
    return f"{cpp_stack_array2d_type(elem, rows, cols, row_off, col_off)} {name}"
  parsed = parse_cpp_stack_array_type(cpp_type)
  if parsed is None:
    return f"{cpp_type} {name}"
  elem, length, offset = parsed
  return f"{cpp_stack_array_type(elem, length, offset)} {name}"


def cpp_stack_array_field_decl(cpp_type: str, name: str) -> str:
  """兼容旧名：与 ``cpp_stack_array_var_decl`` 相同（统一为 ``PyStackArray`` 对象）。"""
  return cpp_stack_array_var_decl(cpp_type, name)


def cpp_iterator_type(iterator_py: str, elem: str, elem2: str | None = None) -> str:
  """``list_iterator`` + ``T`` → ``PyListIterator<T>``；双参数形如 ``dict_key_iterator<K,V>``。"""
  if elem2 is not None:
    return cpp_template_type(iterator_py, f"{elem}, {elem2}")
  return cpp_template_type(iterator_py, elem)


def cpp_template_type(py_name: str, args: str) -> str:
  """``list`` + ``int`` → ``PyList<PyInt>``（Python 名 → C++ 模板）。"""
  return f"{cpp_ident(py_name)}<{args}>"


_ALLOCATOR_CONTAINER_PREFIXES = (
  CPP_LIST_PREFIX,
  CPP_FROZENLIST_PREFIX,
  CPP_ARRAY_PREFIX,
)


def cpp_fill_allocator_default_args(cpp_type: str) -> str:
  """``PyList<T>`` / ``PyFrozenList<T>`` / ``PyArray<T>`` 单实参 → 补 NTTP ``0``（纯堆）。"""
  s = cpp_type.rstrip()
  if not s.endswith(">"):
    return cpp_type
  for prefix in _ALLOCATOR_CONTAINER_PREFIXES:
    idx = s.find(prefix)
    if idx < 0:
      continue
    if "<" in s[:idx]:
      continue
    inner = s[idx + len(prefix) : -1]
    parts = split_cpp_template_args(inner)
    if len(parts) != 1:
      continue
    return (
      f"{s[:idx]}{prefix}{parts[0]}, 0>"
    )
  return cpp_type


def cpp_fill_counter_default_args(cpp_type: str) -> str:
  """``PyCounter<K>`` 单实参 → 补默认计数类型 ``PyInt``。"""
  t = strip_cpp_type_qualifiers(strip_cpp_ref(cpp_type.strip()))
  if not _type_pred().is_counter_type(t):
    return cpp_type
  inner = t[len(CPP_COUNTER_PREFIX) : -1].strip()
  parts = split_cpp_template_args(inner)
  if len(parts) != 1:
    return cpp_type
  return f"{CPP_COUNTER_PREFIX}{parts[0]}, {cpp_ident('int')}>"


def cpp_normalize_type_for_compare(cpp_type: str) -> str:
  """推断类型与注解比较：补 ``list``/``array`` NTTP ``0``、``Counter`` 默认 ``int``；递归模板实参。"""
  t = strip_cpp_ref(cpp_type.strip())
  if t.endswith(">"):
    for prefix in (
      CPP_DICT_PREFIX,
      CPP_FROZENDICT_PREFIX,
      CPP_LIST_PREFIX,
      CPP_FROZENLIST_PREFIX,
      CPP_ARRAY_PREFIX,
      CPP_ARRAY2D_PREFIX,
      CPP_ARRAY3D_PREFIX,
      CPP_COUNTER_PREFIX,
      CPP_TUPLE_PREFIX,
      CPP_OPTIONAL_PREFIX,
      CPP_DEQUE_PREFIX,
    ):
      idx = t.find(prefix)
      if idx < 0 or "<" in t[:idx]:
        continue
      inner = t[idx + len(prefix) : -1]
      parts = split_cpp_template_args(inner)
      if not parts:
        continue
      norm = ", ".join(cpp_normalize_type_for_compare(p.strip()) for p in parts)
      t = f"{t[:idx]}{prefix}{norm}>"
      break
  t = cpp_fill_allocator_default_args(t)
  t = cpp_fill_counter_default_args(t)
  return t


def cpp_inferred_type_matches_ann(expected: str, ann: str) -> bool:
  return cpp_normalize_type_for_compare(expected) == cpp_normalize_type_for_compare(ann)


def heap_array_type_with_allocator(cpp_type: str, info: "ClassInfo") -> str:
  """``list[Element, StackLength]`` / ``array[Element, StackLength]`` 内 ``Element[:]`` → ``PyArray<Element, StackLength>``。"""
  if info.name not in ("list", "frozenlist", "array"):
    return cpp_type
  if len(info.type_params) < 2:
    return cpp_type
  inner = cpp_template_inner_args(cpp_type, CPP_ARRAY_PREFIX)
  if inner is None:
    return cpp_type
  parts = split_cpp_template_args(inner)
  if not parts:
    return cpp_type
  cap = cpp_type_param_template_name(info.type_params[1])
  return f"{CPP_ARRAY_PREFIX}{parts[0]}, {cap}>"


def cpp_fault_result_type(ok_ty: str, err_ty: str) -> str:
  """``Result[T, E]`` → ``PyResult<T, E>``（``None``/``void`` → ``PyNone``）。"""
  if ok_ty == "void":
    ok_ty = cpp_ident("PyNone")
  return cpp_template_type("Result", f"{ok_ty}, {err_ty}")


def cpp_fault_result_type_args(cpp_type: str) -> tuple[str, str] | None:
  """``PyResult<T, E>`` → ``(T, E)``。"""
  inner = cpp_template_inner_args(cpp_type, CPP_FAULT_RESULT_PREFIX)
  if inner is None:
    return None
  parts = split_cpp_template_args(inner)
  if len(parts) >= 2:
    return parts[0], parts[1]
  return None


def cpp_fault_ok_expr(result_cpp: str, value_cpp: str) -> str:
  return cpp_union_static_call(strip_cpp_ref(result_cpp), "Ok", value_cpp)


def cpp_fault_err_expr(result_cpp: str, err_cpp: str) -> str:
  return cpp_union_static_call(strip_cpp_ref(result_cpp), "Err", err_cpp)


def fault_result_ok_expr(lhs_cpp: str) -> str:
  return f"{lhs_cpp}.ok__get()"


def fault_result_value_expr(lhs_cpp: str) -> str:
  return f"{lhs_cpp}.value__get()"


def cpp_result_type(yield_ty: str, return_ty: str | None = None) -> str:
  """``IterResult[Y,R]`` → ``PyIterResult<Y, R>``。"""
  if return_ty is None or return_ty == yield_ty:
    return cpp_template_type("IterResult", f"{yield_ty}, {yield_ty}")
  return cpp_template_type("IterResult", f"{yield_ty}, {return_ty}")


def split_cpp_template_args(inner: str) -> list[str]:
  """按顶层逗号拆分模板实参（忽略 ``<...>`` 内的逗号）。"""
  parts: list[str] = []
  depth = 0
  start = 0
  for i, ch in enumerate(inner):
    if ch == "<":
      depth += 1
    elif ch == ">":
      depth -= 1
    elif ch == "," and depth == 0:
      parts.append(inner[start:i].strip())
      start = i + 1
  parts.append(inner[start:].strip())
  return parts


def cpp_template_base_and_args(cpp_type: str) -> tuple[str, list[str]] | None:
  """``Counter<PyStr, PyInt>`` → ``("Counter", ["PyStr", "PyInt"])``。"""
  t = strip_cpp_ref(cpp_type.strip())
  if "<" not in t or not t.endswith(">"):
    return None
  base, inner = t.split("<", 1)
  return base, split_cpp_template_args(inner[:-1])


def specialize_cpp_template_placeholders(
  pattern: str,
  *,
  class_cpp_name: str,
  type_params: list[str],
  recv_cpp: str,
  default_cpp_for_param: Callable[[str], str | None] | None = None,
) -> str:
  """用接收者实例化类型把 ``K``/``Node`` 等形参名替换为具体 C++ 类型。"""
  import re

  parsed = cpp_template_base_and_args(recv_cpp)
  if parsed is None or parsed[0] != class_cpp_name:
    return pattern
  _, args = parsed
  full_args = list(args)
  while len(full_args) < len(type_params):
    p = type_params[len(full_args)]
    if default_cpp_for_param is None:
      break
    dv = default_cpp_for_param(p)
    if not dv:
      break
    full_args.append(dv)
  if len(full_args) != len(type_params):
    return pattern
  out = pattern
  for param, concrete in zip(type_params, full_args):
    out = re.sub(rf"\b{re.escape(param)}\b", concrete, out)
  return out


def cpp_result_type_args(cpp_type: str) -> tuple[str, str] | None:
  """``PyIterResult<Y, R>`` → ``(Y, R)``。"""
  inner = cpp_template_inner_args(cpp_type, CPP_RESULT_PREFIX)
  if inner is None:
    return None
  parts = split_cpp_template_args(inner)
  if len(parts) == 1:
    return parts[0], parts[0]
  if len(parts) >= 2:
    return parts[0], parts[1]
  return None


def cpp_refcount_type(inner: str) -> str:
  return cpp_template_type("RefCount", inner)


def cpp_optional_type(inner: str) -> str:
  return cpp_template_type("Optional", inner)


def resolve_self_in_cpp_type(cpp_type: str, host_cpp: str) -> str:
  """类体内 ``Self`` → 宿主 C++ 名（``WeakRef[Self]`` 等字段/局部类型）。"""
  if "Self" not in cpp_type:
    return cpp_type
  return cpp_type.replace("Self", host_cpp)


def cpp_union_static_call(rt: str, variant: str, arg_cpp: str | None = None) -> str:
  """``(T::Variant)(…)``：MSVC Win32 ``Yield``/``Return`` 宏下抑制 ``::Variant`` 被展开。"""
  base = strip_cpp_ref(rt)
  if arg_cpp is None:
    return f"({base}::{variant})()"
  return f"({base}::{variant})({arg_cpp})"


def cpp_iter_result_return_expr(rt: str, return_cpp: str | None = None) -> str:
  """``IterResult::Return(ret)``；``return_cpp`` 缺省为 ``ReturnType()``。"""
  args = cpp_result_type_args(rt)
  if args is None:
    return cpp_union_static_call(rt, "Return")
  _y, r = args
  val = return_cpp if return_cpp is not None else f"{r}()"
  return cpp_union_static_call(rt, "Return", val)


def cpp_iter_result_yield_expr(rt: str, value_cpp: str) -> str:
  return cpp_union_static_call(rt, "Yield", value_cpp)


def iter_result_done_cpp(var: str) -> str:
  return f"{var}.done__get()"


def iter_result_value_cpp(var: str) -> str:
  return f"{var}.value__get()"


def iter_result_return_value_cpp(var: str) -> str:
  return f"{var}.return_value__get()"


def cpp_option_tag_enum(cpp_type: str) -> str:
  base = strip_cpp_ref(cpp_type)
  return f"{base}::Enum"


def cpp_option_some_expr(opt_cpp_type: str, value_cpp: str) -> str:
  return cpp_union_static_call(strip_cpp_ref(opt_cpp_type), "Some", value_cpp)


def cpp_option_none_expr(opt_cpp_type: str) -> str:
  return cpp_union_static_call(strip_cpp_ref(opt_cpp_type), "None_")


def option_is_none_expr(lhs_cpp: str, opt_cpp_type: str) -> str:
  tag = cpp_option_tag_enum(opt_cpp_type)
  return f"({lhs_cpp}.{property_getter_method_for('__enum__')}() == {tag}::None_)"


def option_is_not_none_expr(lhs_cpp: str, opt_cpp_type: str) -> str:
  return f"(!{option_is_none_expr(lhs_cpp, opt_cpp_type)})"


def option_unbox_expr(lhs_cpp: str) -> str:
  return f"{lhs_cpp}.value__get()"


def strip_cpp_ref(cpp_type: str) -> str:
  t = cpp_type.strip()
  if t.endswith("&"):
    return t[:-1].strip()
  return t


def is_json_doc_cursor_type(cpp_type: str) -> bool:
  t = strip_cpp_ref(cpp_type)
  return "JsonDocCursor" in t


def cpp_slice_result_type(base_ty: str) -> str | None:
  """``seq[a:b]`` 的容器结果类型（用于 ``for`` 索引内联）。"""
  t = strip_cpp_ref(base_ty)
  if _type_pred().is_str_type(t):
    return cpp_ident("str")
  if _type_pred().is_list_type(t):
    return t
  if _type_pred().is_bytes_type(t):
    return cpp_ident("bytes")
  if _type_pred().is_span_type(t):
    elem = cpp_span_elem_type(t)
    return cpp_span_type(elem) if elem else None
  if _type_pred().is_char_heap_array_type(t):
    elem = cpp_array_elem_type(t)
    return cpp_template_type("array", elem) if elem else None
  if _type_pred().is_stack_array_type(t):
    elem = cpp_stack_array_elem_type(t)
    return cpp_template_type("array", elem) if elem else None
  return None


INT32_MIN_VALUE = -(1 << 31)


def format_cpp_int(value: int) -> str:
  """``PyInt`` 整型字面量；``INT32_MIN`` 用 ``PY2CPP_INT_MIN``（避免 MSVC C4146）。"""
  if value == INT32_MIN_VALUE:
    return "PY2CPP_INT_MIN"
  return str(value)


def format_cpp_int64(value: int) -> str:
  """Python ``int`` 字面量 → ``PyInt64`` 常量（MSVC ``int`` 为 32 位，大整数须 ``LL``）。"""
  if value < 0:
    return f"({value}LL)"
  return f"{value}LL"


def format_cpp_uint(value: int) -> str:
  """Python ``int`` 字面量 → ``PyUInt`` 常量（无符号 32 位，大值须 ``U``）。"""
  if value < 0:
    raise ValueError(f"uint literal must be non-negative: {value}")
  if value > 0xFFFFFFFF:
    raise ValueError(f"uint literal out of range: {value}")
  if value > 0x7FFFFFFF:
    return f"{value}U"
  return str(value)


def format_cpp_uint64(value: int) -> str:
  """Python ``int`` 字面量 → ``PyUInt64`` 常量（大整数用 ``ULL`` / ``0x…ULL``）。"""
  if value < 0:
    raise ValueError(f"uint64 literal must be non-negative: {value}")
  if value > 0xFFFFFFFF:
    return f"0x{value:X}ULL"
  return f"{value}ULL"


def format_cpp_uintptr(value: int) -> str:
  """Python ``int`` 字面量 → ``PyUPtr`` 常量（与 ``uintptr_t`` 同宽）。"""
  if value < 0:
    raise ValueError(f"uintptr literal must be non-negative: {value}")
  if value > 0xFFFFFFFF:
    return f"0x{value:X}ULL"
  return f"{value}ULL"


def format_cpp_varint(value: int) -> str:
  """``varint`` 注解下的 Python ``int`` 字面量 → ``PyVarInt(PyStr("…"))``（含超 ``PyInt`` 范围）。"""
  ps = cpp_ident("str")
  return f'{cpp_ident("varint")}({ps}({quote_cpp_string(str(value))}))'


def format_cpp_float64(value: float) -> str:
  """Python ``float`` 字面量 → ``double`` 常量（无 ``f`` 后缀）。"""
  text = repr(value)
  if text.lstrip("-").isdigit():
    text = f"{text}.0"
  return text


def _cpp_complex_base_name() -> str:
  return cpp_ident("complex")


def complex_element_cpp_type(cpp_type: str | None) -> str:
  """``PyComplex<PyFloat64>`` → ``PyFloat64``；缺省 ``PyFloat``。"""
  base = _cpp_complex_base_name()
  if cpp_type:
    inner = cpp_template_inner_args(cpp_type.strip(), f"{base}<")
    if inner:
      return inner.split(",", 1)[0].strip()
    if cpp_type.strip() == base:
      return cpp_ident("float")
  return cpp_ident("float")


def complex_template_cpp_type(cpp_type: str | None) -> str:
  """复数字面量目标 C++ 类型（保留模板实参或默认 ``PyComplex<PyFloat>``）。"""
  base = _cpp_complex_base_name()
  if cpp_type:
    t = cpp_type.strip()
    if t.startswith(f"{base}<") and t.endswith(">"):
      return t
    if t == base:
      return f"{base}<{cpp_ident('float')}>"
    elem = complex_element_cpp_type(cpp_type)
    if elem != cpp_ident("float"):
      return f"{base}<{elem}>"
  return f"{base}<{cpp_ident('float')}>"


def _static_method_uses_class_type_param(info: ClassInfo, member: str) -> bool:
  """类静态方法签名是否引用类模板形参（如 ``Task[T].result`` 的 ``T``）。"""
  from .type_emit import collect_sig_type_texts

  if not info.type_params:
    return False
  sig = info.method_sigs.get(member)
  if sig is None:
    return False
  class_tp = info.type_params[0]
  needles = {class_tp, cpp_ident(class_tp)}
  text = " ".join(collect_sig_type_texts(sig))
  return any(f"{n}" in text.split() or f"<{n}>" in text or f", {n}" in text for n in needles)


def qualified_class_static_callee(
  info: ClassInfo,
  member: str,
  *,
  arg_cpp_type: str | None = None,
) -> str:
  """``Cls.method`` / ``Cls.prop__get()`` 的 C++ 限定名；单参 ``PyComplex`` 默认 ``<PyFloat>``。"""
  from .module_namespace import qualify_symbol_in_module

  effective_arg = arg_cpp_type
  if effective_arg and info.type_params:
    for tp in info.type_params:
      if tp in effective_arg:
        effective_arg = None
        break
  base = qualify_symbol_in_module(info.module_path, info.cpp_name())
  if not info.is_template():
    return f"{base}::{member}"
  if info.type_params and not _static_method_uses_class_type_param(info, member):
    if info.cpp_name() == _cpp_complex_base_name():
      tpl = complex_template_cpp_type(None)
      b = _cpp_complex_base_name()
      qbase = qualify_symbol_in_module(info.module_path, b)
      if tpl.startswith(f"{b}<") and tpl.endswith(">"):
        args = tpl[len(b) + 1 : -1].strip()
        return f"{qbase}<{args}>::{member}"
      return f"{qualify_symbol_in_module(info.module_path, tpl)}::{member}"
    return f"{base}<{cpp_ident('int')}>::{member}"
  if info.cpp_name() == _cpp_complex_base_name():
    tpl = complex_template_cpp_type(effective_arg)
    b = _cpp_complex_base_name()
    qbase = qualify_symbol_in_module(info.module_path, b)
    if tpl.startswith(f"{b}<") and tpl.endswith(">"):
      args = tpl[len(b) + 1 : -1].strip()
      return f"{qbase}<{args}>::{member}"
    return f"{qualify_symbol_in_module(info.module_path, tpl)}::{member}"
  spec = info.cpp_specialization()
  name = info.cpp_name()
  if "<" in spec:
    args = spec.split("<", 1)[1].rsplit(">", 1)[0]
    return f"{qualify_symbol_in_module(info.module_path, name)}<{args}>::{member}"
  return f"{base}::{member}"


def format_cpp_complex_component(value: float, elem_cpp: str) -> str:
  if elem_cpp == cpp_ident("float64"):
    return format_cpp_float64(value)
  return format_cpp_float(value)


def format_cpp_complex_literal(
  real: float,
  imag: float,
  cpp_type: str | None = None,
) -> str:
  elem = complex_element_cpp_type(cpp_type)
  cls = complex_template_cpp_type(cpp_type)
  rl = format_cpp_complex_component(real, elem)
  il = format_cpp_complex_component(imag, elem)
  return f"{cls}({rl}, {il})"


def field_property_getter_returns_mutable_ref(cpp_type: str) -> bool:
  """``@property`` 字段 getter：标量 ``const T&``；可变容器 ``T&``（``() const`` + ``mutable`` 存储）。"""
  t = strip_cpp_ref(cpp_type)
  if not t or t.endswith("*"):
    return True
  if (
    _type_pred().is_int_type(t)
    or _type_pred().is_int64_type(t)
    or t in ("PyBool", cpp_ident("bool"))
    or _type_pred().is_float_type(t)
    or _type_pred().is_float64_type(t)
    or _type_pred().is_str_type(t)
    or _type_pred().is_bytes_type(t)
    or _type_pred().is_char_type(t)
    or _type_pred().is_byte_type(t)
  ):
    return False
  return True


def field_property_getter_return_ref(cpp_type: str) -> str:
  t = strip_cpp_ref(cpp_type).strip()
  if field_property_getter_returns_mutable_ref(cpp_type):
    return f"{t}&"
  return f"const {t}&"


def cpp_template_inner_args(cpp_type: str, prefix: str) -> str | None:
  """``PyList<str>`` → ``str``；非匹配前缀时返回 ``None``。"""
  if cpp_type.startswith(prefix) and cpp_type.endswith(">"):
    return cpp_type[len(prefix) : -1]
  return None


def cpp_pointer_type_for_object(cpp_type: str) -> str:
  """值/``PyRefCount``/已有指针 → ``id(x)`` 等所需的 ``T*``。"""
  t = cpp_type.strip()
  if _type_pred().is_refcount_type(t):
    inner = cpp_template_inner_args(t, CPP_REFCount_PREFIX)
    return f"{inner.strip()}*" if inner else "void*"
  if t.endswith("*"):
    return t
  return f"{t}*"


def class_info_for_cpp_type(
  cpp_type: str, classes: dict[str, ClassInfo],
) -> ClassInfo | None:
  """按生成类型名（含模板实参）匹配 ``ClassInfo``。"""
  bare = strip_cpp_type_qualifiers(cpp_type)
  for info in classes.values():
    cn = info.cpp_name()
    if bare == cn or bare.startswith(f"{cn}<"):
      return info
  return None


def _init_allows_zero_args(init: ast.FunctionDef) -> bool:
  """``__init__`` 是否可在无实参下调用（仅 ``self`` 或其余均有默认值）。"""
  a = init.args
  params = list(a.posonlyargs) + list(a.args)
  if params and params[0].arg == "self":
    params = params[1:]
  if len(params) > len(a.defaults):
    return False
  for i, _kw in enumerate(a.kwonlyargs):
    if i >= len(a.kw_defaults) or a.kw_defaults[i] is None:
      return False
  return True


def _class_has_empty_init(info: ClassInfo) -> bool:
  """存在无参 ``__init__``（仅 ``self``）时可默认构造。"""
  if not info.inits:
    return not info.init_sigs
  return any(_init_allows_zero_args(init) for init in info.inits)


def class_needs_explicit_default_ctor(info: ClassInfo) -> bool:
  """显式复制/移动成员会抑制隐式默认构造；无 ``__init__`` 且字段均有类内初值时需 ``= default``。"""
  if info.inits or info.init_sigs:
    return False
  if not info.has_copy and not info.has_move:
    return False
  from ..passes.move_state import MOVE_STATE_FIELD

  instance_fields = [
    f
    for f in info.fields
    if not f.startswith("__ann__")
    and f != MOVE_STATE_FIELD
    and f not in info.static_class_fields
    and f not in info.static_property_storage
  ]
  if not instance_fields:
    return True
  from .type_emit import field_type_node
  from .type_pred import is_erased_protocol_storage_type

  def _field_is_erased_storage(field: str) -> bool:
    return _type_pred().is_erased_protocol_storage_type(field_type_node(info, field))

  if all(_field_is_erased_storage(f) for f in instance_fields):
    return True
  return all(f in info.field_defaults for f in instance_fields)


def _class_has_mapping_literal_support(
  info: ClassInfo, classes: dict[str, ClassInfo],
) -> bool:
  if "__setitem__" in info.method_sigs:
    return True
  if "dict" in info.bases:
    return True
  for base in info.bases:
    if base == "dict":
      return True
    binfo = classes.get(base)
    if binfo is not None and _class_has_mapping_literal_support(binfo, classes):
      return True
  return False


def cpp_type_supports_dict_literal_setitem(
  cpp_type: str, classes: dict[str, ClassInfo],
) -> str | None:
  """若 ``{…}`` 可通过默认构造 + ``__setitem__`` 初始化，返回完整 C++ 类型；否则 ``None``。"""
  t = strip_cpp_type_qualifiers(cpp_type.strip())
  if _type_pred().is_dict_type(t):
    inner = _type_extract().dict_type_args(t) or ""
    return cpp_template_type("dict", inner)
  info = class_info_for_cpp_type(t, classes)
  if info is None:
    return None
  if not _class_has_mapping_literal_support(info, classes):
    return None
  if not _class_has_empty_init(info):
    return None
  return t


def cpp_type_supports_list_literal_append(
  cpp_type: str, classes: dict[str, ClassInfo],
) -> tuple[str, str] | None:
  """若 ``[…]`` 可通过默认构造 + ``append`` 初始化，返回 ``(完整 C++ 类型, 元素类型)``。"""
  t = strip_cpp_type_qualifiers(cpp_type.strip())
  if _type_pred().is_list_type(t):
    elem = _type_extract().list_elem_type(t)
    if elem is not None:
      return cpp_template_type("list", elem), elem
  if _type_pred().is_deque_type(t):
    elem = _type_extract().deque_elem_type(t)
    if elem is not None:
      return cpp_template_type("deque", elem), elem
  info = class_info_for_cpp_type(t, classes)
  if info is None or "append" not in info.method_sigs:
    return None
  if not _class_has_empty_init(info):
    return None
  elem: str | None = None
  if info.type_params:
    inner = cpp_template_inner_args(t, f"{info.cpp_name()}<")
    if inner:
      elem = inner.split(",")[0].strip()
  if elem is None:
    elem = cpp_ident("int")
  elem = ClassInfo.apply_refcount_storage_cpp_type(elem, classes)
  return t, elem


def cpp_type_supports_set_literal_add(
  cpp_type: str, classes: dict[str, ClassInfo],
) -> str | None:
  """若 ``{…}`` 可通过 ``.add`` 初始化，返回元素类型 ``T``；否则 ``None``。"""
  if _type_pred().is_set_type(cpp_type):
    return _type_extract().set_elem_type(cpp_type)
  info = class_info_for_cpp_type(cpp_type, classes)
  if info is None or "add" not in info.method_sigs:
    return None
  if info.type_params:
    inner = cpp_template_inner_args(cpp_type, f"{info.cpp_name()}<")
    if inner:
      return inner.split(",")[0].strip()
  return None


def default_new_ctor_cpp(cpp_type: str) -> str:
  """无参 ``new()`` 默认实参 → ``Type()``（方法形参默认值等）。"""
  t = strip_cpp_type_qualifiers(cpp_type)
  if _type_pred().is_str_type(t):
    return f"{t}()"
  if _type_pred().is_bytes_type(t):
    return f"{t}(0)"
  elem_t = _type_extract().list_elem_type(t)
  if elem_t is not None:
    return f"{cpp_ident('list')}<{elem_t}>()"
  elem_t = _type_extract().deque_elem_type(t)
  if elem_t is not None:
    return f"{cpp_ident('deque')}<{elem_t}>()"
  if _type_pred().is_dict_type(t):
    inner = _type_extract().dict_type_args(t) or ""
    return f"{cpp_template_type('dict', inner)}()"
  elem_t = _type_extract().set_elem_type(t)
  if elem_t is not None:
    return f"{cpp_template_type('set', elem_t)}()"
  elem_t = _type_extract().frozenset_elem_type(t)
  if elem_t is not None:
    return f"{cpp_template_type('frozenset', elem_t)}()"
  elem_t = _type_extract().frozenlist_elem_type(t)
  if elem_t is not None:
    return f"{cpp_template_type('frozenlist', elem_t)}()"
  fd_inner = _type_extract().frozendict_type_args(t)
  if fd_inner is not None:
    return f"{cpp_template_type('frozendict', fd_inner)}()"
  if _type_pred().is_stack_array_type(t):
    return f"{t}()"
  return f"{t}()"


def cpp_param(name: str) -> str:
  """Python 形参名 → C++ 形参名。"""
  ren = cpp_type_rename(name)
  if ren is not None:
    return ren
  return escape_cpp_param(name)


def quote_cpp_string(text: str) -> str:
  """Python 字符串 → C++ 字符串字面量（用于 printf 格式串等）。"""
  return json.dumps(text, ensure_ascii=False)


def format_cpp_float(value: float) -> str:
  """Python float → C++ float 字面量（如 ``2.0f``、``1e-5f``）。"""
  text = repr(value)
  if text.endswith(".0") or "." in text or "e" in text:
    pass
  elif text.lstrip("-").isdigit():
    text = f"{text}.0"
  if not text.endswith(("f", "F")):
    text = f"{text}f"
  return text


def str_cpp_from_literal(text: str) -> str:
  """Python 字符串常量 → C++ ``PyStr("...")``。"""
  return f"{cpp_ident('str')}({quote_cpp_string(text)})"


def bytes_cpp_from_literal(data: bytes) -> str:
  """Python ``bytes`` 常量 → ``bytes_from_literal``（见 ``text/+bytes.inl`` inject）。"""
  fn = "::py2cpp::text::bytes::bytes_from_literal"
  if not data:
    return f"{fn}(nullptr, 0)"
  esc = "".join(f"\\x{b:02x}" for b in data)
  return f'{fn}((const unsigned char*)"{esc}", {len(data)})'


def split_cpp_param_list(params: str) -> list[str]:
  """按顶层逗号拆分形参（``ModInt<T, U> x, int y``）。"""
  if not params or not params.strip():
    return []
  parts: list[str] = []
  depth = 0
  start = 0
  for i, ch in enumerate(params):
    if ch == "<":
      depth += 1
    elif ch == ">":
      depth = max(0, depth - 1)
    elif ch == "," and depth == 0:
      piece = params[start:i].strip()
      if piece:
        parts.append(piece)
      start = i + 1
  tail = params[start:].strip()
  if tail:
    parts.append(tail)
  return parts


def format_fn_sig(lead: str, trail: str, name: str, params: str) -> str:
  """拼接函数签名片段，例如 ``void foo(int x)`` 或 ``auto f(T x) -> decltype(...)``。

  返回类型为函数指针（``Ret (*)(Args)``）时用尾返回类型，避免
  ``void (*)() foo(...)`` 这种非法声明（须 ``void (*foo(...))()`` 或 ``auto foo(...) -> void (*)()``）。
  """
  lead_s = (lead or "").strip()
  if format_cpp_callable_var_decl(lead_s, "_") is not None:
    return f"auto {name}({params}){trail} -> {lead_s}"
  return f"{lead} {name}({params}){trail}"


def fn_noexcept_suffix(is_noexcept: bool) -> str:
  return " noexcept" if is_noexcept else ""


@dataclass(frozen=True)
class TypeAliasInfo:
  """``type Alias = rhs`` 或 ``type Alias[T: Proto] = rhs``（PEP 695）。"""

  name: str
  value: ast.expr
  type_params: tuple[str, ...] = ()
  type_param_constraints: dict[str, tuple[str, ...]] = field(default_factory=dict)
  type_param_oneof_constraints: dict[str, tuple[str, ...]] = field(default_factory=dict)
  type_param_nttp: dict[str, str] = field(default_factory=dict)
  member_constraint: bool = False
  """``type Element = ...``：关联类型；要求 ``using Element`` 或嵌套类型 ``Element``。"""
  capture_params: tuple[str, ...] = ()
  """``_V = ...`` 等：捕获形参（须 ``_`` 前缀），调用侧不传，由 RHS 模式绑定。"""
  is_conditional: bool = False
  """RHS 为 ``X if T is … else Y`` 类型三目。"""
  lineno: int = 0

  @property
  def call_params(self) -> tuple[str, ...]:
    cap = set(self.capture_params)
    return tuple(p for p in self.type_params if p not in cap)


@dataclass
class ProtocolMemberConstraint:
  """``@protocol`` 成员约束：字段注解、``@property`` 或 ``type Alias = ...``。"""

  name: str
  kind: str  # "field" | "property" | "type_alias"
  annotation: ast.expr | None = None


def type_alias_rhs_is_ellipsis(value: ast.expr) -> bool:
  if isinstance(value, ast.Constant) and value.value is Ellipsis:
    return True
  return isinstance(value, ast.Ellipsis)


def collect_type_names_in_expr(expr: ast.expr) -> set[str]:
  return {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}


def pep695_declared_type_params(
  node: ast.FunctionDef | ast.ClassDef | ast.TypeAlias,
) -> list[str]:
  """PEP 695 头/别名上的 ``TypeVar`` 名（不含 ``FuncTypeParams`` 分配的 ``T0`` 等）。"""
  names: list[str] = []
  for p in getattr(node, "type_params", None) or ():
    if isinstance(p, ast.TypeVar):
      names.append(p.name)
  return names


def pep695_used_type_params(
  node: ast.FunctionDef | ast.ClassDef,
  declared: frozenset[str],
) -> set[str]:
  """在注解、约束与可静态见到的 ``Name`` 中出现的已声明形参名。"""
  if not declared:
    return set()
  used: set[str] = set()
  for p in getattr(node, "type_params", None) or ():
    if isinstance(p, ast.TypeVar) and p.bound is not None:
      used.update(collect_type_names_in_expr(p.bound) & declared)
  if isinstance(node, ast.FunctionDef):
    if node.returns is not None:
      used.update(collect_type_names_in_expr(node.returns) & declared)
    for arg in node.args.args:
      if arg.annotation is not None:
        used.update(collect_type_names_in_expr(arg.annotation) & declared)
    for child in ast.walk(node):
      if isinstance(child, ast.Name) and child.id in declared:
        used.add(child.id)
    return used
  for stmt in node.body:
    if isinstance(stmt, ast.TypeAlias):
      if stmt.value is not None:
        used.update(collect_type_names_in_expr(stmt.value) & declared)
      for p in getattr(stmt, "type_params", None) or ():
        if isinstance(p, ast.TypeVar) and p.bound is not None:
          used.update(collect_type_names_in_expr(p.bound) & declared)
  for child in ast.walk(node):
    if isinstance(child, ast.Name) and child.id in declared:
      used.add(child.id)
  return used


def parse_typevar_oneof_bounds(bound: ast.expr | None) -> tuple[str, ...]:
  """``T: oneof[char, byte]`` 或 ``T: Proto & oneof[…]`` → 候选类型名元组。"""
  if bound is None:
    return ()
  if isinstance(bound, ast.Subscript) and isinstance(bound.value, ast.Name):
    if bound.value.id == "oneof":
      alts = _oneof_alternative_names(bound.slice)
      if len(alts) < 2:
        raise SyntaxError("oneof[…] 须至少列出 2 个类型")
      return alts
    return ()
  if isinstance(bound, ast.BinOp) and isinstance(bound.op, ast.BitAnd):
    left = parse_typevar_oneof_bounds(bound.left)
    right = parse_typevar_oneof_bounds(bound.right)
    if left and right:
      raise SyntaxError("类型形参至多一个 oneof[…] 约束")
    return left or right
  return ()


def _oneof_alternative_names(slice_node: ast.expr) -> tuple[str, ...]:
  if isinstance(slice_node, ast.Tuple):
    elts = slice_node.elts
  else:
    elts = [slice_node]
  names: list[str] = []
  for elt in elts:
    if isinstance(elt, ast.Name):
      names.append(elt.id)
    else:
      raise SyntaxError("oneof[…] 仅支持类型名列表")
  return tuple(names)


def parse_typevar_protocol_bounds(bound: ast.expr | None) -> tuple[str, ...]:
  """``T: Proto`` 或 ``T: A & B``（PEP 695 交集）→ 协议名元组（不含 ``oneof[…]``）。"""
  if bound is None:
    return ()
  if isinstance(bound, ast.Subscript) and isinstance(bound.value, ast.Name):
    if bound.value.id == "oneof":
      return ()
  if isinstance(bound, ast.Name):
    return (bound.id,)
  if isinstance(bound, ast.BinOp) and isinstance(bound.op, ast.BitAnd):
    return parse_typevar_protocol_bounds(bound.left) + parse_typevar_protocol_bounds(
      bound.right
    )
  return ()


def merge_oneof_type_constraint(
  constraints: dict[str, tuple[str, ...]],
  tp: str,
  alternatives: tuple[str, ...],
) -> None:
  if tp not in constraints:
    constraints[tp] = alternatives
    return
  if constraints[tp] != alternatives:
    raise SyntaxError(f"类型形参 {tp} 的 oneof[…] 约束冲突")


def merge_concrete_oneof_constraint(
  constraints: dict[str, tuple[str, ...]],
  concrete: str,
  alternatives: tuple[str, ...],
) -> None:
  if concrete not in constraints:
    constraints[concrete] = alternatives
    return
  if constraints[concrete] != alternatives:
    raise SyntaxError(f"具体类型 {concrete} 的 oneof[…] 约束冲突")


def cpp_type_for_oneof_alternative(name: str) -> str:
  """``oneof`` 候选类型名 → C++ 类型（``char``→``PyChar``，类名→``Py*``）。"""
  from ..constant.language import CPP_RENAME

  if name in CPP_RENAME:
    return CPP_RENAME[name]
  return cpp_ident(name)


def cpp_oneof_static_assert_expr(type_cpp: str, alternatives: tuple[str, ...]) -> str:
  parts = [
    f"std::is_same<{type_cpp}, {cpp_type_for_oneof_alternative(alt)}>::value"
    for alt in alternatives
  ]
  return " || ".join(parts)


def typevar_default_is_capture(default: ast.expr | None) -> bool:
  if default is None:
    return False
  if isinstance(default, ast.Ellipsis):
    return True
  return isinstance(default, ast.Constant) and default.value is Ellipsis


def validate_capture_param_names(capture_params: tuple[str, ...], *, loc: str) -> None:
  for name in capture_params:
    if name == "_" or not name.startswith("_") or len(name) < 2:
      raise ValueError(
        f"{loc}: 捕获形参须 ``_X`` 形式（如下划线 + 语义字母，如 ``_V``、``_P``），"
        f"得到 ``{name}``"
      )


def parse_type_alias_stmt(stmt: ast.TypeAlias) -> TypeAliasInfo:
  """解析类型别名；仅保留在 ``value`` 中出现的形参上的协议约束。"""
  name = stmt.name.id
  type_params: list[str] = []
  capture_params: list[str] = []
  constraints: dict[str, tuple[str, ...]] = {}
  oneof_constraints: dict[str, tuple[str, ...]] = {}
  nttp: dict[str, str] = {}
  for tp in getattr(stmt, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      nttp_val = type_param_nttp_value_type(tp.bound, type_params)
      type_params.append(tp.name)
      if nttp_val is not None:
        nttp[tp.name] = nttp_val
      dv = getattr(tp, "default_value", None)
      if typevar_default_is_capture(dv):
        capture_params.append(tp.name)
      oneof = parse_typevar_oneof_bounds(tp.bound)
      if oneof:
        oneof_constraints[tp.name] = oneof
      bounds = parse_typevar_protocol_bounds(tp.bound)
      if bounds:
        constraints[tp.name] = bounds
  if type_alias_rhs_is_ellipsis(stmt.value):
    return TypeAliasInfo(
      name,
      stmt.value,
      tuple(type_params),
      {},
      {},
      type_param_nttp=nttp,
      member_constraint=True,
      lineno=getattr(stmt, "lineno", 0),
    )
  used = collect_type_names_in_expr(stmt.value) & set(type_params)
  constraints = {k: v for k, v in constraints.items() if k in used}
  oneof_constraints = {k: v for k, v in oneof_constraints.items() if k in used}
  is_conditional = isinstance(stmt.value, ast.IfExp)
  return TypeAliasInfo(
    name,
    stmt.value,
    tuple(type_params),
    constraints,
    oneof_constraints,
    type_param_nttp=nttp,
    capture_params=tuple(capture_params),
    is_conditional=is_conditional,
    lineno=getattr(stmt, "lineno", 0),
  )


NTTP_INT_SENTINEL = "__nttp_int__"


def type_param_nttp_value_type(
  bound: ast.expr | None,
  prior_type_params: list[str],
) -> str | None:
  """``Mod: T``（``T`` 为已声明类形参）或 ``StackLength: int`` → 非类型模板形参。"""
  if isinstance(bound, ast.Name) and bound.id in prior_type_params:
    return bound.id
  if isinstance(bound, ast.Name) and bound.id == "int":
    return NTTP_INT_SENTINEL
  return None


def cpp_nttp_value_type_name(nttp_val: str) -> str:
  """NTTP 值类型名 → C++ 模板形参类型（``StackLength: int`` → ``PyInt``）。"""
  if nttp_val == NTTP_INT_SENTINEL:
    return "PyInt"
  return cpp_type_param_template_name(nttp_val)


def parse_class_type_params(
  node: ast.ClassDef,
) -> tuple[
  list[str],
  tuple[str, ...],
  str | None,
  dict[str, tuple[str, ...]],
  dict[str, tuple[str, ...]],
  dict[str, ast.expr],
  dict[str, str],
  dict[str, tuple[str, ...]],
]:
  """解析 PEP 695 类形参：TypeVar 列表、捕获形参、TypeVarTuple、协议/oneof/装饰器约束、默认值、NTTP（``Mod: T``）。"""
  regular: list[str] = []
  capture: list[str] = []
  typevar_tuple: str | None = None
  constraints: dict[str, tuple[str, ...]] = {}
  oneof_constraints: dict[str, tuple[str, ...]] = {}
  decorator_constraints: dict[str, tuple[str, ...]] = {}
  defaults: dict[str, ast.expr] = {}
  nttp: dict[str, str] = {}
  ctx = f"class {node.name}"
  for p in getattr(node, "type_params", None) or ():
    if isinstance(p, ast.TypeVar):
      nttp_val = type_param_nttp_value_type(p.bound, regular)
      regular.append(p.name)
      dv = getattr(p, "default_value", None)
      if typevar_default_is_capture(dv):
        capture.append(p.name)
      if nttp_val is not None:
        nttp[p.name] = nttp_val
      else:
        oneof = parse_typevar_oneof_bounds(p.bound)
        if oneof:
          oneof_constraints[p.name] = oneof
        bounds = parse_typevar_protocol_bounds(p.bound)
        if bounds:
          proto_bounds, dec_bounds = split_typevar_bounds(bounds)
          validate_typevar_decorator_bounds(dec_bounds, context=ctx)
          if proto_bounds:
            constraints[p.name] = proto_bounds
          if dec_bounds:
            decorator_constraints[p.name] = dec_bounds
      if dv is not None and not typevar_default_is_capture(dv):
        defaults[p.name] = dv
    elif isinstance(p, ast.TypeVarTuple):
      typevar_tuple = p.name
  return regular, tuple(capture), typevar_tuple, constraints, oneof_constraints, defaults, nttp, decorator_constraints


def format_cpp_doc(doc: str | None) -> list[str]:
  """将文档字符串转为 Doxygen 风格 ``///`` 行列表。"""
  if not doc:
    return []
  lines: list[str] = []
  for line in doc.splitlines():
    text = line.rstrip()
    lines.append(f"/// {text}" if text else "///")
  return lines


def docstring_lines(node: ast.AST) -> list[str]:
  """``ast.get_docstring(clean=True)`` 的 ``///`` 形式。"""
  return format_cpp_doc(ast.get_docstring(node, clean=True))


def has_named_decorator(node: ast.ClassDef | ast.FunctionDef, name: str) -> bool:
  for dec in node.decorator_list:
    if isinstance(dec, ast.Name) and dec.id == name:
      return True
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == name:
      return True
  return False


def _is_enum_mro_decorator_node(dec: ast.expr) -> bool:
  if isinstance(dec, ast.Attribute):
    return (
      isinstance(dec.value, ast.Name)
      and dec.value.id == "enum"
      and dec.attr == "mro"
    )
  if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
    return (
      isinstance(dec.func.value, ast.Name)
      and dec.func.value.id == "enum"
      and dec.func.attr == "mro"
    )
  return False


def has_enum_mro_decorator(node: ast.ClassDef) -> bool:
  return any(_is_enum_mro_decorator_node(dec) for dec in node.decorator_list)


def _is_union_mro_decorator_node(dec: ast.expr) -> bool:
  if isinstance(dec, ast.Attribute):
    return (
      isinstance(dec.value, ast.Name)
      and dec.value.id == "union"
      and dec.attr == "mro"
    )
  if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
    return (
      isinstance(dec.func.value, ast.Name)
      and dec.func.value.id == "union"
      and dec.func.attr == "mro"
    )
  return False


def has_union_mro_decorator(node: ast.ClassDef) -> bool:
  return any(_is_union_mro_decorator_node(dec) for dec in node.decorator_list)


def parse_enum_mro_base(node: ast.ClassDef) -> str | None:
  """``class ExcType(base=Exception):`` → ``Exception``。"""
  for kw in node.keywords:
    if kw.arg != "base":
      continue
    if isinstance(kw.value, ast.Name):
      return kw.value.id
    raise ValueError(f"{node.name}: base=… 须为类名")
  return None


def resolve_decorator_string_pattern(pattern: str, symbol_name: str) -> str:
  """``@native_name(\"fs_*\")`` / ``@global_call(\"py_*\")`` 中 ``*`` → 被装饰符号名。"""
  if "*" in pattern:
    return pattern.replace("*", symbol_name)
  return pattern


def decorator_string_arg(node: ast.ClassDef | ast.FunctionDef, name: str) -> str | None:
  """``@native_name(\"PyFoo\")`` / ``@native_name(\"fs_*\")`` 等单字符串位置参数装饰器。"""
  for dec in node.decorator_list:
    if not isinstance(dec, ast.Call):
      continue
    if not isinstance(dec.func, ast.Name) or dec.func.id != name:
      continue
    if not dec.args:
      return None
    arg = dec.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
      return resolve_decorator_string_pattern(arg.value, node.name)
  return None


def _is_ellipsis_or_pass_stmt(stmt: ast.stmt) -> bool:
  if isinstance(stmt, ast.Pass):
    return True
  if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
    return stmt.value.value is Ellipsis
  return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Ellipsis)


def _native_body_tail_index(body: list[ast.stmt]) -> int:
  """``@native`` 桩体：跳过前导 docstring，返回末语句下标；无有效桩体返回 -1。"""
  if not body:
    return -1
  i = 0
  while i < len(body) - 1:
    stmt = body[i]
    if (
      isinstance(stmt, ast.Expr)
      and isinstance(stmt.value, ast.Constant)
      and isinstance(stmt.value.value, str)
    ):
      i = i + 1
      continue
    return -1
  return len(body) - 1


def is_native_function_body(body: list[ast.stmt]) -> bool:
  """``@native`` 函数体须为 ``...``（可有 docstring；勿 ``pass``）。"""
  tail = _native_body_tail_index(body)
  if tail < 0:
    return False
  stmt = body[tail]
  if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
    return stmt.value.value is Ellipsis
  return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Ellipsis)


def is_abstract_method_body(body: list[ast.stmt]) -> bool:
  """``@abstract`` 方法体须为 ``...``（规则同 ``@native`` 桩体）。"""
  return is_native_function_body(body)


def is_stub_function_body(body: list[ast.stmt]) -> bool:
  """函数体为 ``pass`` / ``...``（可有前导 docstring ``Expr``）。"""
  tail = _native_body_tail_index(body)
  if tail < 0:
    return False
  return _is_ellipsis_or_pass_stmt(body[tail])


def is_overload_stub(func: ast.FunctionDef) -> bool:
  """``@overload`` 且函数体仅 ``pass``（``@native`` 重载用 ``...``，见 ``is_native_function_body``）。"""
  if has_named_decorator(func, "native"):
    return False
  return (
    len(func.body) == 1
    and isinstance(func.body[0], ast.Pass)
  )


def _matmult_marker_name(ann: ast.expr | None, marker: str) -> bool:
  if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
    return False
  right = ann.right
  if isinstance(right, ast.Name):
    return right.id == marker
  if isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
    return right.func.id == marker
  return False


def is_const_type_annotation(ann: ast.expr | None) -> bool:
  """``T @const``（``MatMult``）→ C++ ``static constexpr`` 成员，非实例字段默认值。"""
  return _matmult_marker_name(ann, "const")


def is_final_type_annotation(ann: ast.expr | None) -> bool:
  """``T @final``（``MatMult``）→ 实例 ``const`` 成员；``__init__`` 赋值进 C++ 构造初始化列表。"""
  return _matmult_marker_name(ann, "final")


def is_optional_type_annotation(ann: ast.expr | None) -> bool:
  """``T @optional``：``@dataclass`` 中不参与 ``__init__`` / ``assign`` 形参。"""
  return _matmult_marker_name(ann, "optional")


def is_property_type_annotation(ann: ast.expr | None) -> bool:
  """``T @property``：类体字段只读访问 → ``get_<name>() const``（存储仍为同名字段）。"""
  return _matmult_marker_name(ann, "property")


def parse_postsetter_type_annotation(
  ann: ast.expr | None,
) -> tuple[ast.expr, str, tuple[ast.expr, ...]] | None:
  """``T @property.postsetter(cb, …)`` → ``(T, kind, callbacks)``。"""
  if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
    return None
  right = ann.right
  if not isinstance(right, ast.Call) or right.keywords or not right.args:
    return None
  func = right.func
  if not isinstance(func, ast.Attribute) or func.attr != "postsetter":
    return None
  if not isinstance(func.value, ast.Name) or func.value.id not in (
    "property",
    "staticproperty",
  ):
    return None
  base_ann = copy.deepcopy(ann.left)
  while (
    is_const_type_annotation(base_ann)
    or is_optional_type_annotation(base_ann)
    or is_property_type_annotation(base_ann)
    or is_ref_type_annotation(base_ann)
    or is_postsetter_type_annotation(base_ann)
  ):
    base_ann = _strip_type_annotation_markers_once(base_ann)
  return base_ann, func.value.id, tuple(copy.deepcopy(arg) for arg in right.args)


def is_property_postsetter_type_annotation(ann: ast.expr | None) -> bool:
  """``T @property.postsetter(cb)``。"""
  parsed = parse_postsetter_type_annotation(ann)
  return parsed is not None and parsed[1] == "property"


def is_staticproperty_postsetter_type_annotation(ann: ast.expr | None) -> bool:
  """``T @staticproperty.postsetter(cb)``。"""
  parsed = parse_postsetter_type_annotation(ann)
  return parsed is not None and parsed[1] == "staticproperty"


def is_postsetter_type_annotation(ann: ast.expr | None) -> bool:
  return parse_postsetter_type_annotation(ann) is not None


def is_ref_type_annotation(ann: ast.expr | None) -> bool:
  """``T @ref``：形参/返回值/局部绑定 → C++ ``T&``（可变引用，勿按值拷贝）。"""
  return _matmult_marker_name(ann, "ref")


_TYPE_ANNOTATION_METADATA_MARKERS = frozenset(
  {"const", "final", "optional", "property", "ref", "lazy", "thread_local"},
)


def is_lazy_type_annotation(ann: ast.expr | None) -> bool:
  """``T @lazy``：形参惰性实参（``PyCallable<T>`` supplier）。"""
  return _matmult_marker_name(ann, "lazy")


def is_thread_local_type_annotation(ann: ast.expr | None) -> bool:
  """``T @thread_local``：类级 ``static thread_local`` 字段。"""
  return _matmult_marker_name(ann, "thread_local")


def iter_matmult_marker_names(ann: ast.expr | None) -> list[str]:
  """自外向内收集 ``T @A @B`` 中的标记名（``A``、``B``）。"""
  names: list[str] = []
  cur = ann
  while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.MatMult):
    right = cur.right
    if isinstance(right, ast.Name):
      names.append(right.id)
    elif isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
      names.append(right.func.id)
    cur = cur.left
  return names


def primary_field_annotation_class(ann: ast.expr | None) -> str | None:
  """``T @ComponentTableMeta @property`` → ``ComponentTableMeta``（跳过元数据标记）。"""
  for name in iter_matmult_marker_names(ann):
    if name not in _TYPE_ANNOTATION_METADATA_MARKERS:
      return name
  return None


def _strip_type_annotation_markers_once(ann: ast.expr | None) -> ast.expr | None:
  """剥一层 ``@const`` / ``@optional`` / ``@property`` / ``@ref`` / ``@lazy`` / postsetter 标记。"""
  if ann is None:
    return None
  if is_postsetter_type_annotation(ann):
    return copy.deepcopy(ann.left)
  if (
    is_const_type_annotation(ann)
    or is_final_type_annotation(ann)
    or is_optional_type_annotation(ann)
    or is_property_type_annotation(ann)
    or is_ref_type_annotation(ann)
    or is_lazy_type_annotation(ann)
    or is_thread_local_type_annotation(ann)
  ):
    return copy.deepcopy(ann.left)
  return copy.deepcopy(ann)


def strip_type_annotation_markers(ann: ast.expr | None) -> ast.expr | None:
  """去掉 ``@const`` / ``@optional`` / ``@property`` / ``@ref`` / postsetter 等标记，保留底层类型 AST。"""
  if ann is None:
    return None
  out = copy.deepcopy(ann)
  while (
    is_const_type_annotation(out)
    or is_final_type_annotation(out)
    or is_optional_type_annotation(out)
    or is_property_type_annotation(out)
    or is_ref_type_annotation(out)
    or is_postsetter_type_annotation(out)
    or is_lazy_type_annotation(out)
    or is_thread_local_type_annotation(out)
  ):
    out = _strip_type_annotation_markers_once(out)
  return out


def parse_descriptor_type_annotation(
  ann: ast.expr | None,
  descriptor_class_names: frozenset[str] | set[str],
) -> tuple[str, ast.Call] | None:
  """``T @Desc(args)`` / ``(T @Ann) @Desc(args)`` → ``(Desc, Call)``；非描述符则 ``None``。"""
  if ann is None:
    return None
  if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
    return None
  right = ann.right
  if isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
    if right.func.id in descriptor_class_names:
      return right.func.id, right
  return parse_descriptor_type_annotation(ann.left, descriptor_class_names)


def strip_descriptor_type_annotation(
  ann: ast.expr | None,
  descriptor_class_names: frozenset[str] | set[str] | None = None,
) -> ast.expr | None:
  """去掉描述符 ``@Desc(...)`` 层；保留 ``@annotation`` 等其它 ``MatMult`` 标记。"""
  if ann is None:
    return None
  if descriptor_class_names is None:
    if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
      return copy.deepcopy(ann)
    return copy.deepcopy(ann.left)
  if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
    return copy.deepcopy(ann)
  right = ann.right
  if isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
    if right.func.id in descriptor_class_names:
      return strip_descriptor_type_annotation(ann.left, descriptor_class_names)
  return copy.deepcopy(ann)


# ``@protocol`` 表：自 ``py2cpp/**/protocols.py`` AST 推导（见 ``protocol_stubs``）
from .stubs.protocol_stubs import (
  load_protocol_impl_assoc_receiver,
  load_protocol_param_erase,
  load_protocol_parametric_receiver,
)

PROTOCOL_PARAM_ERASE: frozenset[str] = load_protocol_param_erase()
PROTOCOL_PARAMETRIC_RECEIVER: frozenset[str] = load_protocol_parametric_receiver()
PROTOCOL_IMPL_ASSOC_RECEIVER: frozenset[str] = load_protocol_impl_assoc_receiver()
PROTOCOL_FUNC_TYPE_PARAM: frozenset[str] = (
  PROTOCOL_PARAM_ERASE
  | PROTOCOL_PARAMETRIC_RECEIVER
  | PROTOCOL_IMPL_ASSOC_RECEIVER
)

# PEP 695 装饰器约束（``T: refcount`` 等；Py2Cpp 扩展，非 CPython）
DECORATOR_PARAM_BOUNDS: frozenset[str] = frozenset({"refcount", "copyable", "boxing"})

_DECORATOR_BOUND_MUTEX_PAIRS: tuple[frozenset[str], ...] = (
  frozenset({"refcount", "boxing"}),
  frozenset({"refcount", "copyable"}),
  frozenset({"boxing", "copyable"}),
)


def split_typevar_bounds(
  bounds: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
  """``T: DictKey & refcount`` → 协议约束 + 装饰器约束。"""
  proto: list[str] = []
  dec: list[str] = []
  for b in bounds:
    if b in PROTOCOL_PARAM_ERASE:
      proto.append(b)
    elif b in DECORATOR_PARAM_BOUNDS:
      dec.append(b)
  return tuple(proto), tuple(dec)


def validate_typevar_decorator_bounds(
  dec_bounds: tuple[str, ...],
  *,
  context: str = "",
) -> None:
  s = set(dec_bounds)
  for pair in _DECORATOR_BOUND_MUTEX_PAIRS:
    if pair <= s:
      a, b = sorted(pair)
      msg = f"{a} 与 {b} 互斥"
      if context:
        msg = f"{context}: {msg}"
      raise SyntaxError(msg)


def merge_decorator_type_constraint(
  constraints: dict[str, tuple[str, ...]],
  tp: str,
  bound: str,
) -> None:
  if tp not in constraints:
    constraints[tp] = (bound,)
    return
  prev = constraints[tp]
  if bound not in prev:
    constraints[tp] = prev + (bound,)


@dataclass(frozen=True)
class FuncTypeParametricBound:
  """``Impl: Navigatable[Assoc]`` → ``Navigatable_requires<Impl, Assoc>``。"""

  protocol: str
  assoc_type_param: str


FuncTypeConstraint = str | tuple[str, ...] | FuncTypeParametricBound


def _merge_func_type_constraint(
  constraints: dict[str, FuncTypeConstraint],
  tp: str,
  bound: str,
) -> None:
  """合并同一模板形参上的多条 ``@protocol`` 约束（如 ``DictKey`` + ``Navigatable``）。"""
  if tp not in constraints:
    constraints[tp] = bound
    return
  prev = constraints[tp]
  if isinstance(prev, str):
    if prev == bound:
      return
    constraints[tp] = (prev, bound)
    return
  if bound not in prev:
    constraints[tp] = prev + (bound,)


def _merge_func_type_parametric_constraint(
  constraints: dict[str, FuncTypeConstraint],
  impl_tp: str,
  protocol: str,
  assoc_tp: str,
) -> None:
  constraints[impl_tp] = FuncTypeParametricBound(protocol, assoc_tp)


def _protocol_assoc_for_parametric_bound(
  assoc_name: str,
  *,
  used: set[str],
) -> str:
  """方括号内关联类型：已声明模板形参保留名；具体类型（``int`` 等）→ ``PyInt``。"""
  if assoc_name in used:
    return assoc_name
  return cpp_ident(assoc_name)


def protocol_param_template_from_annotation(
  ann: ast.expr,
) -> tuple[str, str | None] | None:
  """``Comparable`` / ``Iterable[T]`` / ``Navigatable[Node]`` → ``(协议名, 关联形参或 None)``。"""
  match ann:
    case ast.Name(id=name):
      if name in PROTOCOL_FUNC_TYPE_PARAM:
        return name, None
    case ast.Subscript(value=ast.Name(id=proto), slice=ast.Name(id=tp)):
      if proto in PROTOCOL_FUNC_TYPE_PARAM:
        return proto, tp
    case _:
      return None


def arg_has_none_default(func: ast.FunctionDef, arg: ast.arg) -> bool:
  """形参默认值为 ``None``（如 ``key=None``）。"""
  args = func.args.args
  defaults = func.args.defaults
  if not defaults:
    return False
  n_required = len(args) - len(defaults)
  for i, a in enumerate(args):
    if a is arg:
      if i < n_required:
        return False
      d = defaults[i - n_required]
      return isinstance(d, ast.Constant) and d.value is None
  return False


IMPLICIT_VOID_DUNDER_METHODS: frozenset[str] = frozenset({
  "__init__",
  "__del__",
  "__copy__",
  "__move__",
  "__exit__",
  "__post_init__",
  "__setitem__",
  "__setattr__",
  "__delattr__",
  "__delitem__",
  "assign",
})


def is_void_return_annotation(ann: ast.expr | None) -> bool:
  """``-> None`` / ``-> NoneType`` → C++ ``void``。"""
  if ann is None:
    return False
  if isinstance(ann, ast.Constant) and ann.value is None:
    return True
  if isinstance(ann, ast.Name) and ann.id in ("None", "NoneType"):
    return True
  return False


@dataclass(frozen=True)
class FuncTypeParams:
  """函数级模板参数：无注解形参 ``__T0``…；``@protocol`` 注解与 PEP 695 约束 → ``*_requires``。"""

  template_names: list[str]
  typevar_tuple: str | None
  arg_types: dict[str, str]
  constraints: dict[str, FuncTypeConstraint]
  decorator_constraints: dict[str, tuple[str, ...]] = field(default_factory=dict)
  capture_params: tuple[str, ...] = ()
  """``_U = …`` 捕获形参：调用侧不传，由 type if 模式绑定。"""

  @classmethod
  def _skip_func_arg(cls, func: ast.FunctionDef, arg: ast.arg) -> bool:
    if arg.arg == "self":
      return True
    if arg_has_none_default(func, arg):
      return True
    return func.name in ("__copy__", "__move__") and arg.arg == "other"

  @classmethod
  def collect(cls, func: ast.FunctionDef, reserved: frozenset[str] | None = None) -> FuncTypeParams:
    if func.name == "main":
      return cls([], None, {}, {}, {}, ())
    from .variadic_template import parse_function_type_params

    header_regular, header_capture, header_tuple = parse_function_type_params(func)
    used = set(reserved or ())
    template_names: list[str] = []
    arg_types: dict[str, str] = {}
    constraints: dict[str, FuncTypeConstraint] = {}
    decorator_constraints: dict[str, tuple[str, ...]] = {}
    idx = 0
    ctx = f"def {func.name}"

    def alloc_tparam() -> str:
      nonlocal idx
      name = auto_template_type_param_name(f"T{idx}", reserved=used)
      idx += 1
      used.add(name)
      return name

    def apply_protocol_bound(
      impl_tp: str,
      proto: str,
      assoc_tp: str | None,
    ) -> None:
      if assoc_tp is not None and (
        proto in PROTOCOL_PARAMETRIC_RECEIVER
        or proto in PROTOCOL_IMPL_ASSOC_RECEIVER
      ):
        bound_assoc = _protocol_assoc_for_parametric_bound(
          assoc_tp, used=used,
        )
        _merge_func_type_parametric_constraint(
          constraints, impl_tp, proto, bound_assoc,
        )
        if assoc_tp in used and assoc_tp not in template_names:
          template_names.append(assoc_tp)
        return
      if assoc_tp is None:
        _merge_func_type_constraint(constraints, impl_tp, proto)
        return
      if assoc_tp not in used:
        used.add(assoc_tp)
      if assoc_tp not in template_names:
        template_names.append(assoc_tp)
      _merge_func_type_constraint(constraints, assoc_tp, proto)

    for name in header_regular:
      template_names.append(name)
      used.add(name)

    for tp in getattr(func, "type_params", None) or ():
      match tp:
        case ast.TypeVar(name=name):
          bound = tp.bound
          if bound is not None:
            parsed = protocol_param_template_from_annotation(bound)
            if parsed is not None:
              proto, assoc_tp = parsed
              apply_protocol_bound(name, proto, assoc_tp)
            elif isinstance(bound, ast.Name) and bound.id in PROTOCOL_PARAM_ERASE:
              _merge_func_type_constraint(constraints, name, bound.id)
            else:
              bounds = parse_typevar_protocol_bounds(bound)
              if bounds:
                proto_bounds, dec_bounds = split_typevar_bounds(bounds)
                validate_typevar_decorator_bounds(dec_bounds, context=ctx)
                for pb in proto_bounds:
                  _merge_func_type_constraint(constraints, name, pb)
                for db in dec_bounds:
                  merge_decorator_type_constraint(decorator_constraints, name, db)

    unannotated: list[ast.arg] = []
    for arg in func.args.args:
      if cls._skip_func_arg(func, arg):
        continue
      if arg.annotation:
        parsed = protocol_param_template_from_annotation(arg.annotation)
        if parsed is not None:
          proto, assoc_tp = parsed
          if assoc_tp is not None and (
            proto in PROTOCOL_PARAMETRIC_RECEIVER
            or proto in PROTOCOL_IMPL_ASSOC_RECEIVER
          ):
            impl_tp = alloc_tparam()
            template_names.append(impl_tp)
            bound_assoc = _protocol_assoc_for_parametric_bound(
              assoc_tp, used=used,
            )
            _merge_func_type_parametric_constraint(
              constraints, impl_tp, proto, bound_assoc,
            )
            arg_types[arg.arg] = impl_tp
            if assoc_tp in used and assoc_tp not in template_names:
              template_names.append(assoc_tp)
          else:
            impl_tp = assoc_tp if assoc_tp is not None else alloc_tparam()
            if impl_tp not in used:
              used.add(impl_tp)
            if impl_tp not in template_names:
              template_names.append(impl_tp)
            _merge_func_type_constraint(constraints, impl_tp, proto)
            arg_types[arg.arg] = impl_tp
        continue
      unannotated.append(arg)

    for arg in unannotated:
      tp = alloc_tparam()
      template_names.append(tp)
      arg_types[arg.arg] = tp

    return cls(
      template_names,
      header_tuple,
      arg_types,
      constraints,
      decorator_constraints,
      header_capture,
    )


@dataclass(frozen=True)
class MethodSig:
  """类方法的 C++ 签名与形参类型表（预处理结果）。"""

  func_ft: FuncTypeParams
  ret_lead: str
  ret_trail: str
  params_decl: str
  params_def: str
  param_types: dict[str, str]
  doc_lines: tuple[str, ...]
  is_next: bool
  result_cpp_type: str
  vararg_pack: "VarargPackInfo | None" = None
  variadic_template: "VariadicTemplateInfo | None" = None
  is_const: bool = False
  is_static: bool = False
  is_virtual: bool = False
  is_override: bool = False
  is_final: bool = False
  is_abstract: bool = False
  is_noexcept: bool = False
  noexcept_ok_cpp: str = ""
  noexcept_err_cpp: str = ""
  lazy_params: dict[str, "LazyParamInfo"] = field(default_factory=dict)
  param_type_nodes: dict[str, "TypeNode"] = field(default_factory=dict)
  return_type_node: "TypeNode | None" = None


@dataclass(frozen=True)
class FunctionSig:
  """模块级函数（含 ``main``）的 C++ 签名。"""

  func_ft: FuncTypeParams
  ret_lead: str
  ret_trail: str
  params: str
  param_types: dict[str, str]
  doc_lines: tuple[str, ...]
  vararg_pack: "VarargPackInfo | None" = None
  variadic_template: "VariadicTemplateInfo | None" = None
  is_noexcept: bool = False
  noexcept_ok_cpp: str = ""
  noexcept_err_cpp: str = ""
  lazy_params: dict[str, "LazyParamInfo"] = field(default_factory=dict)
  param_type_nodes: dict[str, "TypeNode"] = field(default_factory=dict)
  return_type_node: "TypeNode | None" = None


@dataclass
class ModuleAnalysis:
  """单个 Python 模块的文档与头文件依赖。"""

  path: str
  doc_lines: list[str] = field(default_factory=list)
  includes: list[str] = field(default_factory=list)
  """类定义之前的 ``#include``。"""
  forward_decls: list[str] = field(default_factory=list)
  """打破 ``str`` ↔ 容器循环依赖时的前向声明。"""
  post_class_includes: list[str] = field(default_factory=list)
  """完整类定义之后才安全的 ``#include``（如 ``str.h`` 依赖 ``PyList``）。"""
  type_aliases: list[TypeAliasInfo] = field(default_factory=list)
  """模块级 ``type Alias = ...`` → 头文件中的 ``using``。"""


@dataclass
class PropertyDef:
  """``@property`` / ``@property.setter`` / ``@property.postsetter`` 对应方法。"""

  name: str
  getter: ast.FunctionDef | None = None
  setter: ast.FunctionDef | None = None
  postsetter: ast.FunctionDef | None = None
  getter_sig: MethodSig | None = None
  setter_sig: MethodSig | None = None
  postsetter_sig: MethodSig | None = None
  # 泛型 ``@descriptor`` 内联：对宿主字段具体类型做 ``@protocol`` 编译期校验
  descriptor_protocol_bounds: tuple[str, ...] = ()
  from_descriptor: bool = False


def resolve_host_cpp_type(name: str, host_template_cpp: str | None) -> str | None:
  """``Self`` / ``Super`` 或 mixin 内联后的宿主 C++ 基名 → 完整模板类型。"""
  if not host_template_cpp:
    return None
  base = host_template_cpp.partition("<")[0].strip()
  if name in ("Self", "Super", base):
    return host_template_cpp
  return None


def class_base_name(base: ast.expr) -> str | None:
  """``Mixin[T]`` / ``Mixin`` → 基类名（供 ``expand_mixins`` 解析）。"""
  if isinstance(base, ast.Name):
    return base.id
  if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
    return base.value.id
  return None


def parse_class_friends(node: ast.ClassDef) -> list[str]:
  """``class B(friends=(A,))`` → ``['A', …]``（友元类名；同模块可前向引用，译器全文件解析后绑定）。"""
  out: list[str] = []
  for kw in node.keywords:
    if kw.arg != "friends":
      continue
    match kw.value:
      case ast.Tuple(elts=elts):
        for elt in elts:
          name = class_base_name(elt)
          if name is not None:
            out.append(name)
          elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            raise SyntaxError(
              f"{node.name}: friends= 勿用字符串 '{elt.value}'，请写类名 "
              f"（同模块可前向：友元类可在宿主类之后定义；运行时 import 须友元类已存在，"
              f"一般将友元类声明放在宿主类之前，见 ``py2cpp/util/dict.py``）"
            )
      case ast.Name(id=name):
        out.append(name)
      case ast.Constant(value=v) if isinstance(v, str):
        raise SyntaxError(
          f"{node.name}: friends= 勿用字符串 '{v}'，请写类名 "
          f"（同模块前向引用见编码规范 §4.1）"
        )
      case _:
        raise SyntaxError(
          f"{node.name}: friends= 须为类名或 (Class, …) 元组"
        )
  return out


@dataclass
class UnionVariantInfo:
  """``@union`` 内 ``@variant`` 嵌套类的载荷字段（不单独生成 C++ 类）。"""

  name: str
  fields: list[str]
  field_annotations: dict[str, ast.expr] = field(default_factory=dict)
  field_cpp_types: dict[str, str] = field(default_factory=dict)

  @property
  def is_unit(self) -> bool:
    return not self.fields


@dataclass(frozen=True)
class EnumMemberInfo:
  """``@enum`` 成员名与整型值（``...`` 已在 expand 阶段解析）。"""

  name: str
  value: int


class ClassInfo:
  """一个 ``class`` 定义的布局与成员元数据。"""

  def __init__(
    self,
    node: ast.ClassDef,
    module_path: str = "",
    *,
    outer_class: ClassInfo | None = None,
  ):
    self.node = node
    self.name = node.name
    self.module_path = module_path
    self.outer_class = outer_class
    self.nested_classes: list[ClassInfo] = []
    (
      self.type_params,
      self.capture_params,
      self.typevar_tuple,
      self.type_param_constraints,
      self.type_param_oneof_constraints,
      self.type_param_defaults,
      self.type_param_nttp,
      self.type_param_decorator_constraints,
    ) = parse_class_type_params(node)
    self.concrete_oneof_constraints: dict[str, tuple[str, ...]] = {}
    self.type_alias_list: list[TypeAliasInfo] = []
    self.type_aliases: dict[str, TypeAliasInfo] = {}
    self.bases: list[str] = []
    for base in node.bases:
      name = class_base_name(base)
      if name is not None:
        self.bases.append(name)
    self.friend_classes: list[str] = parse_class_friends(node)
    self.cpp_rename: str | None = decorator_string_arg(node, "native_name")
    self.fields: list[str] = []
    self.field_types: dict[str, str] = {}
    self.field_type_nodes: dict[str, "TypeNode"] = {}
    self.methods: dict[str, ast.FunctionDef] = {}
    self.method_overloads: dict[str, list[ast.FunctionDef]] = {}
    self.method_overload_sigs: dict[str, list[MethodSig]] = {}
    self.inits: list[ast.FunctionDef] = []
    self.init_sigs: list[MethodSig] = []
    self.has_copy: bool = False
    self.has_move: bool = False
    self.is_refcount: bool = self._has_refcount_decorator(node)
    self.is_descriptor: bool = False
    self.is_mixin: bool = False
    self.is_annotation: bool = False
    self.is_copyable: bool = has_named_decorator(node, "copyable")
    self.is_uncopyable: bool = has_named_decorator(node, "uncopyable")
    self.is_final: bool = has_named_decorator(node, "final")
    self.is_boxing: bool = has_named_decorator(node, "boxing")
    self.is_native: bool = has_named_decorator(node, "native")
    self.is_protocol: bool = has_named_decorator(node, "protocol")
    self.is_dataclass: bool = False
    self.dataclass_options: object | None = None
    self.annotation_options: object | None = None
    self.dataclass_field_specs: list | None = None
    self.is_serializable: bool = has_named_decorator(node, "serializable")
    self.is_union: bool = (
      has_named_decorator(node, "union") or has_union_mro_decorator(node)
    )
    self.is_enum: bool = has_named_decorator(node, "enum") or has_enum_mro_decorator(node)
    self.is_enum_mro: bool = has_enum_mro_decorator(node)
    self.is_union_mro: bool = has_union_mro_decorator(node)
    self.enum_mro_base: str | None = parse_enum_mro_base(node) if self.is_enum_mro else None
    self.union_mro_base: str | None = (
      parse_enum_mro_base(node) if self.is_union_mro else None
    )
    self.enum_mro_member_classes: dict[str, str] = {}
    self.union_mro_member_classes: dict[str, str] = {}
    self.union_enum_members: list[EnumMemberInfo] = []
    self.union_enum_underlying_cpp: str = cpp_ident("int")
    self.enum_members: list[EnumMemberInfo] = []
    self.enum_underlying_cpp: str = cpp_ident("int")
    self.enum_is_flag: bool = False
    self.enum_parent: str | None = None
    self.class_id: int | None = None
    self.class_id_root: str | None = None
    self.inject_type_id: bool = False
    self.force_virtual_class_id: bool = False
    self.inject_type_base: bool = False
    self.is_proxy: bool = False
    self.is_proxy_derived: bool = False
    self.is_variant_mixin: bool = (
      has_named_decorator(node, "variant") and not self.is_union
    )
    self.variant_mixin_fields: list[tuple[str, ast.expr]] = []
    self.union_variants: list[UnionVariantInfo] = []
    self.union_family_names: frozenset[str] = frozenset()
    self.protocol_methods: list[str] = []
    self.protocol_members: list[ProtocolMemberConstraint] = []
    self.field_annotations: dict[str, str] = {}
    self.field_annotation_markers: dict[str, list[str]] = {}
    self.field_annotation_kwargs: dict[str, dict[str, str]] = {}
    self.doc_lines: list[str] = docstring_lines(node)
    self.method_sigs: dict[str, MethodSig] = {}
    self.properties: dict[str, PropertyDef] = {}
    self.static_properties: dict[str, PropertyDef] = {}
    # ``@staticproperty`` 存储 ``{name}__value`` → C++ ``static`` 可变成员
    self.static_property_storage: set[str] = set()
    # 类体 ``name: T @const = <编译期常量>`` → C++ ``static const`` 成员
    self.static_class_fields: dict[str, ast.AnnAssign] = {}
    # 类体 ``name: T @thread_local = v`` → C++ ``static thread_local`` 成员
    self.thread_local_fields: dict[str, ast.AnnAssign] = {}
    # 类体 ``name: T = <默认>``（无 ``@const``）→ 实例字段默认值（供 dataclass 等）
    self.field_defaults: dict[str, ast.expr] = {}
    # 类体 ``name: T`` 显式实例字段注解（``__init__`` 赋值推断不得覆盖）
    self.class_body_field_anns: set[str] = set()
    # ``name: T @optional``：不参与 ``__init__`` / ``assign`` 关键字（由 ``expand_dataclass`` 填充）
    self.optional_fields: set[str] = set()
    # ``name: T @final``：实例 const 成员；``__init__`` 赋值 → C++ ctor 初始化列表
    self.final_fields: set[str] = set()
    self.final_ctor_inits: dict[str, ast.expr] = {}
    self.final_ctor_inits_by_init: dict[int, dict[str, ast.expr]] = {}
    # ``name: T @property = …``：对外 ``get_<name>()``，类内 ``self.name`` 仍访问存储字段
    self.field_properties: set[str] = set()
    self.postsetter_properties: set[str] = set()
    # 成员访问级别（``analysis.access.resolve_member_access`` 填充）
    self.member_access: dict[str, str] = {}
    self.member_cpp_names: dict[str, str] = {}
    # 字段名 → (元素 C++ 类型, "free" | "freeArray")，由 __init__ 中 alloc/allocArray 推断
    self.owned_fields: dict[str, tuple[str, str]] = {}
    # ``allocArray`` 字段在构造使用整数字面量大小时的元素个数
    self.owned_array_sizes: dict[str, int] = {}
    self.repr_aliases_str: bool = False
    # ``expand_default_iter`` 注入的序列迭代器类名（如 ``Foo_iterator``）
    self.seq_iterator_name: str | None = None
    self.class_type_if_plan = None
    self.class_type_if_specs: list = []
    # 描述符签名校验 helper / ``set_<field>`` → 须满足的 ``@protocol`` 名（按形参顺序）
    self.descriptor_method_protocol_bounds: dict[str, tuple[str, ...]] = {}
    for stmt in node.body:
      if isinstance(stmt, ast.TypeAlias):
        alias = parse_type_alias_stmt(stmt)
        self.type_alias_list.append(alias)
        self.type_aliases[alias.name] = alias
      elif isinstance(stmt, ast.AnnAssign):
        if self.is_enum:
          raise SyntaxError(
            f"{self.name}: @enum 成员须写 ``name = 值`` 或 ``name = ...``，勿用类型注解赋值",
          )
        if (
          self.is_protocol
          and isinstance(stmt.target, ast.Name)
          and type_alias_rhs_is_ellipsis(stmt.value)
        ):
          self.protocol_members.append(
            ProtocolMemberConstraint(
              stmt.target.id, "field", stmt.annotation,
            ),
          )
        else:
          self._field_from_class_ann(stmt)
      elif isinstance(stmt, ast.Assign):
        if self.is_enum:
          continue
        if self._try_repr_alias_str(stmt):
          continue
        self._field_from_class_assign(stmt)
      elif isinstance(stmt, ast.ClassDef):
        nested = ClassInfo(stmt, module_path, outer_class=self)
        self.nested_classes.append(nested)
      elif isinstance(stmt, ast.FunctionDef):
        sp_kind = self._static_property_decorator_kind(stmt)
        if sp_kind is not None:
          kind, sp_name = sp_kind
          prop = self.static_properties.setdefault(sp_name, PropertyDef(name=sp_name))
          if kind == "getter":
            if prop.postsetter is not None:
              raise ValueError(
                f"{self.name}.{sp_name}: 已有 ``@staticproperty.postsetter``，"
                f"不可再写 ``@staticproperty`` getter"
              )
            prop.getter = self._normalize_static_property_method(stmt)
            self._collect_fields(prop.getter)
          elif kind == "setter":
            if prop.postsetter is not None:
              raise ValueError(
                f"{self.name}.{sp_name}: 已有 ``@staticproperty.postsetter``，"
                f"不可再写 ``@staticproperty.setter``"
              )
            prop.setter = self._normalize_static_property_method(stmt)
            self._collect_fields(prop.setter)
          else:
            if prop.getter is not None or prop.setter is not None:
              raise ValueError(
                f"{self.name}.{sp_name}: ``@staticproperty.postsetter`` 与 "
                f"getter/setter 互斥"
              )
            prop.postsetter = self._normalize_static_property_method(stmt)
            self._collect_fields(prop.postsetter)
          continue
        prop_kind = self._property_decorator_kind(stmt)
        if prop_kind is not None:
          kind, pname = prop_kind
          prop = self.properties.setdefault(pname, PropertyDef(name=pname))
          if kind == "getter":
            if prop.postsetter is not None:
              raise ValueError(
                f"{self.name}.{pname}: 已有 ``@property.postsetter``，"
                f"不可再写 ``@property`` getter"
              )
            prop.getter = stmt
          elif kind == "setter":
            if prop.postsetter is not None:
              raise ValueError(
                f"{self.name}.{pname}: 已有 ``@property.postsetter``，"
                f"不可再写 ``@property.setter``"
              )
            prop.setter = stmt
          else:
            if prop.getter is not None or prop.setter is not None:
              raise ValueError(
                f"{self.name}.{pname}: ``@property.postsetter`` 与 getter/setter 互斥"
              )
            prop.postsetter = stmt
          self._collect_fields(stmt)
          continue
        if stmt.name == "__init__":
          self.inits.append(stmt)
          self._collect_fields_from_init(stmt)
          if has_named_decorator(stmt, "overload"):
            self.method_overloads.setdefault(stmt.name, []).append(stmt)
        elif has_named_decorator(stmt, "overload"):
          self.method_overloads.setdefault(stmt.name, []).append(stmt)
          if stmt.name == "__copy__":
            self.has_copy = True
          elif stmt.name == "__move__":
            self.has_move = True
          self._collect_fields(stmt)
        else:
          self.methods[stmt.name] = stmt
          if stmt.name == "__copy__":
            self.has_copy = True
          elif stmt.name == "__move__":
            self.has_move = True
          self._collect_fields(stmt)

    self._strip_type_param_forward_aliases()

  def _strip_type_param_forward_aliases(self) -> None:
    if not self.type_params:
      return
    tps = set(self.type_params)
    drop = [
      name for name, alias in self.type_aliases.items()
      if is_type_param_forward_alias(alias, tps)
    ]
    for name in drop:
      del self.type_aliases[name]
    if drop:
      self.type_alias_list = [
        a for a in self.type_alias_list if a.name not in drop
      ]

  @staticmethod
  def _static_property_decorator_kind(func: ast.FunctionDef) -> tuple[str, str] | None:
    """``@staticproperty`` / ``@staticproperty.setter`` / ``@staticproperty.postsetter``。"""
    for dec in func.decorator_list:
      if isinstance(dec, ast.Name) and dec.id == "staticproperty":
        return ("getter", func.name)
      if isinstance(dec, ast.Attribute) and dec.attr == "setter":
        if isinstance(dec.value, ast.Name) and dec.value.id == "staticproperty":
          return ("setter", func.name)
      if isinstance(dec, ast.Attribute) and dec.attr == "postsetter":
        if isinstance(dec.value, ast.Name) and dec.value.id == "staticproperty":
          return ("postsetter", func.name)
    return None

  @staticmethod
  def _normalize_static_property_method(func: ast.FunctionDef) -> ast.FunctionDef:
    """``@staticproperty`` / ``@staticproperty.setter`` 不要求 ``cls`` 参数；若写了则剥离。"""
    args = list(func.args.args)
    if args and args[0].arg in ("cls", "self"):
      out = copy.deepcopy(func)
      out.args.args = args[1:]
      return out
    return func

  @staticmethod
  def _property_decorator_kind(func: ast.FunctionDef) -> tuple[str, str] | None:
    """``@property`` / ``@property.setter`` / ``@property.postsetter``。"""
    for dec in func.decorator_list:
      if isinstance(dec, ast.Name) and dec.id == "property":
        return ("getter", func.name)
      if isinstance(dec, ast.Attribute) and dec.attr == "setter":
        if isinstance(dec.value, ast.Name):
          if dec.value.id == "property":
            return ("setter", func.name)
          raise ValueError(
            f"{func.name}: 请写 ``@property.setter``，"
            f"勿写 ``@{dec.value.id}.setter``"
          )
      if isinstance(dec, ast.Attribute) and dec.attr == "postsetter":
        if isinstance(dec.value, ast.Name) and dec.value.id == "property":
          return ("postsetter", func.name)
    return None

  def is_template(self) -> bool:
    return bool(self.type_params) or bool(self.typevar_tuple)

  def class_registry_key(self) -> str:
    parts: list[str] = []
    cur: ClassInfo | None = self
    while cur is not None:
      parts.append(cur.name)
      cur = cur.outer_class
    return ".".join(reversed(parts))

  @property
  def effective_type_params(self) -> list[str]:
    if self.outer_class is None:
      return list(self.type_params)
    return list(self.outer_class.type_params) + list(self.type_params)

  def cpp_name(self) -> str:
    if self.cpp_rename:
      # FFI @native 结构体：Python 名（Pyi_*）即 C++ 名；native_name 仅供 using → C 标签
      from ..constant.ffi_layout import is_ffi_c_struct_class

      if is_ffi_c_struct_class(self):
        return cpp_ident(self.name)
      return cpp_ident(self.cpp_rename)
    return cpp_ident(self.name)

  def template_cpp_type(self) -> str:
    """``list[T]`` → ``PyList<T>``；无类型参数时同 ``cpp_name()``。"""
    base = self.cpp_name()
    if self.type_params:
      return f"{base}<{', '.join(self.type_params)}>"
    return base

  @staticmethod
  def _has_refcount_decorator(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
      if isinstance(dec, ast.Name) and dec.id == "refcount":
        return True
      if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "refcount":
        return True
    return False

  def storage_cpp_type(self) -> str:
    """变量/返回值类型：``@refcount`` 时为 ``PyRefCount<T>``，否则为 ``T``。"""
    if self.is_refcount:
      return cpp_refcount_type(self.cpp_name())
    return self.cpp_name()

  def resolve_instance_property(
    self,
    name: str,
    classes: dict[str, ClassInfo],
    *,
    need_setter: bool = False,
  ) -> tuple[ClassInfo, PropertyDef] | None:
    """沿继承链查找 ``@property``（含基类定义、子类接收者）。"""
    stack: list[ClassInfo] = [self]
    seen: set[str] = set()
    idx = 0
    while idx < len(stack):
      cur = stack[idx]
      idx += 1
      if cur.name in seen:
        continue
      seen.add(cur.name)
      prop = cur.properties.get(name)
      if prop is not None:
        if need_setter:
          if prop.setter or prop.postsetter:
            return cur, prop
        elif prop.getter:
          return cur, prop
      for base_name in cur.bases:
        base_info = classes.get(base_name)
        if base_info is not None:
          stack.append(base_info)
    return None

  def cpp_member_name(self, name: str) -> str:
    if name in self.member_cpp_names:
      return self.member_cpp_names[name]
    return escape_cpp_param(name)

  def member_access_level(self, name: str) -> str:
    from .access import default_member_access

    if name in self.member_access:
      return self.member_access[name]
    acc, _ = default_member_access(name, self.name)
    return acc

  @property
  def has_virtual_methods(self) -> bool:
    """类中是否存在 ``@virtual`` / ``@override`` 方法（需虚析构与动态派发）。"""
    sigs: list[MethodSig] = list(self.method_sigs.values())
    for overload_sigs in self.method_overload_sigs.values():
      sigs.extend(overload_sigs)
    return any(sig.is_virtual or sig.is_override or sig.is_abstract for sig in sigs)

  def iter_methods(self) -> list[ast.FunctionDef]:
    """类中全部方法（含 ``@overload`` 重载与实现）。"""
    out: list[ast.FunctionDef] = list(self.methods.values())
    for overloads in self.method_overloads.values():
      out.extend(overloads)
    return out

  def method_sig_for(self, method: ast.FunctionDef) -> MethodSig | None:
    for name, defs in self.method_overloads.items():
      if method in defs:
        return self.method_overload_sigs[name][defs.index(method)]
    sig = self.method_sigs.get(method.name)
    if sig is not None:
      return sig
    if self.class_type_if_specs:
      for spec in self.class_type_if_specs:
        msig = spec.method_sigs.get(method.name)
        if msig is not None:
          return msig
    return None

  def needs_auto_dtor(self) -> bool:
    """构造里曾 ``alloc``/``allocArray`` 的字段需在析构释放，且用户未写 ``__del__``。"""
    return bool(self.owned_fields) and "__del__" not in self.methods

  def needs_auto_copy(self) -> bool:
    """未手写 ``__copy__`` 时：``@copyable``，或仅 ``alloc()`` 单对象字段（非 ``allocArray`` 容器）。"""
    if self.is_uncopyable:
      return False
    if "__copy__" in self.methods:
      return False
    if self.is_copyable:
      return True
    return any(kind == "free" for _, kind in self.owned_fields.values())

  def needs_auto_move(self) -> bool:
    """未手写 ``__move__`` 且构造里分配了堆字段时生成默认移动（窃取指针）。"""
    return "__move__" not in self.methods and bool(self.owned_fields)

  def has_destructor(self) -> bool:
    return "__del__" in self.methods or self.needs_auto_dtor()

  def uses_auto_copy(self) -> bool:
    return "__copy__" in self.methods or self.needs_auto_copy()

  def uses_auto_move(self) -> bool:
    return "__move__" in self.methods or self.needs_auto_move()

  @staticmethod
  def unwrap_refcount_type(cpp_type: str) -> str:
    inner = cpp_template_inner_args(cpp_type.strip(), CPP_REFCount_PREFIX)
    return inner.strip() if inner is not None else cpp_type.strip()

  @staticmethod
  def apply_refcount_storage_cpp_type(
    cpp_type: str, classes: dict[str, "ClassInfo"]
  ) -> str:
    """``@refcount`` 类在容器元素、参数、局部变量等处用 ``PyRefCount<T>``。"""
    t = cpp_type.strip()
    if _type_pred().is_refcount_type(t):
      return t
    for prefix in (
      CPP_LIST_PREFIX,
      CPP_DEQUE_PREFIX,
      CPP_SET_PREFIX,
      CPP_FROZENSET_PREFIX,
      CPP_FROZENLIST_PREFIX,
    ):
      if t.startswith(prefix) and t.endswith(">"):
        parts = split_cpp_template_args(t[len(prefix) : -1])
        if parts:
          parts[0] = ClassInfo.apply_refcount_storage_cpp_type(parts[0].strip(), classes)
          return f"{prefix}{', '.join(parts)}>"
        return t
    for prefix in (CPP_DICT_PREFIX, CPP_FROZENDICT_PREFIX):
      if t.startswith(prefix) and t.endswith(">"):
        parts = split_cpp_template_args(t[len(prefix) : -1])
        if len(parts) >= 2:
          inner = ", ".join(
            ClassInfo.apply_refcount_storage_cpp_type(p.strip(), classes)
            for p in parts
          )
          return f"{prefix}{inner}>"
    if _type_pred().is_tuple_type(t):
      parts = cpp_tuple_element_types(t)
      if parts:
        inner = ", ".join(
          ClassInfo.apply_refcount_storage_cpp_type(p.strip(), classes)
          for p in parts
        )
        return f"{CPP_TUPLE_PREFIX}{inner}>"
    for info in classes.values():
      if not info.is_refcount:
        continue
      bare = info.cpp_name()
      if t == bare or t == info.storage_cpp_type():
        return info.storage_cpp_type()
      if t.startswith(f"{bare}<") and t.endswith(">"):
        return cpp_refcount_type(t)
    return ClassInfo.apply_boxing_storage_cpp_type(t, classes)

  @staticmethod
  def apply_boxing_storage_cpp_type(
    cpp_type: str, classes: dict[str, "ClassInfo"]
  ) -> str:
    """``@boxing`` 类在局部/参数/字段等处用 ``T*``（等价 ``Pointer[T]``）。"""
    t = cpp_type.strip()
    if t.endswith("*"):
      return t
    for prefix in (CPP_ARRAY_PREFIX, CPP_ARRAY2D_PREFIX, CPP_ARRAY3D_PREFIX):
      if t.startswith(prefix) and t.endswith(">"):
        inner = ClassInfo.apply_boxing_storage_cpp_type(t[len(prefix) : -1], classes)
        return f"{prefix}{inner}>"
    for info in classes.values():
      if not info.is_boxing:
        continue
      bare = info.cpp_name()
      spec = info.cpp_specialization()
      if t == spec or t == bare:
        return f"{t}*"
      # ``Self`` / ``template_cpp_type()`` 用 ``Key`` 等别名，``cpp_specialization()`` 用 ``_Key``。
      if t.startswith(f"{bare}<") and t.endswith(">"):
        return f"{t}*"
    return t

  def cpp_specialization(self) -> str:
    name = self.cpp_name()
    if self.typevar_tuple:
      tpl = cpp_type_param_template_name(self.typevar_tuple)
      if self.type_params:
        args = ", ".join(cpp_type_param_template_name(p) for p in self.type_params) + f", {tpl}..."
        return f"{name}<{args}>"
      return f"{name}<{tpl}...>"
    if not self.type_params:
      return name
    return f"{name}<{', '.join(cpp_type_param_template_name(p) for p in self.type_params)}>"

  def _collect_fields_from_init(self, func: ast.FunctionDef):
    for stmt in func.body:
      if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
          self._field_from_target(target)
      elif isinstance(stmt, ast.AnnAssign):
        self._field_from_target(stmt.target, stmt.annotation)

  def _collect_fields(self, node: ast.AST):
    for child in ast.walk(node):
      if isinstance(child, ast.Assign):
        for target in child.targets:
          self._field_from_target(target)
      elif isinstance(child, ast.AnnAssign):
        self._field_from_target(child.target, child.annotation)

  @staticmethod
  def _is_class_static_initializer(value: ast.expr | None) -> bool:
    """``T @const = <编译期常量>`` 的右值须为整型/浮点/布尔字面量或标量静态属性。"""
    if value is None:
      return False
    if scalar_type_static_attr_from_expr(value) is not None:
      return True
    if isinstance(value, ast.Constant):
      return isinstance(value.value, (int, float, bool))
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
      inner = value.operand
      return isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float))
    return False

  def _try_repr_alias_str(self, stmt: ast.Assign) -> bool:
    """``__repr__ = __str__``：与 ``__str__`` 共用实现。"""
    if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
      return False
    if stmt.targets[0].id != "__repr__":
      return False
    if not isinstance(stmt.value, ast.Name) or stmt.value.id != "__str__":
      return False
    self.repr_aliases_str = True
    return True

  def _field_from_class_assign(self, stmt: ast.Assign) -> None:
    """类体 ``_test_tag = 1``：覆盖混入声明的 ``static const`` 初值。"""
    if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
      return
    name = stmt.targets[0].id
    if not self._is_class_static_initializer(stmt.value):
      return
    ann: ast.expr | None = None
    if name in self.static_class_fields:
      ann = self.static_class_fields[name].annotation
    if ann is None:
      ann = ast.Name(id="int", ctx=ast.Load())
    self.static_class_fields[name] = ast.AnnAssign(
      target=ast.Name(id=name, ctx=ast.Store()),
      annotation=copy.deepcopy(ann),
      value=copy.deepcopy(stmt.value),
      simple=1,
    )

  def _field_from_class_ann(self, stmt: ast.AnnAssign):
    from .type_emit import write_field_ann_ast, write_field_storage

    base_ann = strip_type_annotation_markers(stmt.annotation)
    if isinstance(stmt.target, ast.Name):
      name = stmt.target.id
      if is_const_type_annotation(stmt.annotation):
        if not self._is_class_static_initializer(stmt.value):
          return
        static_stmt = ast.AnnAssign(
          target=ast.Name(id=name, ctx=ast.Store()),
          annotation=copy.deepcopy(base_ann) if base_ann is not None else None,
          value=copy.deepcopy(stmt.value),
          simple=1,
        )
        ast.fix_missing_locations(static_stmt)
        self.static_class_fields[name] = static_stmt
        if base_ann is not None:
          write_field_storage(self, name, None)
          write_field_ann_ast(self, name, base_ann)
        return
      if is_thread_local_type_annotation(stmt.annotation):
        markers = set(iter_matmult_marker_names(stmt.annotation))
        if "const" in markers or "final" in markers or "property" in markers:
          raise NotImplementedError(
            f"{self.name}.{name}: ``@thread_local`` 不支持与 ``@const`` / ``@final`` / ``@property`` 叠用"
          )
        static_stmt = ast.AnnAssign(
          target=ast.Name(id=name, ctx=ast.Store()),
          annotation=copy.deepcopy(base_ann) if base_ann is not None else None,
          value=copy.deepcopy(stmt.value) if stmt.value is not None else None,
          simple=1,
        )
        ast.fix_missing_locations(static_stmt)
        self.thread_local_fields[name] = static_stmt
        if base_ann is not None:
          write_field_storage(self, name, None)
          write_field_ann_ast(self, name, base_ann)
        return
      if is_final_type_annotation(stmt.annotation):
        markers = set(iter_matmult_marker_names(stmt.annotation))
        if "property" in markers:
          raise NotImplementedError(
            f"{self.name}.{name}: 不支持 ``T @property @final`` / ``T @final @property``"
          )
        self.final_fields.add(name)
      if name not in self.fields:
        self.fields.append(name)
      self.class_body_field_anns.add(name)
      if stmt.annotation is not None:
        write_field_storage(self, name, None)
        write_field_ann_ast(self, name, copy.deepcopy(stmt.annotation))
      elif base_ann is not None:
        write_field_storage(self, name, None)
        write_field_ann_ast(self, name, copy.deepcopy(base_ann))
      if stmt.value is not None:
        self.field_defaults[name] = copy.deepcopy(stmt.value)
    else:
      self._field_from_target(stmt.target, base_ann)

  def _field_from_target(self, target: ast.expr, annotation: ast.expr | None = None):
    name: str | None = None
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
      if target.value.id == "self":
        name = target.attr
    if name is None:
      return
    if name in self.properties or name in self.static_properties:
      return
    if name not in self.fields:
      self.fields.append(name)
    if annotation is not None:
      from .type_emit import write_field_ann_ast, write_field_storage

      write_field_storage(self, name, None)
      write_field_ann_ast(self, name, annotation)


def class_const_cpp_ref(expr: ast.expr, cls: ClassInfo | None) -> str | None:
  """``@const`` 类字段 → ``Class::_NAME``（栈/NTTP 引用，勿折叠为字面量）。"""
  if cls is None:
    return None
  name: str | None = None
  if isinstance(expr, ast.Name):
    name = expr.id
  elif isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
    owner = expr.value.id
    if owner in ("Self", cls.name, cls.cpp_name()):
      name = expr.attr
    else:
      return None
  else:
    return None
  if name not in cls.static_class_fields:
    return None
  member = cls.cpp_member_name(name)
  if cls.is_template():
    return member
  return f"{cls.cpp_name()}::{member}"


def eval_class_const_int(expr: ast.expr | None, cls: ClassInfo | None) -> int | None:
  """``@const`` 类字段及其 ``+`` / ``-`` / ``*`` / ``//`` 嵌套 → 编译期 ``int``。"""
  if expr is None or cls is None:
    return None
  if isinstance(expr, ast.Constant) and isinstance(expr.value, int):
    return expr.value
  if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub):
    inner = eval_class_const_int(expr.operand, cls)
    return -inner if inner is not None else None
  if isinstance(expr, ast.BinOp):
    left = eval_class_const_int(expr.left, cls)
    right = eval_class_const_int(expr.right, cls)
    if left is None or right is None:
      return None
    if isinstance(expr.op, ast.Add):
      return left + right
    if isinstance(expr.op, ast.Sub):
      return left - right
    if isinstance(expr.op, ast.Mult):
      return left * right
    if isinstance(expr.op, ast.FloorDiv):
      if right == 0:
        return None
      return left // right
    return None
  if isinstance(expr, ast.Name):
    stmt = cls.static_class_fields.get(expr.id)
    if stmt is not None and stmt.value is not None:
      return eval_class_const_int(stmt.value, cls)
    return None
  if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
    owner = expr.value.id
    if owner in ("Self", cls.name, cls.cpp_name()):
      stmt = cls.static_class_fields.get(expr.attr)
      if stmt is not None and stmt.value is not None:
        return eval_class_const_int(stmt.value, cls)
  return None


def stack_slice_dim_from_ast(
  slice_node: ast.expr,
  cls: ClassInfo | None,
) -> tuple[int, int | str] | None:
  """``[:N]`` / ``[lo:hi]`` / ``[:Class._dim]`` / ``[:Class._dim * 2]`` → ``(offset, length)``。"""
  sub = parse_subslice_bounds(slice_node)
  if sub is not None:
    return sub
  size = parse_slice_fixed_size(slice_node)
  if size is not None:
    return (0, size)
  if not isinstance(slice_node, ast.Slice) or cls is None:
    return None
  lo = slice_node.lower
  step = slice_node.step
  if lo is not None and not (
    isinstance(lo, ast.Constant) and lo.value in (0, None)
  ):
    return None
  if step is not None and not (
    isinstance(step, ast.Constant) and step.value in (1, None)
  ):
    return None
  if slice_node.upper is None:
    return None
  ref = class_const_cpp_ref(slice_node.upper, cls)
  if ref is not None:
    return (0, ref)
  length = eval_class_const_int(slice_node.upper, cls)
  if length is None or length <= 0:
    return None
  return (0, length)

