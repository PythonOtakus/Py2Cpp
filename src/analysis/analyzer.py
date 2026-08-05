"""语义分析（预处理）阶段。

在 ``translator`` 生成 C++ 之前对本模块内所有类与函数执行一次静态分析：

1. ``TypeParser``：把注解 AST 转为 C++ 类型字符串（含 ``T[:]``、``list[T]``、``Pointer[T]``）。
2. ``SignatureBuilder``：解析字段类型、方法/函数签名、``__next__`` → ``IterResult<Y,R>`` 等约定。
3. ``SemanticAnalyzer.analyze``：填充 ``ClassInfo.method_sigs``、``init_sigs``、
   ``ModuleAnalysis.includes``，并挂载 ``translator.type_parser``。

生成阶段只读这些结构，避免对同一 AST 重复推断。
"""
from __future__ import annotations

import ast
import copy
from ..passes.descriptors import storage_field_for
from .delegates import collect_delegates
from .imports import collect_entry_imports
from .stubs.iterator_return_stubs import iter_method_return_type, reversed_method_return_type
from .stubs.iterator_host_stubs import (
  dict_like_host_py_name,
  ecs_query_ptr_cpp_type,
  host_owner_field_name,
  host_owner_param_name,
  host_ptr_cpp_type,
  iterator_owner_host_py_name,
)
from .ir import (
  collect_owned_array_sizes,
  collect_owned_fields_from_inits,
  has_named_decorator,
  INT_FIELDS,
  TYPE_MARKER_CLASSES,
  ClassInfo,
  TypeAliasInfo,
  FuncTypeParams,
  FunctionSig,
  IMPLICIT_VOID_DUNDER_METHODS,
  MethodSig,
  ModuleAnalysis,
  is_void_return_annotation,
  PROTOCOL_PARAM_ERASE,
  PropertyDef,
  cpp_ident,
  cpp_result_type,
  cpp_refcount_type,
  cpp_template_type,
  cpp_iterator_type,
  resolve_host_cpp_type,
  format_cpp_callable_var_decl,
  bytes_cpp_from_literal,
  iter_matmult_marker_names,
  CPP_ARRAY_PREFIX,
  CPP_STACK_ARRAY_PREFIX,
  CPP_SPAN_PREFIX,
  CPP_LIST_PREFIX,
  CPP_RESULT_PREFIX,
  CPP_REFCount_PREFIX,
  cpp_template_type,
  cpp_param,
  cpp_template_inner_args,
  default_new_ctor_cpp,
  docstring_lines,
  format_cpp_float,
  format_cpp_float64,
  format_cpp_int,
  format_cpp_int64,
  format_cpp_uint,
  format_cpp_uint64,
  format_cpp_uintptr,
  format_cpp_varint,
  str_cpp_from_literal,
  quote_cpp_string,
)
from .type_pred import (
  is_array_type,
  is_byte_type,
  is_bytes_type,
  is_callable_type,
  is_char_heap_array_type,
  is_char_type,
  is_container_type,
  is_deque_type,
  is_dict_type,
  is_float64_type,
  is_frozenlist_type,
  is_frozendict_type,
  is_frozenset_type,
  is_heap_array_type,
  is_int64_type,
  is_int_type,
  is_list_type,
  is_optional_type,
  is_py_callable_type,
  is_refcount_type,
  is_set_type,
  is_span_type,
  is_stack_array_type,
  is_str_type,
  is_uint64_type,
  is_uint_type,
  is_uintptr_type,
  is_varint_type,
)

from ..passes.move_state import ensure_move_state_field
from .header_fixups import apply_header_fixups
from ..constant.stdlib_layout import (
  CORE_PKG,
  RUNTIME_PKG,
  stdlib_header_include,
  stdlib_module_path,
)
from ..analysis.runtime_symbols import (
  BUILTINS_CPP_RUNTIME_FUNCS,
  TRANSLATION_ONLY_FUNCS,
)

RUNTIME_PREFIX = RUNTIME_PKG


def _exception_param_cpp_type(cpp_type: str) -> str | None:
  """``Exception`` 形参（含 ``using`` 后的短名）→ 全限定类型，供 const 引用传参。"""
  from ..constant.stdlib_layout import EXCEPTIONS_NS

  bare = cpp_type.strip().rstrip("&").strip()
  if bare.startswith("const "):
    bare = bare[6:].strip()
  if bare in (f"{EXCEPTIONS_NS}::Exception", "Exception"):
    return f"{EXCEPTIONS_NS}::Exception"
  return None


class TypeParser:
  """Python 类型注解 → C++ 类型名。"""

  def _finalize_cpp_type(self, cpp: str) -> str:
    from .ir import cpp_fill_allocator_default_args

    return cpp_fill_allocator_default_args(cpp)

  def __init__(self) -> None:
    self._import_bindings: dict = {}
    self._delegate_names: frozenset[str] = frozenset()
    self._type_aliases: dict[str, TypeAliasInfo] = {}
    self._alias_use_cpp_name = False
    self._user_class_names: frozenset[str] = frozenset()
    self._classes: dict = {}
    self._tr: object | None = None

  def set_translator(self, tr: object | None) -> None:
    self._tr = tr

  def set_user_class_names(self, names: frozenset[str]) -> None:
    self._user_class_names = names

  def set_classes(self, classes: dict) -> None:
    self._classes = classes

  def set_import_bindings(self, bindings: dict) -> None:
    self._import_bindings = bindings

  def set_delegate_names(self, names: frozenset[str]) -> None:
    self._delegate_names = names

  def set_type_aliases(
    self,
    aliases: dict[str, TypeAliasInfo] | None,
    *,
    use_as_cpp_name: bool = False,
  ) -> None:
    self._type_aliases = dict(aliases or {})
    self._alias_use_cpp_name = use_as_cpp_name

  def _maps_to_runtime_protocol_erase(self, py_name: str) -> bool:
    """``@protocol`` 运行时擦除名 → ``Py{Name}``；同名用户类（非 protocol）保留。"""
    from .stubs.protocol_erase_stubs import load_protocol_runtime_erase

    if py_name not in load_protocol_runtime_erase():
      return False
    info = self._classes.get(py_name)
    return info is None or getattr(info, "is_protocol", False)

  def _expand_type_alias_name(
    self,
    name: str,
    type_params: set[str],
    *,
    self_class: str | None = None,
    _seen: frozenset[str] | None = None,
  ) -> str | None:
    if name not in self._type_aliases:
      return None
    ali = self._type_aliases[name]
    if ali.member_constraint:
      return name
    if self._alias_use_cpp_name:
      return name
    seen = set(_seen or ())
    if name in seen:
      return None
    seen.add(name)
    return self.parse_type(
      ali.value,
      type_params,
      self_class=self_class,
      _alias_seen=frozenset(seen),
    )

  def _slice_array_dims(self, slice_node: ast.expr) -> int:
    if isinstance(slice_node, ast.Slice):
      return 1
    if isinstance(slice_node, ast.Tuple):
      if not slice_node.elts:
        return 0
      if all(isinstance(e, ast.Slice) for e in slice_node.elts):
        return len(slice_node.elts)
    return 0

  def _try_parse_span_type(
    self,
    node: ast.Subscript,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    from .ir import cpp_span2d_type, cpp_span3d_type, cpp_span_type

    if isinstance(node.value, ast.Name) and node.value.id == "span":
      elem = self.parse_type(node.slice, type_params, self_class=self_class)
      return cpp_span_type(elem)
    if isinstance(node.value, ast.Name) and node.value.id == "span2d":
      elem = self.parse_type(node.slice, type_params, self_class=self_class)
      return cpp_span2d_type(elem)
    if isinstance(node.value, ast.Name) and node.value.id == "span3d":
      elem = self.parse_type(node.slice, type_params, self_class=self_class)
      return cpp_span3d_type(elem)
    return None

  def _parse_stack_slice_dim(
    self,
    sl: ast.expr,
    *,
    self_class: str | None = None,
    type_params: set[str] | None = None,
  ) -> tuple[int, int | str] | None:
    """单维 ``[:N]`` / ``[lo:hi]`` / NTTP ``[:N]`` → ``(offset, length)``。"""
    from .ir import ClassInfo, cpp_type_param_template_name, stack_slice_dim_from_ast

    cls: ClassInfo | None = None
    if self_class is not None:
      cls = self._classes.get(self_class)
      if cls is None:
        from .ir import class_info_for_cpp_type

        cls = class_info_for_cpp_type(self_class, self._classes)
    fixed = stack_slice_dim_from_ast(sl, cls)
    if fixed is not None:
      return fixed
    tparams = type_params or set()
    if not isinstance(sl, ast.Slice):
      return None
    lo = sl.lower
    step = sl.step
    if lo is not None and not (
      isinstance(lo, ast.Constant) and lo.value in (0, None)
    ):
      return None
    if step is not None and not (
      isinstance(step, ast.Constant) and step.value in (1, None)
    ):
      return None
    upper = sl.upper
    if isinstance(upper, ast.Name) and upper.id in tparams:
      return (0, upper.id)
    return None

  def _try_parse_stack_array_type(
    self,
    node: ast.Subscript,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    from .ir import (
      cpp_stack_array2d_type,
      cpp_stack_array3d_type,
      cpp_stack_array_type,
    )

    if isinstance(node.value, ast.Name):
      info = self._classes.get(node.value.id)
      if info is not None:
        nttp = getattr(info, "type_param_nttp", None) or {}
        if nttp and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
          return None
    elem = self.parse_type(node.value, type_params, self_class=self_class)
    if isinstance(node.slice, ast.Tuple):
      elts = node.slice.elts
      if len(elts) not in (2, 3):
        return None
      if not all(isinstance(e, ast.Slice) for e in elts):
        return None
      parsed_dims: list[tuple[int, int]] = []
      for sl in elts:
        dim = self._parse_stack_slice_dim(sl, self_class=self_class)
        if dim is None:
          return None
        parsed_dims.append(dim)
      if len(parsed_dims) == 2:
        (r0, rows), (c0, cols) = parsed_dims
        return cpp_stack_array2d_type(elem, rows, cols, r0, c0)
      (o0, d0), (o1, d1), (o2, d2) = parsed_dims
      return cpp_stack_array3d_type(elem, d0, d1, d2, o0, o1, o2)
    dim = self._parse_stack_slice_dim(
      node.slice, self_class=self_class, type_params=type_params,
    )
    if dim is None:
      return None
    lo, length = dim
    return cpp_stack_array_type(elem, length, lo)

  def _parse_callable_subscript(
    self,
    node: ast.Subscript,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> tuple[list[str], str] | None:
    sl = node.slice
    if not isinstance(sl, ast.Tuple) or len(sl.elts) != 2:
      return None
    args_node, ret_node = sl.elts
    arg_types: list[str] = []
    if isinstance(args_node, (ast.Tuple, ast.List)):
      arg_types = [
        self.parse_type(e, type_params, self_class=self_class) for e in args_node.elts
      ]
    else:
      arg_types = [self.parse_type(args_node, type_params, self_class=self_class)]
    if (
      isinstance(ret_node, ast.Name) and ret_node.id == "None"
      or isinstance(ret_node, ast.Constant) and ret_node.value is None
    ):
      ret = "void"
    else:
      ret = self.parse_type(ret_node, type_params, self_class=self_class)
    return arg_types, ret

  def _try_parse_function_type(
    self,
    node: ast.Subscript,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    """``Function[[A, B], R]`` → ``R (*)(A, B)``。"""
    if not isinstance(node.value, ast.Name) or node.value.id != "Function":
      return None
    parsed = self._parse_callable_subscript(
      node, type_params, self_class=self_class,
    )
    if parsed is None:
      return None
    arg_types, ret = parsed
    args_str = ", ".join(arg_types)
    if not args_str:
      return f"{ret} (*)()"
    return f"{ret} (*)({args_str})"

  def _try_parse_callable_type(
    self,
    node: ast.Subscript,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    """``Callable[[A, B], R]`` → ``PyCallable<R, A, B>``。"""
    if not isinstance(node.value, ast.Name) or node.value.id != "Callable":
      return None
    parsed = self._parse_callable_subscript(
      node, type_params, self_class=self_class,
    )
    if parsed is None:
      return None
    arg_types, ret = parsed
    args_str = ", ".join(arg_types)
    if not args_str:
      return f"PyCallable<{ret}>"
    return f"PyCallable<{ret}, {args_str}>"

  def _parse_tuple_type_shorthand(
    self,
    node: ast.Tuple,
    type_params: set[str],
    *,
    self_class: str | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ) -> str:
    """``(T, U, ...)`` 类型注解简写 → ``PyTuple<T, U, ...>``（同 ``tuple[T, U, ...]``）。"""
    from .variadic_template import (
      cpp_typevar_tuple_as_pytuple,
      typevar_tuple_pack_from_type_node,
    )

    if typevar_tuple_names:
      pack = typevar_tuple_pack_from_type_node(node, typevar_tuple_names)
      if pack is not None:
        return cpp_typevar_tuple_as_pytuple(pack)
    if not node.elts:
      return f"{cpp_ident('tuple')}<>"
    if any(isinstance(e, ast.Starred) for e in node.elts):
      raise NotImplementedError(
        "元组类型注解中 ``*Pack`` 仅支持单元素 ``(*Ts,)``（形参包对应 ``PyTuple<Ts...>``）",
      )
    args = ", ".join(
      self.parse_type(
        e, type_params, self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      for e in node.elts
    )
    return f"{cpp_ident('tuple')}<{args}>"

  def _try_parse_slice_array_type(
    self,
    node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    if not isinstance(node, ast.Subscript):
      return None
    stack = self._try_parse_stack_array_type(
      node, type_params, self_class=self_class,
    )
    if stack:
      return stack
    span = self._try_parse_span_type(node, type_params, self_class=self_class)
    if span:
      return span
    dims = self._slice_array_dims(node.slice)
    if dims < 1:
      return None
    elem = self.parse_type(node.value, type_params, self_class=self_class)
    if dims == 1:
      return cpp_template_type("array", elem)
    if dims == 2:
      return cpp_template_type("array2d", elem)
    return cpp_template_type("array3d", elem)

  def parse_type(
    self,
    node: ast.expr | None,
    type_params: set[str],
    *,
    self_class: str | None = None,
    _alias_seen: frozenset[str] | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ) -> str:
    if node is None:
      return "void"
    return self._finalize_cpp_type(
      self._parse_type_impl(
        node,
        type_params,
        self_class=self_class,
        _alias_seen=_alias_seen,
        typevar_tuple_names=typevar_tuple_names,
      ),
    )

  def _parse_type_impl(
    self,
    node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
    _alias_seen: frozenset[str] | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ) -> str:
    if isinstance(node, ast.Tuple):
      return self._parse_tuple_type_shorthand(
        node,
        type_params,
        self_class=self_class,
        typevar_tuple_names=typevar_tuple_names,
      )
    if isinstance(node, ast.Subscript):
      from .variadic_template import (
        cpp_typevar_tuple_as_pytuple,
        typevar_tuple_pack_from_type_node,
      )

      if typevar_tuple_names:
        pack = typevar_tuple_pack_from_type_node(node, typevar_tuple_names)
        if pack is not None:
          return cpp_typevar_tuple_as_pytuple(pack)
      arr = self._try_parse_slice_array_type(
        node, type_params, self_class=self_class,
      )
      if arr:
        return arr
      function_t = self._try_parse_function_type(node, type_params, self_class=self_class)
      if function_t:
        return function_t
      callable_t = self._try_parse_callable_type(node, type_params, self_class=self_class)
      if callable_t:
        return callable_t
      if isinstance(node.value, ast.Name) and node.value.id == "Pointer":
        # 嵌套 ``Pointer[Pointer[T]]`` 须得到 ``T**``（勿因内层已以 ``*`` 结尾而吞掉一层）
        if (
          isinstance(node.slice, ast.Subscript)
          and isinstance(node.slice.value, ast.Name)
          and node.slice.value.id == "Pointer"
        ):
          inner = self.parse_type(node.slice, type_params, self_class=self_class)
          return f"{inner}*"
        inner = self.parse_type(node.slice, type_params, self_class=self_class)
        return inner if inner.endswith("*") else f"{inner}*"
      if isinstance(node.value, ast.Name) and node.value.id == "slice":
        return self._parse_slice_type(node.slice, type_params, self_class=self_class)
      if isinstance(node.value, ast.Name) and node.value.id in self._type_aliases:
        ali = self._type_aliases[node.value.id]
        if ali.is_conditional and self._tr is not None and not self._alias_use_cpp_name:
          from ..passes.type_conditional import instantiate_conditional_alias_subscript

          return instantiate_conditional_alias_subscript(
            self._tr, ali, node.slice, type_params,
          )
        if ali.type_params:
          args = self.parse_type_args(
            node.slice, type_params, self_class=self_class,
          )
          return f"{node.value.id}<{args}>"
      if isinstance(node.value, ast.Name):
        spec = self._try_specialize_class_type(
          node.value.id,
          node.slice,
          type_params,
          self_class=self_class,
        )
        if spec is not None:
          return spec
      if isinstance(node.value, ast.Name) and node.value.id == "IterResult":
        from .ir import cpp_result_type

        sl = node.slice
        if isinstance(sl, ast.Tuple):
          elts = sl.elts
          if len(elts) >= 2:
            y = self.parse_type(elts[0], type_params, self_class=self_class)
            r = self.parse_type(elts[1], type_params, self_class=self_class)
            if r == "void":
              r = cpp_ident("PyNone")
            return cpp_result_type(y, r)
          if len(elts) == 1:
            y = self.parse_type(elts[0], type_params, self_class=self_class)
            return cpp_result_type(y)
        inner = self.parse_type(sl, type_params, self_class=self_class)
        return cpp_result_type(inner)
      if isinstance(node.value, ast.Name) and node.value.id == "Result":
        from .ir import cpp_fault_result_type
        from ..constant.stdlib_layout import EXCEPTIONS_NS

        sl = node.slice
        if isinstance(sl, ast.Tuple):
          elts = sl.elts
          if len(elts) >= 2:
            ok = self.parse_type(elts[0], type_params, self_class=self_class)
            err = self.parse_type(elts[1], type_params, self_class=self_class)
            if ok == "void":
              ok = cpp_ident("PyNone")
            return cpp_fault_result_type(ok, err)
        inner = self.parse_type(sl, type_params, self_class=self_class)
        if inner == "void":
          inner = cpp_ident("PyNone")
        return cpp_fault_result_type(inner, f"{EXCEPTIONS_NS}::Exception")
      if isinstance(node.value, ast.Name):
        resolved = resolve_host_cpp_type(node.value.id, self_class)
        if resolved is not None:
          base = resolved.partition("<")[0].strip()
          args = self.parse_type_args(
            node.slice, type_params, self_class=self_class,
          )
          return f"{base}<{args}>"
    match node:
      case ast.Name(id=name):
        resolved = resolve_host_cpp_type(name, self_class)
        if resolved is not None:
          return resolved
        if name in type_params:
          return name
        from .stubs.protocol_erase_stubs import (
          erased_protocol_cpp_name,
          load_protocol_runtime_erase,
        )

        if self._maps_to_runtime_protocol_erase(name):
          return erased_protocol_cpp_name(name)
        # 内置标量注解优先于模块 ``type int64 = int`` 等别名（``@const`` 类字段须保留 ``PyInt64``）。
        if name in (
          "int", "int64", "uint", "uint64", "uintptr", "float", "float64", "bool", "str", "bytes", "char", "byte",
          "object", "RefCount", "IterResult", "Result", "Optional", "Generator",
          "Coroutine", "AsyncGenerator", "Awaitable", "AsyncIterable", "AsyncIterator",
          "ContextManager", "AsyncContextManager", "PyNone", "void", "Never",
        ):
          return cpp_ident(name)
        if name == "None":
          return cpp_ident("PyNone")
        if name == "c_str":
          return "c_str"
        expanded = self._expand_type_alias_name(
          name, type_params, self_class=self_class, _seen=_alias_seen,
        )
        if expanded is not None:
          return expanded
        imp = self._import_bindings.get(name)
        if imp is not None and imp.kind in ("class", "delegate"):
          info = self._classes.get(name)
          if info is not None and info.type_params and not info.typevar_tuple:
            defaults = info.type_param_defaults
            if defaults and len(defaults) == len(info.type_params):
              cpp_args = [
                self.parse_type(
                  defaults[p], type_params, self_class=self_class,
                )
                for p in info.type_params
              ]
              return f"{info.cpp_name()}<{', '.join(cpp_args)}>"
          return imp.cpp_name
        if (
          name == "Object"
          and name not in self._user_class_names
          and (imp is None or imp.kind != "class")
        ):
          raise NotImplementedError(
            "类型注解 Object 已禁止，请改用 object（映射 PyObject）"
          )
        info = self._classes.get(name)
        if info is not None and info.type_params and not info.typevar_tuple:
          defaults = info.type_param_defaults
          if defaults and len(defaults) == len(info.type_params):
            cpp_args = [
              self.parse_type(
                defaults[p], type_params, self_class=self_class,
              )
              for p in info.type_params
            ]
            return f"{info.cpp_name()}<{', '.join(cpp_args)}>"
        return cpp_ident(name)
      case ast.Subscript(value=ast.Name(id=name), slice=sl) if name == "WeakRef":
        inner = self._weakref_target_cpp_type(
          sl,
          type_params,
          {},
          self_class=self_class,
        )
        imp = self._import_bindings.get("WeakRef")
        base = imp.cpp_name if imp is not None else cpp_ident("WeakRef")
        return f"{base}<{inner}>"
      case ast.Subscript(value=ast.Name(id=name), slice=sl) if name in self._delegate_names:
        base = cpp_ident(name)
        imp = self._import_bindings.get(name)
        if imp is not None and imp.kind == "delegate":
          base = imp.cpp_name
        if isinstance(sl, ast.Tuple):
          args = ", ".join(
            self.parse_type(e, type_params, self_class=self_class) for e in sl.elts
          )
        else:
          args = self.parse_type(sl, type_params, self_class=self_class)
        return f"{base}<{args}>"
      case ast.Subscript(value=ast.Name(id=name), slice=sl):
        spec = self._try_specialize_class_type(
          name, sl, type_params, self_class=self_class,
        )
        if spec is not None:
          return spec
        base = self.parse_type(
          ast.Name(id=name), type_params, self_class=self_class,
        )
        if isinstance(sl, ast.Tuple):
          args = ", ".join(
            self.parse_type(e, type_params, self_class=self_class) for e in sl.elts
          )
        else:
          args = self.parse_type(sl, type_params, self_class=self_class)
        return f"{base}<{args}>"
      case ast.Subscript(value=value, slice=sl):
        base = self.parse_type(value, type_params, self_class=self_class)
        if isinstance(sl, ast.Tuple):
          args = ", ".join(
            self.parse_type(e, type_params, self_class=self_class) for e in sl.elts
          )
        else:
          args = self.parse_type(sl, type_params, self_class=self_class)
        return f"{base}<{args}>"
      case ast.BinOp(left=left, op=ast.BitOr(), right=ast.Constant(value=None)):
        from .ir import ClassInfo, cpp_optional_type

        inner = self.parse_type(left, type_params, self_class=self_class)
        stored = ClassInfo.apply_refcount_storage_cpp_type(inner, self._classes)
        if is_refcount_type(stored):
          return stored
        return cpp_optional_type(stored)
      case ast.BinOp(left=left, op=ast.MatMult()):
        from .lazy_param import is_lazy_type_annotation

        if is_lazy_type_annotation(node):
          return self.parse_type(left, type_params, self_class=self_class)
        base = self.parse_type(left, type_params, self_class=self_class)
        if "ref" in iter_matmult_marker_names(node):
          if not base.endswith("&"):
            return f"{base}&"
        return base
      case ast.Attribute(value=value, attr=attr):
        if isinstance(value, ast.Name) and attr == "Enum":
          info = self._classes.get(value.id)
          if info is not None and info.is_union_mro:
            from .module_namespace import qualify_symbol_in_module

            qual = qualify_symbol_in_module(info.module_path, info.cpp_name())
            return f"{qual}::Enum"
        if isinstance(value, ast.Name) and value.id in type_params:
          return f"typename {value.id}::{attr}"
        expanded = self._parse_class_nested_type_alias(
          value, attr, type_params, self_class=self_class,
        )
        if expanded is not None:
          return expanded
        return "void"
      case ast.Constant(value=None):
        return cpp_ident("PyNone")
      case ast.Constant():
        return self._nttp_cpp_arg(node)
      case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=v)) if isinstance(v, int):
        return self._nttp_cpp_arg(node)
      case _:
        return "void"

  def _parse_generator_type_arg(
    self,
    node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str:
    if isinstance(node, ast.Constant) and node.value is None:
      return cpp_ident("PyNone")
    return self.parse_type(node, type_params, self_class=self_class)

  @staticmethod
  def _has_refcount_decorator_constraint(
    name: str,
    decorator_constraints: dict[str, tuple[str, ...]] | None,
  ) -> bool:
    if not decorator_constraints:
      return False
    bounds = decorator_constraints.get(name, ())
    return "refcount" in bounds

  @staticmethod
  def _has_boxing_decorator_constraint(
    name: str,
    decorator_constraints: dict[str, tuple[str, ...]] | None,
  ) -> bool:
    if not decorator_constraints:
      return False
    bounds = decorator_constraints.get(name, ())
    return "boxing" in bounds

  def _weakref_target_cpp_type(
    self,
    inner_node: ast.expr,
    type_params: set[str],
    decorator_constraints: dict[str, tuple[str, ...]],
    *,
    self_class: str | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ) -> str:
    """``WeakRef[T]`` 内层 ``T`` 不包 ``PyRefCount``；约束形参 ``T: refcount`` 用 ``unwrap``。"""
    if isinstance(inner_node, ast.Name) and self._has_refcount_decorator_constraint(
      inner_node.id, decorator_constraints,
    ):
      return f"typename py2cpp_refcount_unwrap<{inner_node.id}>::type"
    t = self.parse_type(
      inner_node,
      type_params,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )
    return ClassInfo.unwrap_refcount_type(t)

  def parse_storage_type(
    self,
    node: ast.expr | None,
    type_params: set[str],
    *,
    decorator_constraints: dict[str, tuple[str, ...]] | None = None,
    self_class: str | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ) -> str:
    """``T: refcount`` / ``T: boxing`` 仅校验（C++ 形参仍为 ``T``）；``WeakRef[T]`` 内层 ``T`` 不包装。"""
    dec = decorator_constraints or {}
    if node is None:
      return "void"
    if (
      isinstance(node, ast.BinOp)
      and isinstance(node.op, ast.BitOr)
      and isinstance(node.right, ast.Constant)
      and node.right.value is None
    ):
      from .ir import ClassInfo, cpp_optional_type

      inner = self.parse_storage_type(
        node.left,
        type_params,
        decorator_constraints=dec,
        self_class=self_class,
        typevar_tuple_names=typevar_tuple_names,
      )
      stored = ClassInfo.apply_refcount_storage_cpp_type(inner, self._classes)
      if is_refcount_type(stored):
        return stored
      return cpp_optional_type(stored)
    if isinstance(node, ast.Tuple):
      from .variadic_template import (
        cpp_typevar_tuple_as_pytuple,
        typevar_tuple_pack_from_type_node,
      )

      if typevar_tuple_names:
        pack = typevar_tuple_pack_from_type_node(node, typevar_tuple_names)
        if pack is not None:
          return cpp_typevar_tuple_as_pytuple(pack)
      if not node.elts:
        return f"{cpp_ident('tuple')}<>"
      args = ", ".join(
        self.parse_storage_type(
          e,
          type_params,
          decorator_constraints=dec,
          self_class=self_class,
          typevar_tuple_names=typevar_tuple_names,
        )
        for e in node.elts
      )
      return f"{cpp_ident('tuple')}<{args}>"
    if isinstance(node, ast.Subscript):
      arr = self._try_parse_slice_array_type(
        node, type_params, self_class=self_class,
      )
      if arr:
        return arr
      if isinstance(node.value, ast.Name):
        imp = self._import_bindings.get(node.value.id)
        if imp is not None and imp.kind == "type_alias":
          if node.value.id not in self._type_aliases:
            args = self.parse_type_args(
              node.slice, type_params, self_class=self_class,
            )
            return f"{imp.cpp_name}<{args}>"
      if isinstance(node.value, ast.Name) and node.value.id in self._type_aliases:
        ali = self._type_aliases[node.value.id]
        if ali.is_conditional and self._tr is not None:
          from ..passes.type_conditional import instantiate_conditional_alias_subscript

          cpp = instantiate_conditional_alias_subscript(
            self._tr, ali, node.slice, type_params,
          )
          from .type_extract import is_never_cpp_type

          if is_never_cpp_type(cpp):
            raise ValueError(
              f"类型 {ali.name}[…] 求值为 Never，不能用作存储类型"
            )
          return cpp
      if isinstance(node.value, ast.Name) and node.value.id == "WeakRef":
        inner = self._weakref_target_cpp_type(
          node.slice,
          type_params,
          dec,
          self_class=self_class,
          typevar_tuple_names=typevar_tuple_names,
        )
        imp = self._import_bindings.get("WeakRef")
        base = imp.cpp_name if imp is not None else cpp_ident("WeakRef")
        return f"{base}<{inner}>"
      if isinstance(node.value, ast.Name) and node.value.id == "RefCount":
        return self.parse_storage_type(
          node.slice,
          type_params,
          decorator_constraints=dec,
          self_class=self_class,
          typevar_tuple_names=typevar_tuple_names,
        )
      if isinstance(node.value, ast.Name) and node.value.id == "Generator":
        sl = node.slice
        if isinstance(sl, ast.Tuple) and len(sl.elts) == 3:
          args = ", ".join(
            self._parse_generator_type_arg(e, type_params, self_class=self_class)
            for e in sl.elts
          )
          return f"{cpp_ident('PyGenerator')}<{args}>"
        return cpp_ident("PyGenerator")
      if isinstance(node.value, ast.Name) and node.value.id == "Coroutine":
        sl = node.slice
        if isinstance(sl, ast.Tuple) and len(sl.elts) == 3:
          args = ", ".join(
            self._parse_generator_type_arg(e, type_params, self_class=self_class)
            for e in sl.elts
          )
          return f"{cpp_ident('PyCoroutine')}<{args}>"
        return cpp_ident("PyCoroutine")
      if isinstance(node.value, ast.Name) and node.value.id == "AsyncGenerator":
        sl = node.slice
        if isinstance(sl, ast.Tuple) and len(sl.elts) == 2:
          args = ", ".join(
            self._parse_generator_type_arg(e, type_params, self_class=self_class)
            for e in sl.elts
          )
          return f"{cpp_ident('PyAsyncGenerator')}<{args}>"
        return cpp_ident("PyAsyncGenerator")
      if isinstance(node.value, ast.Name):
        from .stubs.protocol_erase_stubs import (
          erased_protocol_cpp_name,
          load_protocol_runtime_erase,
        )

        if self._maps_to_runtime_protocol_erase(node.value.id):
          sl = node.slice
          if isinstance(sl, ast.Tuple):
            args = ", ".join(
              self.parse_storage_type(
                e,
                type_params,
                decorator_constraints=dec,
                self_class=self_class,
              )
              for e in sl.elts
            )
          else:
            args = self.parse_storage_type(
              sl, type_params, decorator_constraints=dec, self_class=self_class,
            )
          return f"{erased_protocol_cpp_name(node.value.id)}<{args}>"
      if isinstance(node.value, ast.Name) and node.value.id in (
        "list", "dict", "set", "frozenset", "deque", "frozenlist", "frozendict",
      ):
        sl = node.slice
        if isinstance(sl, ast.Tuple):
          args = ", ".join(
            self.parse_storage_type(
              e,
              type_params,
              decorator_constraints=dec,
              self_class=self_class,
            )
            for e in sl.elts
          )
        else:
          args = self.parse_storage_type(
            sl, type_params, decorator_constraints=dec, self_class=self_class,
          )
        return f"{cpp_ident(node.value.id)}<{args}>"
    if isinstance(node, ast.Name):
      if self._has_refcount_decorator_constraint(node.id, dec):
        return node.id
      if self._has_boxing_decorator_constraint(node.id, dec):
        return node.id
      return self.parse_type(
        node, type_params, self_class=self_class,
        typevar_tuple_names=typevar_tuple_names,
      )
    return self.parse_type(
      node, type_params, self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )

  def _parse_slice_type(
    self,
    slice_node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str:
    """``slice[T]`` → ``PySlice<T,T>``；``slice[T,U]`` → ``PySlice<T,U>``。"""
    if isinstance(slice_node, ast.Tuple):
      elts = slice_node.elts
      if len(elts) == 1:
        t = self.parse_type(elts[0], type_params, self_class=self_class)
        return f"{cpp_ident('slice')}<{t}, {t}>"
      args = ", ".join(
        self.parse_type(e, type_params, self_class=self_class) for e in elts
      )
      return f"{cpp_ident('slice')}<{args}>"
    t = self.parse_type(slice_node, type_params, self_class=self_class)
    return f"{cpp_ident('slice')}<{t}, {t}>"

  def parse_type_node(
    self,
    node: ast.expr | None,
    type_params: set[str],
    *,
    self_class: str | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ):
    """``parse_type`` 的 TypeNode 形式（见 ``docs/type-node.md``）。"""
    from .type_parse import parse_type_node as _parse_type_node

    return _parse_type_node(
      self,
      node,
      type_params,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )

  def parse_storage_type_node(
    self,
    node: ast.expr | None,
    type_params: set[str],
    *,
    decorator_constraints: dict[str, tuple[str, ...]] | None = None,
    self_class: str | None = None,
    typevar_tuple_names: frozenset[str] | None = None,
  ):
    """``parse_storage_type`` 的 TypeNode 形式。"""
    from .type_parse import parse_storage_type_node as _parse_storage_type_node

    return _parse_storage_type_node(
      self,
      node,
      type_params,
      decorator_constraints=decorator_constraints,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )

  def parse_type_args(
    self,
    slice_node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str:
    match slice_node:
      case ast.Tuple(elts=elts):
        return ", ".join(
          self.parse_type(e, type_params, self_class=self_class) for e in elts
        )
      case _:
        return self.parse_type(slice_node, type_params, self_class=self_class)

  @staticmethod
  def _slice_type_arg_nodes(slice_node: ast.expr) -> list[ast.expr]:
    if isinstance(slice_node, ast.Tuple):
      return list(slice_node.elts)
    return [slice_node]

  def _nttp_cpp_arg(
    self,
    node: ast.expr,
    *,
    cpp_type: str | None = None,
    type_params: set[str] | None = None,
    cls: ClassInfo | None = None,
  ) -> str:
    """NTTP 或类型位中的整型/布尔字面量 → C++ 模板实参。"""
    from .ir import (
      class_const_cpp_ref,
      cpp_type_param_template_name,
      eval_class_const_int,
      scalar_type_static_attr_from_expr,
    )

    macro = scalar_type_static_attr_from_expr(node)
    if macro is not None:
      return macro
    if cls is not None:
      ref = class_const_cpp_ref(node, cls)
      if ref is not None:
        return ref
      const_v = eval_class_const_int(node, cls)
      if const_v is not None:
        return self._nttp_cpp_arg(
          ast.Constant(value=const_v), cpp_type=cpp_type, type_params=type_params,
        )
    match node:
      case ast.Name(id=name) if type_params and name in type_params:
        return name
      case ast.Constant(value=v):
        if isinstance(v, bool):
          return "true" if v else "false"
        if isinstance(v, int):
          if cpp_type and is_int64_type(cpp_type):
            return format_cpp_int64(v)
          if cpp_type and is_uint_type(cpp_type):
            return format_cpp_uint(v)
          if cpp_type and is_uint64_type(cpp_type):
            return format_cpp_uint64(v)
          if cpp_type and is_uintptr_type(cpp_type):
            return format_cpp_uintptr(v)
          if cpp_type and is_varint_type(cpp_type):
            return format_cpp_varint(v)
          return format_cpp_int(v)
        raise NotImplementedError(f"NTTP literal: {ast.dump(node)}")
      case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=v)) if isinstance(v, int):
        if cpp_type and is_uint_type(cpp_type):
          raise NotImplementedError("uint NTTP 不支持一元负号")
        if cpp_type and is_uint64_type(cpp_type):
          raise NotImplementedError("uint64 NTTP 不支持一元负号")
        if cpp_type and is_uintptr_type(cpp_type):
          raise NotImplementedError("uintptr NTTP 不支持一元负号")
        if cpp_type and is_int64_type(cpp_type):
          return format_cpp_int64(-v)
        if cpp_type and is_varint_type(cpp_type):
          return format_cpp_varint(-v)
        return format_cpp_int(-v)
      case _:
        raise NotImplementedError(f"NTTP literal: {ast.dump(node)}")

  @staticmethod
  def _skip_refcount_wrap_for_class_template_arg(info: object) -> bool:
    """``WeakRef[T]`` 内层 ``T`` 保持裸 ``@refcount`` 类名，不包 ``PyRefCount``。"""
    name = getattr(info, "name", "")
    cpp = info.cpp_name() if hasattr(info, "cpp_name") else ""
    return name == "WeakRef" or cpp == "PyWeakRef"

  def _cpp_class_template_arg_type(
    self,
    info: object,
    node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str:
    """``list[Node]`` 等：``@refcount`` → ``PyRefCount<…>``；``@boxing`` → ``…*``（与约束无关）。"""
    t = self.parse_type(node, type_params, self_class=self_class)
    if self._skip_refcount_wrap_for_class_template_arg(info):
      return t
    return ClassInfo.apply_refcount_storage_cpp_type(t, self._classes)

  def _parse_class_template_arg(
    self,
    info: object,
    node: ast.expr,
    param: str,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str:
    """类型实参或 NTTP 实参（``Mod: T`` → 整型字面量）。"""
    nttp = getattr(info, "type_param_nttp", None) or {}
    if param in nttp:
      from .ir import class_info_for_cpp_type

      host: ClassInfo | None = None
      if self_class is not None:
        host = self._classes.get(self_class)
        if host is None:
          host = class_info_for_cpp_type(self_class, self._classes)
      val_ty = self.parse_type(
        ast.Name(id=nttp[param]),
        type_params,
        self_class=self_class,
      )
      return self._nttp_cpp_arg(
        node, cpp_type=val_ty, type_params=type_params, cls=host,
      )
    return self._cpp_class_template_arg_type(
      info, node, type_params, self_class=self_class,
    )

  def _subst_type_params_in_expr(
    self,
    node: ast.expr,
    subst: dict[str, ast.expr],
  ) -> ast.expr:
    class _Subst(ast.NodeTransformer):
      def visit_Name(self, n: ast.Name) -> ast.expr:
        if isinstance(n.ctx, ast.Load) and n.id in subst:
          return ast.copy_location(copy.deepcopy(subst[n.id]), n)
        return n

    return _Subst().visit(copy.deepcopy(node))

  def _parse_class_nested_type_alias(
    self,
    class_ref: ast.expr,
    attr: str,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    """``Cls.__alias__`` / ``Cls[T].__alias__`` → 展开类内 ``type`` 别名。"""
    class_name: str | None = None
    specialize_slice: ast.expr | None = None
    match class_ref:
      case ast.Name(id=name):
        class_name = name
      case ast.Subscript(value=ast.Name(id=name), slice=sl):
        class_name = name
        specialize_slice = sl
      case _:
        return None
    info = self._classes.get(class_name)
    if info is None:
      return None
    if attr in info.type_params and specialize_slice is not None:
      nodes = self._slice_type_arg_nodes(specialize_slice)
      for i, p in enumerate(info.type_params):
        if p == attr and i < len(nodes):
          return self.parse_type(
            nodes[i], type_params, self_class=self_class,
          )
      return None
    alias = info.type_aliases.get(attr)
    if alias is None or alias.member_constraint:
      return None
    value = alias.value
    if specialize_slice is not None and info.type_params:
      nodes = self._slice_type_arg_nodes(specialize_slice)
      subst: dict[str, ast.expr] = {}
      for i, p in enumerate(info.type_params):
        if i < len(nodes):
          subst[p] = nodes[i]
      if subst:
        value = self._subst_type_params_in_expr(value, subst)
    prev = dict(self._type_aliases)
    prev_use = self._alias_use_cpp_name
    try:
      self.set_type_aliases(
        {n: a for n, a in info.type_aliases.items() if n != attr},
      )
      return self.parse_type(
        value,
        set(info.type_params) | type_params,
        self_class=class_name,
      )
    finally:
      self.set_type_aliases(prev, use_as_cpp_name=prev_use)

  def _try_specialize_class_type(
    self,
    class_name: str,
    slice_node: ast.expr,
    type_params: set[str],
    *,
    self_class: str | None = None,
  ) -> str | None:
    """``Counter[str]`` → ``Counter<PyStr>``（省略的形参由 C++ 模板默认值补齐）。"""
    if class_name == "Generator":
      return None
    if class_name == "Coroutine":
      return None
    if class_name == "AsyncGenerator":
      return None
    info = self._classes.get(class_name)
    if info is None or not info.type_params:
      return None
    nodes = self._slice_type_arg_nodes(slice_node)
    if len(nodes) > len(info.type_params):
      return None
    cpp_args = [
      self._parse_class_template_arg(
        info, n, info.type_params[i], type_params, self_class=self_class,
      )
      for i, n in enumerate(nodes)
    ]
    defaults = info.type_param_defaults
    if defaults:
      for i in range(len(nodes), len(info.type_params)):
        param = info.type_params[i]
        dv = defaults.get(param)
        if dv is None:
          break
        cpp_args.append(
          self._parse_class_template_arg(
            info, dv, param, type_params, self_class=self_class,
          )
        )
    if class_name == "IterResult":
      from .ir import cpp_result_type

      if len(cpp_args) >= 2:
        y, r = cpp_args[0], cpp_args[1]
        if r == "void":
          r = cpp_ident("PyNone")
        return cpp_result_type(y, r)
      if len(cpp_args) == 1:
        return cpp_result_type(cpp_args[0])
    if class_name == "Result" and len(cpp_args) >= 2:
      from .ir import cpp_fault_result_type

      ok, err = cpp_args[0], cpp_args[1]
      if ok == "void":
        ok = cpp_ident("PyNone")
      return cpp_fault_result_type(ok, err)
    return f"{info.cpp_name()}<{', '.join(cpp_args)}>"


class SignatureBuilder:
  """根据 ``ClassInfo`` 与 ``FunctionDef`` 构建 ``MethodSig`` / ``FunctionSig``。"""

  def __init__(self, types: TypeParser):
    self._types = types
    self._classes: dict = {}
    self._lazy_param_defaults: dict[int, dict[str, ast.expr]] = {}

  def set_lazy_param_defaults(self, mapping: dict[int, dict[str, ast.expr]]) -> None:
    self._lazy_param_defaults = mapping

  def set_classes(self, classes: dict) -> None:
    self._classes = classes

  def _type_node_from_cpp(self, cpp: str):
    from .type_compat import type_node_from_cpp_string

    return type_node_from_cpp_string(cpp, classes=self._classes)

  def _reconcile_param_type_node(self, node, cpp_t: str):
    """``param_type_nodes`` 须与 ``_param_cpp_type`` 字符串一致（含末尾 storage 变换）。"""
    from .type_render import CLASS_BODY

    if node.render(CLASS_BODY) != cpp_t:
      return self._type_node_from_cpp(cpp_t)
    return node

  def _return_type_node_from_method_annotation(
    self,
    info: ClassInfo,
    method: ast.FunctionDef,
    ret_lead: str,
  ):
    """方法返回 ``TypeNode``（优先注解 AST；``ret_lead`` 不一致时回退字符串桥接）。"""
    from .type_node import TypeNode
    from .type_parse import parse_storage_type_node
    from .type_storage import apply_full_storage_type_node

    if method.returns is None:
      return None
    if ret_lead == "auto":
      return TypeNode.scalar("auto")
    func_ft = self._method_func_ft(info, method)
    tparams = set(info.type_params) | set(func_ft.template_names)
    if isinstance(method.returns, ast.Subscript) and isinstance(
      method.returns.value, ast.Name,
    ):
      if method.returns.value.id in ("Generator", "Coroutine", "AsyncGenerator"):
        return None
    dec = self._decorator_constraints_for(info, func_ft)
    node = apply_full_storage_type_node(
      parse_storage_type_node(
        self._types,
        method.returns,
        tparams,
        decorator_constraints=dec,
        self_class=info.template_cpp_type(),
      ),
      self._classes,
    )
    return self._reconcile_param_type_node(node, ret_lead)

  def _return_type_node_from_function_annotation(
    self,
    func: ast.FunctionDef,
    ret_lead: str,
    *,
    module_path: str = "",
  ):
    from .ir import FuncTypeParams
    from .type_node import TypeNode
    from .type_parse import parse_storage_type_node
    from .type_storage import apply_full_storage_type_node

    if func.returns is None:
      return None
    if ret_lead == "auto":
      return TypeNode.scalar("auto")
    func_ft = FuncTypeParams.collect(func)
    tparams = set(func_ft.template_names)
    if module_path and self._types._tr is not None:
      tr = self._types._tr
      self._types.set_import_bindings(
        tr.module_import_bindings.get(module_path, {}),
      )
      from .imports import effective_module_type_aliases

      self._types.set_type_aliases(
        effective_module_type_aliases(tr, module_path),
        use_as_cpp_name=False,
      )
    if isinstance(func.returns, ast.Subscript) and isinstance(
      func.returns.value, ast.Name,
    ):
      if func.returns.value.id in ("Generator", "Coroutine", "AsyncGenerator"):
        return None
    node = apply_full_storage_type_node(
      parse_storage_type_node(self._types, func.returns, tparams),
      self._classes,
    )
    return self._reconcile_param_type_node(node, ret_lead)

  def _method_param_type_nodes(
    self, info: ClassInfo, method: ast.FunctionDef,
  ) -> dict[str, "TypeNode"]:
    """形参 ``TypeNode``（优先 AST ``parse_storage_type_node``，特殊形参回退字符串桥接）。"""
    from .lazy_param import is_lazy_type_annotation, lazy_param_inner_annotation
    from .type_node import TypeNode
    from .type_parse import parse_storage_type_node
    from .type_storage import apply_full_storage_type_node
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    func_ft = self._method_func_ft(info, method)
    variadic_template = resolve_variadic_template(
      method,
      class_type_params=info.effective_type_params,
      class_typevar_tuple=info.typevar_tuple,
    )
    vararg_pack = resolve_vararg_pack(
      self._types,
      method,
      class_type_params=info.effective_type_params,
      class_typevar_tuple=info.typevar_tuple,
      self_class=info.template_cpp_type(),
    )
    tparams = set(info.effective_type_params) | set(func_ft.template_names)
    dec = self._decorator_constraints_for(info, func_ft)
    self_class = info.template_cpp_type()
    out: dict[str, TypeNode] = {}
    for arg in method.args.args:
      if arg.arg in ("self", "cls"):
        continue
      cpp_t = self._param_cpp_type(
        arg, class_type_params=info.type_params, func_ft=func_ft, info=info, method=method,
      )
      if is_lazy_type_annotation(arg.annotation):
        inner = lazy_param_inner_annotation(arg.annotation)
        if inner is not None:
          out[arg.arg] = self._reconcile_param_type_node(
            apply_full_storage_type_node(
              parse_storage_type_node(
                self._types, inner, tparams, decorator_constraints=dec, self_class=self_class,
              ),
              self._classes,
            ),
            cpp_t,
          )
        else:
          out[arg.arg] = self._type_node_from_cpp(cpp_t)
      elif arg.annotation is not None and arg.arg not in func_ft.arg_types:
        out[arg.arg] = self._reconcile_param_type_node(
          apply_full_storage_type_node(
            parse_storage_type_node(
              self._types, arg.annotation, tparams, decorator_constraints=dec, self_class=self_class,
            ),
            self._classes,
          ),
          cpp_t,
        )
      else:
        out[arg.arg] = self._type_node_from_cpp(cpp_t)
    if variadic_template is not None:
      out[variadic_template.param_name] = TypeNode.type_param(
        f"{variadic_template.pack_name}...",
      )
    elif vararg_pack is not None:
      out[vararg_pack.param_name] = self._type_node_from_cpp(vararg_pack.cpp_type)
    return out

  def _return_type_node_from_method(
    self, info: ClassInfo, method: ast.FunctionDef, ret_lead: str,
  ):
    from .type_node import TypeNode

    if not ret_lead or ret_lead == "void":
      return TypeNode.void()
    node = self._return_type_node_from_method_annotation(info, method, ret_lead)
    if node is not None:
      return node
    return self._type_node_from_cpp(ret_lead)

  def _return_type_node_from_function(
    self, func: ast.FunctionDef, ret_lead: str, module_path: str = "",
  ):
    from .type_node import TypeNode

    if not ret_lead or ret_lead == "void":
      return TypeNode.void()
    node = self._return_type_node_from_function_annotation(
      func, ret_lead, module_path=module_path,
    )
    if node is not None:
      return node
    return self._type_node_from_cpp(ret_lead)

  def _function_param_type_nodes(
    self, func: ast.FunctionDef, *, module_path: str = "",
  ) -> dict[str, "TypeNode"]:
    from .ir import FuncTypeParams
    from .lazy_param import is_lazy_type_annotation, lazy_param_inner_annotation
    from .type_node import TypeNode
    from .type_parse import parse_storage_type_node
    from .type_storage import apply_full_storage_type_node
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    func_ft = FuncTypeParams.collect(func)
    variadic_template = resolve_variadic_template(func)
    vararg_pack = resolve_vararg_pack(self._types, func)
    tparams = set(func_ft.template_names)
    if module_path and self._types._tr is not None:
      tr = self._types._tr
      self._types.set_import_bindings(
        tr.module_import_bindings.get(module_path, {}),
      )
      from .imports import effective_module_type_aliases

      self._types.set_type_aliases(
        effective_module_type_aliases(tr, module_path),
        use_as_cpp_name=False,
      )
    out: dict[str, TypeNode] = {}
    for arg in func.args.args:
      cpp_t = self._param_cpp_type(
        arg, class_type_params=[], func_ft=func_ft, method=func,
      )
      if is_lazy_type_annotation(arg.annotation):
        inner = lazy_param_inner_annotation(arg.annotation)
        if inner is not None:
          out[arg.arg] = self._reconcile_param_type_node(
            apply_full_storage_type_node(
              parse_storage_type_node(self._types, inner, tparams),
              self._classes,
            ),
            cpp_t,
          )
        else:
          out[arg.arg] = self._type_node_from_cpp(cpp_t)
      elif arg.annotation is not None and arg.arg not in func_ft.arg_types:
        out[arg.arg] = self._reconcile_param_type_node(
          apply_full_storage_type_node(
            parse_storage_type_node(self._types, arg.annotation, tparams),
            self._classes,
          ),
          cpp_t,
        )
      else:
        out[arg.arg] = self._type_node_from_cpp(cpp_t)
    if variadic_template is not None:
      out[variadic_template.param_name] = TypeNode.type_param(
        f"{variadic_template.pack_name}...",
      )
    elif vararg_pack is not None:
      out[vararg_pack.param_name] = self._type_node_from_cpp(vararg_pack.cpp_type)
    return out

  def _param_type_nodes(self, param_types: dict[str, str]) -> dict:
    return {k: self._type_node_from_cpp(v) for k, v in param_types.items()}

  def _return_type_node(self, ret_lead: str):
    from .type_node import TypeNode

    if not ret_lead or ret_lead == "void":
      return TypeNode.void()
    return self._type_node_from_cpp(ret_lead)

  def _set_field_type_node(self, info: ClassInfo, field: str, node) -> None:
    from .type_emit import write_field_storage

    write_field_storage(info, field, node)

  def _set_field_cpp_type(self, info: ClassInfo, field: str, ft: str) -> None:
    self._set_field_type_node(info, field, self._type_node_from_cpp(ft))

  @staticmethod
  def _method_func_ft(info: ClassInfo, method: ast.FunctionDef) -> FuncTypeParams:
    reserved = frozenset(info.type_params) | {
      p for a in info.type_aliases.values() for p in a.type_params
    }
    return FuncTypeParams.collect(method, reserved)

  def _default_cpp_arg(
    self,
    node: ast.expr,
    *,
    cpp_type: str | None = None,
    info: ClassInfo | None = None,
  ) -> str:
    from .ir import scalar_type_static_attr_from_expr

    macro = scalar_type_static_attr_from_expr(node)
    if macro is not None:
      return macro
    from .ir import class_const_cpp_ref

    const_ref = class_const_cpp_ref(node, info)
    if const_ref is not None:
      return const_ref
    match node:
      case ast.Constant(value=v):
        if v is None:
          if cpp_type:
            from .ir import cpp_union_static_call, strip_cpp_ref

            ct = cpp_type.strip()
            if is_py_callable_type(ct):
              base = strip_cpp_ref(ct)
              return f"{base}{{}}"
            if ct.startswith("PyOptional<"):
              return cpp_union_static_call(strip_cpp_ref(ct), "None_")
            if is_refcount_type(ct):
              return "nullptr"
            from .type_pred import is_str_type

            if is_str_type(ct, classes=self._classes):
              return f"{cpp_ident('str')}{{}}"
          return "0"
        if isinstance(v, bool):
          return "true" if v else "false"
        if isinstance(v, bytes):
          if cpp_type and is_bytes_type(cpp_type):
            return bytes_cpp_from_literal(v)
          raise NotImplementedError("bytes 字面量须用于 bytes 类型注解或 byte[:] 初始化")
        if isinstance(v, str):
          if cpp_type and is_char_heap_array_type(cpp_type) and v == "":
            return f"{cpp_type}(0)"
          if cpp_type == "c_str":
            return quote_cpp_string(v)
          return str_cpp_from_literal(v)
        if isinstance(v, float):
          if cpp_type and is_float64_type(cpp_type):
            return format_cpp_float64(v)
          return format_cpp_float(v)
        if isinstance(v, int):
          if cpp_type and is_byte_type(cpp_type):
            return f"PyByte({v})"
          if cpp_type and is_char_type(cpp_type):
            return f"PyChar({v})"
          if cpp_type and is_int64_type(cpp_type):
            return format_cpp_int64(v)
          if cpp_type and is_uint_type(cpp_type):
            return format_cpp_uint(v)
          if cpp_type and is_uint64_type(cpp_type):
            return format_cpp_uint64(v)
          if cpp_type and is_uintptr_type(cpp_type):
            return format_cpp_uintptr(v)
          if cpp_type and is_varint_type(cpp_type):
            return format_cpp_varint(v)
          return format_cpp_int(v)
        return format_cpp_int(v) if isinstance(v, int) else str(v)
      case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=v)) if isinstance(v, int):
        if cpp_type and is_uint_type(cpp_type):
          raise NotImplementedError("uint 字面量不支持一元负号")
        if cpp_type and is_uint64_type(cpp_type):
          raise NotImplementedError("uint64 字面量不支持一元负号")
        if cpp_type and is_int64_type(cpp_type):
          return format_cpp_int64(-v)
        if cpp_type and is_varint_type(cpp_type):
          return format_cpp_varint(-v)
        return format_cpp_int(-v)
      case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=v)) if isinstance(v, float):
        if cpp_type and is_float64_type(cpp_type):
          return format_cpp_float64(-v)
        return format_cpp_float(-v)
      case ast.Call(func=ast.Name(id="new")):
        if not cpp_type:
          raise NotImplementedError("new() 默认参数须能推断 C++ 类型")
        from ..analysis.ir import class_info_for_cpp_type
        from ..emit.literal_ctor_emit import new_call_default_ctor_cpp

        target = class_info_for_cpp_type(cpp_type, self._classes)
        target_init = target.inits[0] if target and target.inits else None
        target_ft = (
          FuncTypeParams.collect(target_init, frozenset(target.type_params))
          if target_init is not None and target is not None
          else None
        )
        target_tparams = list(target.type_params) if target else []

        def _parse_new_param_type(arg: ast.arg) -> str | None:
          if arg.annotation is None:
            return None
          return self._param_cpp_type(
            arg,
            class_type_params=target_tparams,
            func_ft=target_ft,
            info=target,
            method=target_init,
          )

        return new_call_default_ctor_cpp(
          node,
          cpp_type,
          classes=self._classes,
          emit_default_arg=lambda e, t=None: self._default_cpp_arg(e, cpp_type=t),
          parse_param_type=_parse_new_param_type,
        )
      case ast.Call(func=ast.Name(id=class_name), args=[], keywords=[]):
        if class_name in self._classes:
          from ..analysis.ir import strip_cpp_ref as _strip_cpp_ref
          if cpp_type:
            return f"{_strip_cpp_ref(cpp_type)}()"
          return f"{self._classes[class_name].cpp_name()}()"
      case ast.Tuple(elts=elts):
        if cpp_type:
          tuple_prefix = f"{cpp_ident('tuple')}<"
          inner = cpp_template_inner_args(cpp_type, tuple_prefix)
          if inner is not None:
            elem_types = [t.strip() for t in inner.split(",") if t.strip()]
            if len(elts) != len(elem_types):
              raise NotImplementedError(
                f"tuple 默认值元素个数与类型 {cpp_type} 不一致",
              )
            args = ", ".join(
              self._default_cpp_arg(e, cpp_type=elem_types[i])
              for i, e in enumerate(elts)
            )
            return f"{cpp_type}({args})"
        raise NotImplementedError(f"default arg: {ast.dump(node)}")
      case ast.Attribute(value=ast.Name(id=enum_name), attr=member) if enum_name != "new":
        from ..passes.enum_expand import enum_member_names
        from ..analysis.module_namespace import qualify_symbol_in_module

        cinfo = self._classes.get(enum_name)
        if cinfo is not None and cinfo.is_enum and member in enum_member_names(cinfo):
          base = qualify_symbol_in_module(cinfo.module_path, cinfo.cpp_name())
          return f"{base}::{member}"
        raise NotImplementedError(f"default arg: {ast.dump(node)}")
      case ast.Attribute(value=ast.Name(id="new"), attr=attr):
        if cpp_type:
          from ..analysis.ir import (
            class_info_for_cpp_type,
            property_getter_method_for,
            qualified_class_static_callee,
          )

          info = class_info_for_cpp_type(cpp_type, self._classes)
          if info is not None and attr in info.static_properties:
            getter = info.cpp_member_name(property_getter_method_for(attr))
            return f"{qualified_class_static_callee(info, getter)}()"
        raise NotImplementedError(f"default arg: {ast.dump(node)}")
      case _:
        raise NotImplementedError(f"default arg: {ast.dump(node)}")

  def _field_cpp_type(self, info: ClassInfo, field: str) -> str:
    from .type_emit import field_storage_cpp

    cached = field_storage_cpp(info, field)
    if cached:
      return cached
    if field in INT_FIELDS:
      return cpp_ident("int")
    return "void*"

  @staticmethod
  def _alloc_elem_type_from_call(node: ast.expr) -> str | None:
    if not isinstance(node, ast.Call):
      return None
    match node.func:
      case ast.Subscript(value=ast.Name(id=name), slice=sl) if name in ("alloc", "allocArray", "allocRawArray"):
        match sl:
          case ast.Name(id=elem):
            return elem
          case _:
            return None
      case _:
        return None

  def _infer_pointer_fields_from_inits(self, info: ClassInfo):
    for init in info.inits:
      for stmt in ast.walk(init):
        if not isinstance(stmt, ast.Assign):
          continue
        for target in stmt.targets:
          if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
          ):
            elem = self._alloc_elem_type_from_call(stmt.value)
            if elem:
              self._set_field_cpp_type(info, target.attr, f"{elem}*")

  def _infer_fields_from_init_assignments(self, info: ClassInfo):
    """从 ``__init__`` 里 ``self.f = param`` 推断字段类型。"""
    from .ir import resolve_self_in_cpp_type
    from .type_emit import field_storage_cpp

    tparams = set(info.type_params)
    for init in info.inits:
      arg_types: dict[str, str] = {}
      for arg in init.args.args:
        if arg.arg == "self":
          continue
        if arg.annotation:
          arg_types[arg.arg] = resolve_self_in_cpp_type(
            self._parse_ann_storage_type(arg.annotation, tparams, info=info),
            info.cpp_name(),
          )
      for stmt in init.body:
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
          if field in info.class_body_field_anns:
            continue
          match stmt.value:
            case ast.Name(id=name) if name in arg_types:
              new_ft = arg_types[name]
              cur = field_storage_cpp(info, field)
              if cur.endswith("*") and not new_ft.rstrip().endswith("*"):
                continue
              self._set_field_cpp_type(info, field, new_ft)
            case ast.Constant(value=v) if isinstance(v, bool):
              self._set_field_cpp_type(info, field, cpp_ident("bool"))
            case ast.Constant(value=v) if isinstance(v, int):
              cur = field_storage_cpp(info, field)
              if cur and cur not in ("", "void*", cpp_ident("int")):
                continue
              self._set_field_cpp_type(info, field, cpp_ident("int"))
            case ast.Constant(value=v) if isinstance(v, float):
              self._set_field_cpp_type(info, field, cpp_ident("float"))
            case ast.Constant(value=None):
              cur = field_storage_cpp(info, field)
              if cur and cur not in ("", "void*"):
                continue
              self._set_field_cpp_type(info, field, "void*")

  def resolve_class_field_types(self, info: ClassInfo):
    from .type_emit import clear_field_ann_ast, field_ann_ast, field_storage_cpp, write_field_ann_ast, write_field_storage

    tparams = set(info.effective_type_params)
    for field in list(info.fields):
      ann = field_ann_ast(info, field)
      if ann is not None:
        node = self._parse_ann_storage_type_node(ann, tparams, info=info)
        ecs_ft = ecs_query_ptr_cpp_type(info.name, field, info.type_params)
        if ecs_ft is not None:
          self._set_field_cpp_type(info, field, ecs_ft)
          clear_field_ann_ast(info, field)
          continue
        owner_field = host_owner_field_name(info.name)
        if owner_field and field == owner_field and info.type_params:
          host_py = dict_like_host_py_name(info.name) or iterator_owner_host_py_name(info.name)
          if host_py:
            const = host_py not in ("deque", "ChunkDeque")
            resolved = host_ptr_cpp_type(host_py, info.type_params, const=const)
            if resolved is not None:
              self._set_field_cpp_type(info, field, resolved)
              clear_field_ann_ast(info, field)
              continue
        if info.name == "array" and field == "_data" and info.type_params:
          self._set_field_cpp_type(info, field, f"{info.type_params[0]}*")
          clear_field_ann_ast(info, field)
          continue
        if info.name.endswith("_iterator") and field == "_host":
          host_py = info.name[: -len("_iterator")]
          host_info = self._classes.get(host_py)
          if host_info is not None:
            self._set_field_cpp_type(
              info, field, f"{host_info.template_cpp_type()}*",
            )
            clear_field_ann_ast(info, field)
            continue
        from .ir import resolve_self_in_cpp_type
        from .type_render import CLASS_BODY

        rendered = node.render(CLASS_BODY)
        resolved = resolve_self_in_cpp_type(rendered, info.cpp_name())
        if resolved != rendered:
          self._set_field_cpp_type(info, field, resolved)
        else:
          write_field_storage(info, field, node)
        clear_field_ann_ast(info, field)
      elif field not in info.field_type_nodes and not field_storage_cpp(info, field):
        self._set_field_cpp_type(info, field, self._field_cpp_type(info, field))
    for field, stmt in getattr(info, "thread_local_fields", {}).items():
      ann = field_ann_ast(info, field) or stmt.annotation
      if ann is None:
        continue
      node = self._parse_ann_storage_type_node(ann, tparams, info=info)
      from .ir import resolve_self_in_cpp_type
      from .type_render import CLASS_BODY

      rendered = node.render(CLASS_BODY)
      resolved = resolve_self_in_cpp_type(rendered, info.cpp_name())
      if resolved != rendered:
        self._set_field_cpp_type(info, field, resolved)
      else:
        write_field_storage(info, field, node)
      clear_field_ann_ast(info, field)
    self._infer_fields_from_init_assignments(info)
    if info.name.endswith("_iterator") and "_host" in info.fields:
      host_py = info.name[: -len("_iterator")]
      host_info = self._classes.get(host_py)
      if host_info is not None:
        self._set_field_cpp_type(info, "_host", f"{host_info.template_cpp_type()}*")
    self._infer_pointer_fields_from_inits(info)
    info.owned_fields = collect_owned_fields_from_inits(info.inits)
    info.owned_array_sizes = collect_owned_array_sizes(info.inits)
    if info.needs_auto_copy():
      info.has_copy = True
    if info.needs_auto_move():
      info.has_move = True
    if info.is_uncopyable:
      info.has_copy = False

  def _param_cpp_type(
    self,
    arg: ast.arg,
    *,
    class_type_params: list[str],
    func_ft: FuncTypeParams,
    info: ClassInfo | None = None,
    method: ast.FunctionDef | None = None,
  ) -> str:
    from .lazy_param import is_lazy_type_annotation, lazy_param_inner_annotation, lazy_supplier_cpp_type

    tparams = set(class_type_params) | set(func_ft.template_names)
    if is_lazy_type_annotation(arg.annotation):
      inner = lazy_param_inner_annotation(arg.annotation)
      if inner is None:
        inner_t = "void*"
      else:
        self_class = info.template_cpp_type() if info else None
        inner_t = self._types.parse_type(
          inner,
          tparams,
          self_class=self_class,
        )
      return lazy_supplier_cpp_type(inner_t)
    if arg.arg in func_ft.arg_types:
      t = func_ft.arg_types[arg.arg]
    elif arg.annotation:
      self_class = info.template_cpp_type() if info else None
      t = self._types.parse_storage_type(
        arg.annotation,
        tparams,
        decorator_constraints=self._decorator_constraints_for(info, func_ft),
        self_class=self_class,
      )
      base = t.split("<", 1)[0].strip()
      if base in PROTOCOL_PARAM_ERASE:
        raise NotImplementedError(
          f"形参 {arg.arg}: 协议注解 {base} 须由 FuncTypeParams 转为模板约束，"
          "请写 ``x: Comparable``、``xs: Iterable[T]`` 或 ``def f[T: Comparable](...)``"
        )
    else:
      t = "void*"
    if (
      info is not None
      and method
      and method.name == "__init__"
      and arg.arg == "data"
      and info.name == "str"
    ):
      return f"{cpp_template_type('array', cpp_ident('char'))}&"
    if (
      info is not None
      and method
      and method.name == "__init__"
      and arg.arg == "data"
      and info.name == "bytes"
    ):
      elem = "byte"
      return f"{cpp_template_type('array', cpp_ident(elem))}"
    if (
      method
      and method.name == "_append"
      and arg.arg == "buf"
    ):
      elem = "byte" if info is not None and info.name == "bytes" else "char"
      return f"{cpp_template_type('array', cpp_ident(elem))}&"
    if (
      method
      and method.name in ("_append_byte", "_write_utf8")
      and arg.arg == "buf"
    ):
      return f"{cpp_template_type('array', cpp_ident('byte'))}&"
    if info is not None:
      if info.name == "str" and method and method.name == "__init__" and arg.arg == "text":
        return "c_str"
      if method and arg.arg == "other":
        if method.name == "__copy__":
          if info.is_template():
            return f"const {info.cpp_specialization()}&"
          return f"const {info.cpp_name()}&"
        if method.name == "__move__":
          if info.is_template():
            return f"{info.cpp_specialization()}&"
          return f"{info.cpp_name()}&"
      if (
        info.is_copyable
        and method
        and not has_named_decorator(method, "staticmethod")
        and not has_named_decorator(method, "classmethod")
        and arg.arg not in ("self", "cls")
        and method.name != "__move__"
        and arg.annotation
        and isinstance(arg.annotation, ast.Name)
        and arg.annotation.id in (info.name, "Self")
      ):
        if info.is_template():
          return f"const {info.cpp_specialization()}&"
        return f"const {info.cpp_name()}&"
      ecs_t = ecs_query_ptr_cpp_type(info.name, arg.arg, info.type_params)
      if ecs_t is not None:
        t = ecs_t
      owner_param = host_owner_param_name(info.name)
      if owner_param and arg.arg == owner_param and info.type_params:
        host_py = dict_like_host_py_name(info.name) or iterator_owner_host_py_name(info.name)
        if host_py:
          const = host_py not in ("deque", "ChunkDeque")
          resolved = host_ptr_cpp_type(host_py, info.type_params, const=const)
          if resolved is not None:
            t = resolved
    return self._storage_cpp_type(t)

  def _collect_lazy_params(
    self,
    func: ast.FunctionDef,
    *,
    info: ClassInfo | None = None,
  ) -> dict[str, "LazyParamInfo"]:
    from .lazy_param import (
      LazyParamInfo,
      is_lazy_type_annotation,
      lazy_param_has_ref,
      lazy_param_inner_annotation,
      lazy_supplier_cpp_type,
    )

    func_ft = (
      self._method_func_ft(info, func)
      if info is not None
      else FuncTypeParams.collect(func)
    )
    tparams = set(func_ft.template_names)
    if info is not None:
      tparams |= set(info.type_params)
    stored = self._lazy_param_defaults.get(id(func), {})
    out: dict[str, LazyParamInfo] = {}
    for arg in func.args.args:
      if arg.arg in ("self", "cls"):
        continue
      if not is_lazy_type_annotation(arg.annotation):
        continue
      inner = lazy_param_inner_annotation(arg.annotation)
      if inner is None:
        value_t = "void*"
      else:
        self_class = info.template_cpp_type() if info else None
        value_t = self._types.parse_type(inner, tparams, self_class=self_class)
      base = value_t.rstrip("&").strip()
      out[arg.arg] = LazyParamInfo(
        value_cpp_type=base,
        supplier_cpp_type=lazy_supplier_cpp_type(base),
        materialized_ref=lazy_param_has_ref(arg.annotation),
        default_expr=stored.get(arg.arg),
      )
    return out

  _PASS_BY_REF_METHOD_PARAM_TYPES = frozenset(
    {
      "TestResult",
      "TestSuite",
      cpp_ident("TextIOWrapper"),
      cpp_ident("StringIO"),
    },
  )

  @classmethod
  def _is_staticmethod_self_receiver(
    cls,
    info: ClassInfo | None,
    method: ast.FunctionDef | None,
    arg_name: str | None,
  ) -> bool:
    """``@staticmethod`` 上 ``z: Self`` 等可变接收者须 ``T&``（如 ``varint._parse_decimal``）。"""
    if info is None or method is None or not arg_name:
      return False
    if not has_named_decorator(method, "staticmethod"):
      return False
    for arg in method.args.args:
      if arg.arg != arg_name:
        continue
      ann = arg.annotation
      if isinstance(ann, ast.Name) and ann.id in ("Self", info.name):
        return True
      return False
    return False

  def _method_param_pass_by_ref(
    self,
    cpp_type: str,
    classes: dict[str, ClassInfo] | None = None,
    *,
    info: ClassInfo | None = None,
    method: ast.FunctionDef | None = None,
    arg_name: str | None = None,
  ) -> bool:
    """容器与用户类按引用传参，避免按值拷贝/移动（含友元测试里 ``bump(self, v: Vault)``）。

    ``list_iterator`` / ``frozenlist_iterator`` / ``set_iterator`` / ``frozenset_iterator`` 的 ``owner`` 为 ``const PyList*`` / ``const PyFrozenList*`` / ``const PySet*`` / ``const PyFrozenSet*``（只读遍历），见 ``_param_cpp_type``。
    """
    from .type_pred import is_delegate_type

    if is_delegate_type(cpp_type, delegate_names=self._types._delegate_names):
      return True
    if self._is_staticmethod_self_receiver(info, method, arg_name):
      return True
    if method is not None and arg_name:
      from ..passes.descriptor_signatures import is_descriptor_signature_helper

      if is_descriptor_signature_helper(method.name):
        return True
      if method.name == "serialize" and arg_name == "encoder":
        return True
      if method.name == "deserialize" and arg_name == "decoder":
        return True
      if arg_name in ("dec", "decoder") and "JsonDecoder" in cpp_type:
        return True
      if (
        info is not None
        and info.name == "list"
        and method.name in ("append", "insert", "_insert_new")
        and arg_name == "item"
      ):
        return True
      if info is not None and info.name == "ExceptionGroup":
        if method.name == "append" and arg_name == "e":
          return True
        if method.name == "assign" and arg_name == "other":
          return True
      # ``PyBytes`` 由 ``_sub`` 等临时 ``PyArray`` 构造：按值接管，勿绑到悬垂引用。
      if (
        info is not None
        and method.name == "__init__"
        and arg_name == "data"
        and info.name == "bytes"
      ):
        return False
    if _exception_param_cpp_type(cpp_type) is not None:
      return True
    if is_heap_array_type(cpp_type):
      return True
    if cpp_type in self._PASS_BY_REF_METHOD_PARAM_TYPES:
      return True
    bare = cpp_type.strip()
    if bare.endswith("&"):
      bare = bare[:-1].strip()
    # ``Pointer[T]`` / ``T*``：按值传指针，勿剥 ``*`` 后按用户类再加 ``&``（会得到 ``T*&``）
    if bare.endswith("*"):
      return False
    if bare.startswith("const "):
      bare = bare[6:].strip()
    if info is not None and bare in info.type_aliases:
      return False
    if classes:
      for cinfo in classes.values():
        if (
          cinfo.is_protocol
          or cinfo.is_mixin
          or cinfo.is_annotation
          or cinfo.is_descriptor
          or cinfo.is_enum
        ):
          continue
        mp = cinfo.module_path.replace("\\", "/").strip("/")
        if mp == RUNTIME_PKG or mp.startswith(f"{RUNTIME_PKG}/"):
          continue
        cn = cinfo.cpp_name()
        if bare == cn or bare.startswith(f"{cn}<"):
          return True
    return (
      is_list_type(cpp_type)
      or is_deque_type(cpp_type)
      or is_dict_type(cpp_type)
      or is_set_type(cpp_type)
      or is_frozenset_type(cpp_type)
      or is_frozenlist_type(cpp_type)
      or is_frozendict_type(cpp_type)
      or is_stack_array_type(cpp_type)
      or is_span_type(cpp_type)
    )

  @staticmethod
  def _format_param_decl(
    cpp_type: str,
    name: str,
    *,
    ref_str: bool = False,
    pass_by_ref: bool = False,
    const_ref: bool = False,
  ) -> str:
    exc = _exception_param_cpp_type(cpp_type)
    if pass_by_ref and exc is not None:
      return f"const {exc}& {name}"
    if cpp_type.endswith("&"):
      return f"{cpp_type} {name}"
    if pass_by_ref:
      if cpp_type.rstrip().endswith("*"):
        return f"{cpp_type} {name}"
      if is_str_type(cpp_type):
        ps = cpp_ident("str")
        return f"const {ps}& {name}"
      if is_container_type(cpp_type):
        return f"const {cpp_type}& {name}"
      if const_ref:
        return f"const {cpp_type}& {name}"
      return f"{cpp_type}& {name}"
    if is_str_type(cpp_type) and ref_str:
      ps = cpp_ident("str")
      return f"const {ps}& {name}"
    if is_str_type(cpp_type):
      return f"{cpp_ident('str')} {name}"
    if is_py_callable_type(cpp_type):
      return f"{cpp_type} {name}"
    if is_callable_type(cpp_type):
      return format_cpp_callable_var_decl(cpp_type, name) or f"{cpp_type} {name}"
    return f"{cpp_type} {name}"

  @staticmethod
  def _decltype_binop(op: ast.operator) -> str | None:
    match op:
      case ast.Add():
        return "+"
      case ast.Sub():
        return "-"
      case ast.Mult():
        return "*"
      case ast.Div() | ast.FloorDiv():
        return "/"
      case ast.Mod():
        return "%"
      case ast.BitOr():
        return "|"
      case ast.BitXor():
        return "^"
      case ast.BitAnd():
        return "&"
      case ast.LShift():
        return "<<"
      case ast.RShift():
        return ">>"
      case _:
        return None

  @staticmethod
  def _decltype_binop_prec(op: ast.operator) -> int:
    match op:
      case ast.Add() | ast.Sub() | ast.BitOr() | ast.BitXor():
        return 1
      case ast.BitAnd():
        return 2
      case ast.LShift() | ast.RShift():
        return 3
      case ast.Mult() | ast.Div() | ast.FloorDiv() | ast.Mod():
        return 4
      case _:
        return 0

  def _wrap_decltype_operand(self, node: ast.expr, text: str, parent_op: ast.operator) -> str:
    if isinstance(node, ast.BinOp) and self._decltype_binop_prec(node.op) < self._decltype_binop_prec(parent_op):
      return f"({text})"
    return text

  def _expr_for_decltype(self, node: ast.expr) -> str | None:
    match node:
      case ast.BinOp(left=l, op=op, right=r):
        sym = self._decltype_binop(op)
        if not sym:
          return None
        ls, rs = self._expr_for_decltype(l), self._expr_for_decltype(r)
        if not ls or not rs:
          return None
        ls = self._wrap_decltype_operand(l, ls, op)
        rs = self._wrap_decltype_operand(r, rs, op)
        return f"{ls} {sym} {rs}"
      case ast.UnaryOp(op=ast.USub(), operand=inner):
        inner_s = self._expr_for_decltype(inner)
        if not inner_s:
          return None
        if isinstance(inner, ast.BinOp):
          return f"-({inner_s})"
        return f"-{inner_s}"
      case ast.Name(id=name):
        return cpp_param(name)
      case ast.Attribute(value=val, attr=attr):
        base = self._expr_for_decltype(val)
        if not base:
          return None
        return f"{base}.{attr}"
      case ast.Call(func=ast.Attribute(value=val, attr=attr), args=args, keywords=kw) if not kw:
        base = self._expr_for_decltype(val)
        if not base:
          return None
        arg_parts: list[str] = []
        for a in args:
          s = self._expr_for_decltype(a)
          if not s:
            return None
          arg_parts.append(s)
        inside = ", ".join(arg_parts)
        return f"({base}.{attr}({inside}))"
      case ast.Call(func=ast.Name(id=name), args=args, keywords=kw) if not kw:
        arg_parts = []
        for a in args:
          s = self._expr_for_decltype(a)
          if not s:
            return None
          arg_parts.append(s)
        inside = ", ".join(arg_parts)
        return f"({cpp_param(name)}({inside}))"
      case ast.Constant(value=v):
        if v is None:
          return "nullptr"
        if isinstance(v, bool):
          return "true" if v else "false"
        if isinstance(v, str):
          return str_cpp_from_literal(v)
        if isinstance(v, float):
          return format_cpp_float(v)
        return str(v)
      case _:
        return None

  def _return_decltype_expr(self, func: ast.FunctionDef) -> str | None:
    for stmt in func.body:
      if isinstance(stmt, ast.Return) and stmt.value is not None:
        return self._expr_for_decltype(stmt.value)
    return None

  def _single_return_value(self, func: ast.FunctionDef) -> ast.expr | None:
    """仅含可选 docstring + ``return expr`` 的薄转发函数。"""
    body = list(func.body)
    if (
      body
      and isinstance(body[0], ast.Expr)
      and isinstance(body[0].value, ast.Constant)
      and isinstance(body[0].value.value, str)
    ):
      body = body[1:]
    if len(body) != 1:
      return None
    stmt = body[0]
    if not isinstance(stmt, ast.Return) or stmt.value is None:
      return None
    return stmt.value

  def _simple_self_field_method_return_parts(
    self,
    info: ClassInfo,
    method: ast.FunctionDef,
  ) -> tuple[str, str] | None:
    """推断 ``return self.field.method(...)`` 的返回类型。

    异步/生成器实现会产生宿主私有的 ``*_coroutine`` / ``*_generator`` 类型。
    标准库 Python 不应显式标注这些内部类型；薄 wrapper 由这里复用目标
    方法的已分析签名。
    """
    if method.returns is not None:
      return None
    expr = self._single_return_value(method)
    if not isinstance(expr, ast.Call):
      return None
    if not isinstance(expr.func, ast.Attribute):
      return None
    recv = expr.func.value
    if not (
      isinstance(recv, ast.Attribute)
      and isinstance(recv.value, ast.Name)
      and recv.value.id == "self"
    ):
      return None
    from .ir import class_info_for_cpp_type
    from .type_emit import field_storage_cpp

    field_t = field_storage_cpp(info, recv.attr)
    if not field_t:
      return None
    target_t = ClassInfo.unwrap_refcount_type(field_t)
    target = class_info_for_cpp_type(target_t, self._classes)
    if target is None:
      return None
    target_sig = target.method_sigs.get(expr.func.attr)
    if target_sig is None:
      target_method = target.methods.get(expr.func.attr)
      if target_method is None or (target is info and target_method is method):
        return None
      target_sig = self.build_method_sig(target, target_method)
      target.method_sigs[expr.func.attr] = target_sig
    return target_sig.ret_lead, target_sig.ret_trail

  def _storage_cpp_type(self, cpp_type: str) -> str:
    """``@refcount`` / ``@boxing`` 等在参数、局部、返回等处的一致命名。"""
    from .ir import cpp_fill_allocator_default_args

    cpp_type = cpp_fill_allocator_default_args(cpp_type)
    return ClassInfo.apply_refcount_storage_cpp_type(cpp_type, self._classes)

  def _decorator_constraints_for(
    self,
    info: ClassInfo | None,
    func_ft: FuncTypeParams | None = None,
  ) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    if info is not None:
      out.update(getattr(info, "type_param_decorator_constraints", {}))
    if func_ft is not None:
      out.update(getattr(func_ft, "decorator_constraints", {}))
    return out

  def _parse_ann_storage_type_node(
    self,
    ann: ast.expr | None,
    tparams: set[str],
    *,
    info: ClassInfo | None = None,
    func_ft: FuncTypeParams | None = None,
  ):
    """字段/形参注解 AST → 存储层 ``TypeNode``。"""
    if ann is None:
      from .type_node import TypeNode

      return TypeNode.void()
    from .ir import strip_type_annotation_markers
    from .proxy import entity_base_ast
    from .type_parse import parse_storage_type_node
    from .type_storage import apply_full_storage_type_node

    ann = strip_type_annotation_markers(ann)
    if (
      isinstance(ann, ast.Name)
      and ann.id == "Super"
      and info is not None
    ):
      base_ast = entity_base_ast(info)
      if base_ast is not None:
        ann = base_ast
    self_class = info.template_cpp_type() if info else None
    node = parse_storage_type_node(
      self._types,
      ann,
      tparams,
      decorator_constraints=self._decorator_constraints_for(info, func_ft),
      self_class=self_class,
    )
    return apply_full_storage_type_node(node, self._classes)

  def _parse_ann_storage_type(
    self,
    ann: ast.expr | None,
    tparams: set[str],
    *,
    info: ClassInfo | None = None,
    func_ft: FuncTypeParams | None = None,
  ) -> str:
    if ann is None:
      return "void"
    from .ir import strip_type_annotation_markers
    from .proxy import entity_base_ast

    ann = strip_type_annotation_markers(ann)
    if (
      isinstance(ann, ast.Name)
      and ann.id == "Super"
      and info is not None
    ):
      base_ast = entity_base_ast(info)
      if base_ast is not None:
        ann = base_ast
    self_class = info.template_cpp_type() if info else None
    cpp = self._types.parse_storage_type(
      ann,
      tparams,
      decorator_constraints=self._decorator_constraints_for(info, func_ft),
      self_class=self_class,
    )
    return self._storage_cpp_type(cpp)

  def _return_type_parts(
    self,
    func: ast.FunctionDef,
    func_ft: FuncTypeParams,
    extra_tparams: set[str],
    *,
    self_class: str | None = None,
    info: ClassInfo | None = None,
  ) -> tuple[str, str] | None:
    if is_void_return_annotation(func.returns):
      return "void", ""
    if func.returns is not None:
      return (
        self._storage_cpp_type(
          self._types.parse_storage_type(
            func.returns,
            extra_tparams,
            decorator_constraints=self._decorator_constraints_for(info, func_ft),
            self_class=self_class,
          ),
        ),
        "",
      )
    if not func_ft.template_names:
      return None
    expr = self._return_decltype_expr(func)
    if expr:
      return "auto", f" -> decltype({expr})"
    return None

  def _method_return_parts(self, info: ClassInfo, method: ast.FunctionDef) -> tuple[str, str]:
    func_ft = self._method_func_ft(info, method)
    tparams = set(info.type_params) | set(func_ft.template_names)
    if method.returns and isinstance(method.returns, ast.Name):
      if (
        method.returns.id in tparams
        and method.name not in ("__next__", "send", "__resume")
      ):
        dec = self._decorator_constraints_for(info, func_ft)
        if "refcount" in dec.get(method.returns.id, ()):
          rt = self._parse_ann_storage_type(
            method.returns, tparams, info=info, func_ft=func_ft,
          )
          if method.name in ("__enter__", "__iter__"):
            return f"{rt}&", ""
          return rt, ""
      cpp = resolve_host_cpp_type(method.returns.id, info.template_cpp_type())
      if cpp is not None:
        # ``Self`` / 同名宿主 → 与形参/字段一致走 ``@refcount`` 存储层（勿裸 ``T``）
        cpp = self._storage_cpp_type(cpp)
        if method.name in ("__enter__", "__iter__"):
          return f"{cpp}&", ""
        return cpp, ""
    if method.name == "__bool__":
      return cpp_ident("bool"), ""
    if method.name == "__cmp__":
      return cpp_ident("int"), ""
    if method.name in ("__len__", "_index"):
      return cpp_ident("int"), ""
    if method.name == "_advance" and method.returns is not None:
      rt = self._storage_cpp_type(
        self._types.parse_type(
          method.returns, tparams, self_class=info.template_cpp_type(),
        ),
      )
      if rt.startswith(CPP_RESULT_PREFIX):
        return rt, ""
      return cpp_result_type(rt), ""
    if method.name == "__getitem__" and info.name == "list" and info.type_params:
      if method.returns:
        rt = self._storage_cpp_type(
          self._types.parse_type(
            method.returns, tparams, self_class=info.template_cpp_type(),
          ),
        )
        if rt.startswith(CPP_LIST_PREFIX):
          return rt, ""
      return f"{info.type_params[0]}&", ""
    if method.name == "__getitem__" and info.name == "array" and info.type_params:
      return f"{info.type_params[0]}&", ""
    if method.name in IMPLICIT_VOID_DUNDER_METHODS:
      return "void", ""
    if method.returns and isinstance(method.returns, ast.Subscript):
      if isinstance(method.returns.value, ast.Name):
        from .stubs.protocol_erase_stubs import load_protocol_runtime_erase

        proto = method.returns.value.id
        match proto:
          case "Generator":
            if has_named_decorator(method, "virtual") or has_named_decorator(
              method, "override",
            ) or has_named_decorator(method, "abstract"):
              rt = self._parse_ann_storage_type(
                method.returns, tparams, info=info, func_ft=func_ft,
              )
              return rt, ""
            return cpp_ident(f"{info.name}_{method.name}_generator"), ""
          case "Coroutine":
            if has_named_decorator(method, "virtual") or has_named_decorator(
              method, "override",
            ) or has_named_decorator(method, "abstract"):
              rt = self._parse_ann_storage_type(
                method.returns, tparams, info=info, func_ft=func_ft,
              )
              return rt, ""
            return cpp_ident(f"{info.name}_{method.name}_coroutine"), ""
          case "AsyncGenerator":
            if has_named_decorator(method, "virtual") or has_named_decorator(
              method, "override",
            ) or has_named_decorator(method, "abstract"):
              rt = self._parse_ann_storage_type(
                method.returns, tparams, info=info, func_ft=func_ft,
              )
              return rt, ""
            return cpp_ident(f"{info.name}_{method.name}_coroutine"), ""
          case _:
            if proto in load_protocol_runtime_erase():
              rt = self._parse_ann_storage_type(
                method.returns, tparams, info=info, func_ft=func_ft,
              )
              return rt, ""
    if method.name in ("__next__", "send", "__resume") and not (
      method.name == "send" and info.is_native
    ):
      if method.returns:
        rt = self._storage_cpp_type(
          self._types.parse_type(
            method.returns, tparams, self_class=info.template_cpp_type(),
          ),
        )
        if rt.startswith(CPP_RESULT_PREFIX):
          return rt, ""
        return cpp_result_type(rt), ""
      if info.type_params:
        return cpp_result_type(info.type_params[0]), ""
      return cpp_result_type("void*"), ""
    if (
      info.name == "Task"
      and method.name == "run"
      and info.module_path.endswith("concur/task")
      and len(func_ft.template_names) >= 1
    ):
      coro = func_ft.template_names[0]
      return f"typename {coro}::ReturnType", ""
    inferred_forward = self._simple_self_field_method_return_parts(info, method)
    if inferred_forward is not None:
      return inferred_forward
    inferred = self._return_type_parts(
      method, func_ft, tparams, self_class=info.template_cpp_type(), info=info,
    )
    if inferred is not None:
      return inferred
    if method.returns is not None:
      rt = self._parse_ann_storage_type(
        method.returns, tparams, info=info, func_ft=func_ft,
      )
      return rt, ""
    if method.name == "__reversed__":
      hit = reversed_method_return_type(info)
      if hit is not None:
        return hit
    if method.name == "__iter__":
      hit = iter_method_return_type(info)
      if hit is not None:
        return hit
    return "void", ""

  def _format_method_params(
    self,
    info: ClassInfo,
    method: ast.FunctionDef,
    *,
    for_decl: bool,
    vararg_pack: "VarargPackInfo | None" = None,
    variadic_template: "VariadicTemplateInfo | None" = None,
  ) -> str:
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    func_ft = self._method_func_ft(info, method)
    eff = info.effective_type_params
    if variadic_template is None:
      variadic_template = resolve_variadic_template(
        method,
        class_type_params=eff,
        class_typevar_tuple=info.typevar_tuple,
      )
    if vararg_pack is None:
      vararg_pack = resolve_vararg_pack(
        self._types,
        method,
        class_type_params=eff,
        class_typevar_tuple=info.typevar_tuple,
        self_class=info.template_cpp_type(),
      )
    defaults = method.args.defaults
    num_defaults = len(defaults)
    args = method.args.args
    parts = []
    for i, arg in enumerate(args):
      if arg.arg in ("self", "cls"):
        continue
      t = self._param_cpp_type(
        arg, class_type_params=info.type_params, func_ft=func_ft, info=info, method=method,
      )
      by_ref = self._method_param_pass_by_ref(
        t, self._classes, info=info, method=method, arg_name=arg.arg,
      )
      if (
        method is not None
        and method.name == "__setitem__"
        and arg.arg not in ("self", "cls")
        and by_ref
      ):
        const_ref = True
      elif (
        info is not None
        and info.name == "list"
        and method.name in ("append", "insert", "_insert_new")
        and arg.arg == "item"
        and by_ref
      ):
        const_ref = True
      elif (
        info is not None
        and info.name == "ExceptionGroup"
        and method.name == "append"
        and arg.arg == "e"
        and by_ref
      ):
        const_ref = True
      elif (
        info is not None
        and info.name == "ExceptionGroup"
        and method.name == "assign"
        and arg.arg == "other"
        and by_ref
      ):
        const_ref = True
      else:
        if self._is_staticmethod_self_receiver(info, method, arg.arg):
          const_ref = has_named_decorator(method, "immutable")
        else:
          const_ref = (
            by_ref
            and has_named_decorator(method, "immutable")
            and arg.arg not in ("encoder", "decoder")
          )
      decl = self._format_param_decl(
        t,
        cpp_param(arg.arg),
        pass_by_ref=by_ref,
        const_ref=const_ref,
      )
      default_index = i - (len(args) - num_defaults)
      if for_decl and default_index >= 0 and default_index < num_defaults:
        from .lazy_param import is_lazy_type_annotation

        if is_lazy_type_annotation(arg.annotation):
          decl += f" = {t}{{}}"
        else:
          decl += f" = {self._default_cpp_arg(defaults[default_index], cpp_type=t, info=info)}"
      parts.append(decl)
    if variadic_template is not None:
      parts.append(
        f"{variadic_template.pack_name}... {cpp_param(variadic_template.param_name)}",
      )
    elif vararg_pack is not None:
      t = vararg_pack.cpp_type
      by_ref = self._method_param_pass_by_ref(
        t, self._classes, info=info, method=method, arg_name=vararg_pack.param_name,
      )
      decl = self._format_param_decl(
        t,
        cpp_param(vararg_pack.param_name),
        pass_by_ref=by_ref,
        const_ref=by_ref and has_named_decorator(method, "immutable"),
      )
      parts.append(decl)
    return ", ".join(parts)

  def _method_param_types(self, info: ClassInfo, method: ast.FunctionDef) -> dict[str, str]:
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    func_ft = self._method_func_ft(info, method)
    variadic_template = resolve_variadic_template(
      method,
      class_type_params=info.type_params,
      class_typevar_tuple=info.typevar_tuple,
    )
    vararg_pack = resolve_vararg_pack(
      self._types,
      method,
      class_type_params=info.type_params,
      class_typevar_tuple=info.typevar_tuple,
      self_class=info.template_cpp_type(),
    )
    out: dict[str, str] = {}
    for arg in method.args.args:
      if arg.arg in ("self", "cls"):
        continue
      out[arg.arg] = self._param_cpp_type(
        arg, class_type_params=info.type_params, func_ft=func_ft, info=info, method=method,
      )
    if variadic_template is not None:
      out[variadic_template.param_name] = (
        f"{variadic_template.pack_name}..."
      )
    elif vararg_pack is not None:
      out[vararg_pack.param_name] = vararg_pack.cpp_type
    return out

  def _property_getter_return(self, info: ClassInfo, method: ast.FunctionDef) -> tuple[str, str]:
    func_ft = self._method_func_ft(info, method)
    tparams = set(info.type_params) | set(func_ft.template_names)
    if method.returns:
      dec = self._decorator_constraints_for(info, func_ft)
      if isinstance(method.returns, ast.Name) and "refcount" in dec.get(
        method.returns.id, (),
      ):
        return self._parse_ann_storage_type(
          method.returns, tparams, info=info, func_ft=func_ft,
        ), ""
      return self._storage_cpp_type(
        self._types.parse_type(
          method.returns, tparams, self_class=info.template_cpp_type(),
        ),
      ), ""
    for stmt in ast.walk(method):
      if not isinstance(stmt, ast.Return) or stmt.value is None:
        continue
      match stmt.value:
        case ast.Attribute(value=ast.Name(id="self"), attr=field):
          from .type_emit import field_storage_cpp

          ft = field_storage_cpp(info, field)
          if ft:
            return ft, ""
        case ast.Name(id=name):
          from .type_emit import field_storage_cpp

          ft = field_storage_cpp(info, name)
          if ft:
            return ft, ""
    return "void", ""

  def build_static_property_getter_sig(self, info: ClassInfo, method: ast.FunctionDef) -> MethodSig:
    from .type_node import TypeNode

    func_ft = self._method_func_ft(info, method)
    ret_lead, ret_trail = self._property_getter_return(info, method)
    return_type_node = self._return_type_node_from_method(info, method, ret_lead)
    sig = MethodSig(
      func_ft=func_ft,
      ret_lead="",
      ret_trail=ret_trail,
      params_decl="",
      params_def="",
      param_types={},
      return_type_node=return_type_node,
      doc_lines=tuple(docstring_lines(method)),
      is_next=False,
      result_cpp_type=cpp_result_type("void*"),
    )
    from .type_emit import sync_sig_cache

    return sync_sig_cache(sig)

  def build_property_getter_sig(self, info: ClassInfo, method: ast.FunctionDef) -> MethodSig:
    from .type_node import TypeNode

    func_ft = self._method_func_ft(info, method)
    ret_lead, ret_trail = self._property_getter_return(info, method)
    return_type_node = self._return_type_node_from_method(info, method, ret_lead)
    sig = MethodSig(
      func_ft=func_ft,
      ret_lead="",
      ret_trail=ret_trail,
      params_decl="",
      params_def="",
      param_types={},
      return_type_node=return_type_node,
      doc_lines=tuple(docstring_lines(method)),
      is_next=False,
      result_cpp_type=cpp_result_type("void*"),
    )
    from .type_emit import sync_sig_cache

    return sync_sig_cache(sig)

  def build_property_setter_sig(self, info: ClassInfo, method: ast.FunctionDef) -> MethodSig:
    from .type_node import TypeNode

    func_ft = self._method_func_ft(info, method)
    sig = MethodSig(
      func_ft=func_ft,
      ret_lead="",
      ret_trail="",
      params_decl=self._format_method_params(info, method, for_decl=True),
      params_def=self._format_method_params(info, method, for_decl=False),
      param_types={},
      param_type_nodes=self._method_param_type_nodes(info, method),
      return_type_node=TypeNode.void(),
      doc_lines=tuple(docstring_lines(method)),
      is_next=False,
      result_cpp_type=cpp_result_type("void*"),
    )
    from .type_emit import sync_sig_cache

    return sync_sig_cache(sig)

  def build_method_sig(self, info: ClassInfo, method: ast.FunctionDef) -> MethodSig:
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    func_ft = self._method_func_ft(info, method)
    eff = info.effective_type_params
    variadic_template = resolve_variadic_template(
      method,
      class_type_params=eff,
      class_typevar_tuple=info.typevar_tuple,
    )
    vararg_pack = resolve_vararg_pack(
      self._types,
      method,
      class_type_params=eff,
      class_typevar_tuple=info.typevar_tuple,
      self_class=info.template_cpp_type(),
    )
    ret_lead, ret_trail = self._method_return_parts(info, method)
    ret_lead, ret_trail, is_noexcept, ok_cpp, err_cpp = self._wrap_noexcept_return(
      method, ret_lead, ret_trail,
    )
    is_next = method.name in ("__next__", "send", "__resume") and not (
      method.name == "send" and info.is_native
    )
    result_cpp_type = ret_lead if is_next else cpp_result_type("void*")
    sig = MethodSig(
      func_ft=func_ft,
      ret_lead="",
      ret_trail=ret_trail,
      params_decl=self._format_method_params(
        info,
        method,
        for_decl=True,
        vararg_pack=vararg_pack,
        variadic_template=variadic_template,
      ),
      params_def=self._format_method_params(
        info,
        method,
        for_decl=False,
        vararg_pack=vararg_pack,
        variadic_template=variadic_template,
      ),
      param_types={},
      param_type_nodes=self._method_param_type_nodes(info, method),
      return_type_node=self._return_type_node_from_method(info, method, ret_lead),
      doc_lines=tuple(docstring_lines(method)),
      is_next=is_next,
      result_cpp_type=result_cpp_type,
      vararg_pack=vararg_pack,
      variadic_template=variadic_template,
      is_const=has_named_decorator(method, "immutable"),
      is_static=has_named_decorator(method, "staticmethod"),
      is_abstract=has_named_decorator(method, "abstract"),
      is_virtual=has_named_decorator(method, "virtual")
      or has_named_decorator(method, "abstract"),
      is_override=has_named_decorator(method, "override"),
      is_final=has_named_decorator(method, "final"),
      is_noexcept=is_noexcept,
      noexcept_ok_cpp=ok_cpp,
      noexcept_err_cpp=err_cpp,
      lazy_params=self._collect_lazy_params(method, info=info),
    )
    from dataclasses import replace

    from .type_emit import sync_sig_cache

    return sync_sig_cache(sig)

  def function_return_parts(
    self, func: ast.FunctionDef, module_path: str = "",
  ) -> tuple[str, str]:
    func_ft = FuncTypeParams.collect(func)
    if func.name == "main":
      return cpp_ident("int"), ""
    if (
      func.name == "run"
      and module_path.endswith("/task")
      and len(func_ft.template_names) == 1
    ):
      coro = func_ft.template_names[0]
      return f"typename {coro}::ReturnType", ""
    if func.returns and isinstance(func.returns, ast.Subscript):
      if isinstance(func.returns.value, ast.Name):
        match func.returns.value.id:
          case "Generator":
            return cpp_ident(f"{func.name}_generator"), ""
          case "Coroutine":
            return cpp_ident(f"{func.name}_coroutine"), ""
          case "AsyncGenerator":
            return cpp_ident(f"{func.name}_coroutine"), ""
    inferred = self._return_type_parts(func, func_ft, set(func_ft.template_names))
    if inferred is not None:
      return inferred
    return "void", ""

  def _wrap_noexcept_return(
    self,
    func: ast.FunctionDef,
    ret_lead: str,
    ret_trail: str,
  ) -> tuple[str, str, bool, str, str]:
    """``@noexcept``：``-> T`` 对外 ``PyResult<T,E>``。"""
    if not has_named_decorator(func, "noexcept"):
      return ret_lead, ret_trail, False, "", ""
    from ..passes.noexcept_meta import collect_raise_exception_names, resolve_noexcept_err_type
    from .ir import cpp_fault_result_type, cpp_ident

    ok_cpp = cpp_ident("PyNone") if ret_lead == "void" else ret_lead
    err_cpp = resolve_noexcept_err_type(collect_raise_exception_names(func))
    result_cpp = cpp_fault_result_type(ok_cpp, err_cpp)
    return result_cpp, ret_trail, True, ok_cpp, err_cpp

  def format_function_params(
    self,
    func: ast.FunctionDef,
    *,
    vararg_pack: "VarargPackInfo | None" = None,
    variadic_template: "VariadicTemplateInfo | None" = None,
  ) -> tuple[str, dict[str, str]]:
    from .vararg_pack import VarargPackInfo, resolve_vararg_pack
    from .variadic_template import VariadicTemplateInfo, resolve_variadic_template

    func_ft = FuncTypeParams.collect(func)
    if variadic_template is None:
      variadic_template = resolve_variadic_template(func)
    if vararg_pack is None:
      vararg_pack = resolve_vararg_pack(self._types, func)
    defaults = func.args.defaults
    num_defaults = len(defaults)
    args = func.args.args
    parts = []
    param_types: dict[str, str] = {}
    for i, arg in enumerate(args):
      t = self._param_cpp_type(arg, class_type_params=[], func_ft=func_ft, method=func)
      param_types[arg.arg] = t
      decl = self._format_param_decl(
        t,
        cpp_param(arg.arg),
        ref_str=True,
        pass_by_ref=self._method_param_pass_by_ref(
          t, self._classes, method=func, arg_name=arg.arg,
        ),
      )
      default_index = i - (len(args) - num_defaults)
      if default_index >= 0 and default_index < num_defaults:
        from .lazy_param import is_lazy_type_annotation

        if is_lazy_type_annotation(arg.annotation):
          decl += f" = {t}{{}}"
        else:
          decl += f" = {self._default_cpp_arg(defaults[default_index], cpp_type=t)}"
      parts.append(decl)
    if variadic_template is not None:
      param_types[variadic_template.param_name] = (
        f"{variadic_template.pack_name}..."
      )
      parts.append(
        f"{variadic_template.pack_name}... "
        f"{cpp_param(variadic_template.param_name)}",
      )
    elif vararg_pack is not None:
      param_types[vararg_pack.param_name] = vararg_pack.cpp_type
      parts.append(
        self._format_param_decl(
          vararg_pack.cpp_type,
          cpp_param(vararg_pack.param_name),
          ref_str=True,
          pass_by_ref=self._method_param_pass_by_ref(
            vararg_pack.cpp_type,
            self._classes,
            method=func,
            arg_name=vararg_pack.param_name,
          ),
        )
      )
    return ", ".join(parts), param_types

  def build_function_sig(self, func: ast.FunctionDef, module_path: str = "") -> FunctionSig:
    from .imports import effective_module_type_aliases
    from .vararg_pack import resolve_vararg_pack
    from .variadic_template import resolve_variadic_template

    if module_path and self._types._tr is not None:
      tr = self._types._tr
      self._types.set_import_bindings(
        tr.module_import_bindings.get(module_path, {}),
      )
      self._types.set_type_aliases(
        effective_module_type_aliases(tr, module_path),
        use_as_cpp_name=False,
      )

    func_ft = FuncTypeParams.collect(func)
    variadic_template = resolve_variadic_template(func)
    vararg_pack = resolve_vararg_pack(self._types, func)
    ret_lead, ret_trail = self.function_return_parts(func, module_path)
    ret_lead, ret_trail, is_noexcept, ok_cpp, err_cpp = self._wrap_noexcept_return(
      func, ret_lead, ret_trail,
    )
    params, param_types = self.format_function_params(
      func, vararg_pack=vararg_pack, variadic_template=variadic_template,
    )
    sig = FunctionSig(
      func_ft=func_ft,
      ret_lead="",
      ret_trail=ret_trail,
      params=params,
      param_types={},
      param_type_nodes=self._function_param_type_nodes(func, module_path=module_path),
      return_type_node=self._return_type_node_from_function(func, ret_lead, module_path),
      doc_lines=tuple(docstring_lines(func)),
      vararg_pack=vararg_pack,
      variadic_template=variadic_template,
      is_noexcept=is_noexcept,
      noexcept_ok_cpp=ok_cpp,
      noexcept_err_cpp=err_cpp,
      lazy_params=self._collect_lazy_params(func),
    )
    from dataclasses import replace

    from .type_emit import sync_sig_cache

    return sync_sig_cache(sig)


def _headers_from_type_text(
  text: str,
  own_header: str,
  classes: dict,
) -> list[str]:
  from .type_deps import collect_type_header_deps

  return collect_type_header_deps(text, own_header, classes)


def finalize_module_headers(
  module_path: str,
  includes: list[str],
) -> tuple[list[str], list[str], list[str]]:
  return apply_header_fixups(module_path, includes)


def collect_type_texts_for_class(info: ClassInfo) -> list[str]:
  from .type_emit import collect_sig_type_texts, field_storage_cpp

  texts: list[str] = []
  for field in info.fields:
    if field.startswith("__ann__"):
      continue
    ft = field_storage_cpp(info, field)
    if ft:
      texts.append(ft)

  def _append_sig(sig: MethodSig | None) -> None:
    if sig is None:
      return
    texts.extend(collect_sig_type_texts(sig))

  for sig in info.method_sigs.values():
    _append_sig(sig)
  for sig in info.init_sigs:
    _append_sig(sig)
  for prop in info.properties.values():
    _append_sig(prop.getter_sig)
    _append_sig(prop.setter_sig)
    if prop.postsetter_sig:
      texts.extend(collect_sig_type_texts(prop.postsetter_sig))
  for prop in info.static_properties.values():
    _append_sig(prop.getter_sig)
  return texts


class SemanticAnalyzer:
  """一次遍历填充翻译器所需的全部预处理结果。"""

  def __init__(self):
    self.types = TypeParser()
    self.sigs = SignatureBuilder(self.types)

  def _inherited_field_names(self, info: ClassInfo, classes: dict[str, ClassInfo]) -> set[str]:
    """真实基类（含 MRO）上已声明的实例字段名。

    跳过 mixin / protocol / annotation：它们不占 C++ 存储，且常因方法体
    ``self.x = …`` 误收集同名字段；若当作「已继承」会误删宿主上带注解的字段
    （如 ``dict._buckets``）。
    """
    names: set[str] = set()
    seen: set[str] = set()
    stack = list(info.bases)
    while stack:
      base_name = stack.pop()
      if base_name in seen:
        continue
      seen.add(base_name)
      base = classes.get(base_name)
      if base is None:
        for cand in classes.values():
          if cand.name == base_name or cand.cpp_name() == base_name:
            base = cand
            break
      if base is None:
        continue
      stack.extend(base.bases)
      if base.is_mixin or base.is_annotation or base.is_protocol:
        continue
      names.update(base.fields)
      names.update(base.class_body_field_anns)
    return names

  def _drop_inherited_init_shadow_fields(self, tr) -> None:
    """子类 ``__init__`` 对基类字段赋值勿再声明同名字段（避免 ``void*`` 遮蔽）。"""
    for info in tr.classes.values():
      if not info.bases:
        continue
      inherited = self._inherited_field_names(info, tr.classes)
      if not inherited:
        continue
      kept: list[str] = []
      for field in info.fields:
        if field in inherited and field not in info.class_body_field_anns:
          info.field_type_nodes.pop(field, None)
          info.field_types.pop(field, None)
          info.field_defaults.pop(field, None)
          continue
        kept.append(field)
      info.fields = kept

  def analyze(self, tr):
    collect_entry_imports(tr)
    tr.type_parser = self.types
    self.types.set_translator(tr)
    tr.sigs = self.sigs
    self.types.set_import_bindings(tr.import_bindings)
    tr.delegates = {}
    for module_path in tr.module_order:
      tree = tr.module_asts.get(module_path)
      if tree is None:
        continue
      found = collect_delegates(
        module_path,
        tree,
        parse_type=lambda node, tp: self.types.parse_type(node, tp),
      )
      tr.delegates.update(found)
    tr.module_functions = [
      (mp, f) for mp, f in tr.module_functions if f.name not in tr.delegates
    ]
    self.types.set_delegate_names(frozenset(tr.delegates.keys()))
    from .ir import parse_type_alias_stmt
    from .imports import collect_all_imports, effective_module_type_aliases

    tr.module_analysis: dict[str, ModuleAnalysis] = {}
    for module_path in tr.module_order:
      tree = tr.module_asts.get(module_path)
      ma = ModuleAnalysis(path=module_path)
      if tree is not None:
        for stmt in tree.body:
          if isinstance(stmt, ast.TypeAlias):
            ma.type_aliases.append(parse_type_alias_stmt(stmt))
      tr.module_analysis[module_path] = ma

    collect_all_imports(tr)
    self.types.set_import_bindings(tr.import_bindings)
    tr.function_sigs: dict[tuple[str, str], FunctionSig] = {}
    tr.function_node_sigs: dict[int, FunctionSig] = {}
    tr.module_function_overload_sigs: dict[tuple[str, str], list[FunctionSig]] = {}

    for module_path in tr.module_order:
      tree = tr.module_asts.get(module_path)
      ma = tr.module_analysis[module_path]
      if tree is not None:
        ma.doc_lines = docstring_lines(tree)
        mod_bindings = tr.module_import_bindings.get(module_path, {})
        self.types.set_import_bindings(mod_bindings)
        self.types.set_type_aliases(
          effective_module_type_aliases(tr, module_path),
          use_as_cpp_name=False,
        )
        for alias in ma.type_aliases:
          if alias.is_conditional:
            from ..passes.type_conditional import plan_conditional_alias

            plan_conditional_alias(tr, alias)

    self.sigs.set_classes(tr.classes)
    self.types.set_classes(tr.classes)
    self.types.set_user_class_names(frozenset(tr.classes.keys()))
    self.sigs.set_lazy_param_defaults(getattr(tr, "lazy_param_default_exprs", {}))
    from ..passes.class_type_if import analyze_class_type_if_specs, plan_class_type_if

    for info in tr.classes.values():
      plan = plan_class_type_if(tr, info)
      if plan is not None:
        info.class_type_if_plan = plan
    for info in tr.classes.values():
      self.types.set_type_aliases(
        info.type_aliases,
        use_as_cpp_name=not info.is_protocol,
      )
      if info.is_descriptor or info.is_mixin or info.is_annotation or info.is_protocol:
        continue
      if info.name in TYPE_MARKER_CLASSES:
        continue
      if info.class_type_if_plan is not None:
        analyze_class_type_if_specs(self, tr, info)
        self.sigs.resolve_class_field_types(info)
        continue
      if info.is_boxing and info.is_refcount:
        raise ValueError(f"{info.name}: @boxing 与 @refcount 不能同时用于同一类")
      if info.is_boxing and info.is_copyable:
        raise ValueError(f"{info.name}: @boxing 与 @copyable 不能同时用于同一类")
      if info.is_copyable and info.is_uncopyable:
        raise ValueError(f"{info.name}: @copyable 与 @uncopyable 不能同时用于同一类")
      if info.is_uncopyable and "__copy__" in info.methods:
        raise ValueError(f"{info.name}: @uncopyable 类勿手写 ``__copy__``")
      self.sigs.resolve_class_field_types(info)
      info.init_sigs = [self.sigs.build_method_sig(info, init) for init in info.inits]
      if info.init_sigs and "__init__" not in info.method_sigs:
        info.method_sigs["__init__"] = info.init_sigs[-1]
      for name, overloads in info.method_overloads.items():
        if name != "__init__" and name in info.methods:
          raise ValueError(
            f"{info.name}.{name}: 同名重载须全部使用 @overload，"
            "不得再保留未标注的实现"
          )
        info.method_overload_sigs[name] = [
          self.sigs.build_method_sig(info, ov) for ov in overloads
        ]
      for method in info.methods.values():
        info.method_sigs[method.name] = self.sigs.build_method_sig(info, method)
      if info.repr_aliases_str:
        if "__str__" not in info.methods:
          raise ValueError(f"{info.name}: __repr__ = __str__ 需要类内定义 __str__")
        info.method_sigs["__repr__"] = info.method_sigs["__str__"]
      for prop in info.properties.values():
        if prop.setter:
          prop.setter_sig = self.sigs.build_property_setter_sig(info, prop.setter)
        if prop.postsetter:
          prop.postsetter_sig = self.sigs.build_property_setter_sig(info, prop.postsetter)
          prop.setter_sig = prop.postsetter_sig
        if prop.getter:
          prop.getter_sig = self.sigs.build_property_getter_sig(info, prop.getter)
        from .type_emit import method_param_storage_cpp, sig_return_storage_cpp, sync_sig_cache

        storage = storage_field_for(prop.name)
        value_t = (
          method_param_storage_cpp(prop.setter_sig, "value", fallback="")
          if prop.setter_sig
          else ""
        ) or None
        if value_t and storage in info.fields:
          self.sigs._set_field_cpp_type(info, storage, value_t)
        if (
          prop.getter_sig
          and sig_return_storage_cpp(prop.getter_sig) in ("void", "void*")
          and value_t
        ):
          from dataclasses import replace

          prop.getter_sig = sync_sig_cache(
            replace(
              prop.getter_sig,
              return_type_node=self.sigs._type_node_from_cpp(value_t),
            ),
          )
      for prop in info.static_properties.values():
        if prop.setter:
          prop.setter_sig = self.sigs.build_property_setter_sig(info, prop.setter)
        if prop.postsetter:
          prop.postsetter_sig = self.sigs.build_property_setter_sig(info, prop.postsetter)
          prop.setter_sig = prop.postsetter_sig
        if prop.getter:
          prop.getter_sig = self.sigs.build_static_property_getter_sig(info, prop.getter)
        from .type_emit import method_param_storage_cpp

        storage = storage_field_for(prop.name)
        value_t = (
          method_param_storage_cpp(prop.setter_sig, "value", fallback="")
          if prop.setter_sig
          else ""
        ) or None
        if value_t and storage in info.static_property_storage:
          from .ir import strip_cpp_ref, strip_cpp_type_qualifiers

          storage_t = strip_cpp_type_qualifiers(strip_cpp_ref(value_t))
          self.sigs._set_field_cpp_type(info, storage, storage_t)
      ensure_move_state_field(info)

    self._drop_inherited_init_shadow_fields(tr)

    from .module_functions import partition_module_functions_from_asts

    partition_module_functions_from_asts(
      tr,
      runtime_pkg=RUNTIME_PKG,
      builtins_runtime_funcs=BUILTINS_CPP_RUNTIME_FUNCS,
      translation_only_funcs=TRANSLATION_ONLY_FUNCS,
    )
    tr.module_functions = [
      (mp, f) for mp, f in tr.module_functions if f.name not in tr.delegates
    ]

    for (module_path, name), overloads in tr.module_function_overloads.items():
      if any(
        mp == module_path and f.name == name
        for mp, f in tr.module_functions
      ):
        raise ValueError(
          f"{module_path}.{name}: 同名重载须全部使用 @overload，"
          "不得再保留未标注的实现"
        )
      tr.module_function_overload_sigs[(module_path, name)] = [
        self.sigs.build_function_sig(ov, module_path) for ov in overloads
      ]
      for ov, sig in zip(overloads, tr.module_function_overload_sigs[(module_path, name)]):
        tr.function_node_sigs[id(ov)] = sig

    for module_path, func in tr.module_functions:
      if func.name in tr.delegates:
        continue
      sig = self.sigs.build_function_sig(func, module_path)
      tr.function_sigs[(module_path, func.name)] = sig
      tr.function_node_sigs[id(func)] = sig

    for module_path in tr.module_order:
      own_header = f"{module_path}.h"
      includes: list[str] = []
      for info in tr.classes.values():
        if (
          info.module_path != module_path
          or info.is_descriptor
          or info.is_mixin
          or info.is_annotation
          or info.is_protocol
          or info.name in TYPE_MARKER_CLASSES
        ):
          continue
        for text in collect_type_texts_for_class(info):
          for h in _headers_from_type_text(text, own_header, tr.classes):
            if h not in includes:
              includes.append(h)
      from .type_emit import collect_sig_type_texts

      for (mp, name), fsig in tr.function_sigs.items():
        if mp != module_path:
          continue
        for text in collect_sig_type_texts(fsig):
          for h in _headers_from_type_text(text, own_header, tr.classes):
            if h not in includes:
              includes.append(h)
      for (mp, _name), sigs in tr.module_function_overload_sigs.items():
        if mp != module_path:
          continue
        for fsig in sigs:
          for text in collect_sig_type_texts(fsig):
            for h in _headers_from_type_text(text, own_header, tr.classes):
              if h not in includes:
                includes.append(h)
      _protocol_traits_h = f"{CORE_PKG}/protocol_traits.h"
      if module_path != stdlib_module_path("core/protocols"):
        for info in tr.classes.values():
          if info.module_path != module_path or info.is_protocol:
            continue
          if info.type_param_constraints or info.type_param_oneof_constraints or info.concrete_oneof_constraints:
            if _protocol_traits_h not in includes:
              includes.insert(0, _protocol_traits_h)
            break
      _delegate_h = stdlib_header_include("core/delegate")
      if any(d.module_path == module_path for d in tr.delegates.values()):
        if _delegate_h not in includes:
          includes.insert(0, _delegate_h)
      from .type_deps import header_for_module
      from .import_resolver import is_runtime_module_path
      from ..constant.ffi_layout import ffi_header_include, is_ffi_module_path

      for imp in tr.module_import_bindings.get(module_path, {}).values():
        if not imp.module_path or imp.module_path == module_path:
          continue
        if is_ffi_module_path(imp.module_path):
          h = ffi_header_include(imp.module_path)
          if h not in includes:
            includes.append(h)
          continue
        if is_runtime_module_path(imp.module_path):
          # stdlib 仍靠类型文本推导，避免函数 import 拉满头文件环。
          if imp.kind == "delegate":
            h = header_for_module(imp.module_path)
            if h != own_header and h not in includes:
              includes.append(h)
          continue
        # 用户工程：仅函数符号的跨模块 import 也须 #include 对端头。
        h = header_for_module(imp.module_path)
        if h != own_header and h not in includes:
          includes.append(h)
      pre, forward, post = finalize_module_headers(module_path, includes)
      ma = tr.module_analysis[module_path]
      ma.includes = pre
      ma.forward_decls = forward
      ma.post_class_includes = post

    from .header_usings import build_header_usings_index

    tr.header_usings_index = build_header_usings_index(tr.classes)
