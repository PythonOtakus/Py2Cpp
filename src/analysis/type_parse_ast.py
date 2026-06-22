"""AST 类型注解 → TypeNode（直 lower；复杂形态回退 C++ 字符串桥接）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .ir import cpp_ident, resolve_host_cpp_type
from .type_node import TypeKind, TypeNode

if TYPE_CHECKING:
  from .analyzer import TypeParser


class _UseCppStringBridge(Exception):
  """当前 AST 形态尚无 TypeNode lower，回退 ``parse_type`` + ``from_cpp_string``。"""


def _bind_self_if_needed(
  node: ast.expr,
  tn: TypeNode,
  *,
  self_class: str | None,
  classes: dict,
) -> TypeNode:
  if not isinstance(node, ast.Name) or node.id != "Self" or not self_class:
    return tn
  from .type_compat import type_node_from_cpp_string

  host = type_node_from_cpp_string(self_class, classes=classes)
  if tn.kind == TypeKind.TYPE_PARAM or (
    tn.kind == TypeKind.TEMPLATE and host.kind == TypeKind.TEMPLATE and tn.name == host.name
  ):
    return host
  if tn.kind == TypeKind.SELF:
    return host
  return tn


def _parse_type_args_nodes(
  parser: TypeParser,
  slice_node: ast.expr,
  type_params: set[str],
  *,
  self_class: str | None,
  typevar_tuple_names: frozenset[str] | None,
) -> tuple[TypeNode, ...]:
  match slice_node:
    case ast.Tuple(elts=elts):
      return tuple(
        parse_type_node_direct(
          parser, e, type_params,
          self_class=self_class, typevar_tuple_names=typevar_tuple_names,
        )
        for e in elts
      )
    case _:
      return (
        parse_type_node_direct(
          parser, slice_node, type_params,
          self_class=self_class, typevar_tuple_names=typevar_tuple_names,
        ),
      )


def _template_from_py_name(
  parser: TypeParser,
  py_name: str,
  cpp_base: str,
  args: tuple[TypeNode, ...],
) -> TypeNode:
  return TypeNode.template(py_name, cpp_base, *args)


def _parse_name_node(
  parser: TypeParser,
  name: str,
  type_params: set[str],
  *,
  self_class: str | None,
  alias_seen: frozenset[str] | None,
) -> TypeNode:
  if name == "Self":
    return TypeNode.self_ref()
  resolved = resolve_host_cpp_type(name, self_class)
  if resolved is not None:
    from .type_compat import type_node_from_cpp_string

    return type_node_from_cpp_string(resolved, classes=parser._classes)
  if name in type_params:
    return TypeNode.type_param(name)
  from .stubs.protocol_erase_stubs import erased_protocol_cpp_name

  if parser._maps_to_runtime_protocol_erase(name):
    return TypeNode.template(name, erased_protocol_cpp_name(name))
  scalars = {
    "int", "int64", "uint", "uint64", "uintptr", "float", "float64", "bool",
    "str", "bytes", "char", "byte", "object", "RefCount", "IterResult", "Result",
    "Optional", "Generator", "Coroutine", "AsyncGenerator", "Awaitable",
    "AsyncIterable", "AsyncIterator", "ContextManager", "AsyncContextManager",
    "PyNone", "void", "Never",
  }
  if name in scalars:
    return TypeNode.scalar(cpp_ident(name))
  if name == "None":
    return TypeNode.scalar(cpp_ident("PyNone"))
  if name == "c_str":
    return TypeNode.scalar("c_str")
  expanded = parser._expand_type_alias_name(
    name, type_params, self_class=self_class, _seen=alias_seen,
  )
  if expanded is not None:
    from .type_compat import type_node_from_cpp_string

    return type_node_from_cpp_string(expanded, classes=parser._classes)
  imp = parser._import_bindings.get(name)
  if imp is not None and imp.kind in ("class", "delegate"):
    info = parser._classes.get(name)
    if info is not None and info.type_params and not info.typevar_tuple:
      defaults = info.type_param_defaults
      if defaults and len(defaults) == len(info.type_params):
        args = tuple(
          parse_type_node_direct(
            parser, defaults[p], type_params, self_class=self_class,
          )
          for p in info.type_params
        )
        return TypeNode.template(name, info.cpp_name(), *args)
    return TypeNode.scalar(imp.cpp_name)
  if name == "Object" and name not in parser._user_class_names:
    if imp is None or imp.kind != "class":
      raise NotImplementedError(
        "类型注解 Object 已禁止，请改用 object（映射 PyObject）"
      )
  info = parser._classes.get(name)
  if info is not None and info.type_params and not info.typevar_tuple:
    defaults = info.type_param_defaults
    if defaults and len(defaults) == len(info.type_params):
      args = tuple(
        parse_type_node_direct(
          parser, defaults[p], type_params, self_class=self_class,
        )
        for p in info.type_params
      )
      return TypeNode.template(name, info.cpp_name(), *args)
  return TypeNode.scalar(cpp_ident(name))


def _parse_callable_subscript_nodes(
  parser: TypeParser,
  node: ast.Subscript,
  type_params: set[str],
  *,
  self_class: str | None,
  typevar_tuple_names: frozenset[str] | None,
) -> tuple[tuple[TypeNode, ...], TypeNode] | None:
  sl = node.slice
  if not isinstance(sl, ast.Tuple) or len(sl.elts) != 2:
    return None
  args_node, ret_node = sl.elts
  if isinstance(args_node, (ast.Tuple, ast.List)):
    arg_types = tuple(
      parse_type_node_direct(
        parser, e, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      for e in args_node.elts
    )
  else:
    arg_types = (
      parse_type_node_direct(
        parser, args_node, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      ),
    )
  ret = parse_type_node_direct(
    parser, ret_node, type_params,
    self_class=self_class, typevar_tuple_names=typevar_tuple_names,
  )
  return arg_types, ret


def _parse_subscript_node(
  parser: TypeParser,
  node: ast.Subscript,
  type_params: set[str],
  *,
  self_class: str | None,
  typevar_tuple_names: frozenset[str] | None,
) -> TypeNode:
  from .variadic_template import (
    cpp_typevar_tuple_as_pytuple,
    typevar_tuple_pack_from_type_node,
  )

  if typevar_tuple_names:
    pack = typevar_tuple_pack_from_type_node(node, typevar_tuple_names)
    if pack is not None:
      from .type_compat import type_node_from_cpp_string

      return type_node_from_cpp_string(
        cpp_typevar_tuple_as_pytuple(pack), classes=parser._classes,
      )
  if parser._try_parse_slice_array_type(node, type_params, self_class=self_class):
    raise _UseCppStringBridge()
  if isinstance(node.value, ast.Name) and node.value.id == "Function":
    parsed = _parse_callable_subscript_nodes(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    if parsed is None:
      raise _UseCppStringBridge()
    arg_types, ret = parsed
    return TypeNode.function_ptr(ret, *arg_types)
  if isinstance(node.value, ast.Name) and node.value.id == "Callable":
    parsed = _parse_callable_subscript_nodes(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    if parsed is None:
      raise _UseCppStringBridge()
    arg_types, ret = parsed
    return TypeNode.template("Callable", "PyCallable", ret, *arg_types)
  if isinstance(node.value, ast.Name) and node.value.id == "Pointer":
    inner = parse_type_node_direct(
      parser, node.slice, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    return TypeNode.pointer(inner)
  if isinstance(node.value, ast.Name) and node.value.id == "slice":
    raise _UseCppStringBridge()
  if isinstance(node.value, ast.Name) and node.value.id in parser._type_aliases:
    ali = parser._type_aliases[node.value.id]
    if ali.is_conditional and parser._tr is not None and not parser._alias_use_cpp_name:
      raise _UseCppStringBridge()
    if ali.type_params:
      args = _parse_type_args_nodes(
        parser, node.slice, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      return TypeNode.template(node.value.id, node.value.id, *args)
  if isinstance(node.value, ast.Name):
    spec = parser._try_specialize_class_type(
      node.value.id, node.slice, type_params, self_class=self_class,
    )
    if spec is not None:
      from .type_compat import type_node_from_cpp_string

      return type_node_from_cpp_string(spec, classes=parser._classes)
  if isinstance(node.value, ast.Name) and node.value.id in (
    "IterResult", "Result", "WeakRef", "Generator", "Coroutine", "AsyncGenerator",
  ):
    raise _UseCppStringBridge()
  if isinstance(node.value, ast.Name):
    resolved = resolve_host_cpp_type(node.value.id, self_class)
    if resolved is not None:
      base = resolved.partition("<")[0].strip()
      args = _parse_type_args_nodes(
        parser, node.slice, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      return TypeNode.template(node.value.id, base, *args)
  match node:
    case ast.Subscript(value=ast.Name(id=name), slice=sl) if name in parser._delegate_names:
      base = cpp_ident(name)
      imp = parser._import_bindings.get(name)
      if imp is not None and imp.kind == "delegate":
        base = imp.cpp_name
      args = _parse_type_args_nodes(
        parser, sl, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      return TypeNode.template(name, base, *args)
    case ast.Subscript(value=ast.Name(id=name), slice=sl):
      spec = parser._try_specialize_class_type(
        name, sl, type_params, self_class=self_class,
      )
      if spec is not None:
        from .type_compat import type_node_from_cpp_string

        return type_node_from_cpp_string(spec, classes=parser._classes)
      base = _parse_name_node(
        parser, name, type_params, self_class=self_class, alias_seen=None,
      )
      args = _parse_type_args_nodes(
        parser, sl, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      if base.kind in (TypeKind.SCALAR, TypeKind.TEMPLATE, TypeKind.TYPE_PARAM):
        cpp_base = base.name
      else:
        from .type_render import CLASS_BODY

        cpp_base = base.render(CLASS_BODY)
      return TypeNode.template(name, cpp_base, *args)
    case ast.Subscript(value=value, slice=sl):
      base = parse_type_node_direct(
        parser, value, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      args = _parse_type_args_nodes(
        parser, sl, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      py = base.py_name or base.name
      cpp_base = base.name if base.name else py
      return TypeNode.template(py, cpp_base, *args)
  raise _UseCppStringBridge()


def _parse_tuple_shorthand_node(
  parser: TypeParser,
  node: ast.Tuple,
  type_params: set[str],
  *,
  self_class: str | None,
  typevar_tuple_names: frozenset[str] | None,
) -> TypeNode:
  from .variadic_template import (
    cpp_typevar_tuple_as_pytuple,
    typevar_tuple_pack_from_type_node,
  )

  if typevar_tuple_names:
    pack = typevar_tuple_pack_from_type_node(node, typevar_tuple_names)
    if pack is not None:
      from .type_compat import type_node_from_cpp_string

      return type_node_from_cpp_string(
        cpp_typevar_tuple_as_pytuple(pack), classes=parser._classes,
      )
  if any(isinstance(e, ast.Starred) for e in node.elts):
    raise NotImplementedError(
      "元组类型注解中 ``*Pack`` 仅支持单元素 ``(*Ts,)``（形参包对应 ``PyTuple<Ts...>``）",
    )
  if not node.elts:
    return TypeNode.template("tuple", cpp_ident("tuple"))
  args = tuple(
    parse_type_node_direct(
      parser, e, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    for e in node.elts
  )
  return TypeNode.template("tuple", cpp_ident("tuple"), *args)


def parse_type_node_direct(
  parser: TypeParser,
  node: ast.expr | None,
  type_params: set[str],
  *,
  self_class: str | None = None,
  typevar_tuple_names: frozenset[str] | None = None,
  alias_seen: frozenset[str] | None = None,
) -> TypeNode:
  """AST → TypeNode；无法 lower 时抛 ``_UseCppStringBridge``。"""
  if node is None:
    return TypeNode.void()
  if isinstance(node, ast.Tuple):
    return _parse_tuple_shorthand_node(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
  if isinstance(node, ast.Subscript):
    return _parse_subscript_node(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
  match node:
    case ast.Name(id=name):
      tn = _parse_name_node(
        parser, name, type_params,
        self_class=self_class, alias_seen=alias_seen,
      )
      return _bind_self_if_needed(
        node, tn, self_class=self_class, classes=parser._classes,
      )
    case ast.BinOp(left=left, op=ast.BitOr(), right=ast.Constant(value=None)):
      inner = parse_type_node_direct(
        parser, left, type_params,
        self_class=self_class, typevar_tuple_names=typevar_tuple_names,
      )
      return TypeNode.optional(inner)
    case ast.BinOp(op=ast.MatMult()):
      from .lazy_param import is_lazy_type_annotation

      if is_lazy_type_annotation(node):
        return parse_type_node_direct(
          parser, node.left, type_params,
          self_class=self_class, typevar_tuple_names=typevar_tuple_names,
        )
      raise _UseCppStringBridge()
    case ast.Attribute() | ast.Constant() | ast.UnaryOp():
      raise _UseCppStringBridge()
    case _:
      return TypeNode.void()


def parse_type_node_with_bridge(
  parser: TypeParser,
  node: ast.expr | None,
  type_params: set[str],
  *,
  self_class: str | None = None,
  typevar_tuple_names: frozenset[str] | None = None,
) -> TypeNode:
  """直 lower；失败时 ``parse_type`` + ``from_cpp_string``。"""
  from .type_compat import type_node_from_cpp_string

  try:
    return parse_type_node_direct(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
  except _UseCppStringBridge:
    cpp = parser.parse_type(
      node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    tn = type_node_from_cpp_string(cpp, classes=parser._classes)
    if node is not None:
      tn = _bind_self_if_needed(
        node, tn, self_class=self_class, classes=parser._classes,
      )
    return tn
