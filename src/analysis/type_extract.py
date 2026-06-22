"""条件类型别名 RHS 的编译期求值（结构模式匹配 + 捕获绑定）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .ir import TypeAliasInfo, cpp_ident
from ..passes.type_if import TypePattern, _structural_type_match

from .type_compat import split_cpp_template
from .type_node import TypeKind, TypeNode, structural_match_type_nodes
from .type_render import CLASS_BODY

if TYPE_CHECKING:
  from ..translator import Translator

TypeLike = str | TypeNode | None

NEVER_CPP = cpp_ident("Never")


@dataclass(frozen=True)
class ConditionalBranch:
  pattern: TypePattern
  arm: ast.expr


@dataclass(frozen=True)
class ConditionalAliasPlan:
  subject: str
  call_params: tuple[str, ...]
  capture_params: tuple[str, ...]
  branches: tuple[ConditionalBranch, ...]
  else_arm: ast.expr | None


def try_match_pattern(concrete: str, pat: TypePattern) -> dict[str, str] | None:
  """``concrete`` 匹配 ``pat`` 时返回捕获形参 → C++ 类型名。"""
  wild = set(pat.wildcards_for_match())
  if pat.pattern_node is not None:
    from .type_compat import type_node_from_cpp_string

    conc_node = type_node_from_cpp_string(concrete)
    binds = structural_match_type_nodes(
      conc_node, pat.pattern_node, frozenset(wild),
    )
    if binds is None:
      return None
    return {name: node.render(CLASS_BODY) for name, node in binds.items()}
  if wild:
    if not _structural_type_match(
      concrete, pat.cpp_type, pat.wildcards_for_match(),
    ):
      return None
    _, conc_args = split_cpp_template(concrete)
    _, pat_args = split_cpp_template(pat.cpp_type)
    if len(conc_args) != len(pat_args):
      return None
    binds: dict[str, str] = {}
    bind_set = set(pat.extra_template_params)
    for c_arg, p_arg in zip(conc_args, pat_args):
      if p_arg in bind_set:
        binds[p_arg] = c_arg
      elif p_arg in wild:
        continue
      elif c_arg != p_arg:
        return None
    return binds
  if pat.cpp_type == concrete:
    return {}
  return None


def resolve_type_arm(
  tr: Translator,
  node: ast.expr,
  *,
  arg_bindings: dict[str, str],
  capture_bindings: dict[str, str],
  type_params: set[str],
) -> str:
  if isinstance(node, ast.Name):
    if node.id == "Never":
      return NEVER_CPP
    if node.id in capture_bindings:
      return capture_bindings[node.id]
    if node.id in arg_bindings:
      return arg_bindings[node.id]
    if node.id in type_params:
      return node.id
    return tr._parse_type(node, type_params)
  return tr._parse_type(node, type_params)


def evaluate_conditional_alias(
  tr: Translator,
  alias: TypeAliasInfo,
  plan: ConditionalAliasPlan,
  arg_bindings: dict[str, str],
  type_params: set[str],
) -> str:
  """将调用实参代入 ``subject``，对 RHS 三目链做编译期求值。"""
  if plan.subject not in arg_bindings:
    raise ValueError(f"条件别名 {alias.name}: 缺少形参 {plan.subject}")
  concrete = arg_bindings[plan.subject]
  for br in plan.branches:
    binds = try_match_pattern(concrete, br.pattern)
    if binds is not None:
      return resolve_type_arm(
        tr,
        br.arm,
        arg_bindings=arg_bindings,
        capture_bindings=binds,
        type_params=type_params,
      )
  if plan.else_arm is not None:
    return resolve_type_arm(
      tr,
      plan.else_arm,
      arg_bindings=arg_bindings,
      capture_bindings={},
      type_params=type_params,
    )
  raise ValueError(f"条件别名 {alias.name}[{concrete}] 无匹配分支且无 else")


def is_never_cpp_type(cpp: str) -> bool:
  return cpp.strip() == NEVER_CPP


# --- TypeNode 提取（Phase 6；字符串路径仍可用作 fallback）---


def _render_node(node: TypeNode) -> str:
  return node.render(CLASS_BODY)


def template_type_arg_nodes(
  ty: TypeLike,
  cpp_base: str,
  *,
  classes: dict | None = None,
) -> tuple[TypeNode, ...]:
  from .type_pred import coerce_type_node, _template_core_node

  if isinstance(ty, TypeNode):
    tpl = _template_core_node(ty, cpp_base)
    return tpl.args if tpl else ()
  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return ()
  tpl = _template_core_node(node, cpp_base)
  return tpl.args if tpl else ()


def template_fixed_inners(
  ty: TypeLike,
  cpp_base: str,
  count: int,
  *,
  classes: dict | None = None,
) -> tuple[str, ...] | None:
  args = template_type_arg_nodes(ty, cpp_base, classes=classes)
  if len(args) != count:
    return None
  return tuple(_render_node(a) for a in args)


def single_template_inner(
  ty: TypeLike,
  prefix: str,
  *,
  classes: dict | None = None,
) -> str | None:
  """``PyList<T>`` → ``T`` 文本；与 ``cpp_template_inner_args`` 对齐。"""
  from .ir import cpp_template_inner_args, strip_cpp_type_qualifiers

  if isinstance(ty, str):
    return cpp_template_inner_args(strip_cpp_type_qualifiers(ty), prefix)
  base = prefix[:-1] if prefix.endswith("<") else prefix
  args = template_type_arg_nodes(ty, base, classes=classes)
  if len(args) != 1:
    return None
  return _render_node(args[0])


def optional_inner_node(
  ty: TypeLike,
  *,
  classes: dict | None = None,
) -> TypeNode | None:
  from .type_pred import coerce_type_node, _peel_ptr_ref

  if isinstance(ty, TypeNode):
    node = ty
  else:
    node = coerce_type_node(ty, classes=classes)
  if node is None:
    return None
  core = _peel_ptr_ref(node)
  if core.kind != TypeKind.OPTIONAL or core.inner is None:
    return None
  return core.inner


def optional_inner_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  inner = optional_inner_node(ty, classes=classes)
  return _render_node(inner) if inner is not None else None


def refcount_inner_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .type_pred import coerce_type_node

  node = coerce_type_node(ty, classes=classes)
  if node is None:
    return None
  cur = node
  while cur.kind == TypeKind.POINTER:
    assert cur.inner is not None
    cur = cur.inner
  if cur.kind != TypeKind.REFCOUNT or cur.inner is None:
    return None
  return _render_node(cur.inner)


def template_inner_text(
  ty: TypeLike,
  prefix: str,
  *,
  classes: dict | None = None,
) -> str | None:
  """``PyDict<K,V>`` → ``K, V``；与 ``cpp_template_inner_args`` 对齐。"""
  from .ir import cpp_template_inner_args, strip_cpp_type_qualifiers

  if isinstance(ty, str):
    return cpp_template_inner_args(strip_cpp_type_qualifiers(ty), prefix)
  base = prefix[:-1] if prefix.endswith("<") else prefix
  args = template_type_arg_nodes(ty, base, classes=classes)
  if not args:
    return None
  return ", ".join(_render_node(a) for a in args)


# --- 容器 / 协议提取别名（Phase 7 公开 API）---

def _first_template_inner(
  ty: TypeLike,
  prefix: str,
  *,
  classes: dict | None = None,
) -> str | None:
  """``PyList<T, A>`` / ``PyList<T>`` → ``T``（忽略分配器实参）。"""
  from .ir import split_cpp_template_args

  inner = template_inner_text(ty, prefix, classes=classes)
  if inner is None:
    return None
  parts = split_cpp_template_args(inner)
  return parts[0].strip() if parts else None


def list_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_LIST_PREFIX

  return _first_template_inner(ty, CPP_LIST_PREFIX, classes=classes)


def dict_type_args(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_DICT_PREFIX

  return template_inner_text(ty, CPP_DICT_PREFIX, classes=classes)


def set_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_SET_PREFIX

  return single_template_inner(ty, CPP_SET_PREFIX, classes=classes)


def deque_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_DEQUE_PREFIX

  return single_template_inner(ty, CPP_DEQUE_PREFIX, classes=classes)


def chunk_deque_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_CHUNK_DEQUE_PREFIX

  return single_template_inner(ty, CPP_CHUNK_DEQUE_PREFIX, classes=classes)


def frozenset_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_FROZENSET_PREFIX

  return single_template_inner(ty, CPP_FROZENSET_PREFIX, classes=classes)


def frozenlist_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_FROZENLIST_PREFIX

  return _first_template_inner(ty, CPP_FROZENLIST_PREFIX, classes=classes)


def frozendict_type_args(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_FROZENDICT_PREFIX

  return template_inner_text(ty, CPP_FROZENDICT_PREFIX, classes=classes)


def iterable_elem_type(ty: TypeLike, *, classes: dict | None = None) -> str | None:
  from .ir import CPP_PY_ITERABLE_PREFIX

  return single_template_inner(ty, CPP_PY_ITERABLE_PREFIX, classes=classes)


def generator_type_args(ty: TypeLike, *, classes: dict | None = None) -> tuple[str, str, str] | None:
  got = template_fixed_inners(ty, "PyGenerator", 3, classes=classes)
  if got is None:
    return None
  return got[0], got[1], got[2]


def coroutine_type_args(ty: TypeLike, *, classes: dict | None = None) -> tuple[str, str, str] | None:
  got = template_fixed_inners(ty, "PyCoroutine", 3, classes=classes)
  if got is None:
    return None
  return got[0], got[1], got[2]


def async_generator_type_args(ty: TypeLike, *, classes: dict | None = None) -> tuple[str, str] | None:
  got = template_fixed_inners(ty, "PyAsyncGenerator", 2, classes=classes)
  if got is None:
    return None
  return got[0], got[1]
