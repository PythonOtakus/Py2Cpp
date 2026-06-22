"""AST 类型注解 → TypeNode（语义层；存储层见 ``type_storage``）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .type_node import TypeKind, TypeNode
from .type_parse_ast import _UseCppStringBridge, parse_type_node_direct, parse_type_node_with_bridge

if TYPE_CHECKING:
  from .analyzer import TypeParser


def parse_type_node(
  parser: TypeParser,
  node: ast.expr | None,
  type_params: set[str],
  *,
  self_class: str | None = None,
  typevar_tuple_names: frozenset[str] | None = None,
) -> TypeNode:
  """``TypeParser.parse_type`` 的 TypeNode 形式（Phase 18：优先 AST 直 lower）。"""
  return parse_type_node_with_bridge(
    parser,
    node,
    type_params,
    self_class=self_class,
    typevar_tuple_names=typevar_tuple_names,
  )


def _parse_storage_via_cpp_bridge(
  parser: TypeParser,
  node: ast.expr | None,
  type_params: set[str],
  *,
  decorator_constraints: dict[str, tuple[str, ...]] | None,
  self_class: str | None,
  typevar_tuple_names: frozenset[str] | None,
) -> TypeNode:
  from .type_compat import type_node_from_cpp_string

  cpp = parser.parse_storage_type(
    node,
    type_params,
    decorator_constraints=decorator_constraints,
    self_class=self_class,
    typevar_tuple_names=typevar_tuple_names,
  )
  return type_node_from_cpp_string(cpp, classes=parser._classes)


def _storage_needs_cpp_bridge(
  parser: TypeParser,
  node: ast.expr | None,
  dec: dict[str, tuple[str, ...]],
  *,
  type_params: set[str],
  self_class: str | None,
) -> bool:
  if node is None:
    return False
  if isinstance(node, ast.Subscript):
    if parser._try_parse_slice_array_type(node, type_params, self_class=self_class):
      return True
    if isinstance(node.value, ast.Name):
      name = node.value.id
      if name in ("WeakRef", "RefCount", "Generator", "Coroutine", "AsyncGenerator"):
        return True
      if name in parser._type_aliases:
        ali = parser._type_aliases[name]
        if ali.is_conditional and parser._tr is not None:
          return True
      imp = parser._import_bindings.get(name)
      if imp is not None and imp.kind == "type_alias" and name not in parser._type_aliases:
        return True
  if isinstance(node, ast.Attribute):
    return True
  if isinstance(node, ast.Constant) and not (
    isinstance(node.value, type(None))
  ):
    return True
  if isinstance(node, ast.UnaryOp):
    return True
  return False


def parse_storage_type_node(
  parser: TypeParser,
  node: ast.expr | None,
  type_params: set[str],
  *,
  decorator_constraints: dict[str, tuple[str, ...]] | None = None,
  self_class: str | None = None,
  typevar_tuple_names: frozenset[str] | None = None,
) -> TypeNode:
  """``TypeParser.parse_storage_type`` 的 TypeNode 形式（Phase 18：node 存储变换）。"""
  from .ir import cpp_ident
  from .type_pred import is_refcount_type
  from .type_render import CLASS_BODY
  from .type_storage import apply_refcount_storage_type_node

  dec = decorator_constraints or {}
  if node is None:
    return TypeNode.void()
  if _storage_needs_cpp_bridge(
    parser, node, dec, type_params=type_params, self_class=self_class,
  ):
    return _parse_storage_via_cpp_bridge(
      parser, node, type_params,
      decorator_constraints=dec,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )
  if (
    isinstance(node, ast.BinOp)
    and isinstance(node.op, ast.BitOr)
    and isinstance(node.right, ast.Constant)
    and node.right.value is None
  ):
    inner = parse_storage_type_node(
      parser,
      node.left,
      type_params,
      decorator_constraints=dec,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )
    stored = apply_refcount_storage_type_node(inner, parser._classes)
    if is_refcount_type(stored.render(CLASS_BODY)):
      return stored
    return TypeNode.optional(stored)
  if isinstance(node, ast.Tuple):
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
    if not node.elts:
      return TypeNode.template("tuple", cpp_ident("tuple"))
    args = tuple(
      parse_storage_type_node(
        parser, e, type_params,
        decorator_constraints=dec, self_class=self_class,
        typevar_tuple_names=typevar_tuple_names,
      )
      for e in node.elts
    )
    return TypeNode.template("tuple", cpp_ident("tuple"), *args)
  if isinstance(node, ast.Name):
    if node.id == "Self" and self_class:
      from .type_compat import type_node_from_cpp_string

      host = type_node_from_cpp_string(self_class, classes=parser._classes)
      return apply_refcount_storage_type_node(host, parser._classes)
    if parser._has_refcount_decorator_constraint(node.id, dec):
      return TypeNode.type_param(node.id)
    if parser._has_boxing_decorator_constraint(node.id, dec):
      return TypeNode.type_param(node.id)
  if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
    name = node.value.id
    if parser._maps_to_runtime_protocol_erase(name):
      sl = node.slice
      if isinstance(sl, ast.Tuple):
        args = tuple(
          parse_storage_type_node(
            parser, e, type_params,
            decorator_constraints=dec, self_class=self_class,
          )
          for e in sl.elts
        )
      else:
        args = (
          parse_storage_type_node(
            parser, sl, type_params,
            decorator_constraints=dec, self_class=self_class,
          ),
        )
      from .stubs.protocol_erase_stubs import erased_protocol_cpp_name

      return TypeNode.template(name, erased_protocol_cpp_name(name), *args)
    if name in (
      "list", "dict", "set", "frozenset", "deque", "frozenlist", "frozendict",
    ):
      sl = node.slice
      if isinstance(sl, ast.Tuple):
        args = tuple(
          parse_storage_type_node(
            parser, e, type_params,
            decorator_constraints=dec, self_class=self_class,
          )
          for e in sl.elts
        )
      else:
        args = (
          parse_storage_type_node(
            parser, sl, type_params,
            decorator_constraints=dec, self_class=self_class,
          ),
        )
      return apply_refcount_storage_type_node(
        TypeNode.template(name, cpp_ident(name), *args),
        parser._classes,
      )
  try:
    semantic = parse_type_node_direct(
      parser, node, type_params,
      self_class=self_class, typevar_tuple_names=typevar_tuple_names,
    )
    return apply_refcount_storage_type_node(semantic, parser._classes)
  except _UseCppStringBridge:
    return _parse_storage_via_cpp_bridge(
      parser, node, type_params,
      decorator_constraints=dec,
      self_class=self_class,
      typevar_tuple_names=typevar_tuple_names,
    )
