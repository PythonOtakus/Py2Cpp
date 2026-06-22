"""``super`` / ``Proxy[T]`` 成员访问 emit。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, property_getter_method_for, strip_cpp_ref, cpp_template_inner_args
from ..analysis.proxy import (
  PROXY_TARGET_FIELD,
  cpp_proxy_inner_type,
  entity_base_class_info,
  host_super_uses_proxy_target,
  is_cpp_proxy_type,
  is_super_call_form,
  proxy_target_member_sep,
  receiver_proxy_peel_enabled,
  reject_super_call_with_args,
  require_entity_base_call,
  super_call_form_init_message,
  super_missing_base_call_message,
  unwrap_super_receiver,
  uses_proxy_storage,
)
from .call_emit import call_param_cpp_types, emit_call_args

if TYPE_CHECKING:
  from ..translator import Translator


def _entity_base_cpp_type(tr: Translator) -> str | None:
  info = tr.class_info
  if info is None or "__base__" not in info.type_aliases:
    return None
  base_ast = info.type_aliases["__base__"].value
  if isinstance(base_ast, ast.Name) and base_ast.id == "void":
    return None
  tparams = set(info.type_params or [])
  return tr._parse_type(base_ast, tparams).strip()


def _host_entity_storage_cpp(tr: Translator, host_info: ClassInfo) -> str | None:
  if "__base__" not in host_info.type_aliases:
    return None
  base_ast = host_info.type_aliases["__base__"].value
  if isinstance(base_ast, ast.Name) and base_ast.id == "void":
    return None
  raw = tr._parse_type(base_ast, set(host_info.type_params or []))
  return ClassInfo.apply_refcount_storage_cpp_type(raw, tr.classes)


def _inner_from_receiver(
  tr: Translator,
  receiver: ast.expr,
  host_info: ClassInfo | None,
) -> tuple[ClassInfo | None, str | None]:
  recv_t = strip_cpp_ref(
    tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver) or ""
  )
  if host_info is not None and uses_proxy_storage(host_info):
    inner_cpp = cpp_template_inner_args(recv_t, f"{host_info.cpp_name()}<")
    if inner_cpp:
      storage = ClassInfo.apply_refcount_storage_cpp_type(inner_cpp, tr.classes)
      return tr._class_info_for_type(inner_cpp), storage
  if is_cpp_proxy_type(recv_t):
    inner_cpp = cpp_proxy_inner_type(recv_t)
    if inner_cpp:
      storage = ClassInfo.apply_refcount_storage_cpp_type(inner_cpp, tr.classes)
      return tr._class_info_for_type(inner_cpp), storage
  inner_info = entity_base_class_info(tr, host_info) if host_info is not None else None
  storage = _host_entity_storage_cpp(tr, host_info) if host_info is not None else None
  return inner_info, storage


def _proxy_peel_target(
  tr: Translator,
  receiver: ast.expr,
  host_info: ClassInfo | None,
) -> tuple[str, str]:
  recv = tr.visit(receiver)
  sep_outer = tr._member_access_sep(receiver, recv)
  inner_info, inner_cpp = _inner_from_receiver(tr, receiver, host_info)
  target = f"{recv}{sep_outer}{PROXY_TARGET_FIELD}"
  sep = proxy_target_member_sep(tr, inner_cpp)
  return target, sep


def _super_proxy_target(tr: Translator) -> tuple[str, str]:
  inner_cpp = _host_entity_storage_cpp(tr, tr.class_info) if tr.class_info else None
  sep = proxy_target_member_sep(tr, inner_cpp)
  return f"this->{PROXY_TARGET_FIELD}", sep


def _super_qualified_base_cpp(tr: Translator) -> str | None:
  cpp = _entity_base_cpp_type(tr)
  if not cpp:
    return None
  return cpp.partition("<")[0].strip()


def _read_property_on(
  tr: Translator,
  info: ClassInfo,
  recv: str,
  sep: str,
  attr: str,
) -> str | None:
  prop = info.properties.get(attr)
  if prop and prop.getter:
    getter = tr._property_getter_cpp_name(info, attr)
    return f"{recv}{sep}{getter}()"
  return None


def try_emit_super_attribute(tr: Translator, attr: str) -> str | None:
  inner = entity_base_class_info(tr, tr.class_info)
  if host_super_uses_proxy_target(tr):
    recv, sep = _super_proxy_target(tr)
    if inner is not None:
      prop = _read_property_on(tr, inner, recv, sep, attr)
      if prop is not None:
        return prop
      return f"{recv}{sep}{tr._member_cpp_name(inner, attr)}"
    return f"{recv}{sep}{attr}"
  base_cpp = _super_qualified_base_cpp(tr)
  if not base_cpp:
    return None
  if inner is not None:
    prop = _read_property_on(tr, inner, f"static_cast<{base_cpp}&>(*this)", ".", attr)
    if prop is not None:
      return prop
    mcpp = tr._member_cpp_name(inner, attr)
    return f"static_cast<{base_cpp}&>(*this).{mcpp}"
  return f"static_cast<{base_cpp}&>(*this).{attr}"


def emit_super_base_call_expr(tr: Translator, node: ast.Call | None = None) -> str:
  """``super()`` / ``super.__call__()`` → 基类 ``__call__()``（须已定义）。"""
  if node is not None:
    reject_super_call_with_args(node)
  require_entity_base_call(tr)
  inner = entity_base_class_info(tr, tr.class_info)
  mcpp = tr._member_cpp_name(inner, "__call__") if inner else "__call__"
  if host_super_uses_proxy_target(tr):
    recv, sep = _super_proxy_target(tr)
    return f"{recv}{sep}{mcpp}()"
  base_cpp = _super_qualified_base_cpp(tr)
  if not base_cpp:
    raise NotImplementedError(super_missing_base_call_message())
  return f"{base_cpp}::{mcpp}()"


def try_emit_super_call_expr(tr: Translator, node: ast.Call) -> str | None:
  """``super()`` / ``super.__call__()`` 单独作表达式 → 基类 ``__call__()``。"""
  if isinstance(node.func, ast.Name) and node.func.id == "super":
    return emit_super_base_call_expr(tr, node)
  if (
    isinstance(node.func, ast.Attribute)
    and node.func.attr == "__call__"
    and unwrap_super_receiver(node.func.value)
  ):
    return emit_super_base_call_expr(tr, node)
  return None


def try_emit_super_method_call_from_receiver(
  tr: Translator,
  receiver: ast.expr,
  method: str,
  node: ast.Call,
) -> str | None:
  if isinstance(receiver, ast.Name) and receiver.id == "super":
    return emit_super_method_call(tr, method, node)
  if is_super_call_form(receiver):
    if method == "__init__":
      raise NotImplementedError(super_call_form_init_message())
    if method == "__call__":
      return emit_super_base_call_expr(tr, node)
    require_entity_base_call(tr)
    return emit_super_method_call(tr, method, node)
  if unwrap_super_receiver(receiver):
    return emit_super_method_call(tr, method, node)
  return None


def emit_super_method_call(tr: Translator, method: str, node: ast.Call) -> str | None:
  if method == "__call__":
    return emit_super_base_call_expr(tr, node)
  arg_str = emit_call_args(
    tr,
    node,
    param_cpp_types=call_param_cpp_types(tr, node.func, call=node),
  )
  inner = entity_base_class_info(tr, tr.class_info)
  mcpp = tr._member_cpp_name(inner, method) if inner else method
  if method == "__init__":
    base_cpp = _super_qualified_base_cpp(tr)
    if not base_cpp:
      return None
    ctor = base_cpp.partition("<")[0].strip()
    if host_super_uses_proxy_target(tr):
      recv, sep = _super_proxy_target(tr)
      if arg_str:
        return f"{recv}{sep}{ctor}({arg_str})"
      return f"{recv}{sep}{ctor}()"
    if arg_str:
      return f"{ctor}::{ctor}({arg_str})"
    return f"{ctor}::{ctor}()"
  if host_super_uses_proxy_target(tr):
    recv, sep = _super_proxy_target(tr)
    if arg_str:
      return f"{recv}{sep}{mcpp}({arg_str})"
    return f"{recv}{sep}{mcpp}()"
  base_cpp = _super_qualified_base_cpp(tr)
  if not base_cpp:
    return None
  if arg_str:
    return f"{base_cpp}::{mcpp}({arg_str})"
  return f"{base_cpp}::{mcpp}()"


def super_assign_lvalue(tr: Translator, attr: str) -> str | None:
  inner = entity_base_class_info(tr, tr.class_info)
  if host_super_uses_proxy_target(tr):
    recv, sep = _super_proxy_target(tr)
    mcpp = tr._member_cpp_name(inner, attr) if inner else attr
    return f"{recv}{sep}{mcpp}"
  base_cpp = _super_qualified_base_cpp(tr)
  if not base_cpp:
    return None
  mcpp = tr._member_cpp_name(inner, attr) if inner else attr
  return f"static_cast<{base_cpp}&>(*this).{mcpp}"


def try_super_assign(
  tr: Translator,
  attr: str,
  val: str,
  *,
  rhs_node: ast.expr | None,
) -> bool:
  inner = entity_base_class_info(tr, tr.class_info)
  if inner is None:
    return False
  prop = inner.properties.get(attr)
  if prop and (prop.setter or prop.postsetter):
    lhs_base, sep = (
      _super_proxy_target(tr)
      if host_super_uses_proxy_target(tr)
      else (f"static_cast<{_super_qualified_base_cpp(tr)}&>(*this)", ".")
    )
    setter = tr._property_setter_cpp_name(inner, attr)
    coerced = tr._coerce_property_setter_value(inner, attr, val, rhs_node)
    tr.write_line(f"{lhs_base}{sep}{setter}({coerced});")
    return True
  lhs = super_assign_lvalue(tr, attr)
  if lhs is None:
    return False
  tr.write_line(f"{lhs} = {val};")
  return True


def try_proxy_peel_attribute(
  tr: Translator,
  receiver: ast.expr,
  attr: str,
) -> str | None:
  if not receiver_proxy_peel_enabled(tr, receiver):
    return None
  host = tr._class_info_for_receiver(receiver)
  if host is not None and tr._is_resolved_instance_member(host, attr):
    return None
  inner, _ = _inner_from_receiver(tr, receiver, host)
  if inner is None or not tr._is_resolved_instance_member(inner, attr):
    return None
  target, sep = _proxy_peel_target(tr, receiver, host)
  prop = _read_property_on(tr, inner, target, sep, attr)
  if prop is not None:
    return prop
  mcpp = tr._member_cpp_name(inner, attr)
  return f"{target}{sep}{mcpp}"


def try_proxy_peel_method_call(
  tr: Translator,
  receiver: ast.expr,
  method: str,
  node: ast.Call,
) -> str | None:
  if not receiver_proxy_peel_enabled(tr, receiver):
    return None
  host = tr._class_info_for_receiver(receiver)
  if host is not None and tr._is_resolved_instance_member(host, method):
    return None
  inner, _ = _inner_from_receiver(tr, receiver, host)
  if inner is None or not tr._is_resolved_instance_member(inner, method):
    return None
  target, sep = _proxy_peel_target(tr, receiver, host)
  mcpp = tr._member_cpp_name(inner, method)
  arg_str = emit_call_args(
    tr,
    node,
    param_cpp_types=call_param_cpp_types(tr, node.func, call=node),
  )
  if arg_str:
    return f"{target}{sep}{mcpp}({arg_str})"
  return f"{target}{sep}{mcpp}()"


def try_proxy_peel_assign(
  tr: Translator,
  receiver: ast.expr,
  attr: str,
  val: str,
  *,
  rhs_node: ast.expr | None,
) -> bool:
  if not receiver_proxy_peel_enabled(tr, receiver):
    return False
  host = tr._class_info_for_receiver(receiver)
  if host is not None and tr._is_resolved_instance_member(host, attr):
    return False
  inner, _ = _inner_from_receiver(tr, receiver, host)
  if inner is None or not tr._is_resolved_instance_member(inner, attr):
    return False
  target, sep = _proxy_peel_target(tr, receiver, host)
  prop = inner.properties.get(attr)
  if prop and (prop.setter or prop.postsetter):
    setter = tr._property_setter_cpp_name(inner, attr)
    coerced = tr._coerce_property_setter_value(inner, attr, val, rhs_node)
    tr.write_line(f"{target}{sep}{setter}({coerced});")
    return True
  mcpp = tr._member_cpp_name(inner, attr)
  tr.write_line(f"{target}{sep}{mcpp} = {val};")
  return True
