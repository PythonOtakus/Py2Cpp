"""TypeNode 存储层变换：``@boxing`` / ``@refcount`` / 容器内层递归。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .ir import (
  CPP_ARRAY2D_PREFIX,
  CPP_ARRAY3D_PREFIX,
  CPP_ARRAY_PREFIX,
  CPP_DEQUE_PREFIX,
  CPP_LIST_PREFIX,
  ClassInfo,
)
from .type_node import TypeKind, TypeNode

if TYPE_CHECKING:
  from .ir import ClassInfo as ClassInfoType


def _class_for_template_node(
  node: TypeNode,
  classes: dict[str, ClassInfoType],
) -> ClassInfoType | None:
  if node.kind != TypeKind.TEMPLATE:
    return None
  if node.py_name:
    info = classes.get(node.py_name)
    if info is not None:
      return info
  for info in classes.values():
    if info.cpp_name() == node.name:
      return info
  return None


def _apply_boxing(node: TypeNode, classes: dict[str, ClassInfoType]) -> TypeNode:
  if node.kind == TypeKind.POINTER:
    assert node.inner is not None
    return TypeNode.pointer(_apply_boxing(node.inner, classes))

  if node.kind == TypeKind.ARRAY:
    assert node.inner is not None
    return TypeNode.array(
      _apply_boxing(node.inner, classes),
      kind=node.array_kind,
      cpp_base=node.name,
    )

  if node.kind == TypeKind.TEMPLATE:
    rebuilt = TypeNode.template(
      node.py_name,
      node.name,
      *(_apply_boxing(a, classes) for a in node.args),
    )
    info = _class_for_template_node(node, classes)
    if info is not None and info.is_boxing:
      return TypeNode.pointer(rebuilt)
    list_bare = CPP_LIST_PREFIX.rstrip("<")
    deque_bare = CPP_DEQUE_PREFIX.rstrip("<")
    if node.name in (list_bare, deque_bare):
      return TypeNode.template(
        node.py_name,
        node.name,
        *(_apply_boxing(a, classes) for a in rebuilt.args),
      )
    return rebuilt

  if node.kind == TypeKind.SCALAR:
    for info in classes.values():
      if info.is_boxing and info.cpp_name() == node.name:
        return TypeNode.pointer(TypeNode.scalar(node.name))

  return node


def apply_storage_type_node(
  node: TypeNode,
  classes: dict[str, ClassInfoType],
) -> TypeNode:
  """``@boxing`` 树变换（按 ``ClassInfo`` 身份，与形参 spellings 无关）。"""
  return _apply_boxing(node, classes)


def apply_refcount_storage_type_node(
  node: TypeNode,
  classes: dict[str, ClassInfoType],
) -> TypeNode:
  """``@refcount`` 树变换（与 ``ClassInfo.apply_refcount_storage_cpp_type`` 对齐）。"""
  from .ir import (
    CPP_DEQUE_PREFIX,
    CPP_DICT_PREFIX,
    CPP_FROZENDICT_PREFIX,
    CPP_FROZENLIST_PREFIX,
    CPP_FROZENSET_PREFIX,
    CPP_LIST_PREFIX,
    CPP_REFCount_PREFIX,
    CPP_SET_PREFIX,
    CPP_TUPLE_PREFIX,
    cpp_refcount_type,
  )
  from .type_pred import is_refcount_type
  from .type_render import CLASS_BODY

  cpp = node.render(CLASS_BODY)
  if is_refcount_type(cpp):
    return node

  list_bare = CPP_LIST_PREFIX.rstrip("<")
  deque_bare = CPP_DEQUE_PREFIX.rstrip("<")
  set_bare = CPP_SET_PREFIX.rstrip("<")
  frozenset_bare = CPP_FROZENSET_PREFIX.rstrip("<")
  frozenlist_bare = CPP_FROZENLIST_PREFIX.rstrip("<")
  dict_bare = CPP_DICT_PREFIX.rstrip("<")
  frozendict_bare = CPP_FROZENDICT_PREFIX.rstrip("<")
  tuple_bare = CPP_TUPLE_PREFIX.rstrip("<")

  if node.kind == TypeKind.SCALAR:
    for info in classes.values():
      if not info.is_refcount:
        continue
      bare = info.cpp_name()
      if node.name == bare or node.name == info.storage_cpp_type():
        from .type_compat import type_node_from_cpp_string

        return type_node_from_cpp_string(info.storage_cpp_type(), classes=classes)
    return node

  if node.kind == TypeKind.TEMPLATE and node.name in (
    list_bare,
    deque_bare,
    set_bare,
    frozenset_bare,
    frozenlist_bare,
    dict_bare,
    frozendict_bare,
    tuple_bare,
  ):
    new_args = tuple(
      apply_refcount_storage_type_node(a, classes) for a in node.args
    )
    if new_args != node.args:
      return TypeNode.template(node.py_name, node.name, *new_args)
    return node

  if node.kind == TypeKind.TEMPLATE:
    info = _class_for_template_node(node, classes)
    if info is not None and info.is_refcount:
      bare = info.cpp_name()
      if node.name == bare and node.args:
        return TypeNode.refcount(TypeNode.template(node.py_name, bare, *node.args))
      if node.name == bare or cpp == bare or cpp == info.storage_cpp_type():
        inner_name = info.storage_cpp_type()
        if inner_name.startswith(CPP_REFCount_PREFIX.rstrip("<")):
          from .type_compat import type_node_from_cpp_string

          return type_node_from_cpp_string(inner_name, classes=classes)
        return TypeNode.refcount(
          TypeNode.template(node.py_name, bare, *node.args) if node.args else TypeNode.scalar(bare),
        )
      if cpp.startswith(f"{bare}<") and cpp.endswith(">"):
        from .type_compat import type_node_from_cpp_string

        return type_node_from_cpp_string(cpp_refcount_type(cpp), classes=classes)

  return node


def apply_full_storage_type_node(
  node: TypeNode,
  classes: dict[str, ClassInfoType],
) -> TypeNode:
  """完整 storage：``@boxing`` + ``@refcount``（Phase 18：全程 TypeNode）。"""
  return apply_refcount_storage_type_node(
    apply_storage_type_node(node, classes),
    classes,
  )
