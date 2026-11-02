"""编译期结构化类型 IR（TypeNode）。

语义层类型表达式；存储变换见 ``type_storage``；渲染见 ``type_render``。
自 C++ 字符串反解析见 ``type_compat.type_node_from_cpp_string``。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import TYPE_CHECKING

from .ir import cpp_type_param_template_name

if TYPE_CHECKING:
  from .type_render import NamingPolicy


class TypeKind(Enum):
  VOID = auto()
  NEVER = auto()
  SCALAR = auto()
  TYPE_PARAM = auto()
  SELF = auto()
  TEMPLATE = auto()
  POINTER = auto()
  OPTIONAL = auto()
  REF = auto()
  REFCOUNT = auto()
  ARRAY = auto()
  FUNCTION_PTR = auto()


@dataclass(frozen=True)
class TypeNode:
  kind: TypeKind
  name: str = ""
  py_name: str = ""
  args: tuple[TypeNode, ...] = ()
  inner: TypeNode | None = None
  array_kind: str = "heap"

  @staticmethod
  def void() -> TypeNode:
    return TypeNode(TypeKind.VOID, name="void")

  @staticmethod
  def never(cpp_name: str = "PyNever") -> TypeNode:
    return TypeNode(TypeKind.NEVER, name=cpp_name)

  @staticmethod
  def scalar(cpp_name: str) -> TypeNode:
    return TypeNode(TypeKind.SCALAR, name=cpp_name)

  @staticmethod
  def type_param(name: str) -> TypeNode:
    return TypeNode(TypeKind.TYPE_PARAM, name=name)

  @staticmethod
  def self_ref() -> TypeNode:
    return TypeNode(TypeKind.SELF)

  @staticmethod
  def template(
    py_name: str,
    cpp_name: str,
    *args: TypeNode,
  ) -> TypeNode:
    return TypeNode(
      TypeKind.TEMPLATE,
      name=cpp_name,
      py_name=py_name,
      args=args,
    )

  @staticmethod
  def pointer(inner: TypeNode) -> TypeNode:
    return TypeNode(TypeKind.POINTER, inner=inner)

  @staticmethod
  def optional(inner: TypeNode, cpp_base: str = "Optional") -> TypeNode:
    return TypeNode(TypeKind.OPTIONAL, name=cpp_base, inner=inner)

  @staticmethod
  def ref(inner: TypeNode) -> TypeNode:
    return TypeNode(TypeKind.REF, inner=inner)

  @staticmethod
  def refcount(inner: TypeNode, cpp_base: str = "RefCount") -> TypeNode:
    return TypeNode(TypeKind.REFCOUNT, name=cpp_base, inner=inner)

  @staticmethod
  def array(inner: TypeNode, *, kind: str = "heap", cpp_base: str = "array") -> TypeNode:
    return TypeNode(
      TypeKind.ARRAY,
      name=cpp_base,
      inner=inner,
      array_kind=kind,
    )

  @staticmethod
  def function_ptr(ret: TypeNode, *args: TypeNode) -> TypeNode:
    """``Ret (*)(Args…)`` 语义层（``inner``=返回类型，``args``=形参类型）。"""
    return TypeNode(TypeKind.FUNCTION_PTR, inner=ret, args=args)

  def cpp_base(self) -> str:
    if self.kind in (TypeKind.SCALAR, TypeKind.TYPE_PARAM, TypeKind.NEVER):
      return self.name
    if self.kind == TypeKind.TEMPLATE:
      return self.name
    if self.kind == TypeKind.ARRAY:
      from .ir import CPP_ARRAY2D_PREFIX, CPP_ARRAY3D_PREFIX, CPP_ARRAY_PREFIX

      prefixes = {
        "heap": CPP_ARRAY_PREFIX,
        "heap2d": CPP_ARRAY2D_PREFIX,
        "heap3d": CPP_ARRAY3D_PREFIX,
      }
      return prefixes.get(self.array_kind, CPP_ARRAY_PREFIX).rstrip("<")
    if self.kind == TypeKind.OPTIONAL:
      from .ir import CPP_OPTIONAL_PREFIX

      return CPP_OPTIONAL_PREFIX.rstrip("<")
    if self.kind == TypeKind.REFCOUNT:
      from .ir import CPP_REFCount_PREFIX

      return CPP_REFCount_PREFIX.rstrip("<")
    if self.inner is not None and self.kind in (
      TypeKind.POINTER,
      TypeKind.OPTIONAL,
      TypeKind.REF,
      TypeKind.REFCOUNT,
    ):
      return self.inner.cpp_base()
    return self.name

  def bind_self(self, host: TypeNode) -> TypeNode:
    if self.kind != TypeKind.SELF:
      return self
    return host

  def map_children(self, fn) -> TypeNode:
    new_args = tuple(fn(a) for a in self.args)
    new_inner = fn(self.inner) if self.inner is not None else None
    if new_args == self.args and new_inner is self.inner:
      return self
    return replace(self, args=new_args, inner=new_inner)

  def render(self, policy: NamingPolicy) -> str:
    from .type_render import CLASS_BODY

    if policy is None:
      policy = CLASS_BODY

    match self.kind:
      case TypeKind.VOID:
        return "void"
      case TypeKind.NEVER:
        return self.name or "PyNever"
      case TypeKind.SCALAR:
        return self.name
      case TypeKind.TYPE_PARAM:
        return policy.format_type_param(self.name)
      case TypeKind.SELF:
        raise ValueError("TypeNode.SELF 须先 bind_self(host) 再 render")
      case TypeKind.TEMPLATE:
        args = ", ".join(a.render(policy) for a in self.args)
        from .ir import cpp_fill_allocator_default_args

        return cpp_fill_allocator_default_args(f"{self.name}<{args}>")
      case TypeKind.POINTER:
        assert self.inner is not None
        inner = self.inner.render(policy)
        # 嵌套 Pointer 的 inner 已是 POINTER 节点时须再加 ``*``
        if self.inner.kind == TypeKind.POINTER:
          return f"{inner}*"
        if inner.endswith("*"):
          return inner
        return f"{inner}*"
      case TypeKind.OPTIONAL:
        assert self.inner is not None
        from .ir import cpp_ident

        base = cpp_ident(self.name) if self.name else cpp_ident("Optional")
        return f"{base}<{self.inner.render(policy)}>"
      case TypeKind.REF:
        assert self.inner is not None
        return f"{self.inner.render(policy)}&"
      case TypeKind.REFCOUNT:
        assert self.inner is not None
        from .ir import cpp_refcount_type

        inner = self.inner.render(policy)
        return cpp_refcount_type(inner)
      case TypeKind.ARRAY:
        assert self.inner is not None
        from .ir import (
          CPP_ARRAY2D_PREFIX,
          CPP_ARRAY3D_PREFIX,
          CPP_ARRAY_PREFIX,
          CPP_SPAN2D_PREFIX,
          CPP_SPAN3D_PREFIX,
          CPP_SPAN_PREFIX,
          CPP_STACK_ARRAY2D_PREFIX,
          CPP_STACK_ARRAY3D_PREFIX,
          CPP_STACK_ARRAY_PREFIX,
        )

        inner = self.inner.render(policy)
        prefix = {
          "heap": CPP_ARRAY_PREFIX,
          "heap2d": CPP_ARRAY2D_PREFIX,
          "heap3d": CPP_ARRAY3D_PREFIX,
          "stack": CPP_STACK_ARRAY_PREFIX,
          "stack2d": CPP_STACK_ARRAY2D_PREFIX,
          "stack3d": CPP_STACK_ARRAY3D_PREFIX,
          "span": CPP_SPAN_PREFIX,
          "span2d": CPP_SPAN2D_PREFIX,
          "span3d": CPP_SPAN3D_PREFIX,
        }.get(self.array_kind, CPP_ARRAY_PREFIX)
        from .ir import cpp_fill_allocator_default_args

        return cpp_fill_allocator_default_args(f"{prefix}{inner}>")
      case TypeKind.FUNCTION_PTR:
        assert self.inner is not None
        ret = self.inner.render(policy)
        if not self.args:
          return f"{ret} (*)()"
        args = ", ".join(a.render(policy) for a in self.args)
        return f"{ret} (*)({args})"
      case _:
        raise ValueError(f"无法 render TypeNode: {self.kind}")


def type_param_names_equivalent(a: str, b: str) -> bool:
  """``Key`` 与 ``_Key`` 在同一 host 下视为同一形参。"""
  if a == b:
    return True
  if cpp_type_param_template_name(a) == b:
    return True
  if a == cpp_type_param_template_name(b):
    return True
  return False


def type_nodes_equal(
  left: TypeNode,
  right: TypeNode,
  *,
  wildcards: frozenset[str] = frozenset(),
) -> bool:
  if left.kind != right.kind:
    return False
  if left.kind == TypeKind.TYPE_PARAM and right.kind == TypeKind.TYPE_PARAM:
    if left.name in wildcards or right.name in wildcards:
      return True
    return type_param_names_equivalent(left.name, right.name)
  if left.kind in (TypeKind.SCALAR, TypeKind.NEVER):
    return left.name == right.name
  if left.kind == TypeKind.TEMPLATE:
    if left.name != right.name or len(left.args) != len(right.args):
      return False
    return all(
      type_nodes_equal(a, b, wildcards=wildcards)
      for a, b in zip(left.args, right.args)
    )
  if left.kind == TypeKind.FUNCTION_PTR:
    if len(left.args) != len(right.args):
      return False
    if left.inner is None or right.inner is None:
      return left.inner is right.inner
    if not type_nodes_equal(left.inner, right.inner, wildcards=wildcards):
      return False
    return all(
      type_nodes_equal(a, b, wildcards=wildcards)
      for a, b in zip(left.args, right.args)
    )
  if left.inner is not None or right.inner is not None:
    if left.inner is None or right.inner is None:
      return False
    if not type_nodes_equal(left.inner, right.inner, wildcards=wildcards):
      return False
  if left.kind == TypeKind.ARRAY:
    return left.array_kind == right.array_kind
  return left.name == right.name and left.args == right.args


def structural_match_type_nodes(
  concrete: TypeNode,
  pattern: TypeNode,
  wildcards: frozenset[str],
) -> dict[str, TypeNode] | None:
  """结构匹配；通配形参位绑定到 ``concrete`` 子树。"""
  if concrete.kind != pattern.kind:
    return None
  if pattern.kind == TypeKind.TEMPLATE:
    if concrete.name != pattern.name or len(concrete.args) != len(pattern.args):
      return None
    binds: dict[str, TypeNode] = {}
    for conc_arg, pat_arg in zip(concrete.args, pattern.args):
      if pat_arg.kind == TypeKind.TYPE_PARAM and pat_arg.name in wildcards:
        prev = binds.get(pat_arg.name)
        if prev is not None and not type_nodes_equal(prev, conc_arg):
          return None
        binds[pat_arg.name] = conc_arg
      elif not type_nodes_equal(conc_arg, pat_arg, wildcards=wildcards):
        return None
    return binds
  if pattern.kind == TypeKind.FUNCTION_PTR:
    if concrete.kind != TypeKind.FUNCTION_PTR:
      return None
    if concrete.inner is None or pattern.inner is None:
      return None
    if not type_nodes_equal(concrete.inner, pattern.inner, wildcards=wildcards):
      return None
    if len(concrete.args) != len(pattern.args):
      return None
    binds: dict[str, TypeNode] = {}
    for conc_arg, pat_arg in zip(concrete.args, pattern.args):
      if pat_arg.kind == TypeKind.TYPE_PARAM and pat_arg.name in wildcards:
        prev = binds.get(pat_arg.name)
        if prev is not None and not type_nodes_equal(prev, conc_arg):
          return None
        binds[pat_arg.name] = conc_arg
      elif not type_nodes_equal(conc_arg, pat_arg, wildcards=wildcards):
        return None
    return binds
  if pattern.kind == TypeKind.TYPE_PARAM and pattern.name in wildcards:
    return {pattern.name: concrete}
  if type_nodes_equal(concrete, pattern, wildcards=wildcards):
    return {}
  return None
