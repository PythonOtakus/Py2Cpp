"""字面量容器查表 / 成员：``{a: x}[k]``、``{…}.get``、``x in {a,b}``。

常量键/元素脱糖为三目 / ``||`` 链；``x in {…}`` / ``x in […]`` 均 ``||`` 内联：标量 ``==``、``*{b}`` / ``*[b]`` → ``x in b``，不构造临时 ``PySet`` / ``PyList``。
见 ``.cursor/skills/py2cpp-design/reference.md`` §8.3.3.1。
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_ident, cpp_template_type
from ..constant.stdlib_layout import cpp_exception_ctor
from .comprehensions_emit import _temp_name
from .iife_emit import emit_iife

if TYPE_CHECKING:
  from ..translator import Translator


def dict_literal_has_unpack(node: ast.Dict) -> bool:
  return any(k is None for k in (node.keys or []))


def dict_literal_keys_all_constant(node: ast.Dict) -> bool:
  if dict_literal_has_unpack(node):
    return False
  return all(isinstance(k, ast.Constant) for k in (node.keys or []))


def _isStaticLiteralExpr(node: ast.expr) -> bool:
  """表达式可在 C++ 函数局部 ``static`` 初始化时安全求值。"""
  if isinstance(node, ast.Constant):
    return True
  if not isinstance(node, ast.Call):
    return False
  if not isinstance(node.func, ast.Name) or node.func.id != "ord":
    return False
  return (
    len(node.args) == 1
    and not node.keywords
    and isinstance(node.args[0], ast.Constant)
    and isinstance(node.args[0].value, str)
  )


def _dictLiteralEntriesStatic(node: ast.Dict) -> bool:
  if dict_literal_has_unpack(node):
    return False
  return all(
    _isStaticLiteralExpr(key) and _isStaticLiteralExpr(value)
    for key, value in zip(node.keys or [], node.values or [])
    if key is not None
  )


def dict_literal_inner_types(tr: Translator, node: ast.Dict) -> str:
  keys = [k for k in (node.keys or []) if k is not None]
  if not keys and not node.values:
    return f"{cpp_ident('int')}, {cpp_ident('int')}"
  k_t = cpp_ident("int")
  v_t = cpp_ident("int")
  if keys:
    k_t = tr._infer_expr_cpp_type(keys[0])
  if node.values:
    v_t = tr._infer_expr_cpp_type(node.values[0])
  return f"{k_t}, {v_t}"


def dict_literal_value_cpp(tr: Translator, node: ast.Dict) -> str:
  inner = dict_literal_inner_types(tr, node)
  parts = inner.split(", ", 1)
  return parts[1] if len(parts) == 2 else cpp_ident("int")


def _literal_pairs(tr: Translator, node: ast.Dict) -> list[tuple[str, str]]:
  pairs: list[tuple[str, str]] = []
  for key, val in zip(node.keys or [], node.values or []):
    if key is None:
      raise AssertionError("unpack should use runtime path")
    pairs.append((tr._visit_value_expr(key), tr._visit_value_expr(val)))
  return pairs


def _emit_runtime_lookup(
  tr: Translator,
  node: ast.Dict,
  key_expr: str,
  *,
  mode: str,
  default_node: ast.expr | None = None,
) -> str:
  inner = dict_literal_inner_types(tr, node)
  val_t = dict_literal_value_cpp(tr, node)
  spec = cpp_template_type("dict", inner)
  dname = _temp_name("dmap")
  stmts: list[str] = [f"{spec} {dname};"]
  for key, val in zip(node.keys or [], node.values or []):
    if key is None:
      stmts.append(f"{dname}.update({tr.visit(val)});")
    else:
      stmts.append(
        f"{dname}.__setitem__({tr.visit(key)}, {tr._visit_value_expr(val)});"
      )
  if mode == "getitem":
    stmts.append(f"return {dname}.__getitem__({key_expr});")
  else:
    assert default_node is not None
    from .lazy_param_emit import emit_lazy_supplier_from_expr

    wrapped = emit_lazy_supplier_from_expr(tr, default_node, val_t)
    stmts.append(f"return {dname}.get({key_expr}, {wrapped});")
  return emit_iife(val_t, stmts)


def _emit_static_lookup(
  tr: Translator,
  node: ast.Dict,
  key_expr: str,
  *,
  mode: str,
  default_node: ast.expr | None = None,
) -> str:
  inner = dict_literal_inner_types(tr, node)
  val_t = dict_literal_value_cpp(tr, node)
  spec = cpp_template_type("dict", inner)
  dname = _temp_name("dmap")
  init_name = _temp_name("dinit")
  init_lines = [f"{spec} {init_name};"]
  for key, value in zip(node.keys or [], node.values or []):
    assert key is not None
    init_lines.append(
      f"{init_name}.__setitem__({tr._visit_value_expr(key)}, {tr._visit_value_expr(value)});"
    )
  init_lines.append(f"return {init_name};")
  static_init = "\n".join([
    f"static {spec} {dname} = []() -> {spec}",
    "{",
    *[f"  {line}" for line in init_lines],
    "}();",
  ])
  stmts = [static_init]
  if mode == "getitem":
    stmts.append(f"return {dname}.__getitem__({key_expr});")
  else:
    assert default_node is not None
    from .lazy_param_emit import emit_lazy_supplier_from_expr

    wrapped = emit_lazy_supplier_from_expr(tr, default_node, val_t)
    stmts.append(f"return {dname}.get({key_expr}, {wrapped});")
  return emit_iife(val_t, stmts)


def try_emit_dict_literal_getitem(
  tr: Translator,
  dict_node: ast.Dict,
  slice_node: ast.expr,
) -> str:
  key_expr = tr._visit_value_expr(slice_node)
  val_t = dict_literal_value_cpp(tr, dict_node)
  if not dict_node.keys:
    throw_k = cpp_exception_ctor("KeyError")
    return emit_iife(val_t, [f"throw {throw_k}"])
  if dict_literal_keys_all_constant(dict_node):
    pairs = _literal_pairs(tr, dict_node)
    if not pairs:
      throw_k = cpp_exception_ctor("KeyError")
      return emit_iife(val_t, [f"throw {throw_k}"])
    throw_k = cpp_exception_ctor("KeyError")
    body = [f"if ({key_expr} == {k}) return {v}" for k, v in pairs]
    body.append(f"throw {throw_k}")
    return emit_iife(val_t, body)
  if _dictLiteralEntriesStatic(dict_node):
    return _emit_static_lookup(tr, dict_node, key_expr, mode="getitem")
  return _emit_runtime_lookup(tr, dict_node, key_expr, mode="getitem")


def try_emit_dict_literal_get(
  tr: Translator,
  dict_node: ast.Dict,
  key_node: ast.expr,
  default_node: ast.expr,
) -> str:
  key_expr = tr._visit_value_expr(key_node)
  default_expr = tr._visit_value_expr(default_node)
  val_t = dict_literal_value_cpp(tr, dict_node)
  if not dict_node.keys:
    return default_expr
  if dict_literal_keys_all_constant(dict_node):
    pairs = _literal_pairs(tr, dict_node)
    acc = default_expr
    for k_cpp, v_cpp in reversed(pairs):
      acc = f"({key_expr} == {k_cpp} ? {v_cpp} : {acc})"
    return acc
  if _dictLiteralEntriesStatic(dict_node):
    return _emit_static_lookup(
      tr, dict_node, key_expr, mode="get", default_node=default_node,
    )
  return _emit_runtime_lookup(
    tr, dict_node, key_expr, mode="get", default_node=default_node,
  )


def set_literal_has_starred(node: ast.Set) -> bool:
  return any(isinstance(e, ast.Starred) for e in node.elts)


def _literal_membership_part_for_elt(
  tr: Translator,
  member_expr: str,
  member_node: ast.expr,
  elt: ast.expr,
) -> str:
  """字面量单元素：标量 ``==``；``*{b}`` / ``*[b]`` → ``container.__contains__(member)``。"""
  if isinstance(elt, ast.Starred):
    from .binop_emit import _contains_member_arg

    container = elt.value
    left_v = _contains_member_arg(tr, member_node, container)
    if tr._use_member_dispatch_macro(container):
      return tr._cpp_call_expr(
        container, "__contains__", left_v, site=elt, arg_count=1,
      )
    comp_v = tr.visit(container)
    sep = tr._member_access(comp_v)
    return f"({comp_v}{sep}__contains__({left_v}))"
  return f"({member_expr} == {tr._visit_value_expr(elt)})"


def _literal_membership_or_chain(member_expr: str, elem_exprs: list[str]) -> str:
  """``x in {a,b,…}`` / ``x in [a,b,…]`` → ``(x==a)||(x==b)||…``。"""
  if not elem_exprs:
    return "false"
  if len(elem_exprs) == 1:
    return f"({member_expr} == {elem_exprs[0]})"
  parts = [f"({member_expr} == {e})" for e in elem_exprs]
  return "(" + " || ".join(parts) + ")"


def _literal_membership_or_chain_from_elts(
  tr: Translator,
  member_node: ast.expr,
  elts: list[ast.expr],
) -> str:
  """``x in {a,*b,c}`` / ``x in [a,*b,c]`` → ``(x==a)||(x in b)||(x==c)``。"""
  member_expr = tr._visit_value_expr(member_node)
  parts = [
    _literal_membership_part_for_elt(tr, member_expr, member_node, e)
    for e in elts
  ]
  if not parts:
    return "false"
  if len(parts) == 1:
    return parts[0]
  return "(" + " || ".join(parts) + ")"


def _set_literal_elem_cpp(tr: Translator, node: ast.Set) -> str:
  if not node.elts:
    return cpp_ident("int")
  return tr._infer_expr_cpp_type(node.elts[0])


def _emit_runtime_set_contains(
  tr: Translator,
  set_node: ast.Set,
  member_expr: str,
) -> str:
  elem_t = _set_literal_elem_cpp(tr, set_node)
  spec = cpp_template_type("set", elem_t)
  sname = _temp_name("sset")
  stmts: list[str] = [f"{spec} {sname};"]
  for elt in set_node.elts:
    stmts.append(f"{sname}.add({tr._visit_value_expr(elt)});")
  stmts.append(f"return {sname}.__contains__({member_expr});")
  return emit_iife("PyBool", stmts)


def try_emit_set_literal_contains(
  tr: Translator,
  set_node: ast.Set,
  member_node: ast.expr,
  *,
  negate: bool = False,
) -> str:
  core = _literal_membership_or_chain_from_elts(tr, member_node, set_node.elts)
  if negate:
    return f"(!({core}))"
  return core
