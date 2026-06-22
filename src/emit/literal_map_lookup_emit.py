"""字面量容器查表 / 成员：``{a: x}[k]``、``{…}.get``、``x in {a,b}``。

常量键/元素脱糖为三目 / ``||`` 链或 IIFE；非常量或 ``**`` 展开则临时 ``PyDict`` / ``PySet``。
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
  return _emit_runtime_lookup(
    tr, dict_node, key_expr, mode="get", default_node=default_node,
  )


def set_literal_elems_all_constant(node: ast.Set) -> bool:
  return all(isinstance(e, ast.Constant) for e in node.elts)


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
  member_expr = tr._visit_value_expr(member_node)
  if set_literal_elems_all_constant(set_node):
    if not set_node.elts:
      core = "false"
    else:
      parts = [
        f"({member_expr} == {tr._visit_value_expr(e)})" for e in set_node.elts
      ]
      core = parts[0] if len(parts) == 1 else "(" + " || ".join(parts) + ")"
  else:
    core = _emit_runtime_set_contains(tr, set_node, member_expr)
  if negate:
    return f"(!({core}))"
  return core
