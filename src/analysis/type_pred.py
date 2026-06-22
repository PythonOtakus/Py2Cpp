"""TypeNode 结构谓词：替代 ``is_cpp_*`` 的字符串前缀/相等分析（Phase 6）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .type_node import TypeKind, TypeNode

if TYPE_CHECKING:
  from .ir import ClassInfo

TypeLike = str | TypeNode | None


def coerce_type_node(
  ty: TypeLike,
  *,
  classes: dict[str, ClassInfo] | None = None,
) -> TypeNode | None:
  """``str`` / ``TypeNode`` → ``TypeNode``；空串返回 ``None``。"""
  if ty is None:
    return None
  if isinstance(ty, TypeNode):
    return ty
  text = ty.strip()
  if not text:
    return None
  from .type_compat import type_node_from_cpp_string

  return type_node_from_cpp_string(text, classes=classes)


def peel_storage(node: TypeNode) -> TypeNode:
  """去掉指针 / 引用 / 可选 / 托管外层（保留 ``ARRAY`` / ``TEMPLATE`` 本体）。"""
  cur = node
  while cur.kind in (
    TypeKind.POINTER,
    TypeKind.REF,
    TypeKind.OPTIONAL,
    TypeKind.REFCOUNT,
  ):
    assert cur.inner is not None
    cur = cur.inner
  return cur


def _peel_ptr_ref(node: TypeNode) -> TypeNode:
  """仅去掉指针 / 引用，保留 ``OPTIONAL`` / ``REFCOUNT`` 等包装层。"""
  cur = node
  while cur.kind in (TypeKind.POINTER, TypeKind.REF):
    assert cur.inner is not None
    cur = cur.inner
  return cur


def _peel_ref_only(node: TypeNode) -> TypeNode:
  """仅去掉引用（对齐 ``strip_cpp_ref`` 只剥 ``&``）。"""
  cur = node
  while cur.kind == TypeKind.REF:
    assert cur.inner is not None
    cur = cur.inner
  return cur


def _tpl_cpp_base(prefix: str) -> str:
  return prefix[:-1] if prefix.endswith("<") else prefix


def _matches_template(
  node: TypeNode,
  *,
  py_name: str = "",
  cpp_prefix: str = "",
) -> bool:
  core = _peel_ref_only(node)
  if core.kind != TypeKind.TEMPLATE:
    return False
  if py_name and core.py_name == py_name:
    return True
  if cpp_prefix:
    base = _tpl_cpp_base(cpp_prefix)
    if core.name == base or core.name.endswith(f"::{base}"):
      return True
  return False


def _is_template_type(
  ty: TypeLike,
  *,
  py_name: str = "",
  cpp_prefix: str = "",
  classes: dict[str, ClassInfo] | None = None,
) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  return _matches_template(node, py_name=py_name, cpp_prefix=cpp_prefix)


def _is_scalar_name(node: TypeNode, *names: str) -> bool:
  if node.kind == TypeKind.POINTER:
    return False
  core = _peel_ref_only(node)
  if core.kind != TypeKind.SCALAR:
    return False
  return core.name in names


def _is_scalar_type(
  ty: TypeLike,
  *names: str,
  classes: dict[str, ClassInfo] | None = None,
) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  return _is_scalar_name(node, *names)


def _array_ndim_node(node: TypeNode) -> int | None:
  core = _peel_ref_only(node)
  if core.kind != TypeKind.ARRAY:
    return None
  return {
    "heap": 1,
    "heap2d": 2,
    "heap3d": 3,
    "stack": 1,
    "stack2d": 2,
    "stack3d": 3,
    "span": 1,
    "span2d": 2,
    "span3d": 3,
  }.get(core.array_kind)


# --- 容器模板 ---

def is_list_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_LIST_PREFIX

  return _is_template_type(ty, py_name="list", cpp_prefix=CPP_LIST_PREFIX, classes=classes)


def is_dict_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_DICT_PREFIX

  return _is_template_type(ty, py_name="dict", cpp_prefix=CPP_DICT_PREFIX, classes=classes)


def is_set_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_SET_PREFIX

  return _is_template_type(ty, py_name="set", cpp_prefix=CPP_SET_PREFIX, classes=classes)


def is_frozenset_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_FROZENSET_PREFIX

  return _is_template_type(
    ty, py_name="frozenset", cpp_prefix=CPP_FROZENSET_PREFIX, classes=classes,
  )


def is_frozenlist_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_FROZENLIST_PREFIX

  return _is_template_type(
    ty, py_name="frozenlist", cpp_prefix=CPP_FROZENLIST_PREFIX, classes=classes,
  )


def is_frozendict_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_FROZENDICT_PREFIX

  return _is_template_type(
    ty, py_name="frozendict", cpp_prefix=CPP_FROZENDICT_PREFIX, classes=classes,
  )


def is_deque_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_DEQUE_PREFIX

  return _is_template_type(ty, py_name="deque", cpp_prefix=CPP_DEQUE_PREFIX, classes=classes)


def is_tuple_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_TUPLE_PREFIX

  return _is_template_type(ty, py_name="tuple", cpp_prefix=CPP_TUPLE_PREFIX, classes=classes)


def is_counter_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_COUNTER_PREFIX

  return _is_template_type(ty, py_name="counter", cpp_prefix=CPP_COUNTER_PREFIX, classes=classes)


def is_chunk_deque_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_CHUNK_DEQUE_PREFIX

  return _is_template_type(
    ty, py_name="chunk_deque", cpp_prefix=CPP_CHUNK_DEQUE_PREFIX, classes=classes,
  )


def is_container_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  return (
    is_list_type(ty, classes=classes)
    or is_dict_type(ty, classes=classes)
    or is_set_type(ty, classes=classes)
    or is_frozenset_type(ty, classes=classes)
    or is_frozenlist_type(ty, classes=classes)
    or is_frozendict_type(ty, classes=classes)
    or is_deque_type(ty, classes=classes)
    or is_stack_array_type(ty, classes=classes)
    or is_span_type(ty, classes=classes)
  )


# --- 数组 / span ---

def array_ndim(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> int | None:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return None
  return _array_ndim_node(node)


def is_heap_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  return core.kind == TypeKind.ARRAY and core.array_kind in ("heap", "heap2d", "heap3d")


def is_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  return is_heap_array_type(ty, classes=classes)


def is_stack_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  return core.kind == TypeKind.ARRAY and core.array_kind.startswith("stack")


def is_span_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  return core.kind == TypeKind.ARRAY and core.array_kind.startswith("span")


def array_elem_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> str | None:
  """``PyArray<T>`` / ``PyStackArray<T,…>`` → 元素 ``T`` 文本。"""
  from .type_render import CLASS_BODY

  if isinstance(ty, str):
    from .ir import (
      cpp_array_elem_type,
      cpp_span_elem_type,
      parse_cpp_stack_array_type,
      strip_cpp_type_qualifiers,
    )

    t = strip_cpp_type_qualifiers(ty)
    parsed = parse_cpp_stack_array_type(t)
    if parsed is not None:
      return parsed[0]
    span = cpp_span_elem_type(t)
    if span is not None:
      return span
    return cpp_array_elem_type(t)
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return None
  core = _peel_ref_only(node)
  if core.kind != TypeKind.ARRAY or core.inner is None:
    return None
  return core.inner.render(CLASS_BODY)


def is_char_heap_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``char[:]`` → ``PyArray<PyChar>``。"""
  from .ir import cpp_ident

  return (
    is_array_type(ty, classes=classes)
    and array_ndim(ty, classes=classes) == 1
    and array_elem_type(ty, classes=classes) == cpp_ident("char")
  )


def is_byte_heap_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``byte[:]`` → ``PyArray<PyByte>``。"""
  from .ir import cpp_ident

  return (
    is_array_type(ty, classes=classes)
    and array_ndim(ty, classes=classes) == 1
    and array_elem_type(ty, classes=classes) == cpp_ident("byte")
  )


def is_char_stack_array_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``char[:N]`` / ``char[lo:hi]`` → ``PyStackArray<PyChar, …>``。"""
  from .ir import cpp_ident, parse_cpp_stack_array_type

  if isinstance(ty, str):
    parsed = parse_cpp_stack_array_type(ty)
    return parsed is not None and parsed[0] == cpp_ident("char")
  return (
    is_stack_array_type(ty, classes=classes)
    and array_elem_type(ty, classes=classes) == cpp_ident("char")
  )


# --- 标量 ---

def is_str_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  ps = cpp_ident("str")
  return _is_scalar_type(ty, ps, "PyStr", classes=classes) or _suffix_scalar(ty, ps, classes=classes)


def is_bytes_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  pb = cpp_ident("bytes")
  return _is_scalar_type(ty, pb, "PyBytes", classes=classes) or _suffix_scalar(ty, pb, classes=classes)


def _suffix_scalar(ty: TypeLike, name: str, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None or node.kind == TypeKind.POINTER:
    return False
  core = _peel_ref_only(node)
  return core.kind == TypeKind.SCALAR and core.name.endswith(f"::{name}")


def is_char_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, "PyChar", cpp_ident("char"), classes=classes)


def is_byte_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, "PyByte", cpp_ident("byte"), classes=classes)


def is_int_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("int"), classes=classes)


def is_int64_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("int64"), classes=classes)


def is_uint_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("uint"), classes=classes)


def is_uint64_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("uint64"), classes=classes)


def is_uintptr_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("uintptr"), classes=classes)


def _is_named_cpp_type(node: TypeNode, *names: str) -> bool:
  """类名 / 别名（``PyVarInt`` 等）——对齐旧 ``strip_cpp_ref`` + 字符串相等。"""
  if node.kind == TypeKind.POINTER:
    return False
  core = _peel_ref_only(node)
  if core.kind == TypeKind.SCALAR and core.name in names:
    return True
  return core.name in names or any(core.name.endswith(f"::{n}") for n in names)


def is_varint_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident, strip_cpp_ref

  vn = cpp_ident("varint")
  if isinstance(ty, str):
    t = strip_cpp_ref(ty.strip())
    return t == vn or t.endswith(f"::{vn}")
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  return _is_named_cpp_type(node, vn)


def is_float_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("float"), classes=classes)


def is_float64_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import cpp_ident

  return _is_scalar_type(ty, cpp_ident("float64"), classes=classes)


def is_scalar_int_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  return (
    is_int_type(ty, classes=classes)
    or is_int64_type(ty, classes=classes)
    or is_uint_type(ty, classes=classes)
    or is_uint64_type(ty, classes=classes)
    or is_varint_type(ty, classes=classes)
  )


def is_scalar_float_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  return is_float_type(ty, classes=classes) or is_float64_type(ty, classes=classes)


# --- 包装类型 ---

def is_refcount_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  cur = node
  while cur.kind == TypeKind.POINTER:
    assert cur.inner is not None
    cur = cur.inner
  return cur.kind == TypeKind.REFCOUNT


def is_optional_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  if _peel_ptr_ref(node).kind == TypeKind.OPTIONAL:
    return True
  if isinstance(ty, str):
    from .ir import CPP_OPTIONAL_PREFIX

    t = ty.strip()
    return t.startswith(CPP_OPTIONAL_PREFIX) and t.endswith(">")
  return False


# --- 可调用 / 生成器 / 协程 / 委托 ---

def _strip_qualifiers_text(cpp_type: str) -> str:
  from .ir import strip_cpp_type_qualifiers

  return strip_cpp_type_qualifiers(cpp_type.strip())


def _template_core_node(node: TypeNode, cpp_base: str) -> TypeNode | None:
  """``_peel_ref_only`` 后的 ``PyList`` / ``PyGenerator`` 等模板本体。"""
  core = _peel_ref_only(node)
  if core.kind != TypeKind.TEMPLATE:
    return None
  if core.name == cpp_base or core.name.endswith(f"::{cpp_base}"):
    return core
  return None


def _is_template_named(ty: TypeLike, cpp_base: str, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  if isinstance(ty, str):
    t = _strip_qualifiers_text(ty)
    prefix = f"{cpp_base}<"
    return t.startswith(prefix) and t.endswith(">")
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  return _template_core_node(node, cpp_base) is not None


def is_py_callable_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_PY_CALLABLE_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_PY_CALLABLE_PREFIX), classes=classes)


def is_py_generator_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_PY_GENERATOR_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_PY_GENERATOR_PREFIX), classes=classes)


def is_py_coroutine_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_PY_COROUTINE_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_PY_COROUTINE_PREFIX), classes=classes)


def is_py_async_generator_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_PY_ASYNC_GENERATOR_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_PY_ASYNC_GENERATOR_PREFIX), classes=classes)


def is_py_iterable_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from .ir import CPP_PY_ITERABLE_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_PY_ITERABLE_PREFIX), classes=classes)


def is_delegate_type(
  ty: TypeLike,
  *,
  delegate_names: frozenset[str],
  classes: dict[str, ClassInfo] | None = None,
) -> bool:
  if isinstance(ty, str):
    t = _strip_qualifiers_text(ty)
    if t.startswith("PyDelegate<"):
      return True
    base = t.split("<", 1)[0].strip()
    return base in delegate_names
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  if core.kind == TypeKind.TEMPLATE and core.name == "PyDelegate":
    return True
  return core.name in delegate_names or any(
    core.name.endswith(f"::{n}") for n in delegate_names
  )


def is_concrete_generator_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from ..passes.generators import GENERATOR_SUFFIX

  if isinstance(ty, str):
    return _strip_qualifiers_text(ty).endswith(GENERATOR_SUFFIX)
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  return core.name.endswith(GENERATOR_SUFFIX)


def is_concrete_coroutine_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  from ..passes.generators import COROUTINE_SUFFIX

  if isinstance(ty, str):
    return _strip_qualifiers_text(ty).endswith(COROUTINE_SUFFIX)
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  return core.name.endswith(COROUTINE_SUFFIX)


def is_iter_result_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``PyIterResult<Y, R>``（生成器 / 迭代器 ``__next__`` 返回包装）。"""
  from .ir import CPP_RESULT_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_RESULT_PREFIX), classes=classes)


def is_fault_result_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``PyResult<T, E>``（``@fault_result`` 方法返回）。"""
  from .ir import CPP_FAULT_RESULT_PREFIX

  return _is_template_named(ty, _tpl_cpp_base(CPP_FAULT_RESULT_PREFIX), classes=classes)


def is_complex_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``PyComplex`` / ``PyComplex<PyFloat64>`` / 模块别名 ``complex128`` 等。"""
  from .ir import cpp_ident

  base = cpp_ident("complex")
  if isinstance(ty, str):
    t = ty.strip()
    if t == base:
      return True
    return t.startswith(f"{base}<") and t.endswith(">")
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return False
  core = _peel_ref_only(node)
  if core.kind == TypeKind.SCALAR and core.name == base:
    return True
  if core.kind == TypeKind.TEMPLATE and core.name == base:
    return True
  return core.name == base or core.name.endswith(f"::{base}")


def type_to_cpp_text(
  ty: TypeLike,
  *,
  classes: dict[str, ClassInfo] | None = None,
  fallback: str = "",
) -> str:
  """``TypeNode`` / ``str`` → C++ ``CLASS_BODY`` 文本（emit 边界）。"""
  if isinstance(ty, str):
    return ty.strip() or fallback
  if isinstance(ty, TypeNode):
    from .type_render import CLASS_BODY

    return ty.render(CLASS_BODY) or fallback
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return fallback
  from .type_render import CLASS_BODY

  return node.render(CLASS_BODY) or fallback


def is_callable_type(ty: TypeLike, *, classes: dict[str, ClassInfo] | None = None) -> bool:
  """``Function[[…], R]`` → ``Ret (*)(Args…)``（函数指针）。"""
  if isinstance(ty, TypeNode):
    return ty.kind == TypeKind.FUNCTION_PTR
  text = type_to_cpp_text(ty, classes=classes)
  if not text:
    return False
  from .ir import format_cpp_callable_var_decl

  return format_cpp_callable_var_decl(text, "_") is not None


def is_invokable_type(
  ty: TypeLike,
  *,
  classes: dict[str, ClassInfo] | None = None,
  delegate_names: frozenset[str] | None = None,
) -> bool:
  """``Function`` / ``Callable`` / ``Delegate`` 或带 ``__call__`` 的类类型。"""
  from .ir import class_info_for_cpp_type, strip_cpp_type_qualifiers

  t = strip_cpp_type_qualifiers(type_to_cpp_text(ty, classes=classes)).strip()
  if not t:
    return False
  if is_callable_type(t) or is_py_callable_type(t):
    return True
  if delegate_names is not None and is_delegate_type(t, delegate_names=delegate_names):
    return True
  if classes is not None:
    owner = class_info_for_cpp_type(t, classes)
    if owner and ("__call__" in owner.methods or "__call__" in owner.method_overloads):
      return True
  return False


def is_erased_protocol_type(
  ty: TypeLike,
  protocol: str | None = None,
  *,
  classes: dict[str, ClassInfo] | None = None,
) -> bool:
  from .stubs.protocol_erase_stubs import is_cpp_erased_protocol_type

  text = type_to_cpp_text(ty, classes=classes)
  if not text:
    return False
  return is_cpp_erased_protocol_type(_strip_qualifiers_text(text), protocol)


def is_erased_protocol_storage_type(
  ty: TypeLike,
  *,
  classes: dict[str, ClassInfo] | None = None,
) -> bool:
  """任意运行时擦除协议句柄（``PyGenerator`` / ``PyContextManager<T>`` 等）。"""
  if (
    is_py_generator_type(ty, classes=classes)
    or is_py_coroutine_type(ty, classes=classes)
    or is_py_async_generator_type(ty, classes=classes)
  ):
    return True
  return is_erased_protocol_type(ty, classes=classes)
