"""TypeNode → C++ 文本：emit 边界（Phase 3+）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .type_node import TypeNode
from .type_render import CLASS_BODY, STORAGE

if TYPE_CHECKING:
  from ..translator import Translator
  from .ir import ClassInfo, FunctionSig, MethodSig


def storage_cpp(node: TypeNode | None, *, fallback: str = "") -> str:
  """参数 / 局部 / 字段存储类型（``STORAGE`` == ``CLASS_BODY``）。"""
  if node is None:
    return fallback
  from .ir import cpp_fill_allocator_default_args

  return cpp_fill_allocator_default_args(node.render(STORAGE))


def class_body_cpp(node: TypeNode | None, *, fallback: str = "") -> str:
  if node is None:
    return fallback
  from .ir import cpp_fill_allocator_default_args

  return cpp_fill_allocator_default_args(node.render(CLASS_BODY))


def pystr_header_decl_cpp(module_path: str) -> str:
  """``iter_result`` 等仅前向声明 ``PyStr`` 时须全限定名（避免 ``using`` 绑定不完整类型）。"""
  from .ir import cpp_ident
  from ..constant.stdlib_layout import STR_PYSTR, stdlib_module_path

  if module_path.replace("\\", "/") == stdlib_module_path("core/iter_result"):
    return f"::{STR_PYSTR}"
  return cpp_ident("str")


def pystr_union_cpp(module_path: str) -> str:
  """``@union`` 默认 ``__repr__`` / ``__str__`` 实现中的 ``PyStr`` 类型名。"""
  return pystr_header_decl_cpp(module_path)


def sig_return_storage_cpp(sig: "MethodSig | FunctionSig", *, fallback: str = "void") -> str:
  """签名返回类型 lead（``CLASS_BODY``，无 ``ret_trail``）；只读 ``return_type_node``。"""
  return class_body_cpp(sig.return_type_node, fallback=fallback).rstrip()


def sig_return_full_cpp(sig: "MethodSig | FunctionSig", *, fallback: str = "void") -> str:
  """签名完整返回类型（``lead + trail``）。"""
  trail = getattr(sig, "ret_trail", "") or ""
  return (sig_return_storage_cpp(sig, fallback=fallback) + trail).strip()


def method_param_storage_cpp(
  sig: "MethodSig | FunctionSig",
  name: str,
  *,
  fallback: str = "void*",
) -> str:
  """形参存储 C++ 类型；只读 ``param_type_nodes``。"""
  node = sig.param_type_nodes.get(name)
  return storage_cpp(node, fallback=fallback)


def method_param_types_map(sig: "MethodSig | FunctionSig") -> dict[str, str]:
  """由 ``param_type_nodes`` 渲染的形参类型表（写入 ``param_types`` 缓存用）。"""
  return {
    name: storage_cpp(node)
    for name, node in sig.param_type_nodes.items()
  }


def sync_sig_cache(sig: "MethodSig | FunctionSig"):
  """``param_types`` / ``ret_lead`` ← ``TypeNode`` 渲染缓存（勿手改字符串）。"""
  from dataclasses import replace

  synced = replace(sig, param_types=method_param_types_map(sig))
  return replace(synced, ret_lead=sig_return_storage_cpp(synced))


def collect_sig_type_texts(sig: "MethodSig | FunctionSig") -> list[str]:
  """签名涉及的 C++ 类型文本（头文件依赖扫描）。"""
  out = [sig_return_full_cpp(sig)]
  out.extend(method_param_types_map(sig).values())
  vararg = getattr(sig, "vararg_pack", None)
  if vararg is not None:
    out.append(vararg.cpp_type)
  return [t for t in out if t]


def field_ann_ast(info: "ClassInfo", field: str):
  """字段注解 AST 占位（``__ann__{field}``）；非 C++ 渲染缓存。"""
  return info.field_types.get(f"__ann__{field}")


def write_field_ann_ast(info: "ClassInfo", field: str, ann) -> None:
  """写入或删除 ``__ann__{field}`` AST 占位（``ann is None`` → 删除）。"""
  key = f"__ann__{field}"
  if ann is None:
    info.field_types.pop(key, None)
  else:
    info.field_types[key] = ann


def clear_field_ann_ast(info: "ClassInfo", field: str) -> None:
  write_field_ann_ast(info, field, None)


def write_field_storage(info: "ClassInfo", field: str, node: TypeNode | None) -> None:
  """写入 ``field_type_nodes``（不再维护 ``field_types`` C++ 渲染缓存）。"""
  if node is None:
    info.field_type_nodes.pop(field, None)
    info.field_types.pop(field, None)
  else:
    info.field_type_nodes[field] = node
    info.field_types.pop(field, None)


def field_storage_cpp(
  info: "ClassInfo",
  field: str,
  *,
  fallback: str = "",
  classes: dict[str, "ClassInfo"] | None = None,
) -> str:
  """字段存储 C++ 类型；只读 ``field_type_nodes``；可沿基类链查找。"""
  rendered = field_decl_cpp(info, field)
  if rendered is not None:
    return rendered
  if classes:
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
      # mixin / protocol 不占存储；其方法体误收集的 void* 字段勿遮蔽真实基类类型
      if base.is_mixin or base.is_annotation or base.is_protocol:
        continue
      got = field_storage_cpp(base, field, fallback="", classes=None)
      if got:
        return got
  return fallback


def field_storage_values(info: "ClassInfo") -> list[str]:
  """类字段存储类型列表（跳过 ``__ann__`` 占位）。"""
  out: list[str] = []
  for field in info.fields:
    if field.startswith("__ann__"):
      continue
    t = field_storage_cpp(info, field)
    if t:
      out.append(t)
  return out


def class_decl_return_cpp(
  tr: "Translator",
  sig: "MethodSig",
  info: "ClassInfo",
) -> str:
  """类外 ``.h`` 方法声明的返回类型（模板实参 ``_T`` 化）。"""
  lead = sig_return_storage_cpp(sig)
  if info.is_template():
    return tr._rewrite_template_args_to_cpp_params(lead, info)
  return lead


def method_impl_return_cpp(
  tr: "Translator",
  sig: "MethodSig",
  info: "ClassInfo",
) -> str:
  """``.inl`` 成员定义的返回类型（``typename Qual::T`` + ``_T`` 实参）。"""
  lead = sig_return_storage_cpp(sig)
  return tr._typename_member_alias_type(lead, info)


def field_decl_cpp(info: "ClassInfo", field: str) -> str | None:
  """字段声明 C++ 类型；无 ``field_type_nodes`` 条目时返回 ``None``。"""
  nodes = getattr(info, "field_type_nodes", None)
  if not nodes:
    return None
  node = nodes.get(field)
  if node is None:
    return None
  from .ir import heap_array_type_with_allocator

  return heap_array_type_with_allocator(class_body_cpp(node), info)


def field_type_node(
  info: "ClassInfo",
  field: str,
  *,
  classes: dict | None = None,
) -> TypeNode | None:
  """字段 ``TypeNode``（仅 ``field_type_nodes``）。"""
  nodes = getattr(info, "field_type_nodes", None)
  if not nodes:
    return None
  return nodes.get(field)


def param_type_node(
  sig: "MethodSig | FunctionSig",
  name: str,
  *,
  classes: dict | None = None,
) -> TypeNode | None:
  """形参 ``TypeNode``（仅 ``param_type_nodes``）。"""
  return sig.param_type_nodes.get(name)


def sig_return_type_node(sig: "MethodSig | FunctionSig") -> TypeNode | None:
  """返回类型 ``TypeNode``（仅 ``return_type_node``）。"""
  return getattr(sig, "return_type_node", None)


def render_type_like(
  ty: TypeNode | str | None,
  *,
  classes: dict | None = None,
  fallback: str = "",
) -> str:
  """``TypeNode`` / C++ 串 → ``CLASS_BODY`` 文本（谓词 / emit 共用）。"""
  from .type_pred import type_to_cpp_text

  return type_to_cpp_text(ty, classes=classes, fallback=fallback)


def function_param_cpp_types(
  sig: "FunctionSig",
  func_def,
) -> list[str]:
  """模块函数形参存储类型（优先 ``param_type_nodes``）。"""
  out: list[str] = []
  for arg in func_def.args.args:
    out.append(method_param_storage_cpp(sig, arg.arg, fallback=""))
  if sig.variadic_template is not None:
    out.append(
      method_param_storage_cpp(sig, sig.variadic_template.param_name, fallback=""),
    )
  elif sig.vararg_pack is not None:
    out.append(sig.vararg_pack.cpp_type)
  return out


def bind_scope_param(
  scope,
  name: str,
  sig: "MethodSig | FunctionSig",
  *,
  cpp_type: str = "",
  classes: dict | None = None,
) -> None:
  """写入作用域形参 ``TypeNode`` + 渲染缓存（``param_types`` / ``var_types`` 双写）。"""
  node = sig.param_type_nodes.get(name)
  pt = cpp_type or method_param_storage_cpp(sig, name, fallback="void*")
  scope.param_types[name] = pt
  if node is not None:
    scope.param_type_nodes[name] = node
  bind_scope_var(scope, name, pt, node=node, classes=classes)


def scope_type_node_from_cpp(
  cpp_type: str,
  *,
  classes: dict | None = None,
) -> TypeNode | None:
  """C++ 存储类型文本 → ``TypeNode``（``auto`` / 空 / 不可解析 → ``None``）。"""
  t = (cpp_type or "").strip()
  if not t or t == "auto":
    return None
  from .type_compat import type_node_from_cpp_string

  try:
    return type_node_from_cpp_string(t, classes=classes or {})
  except (ValueError, TypeError):
    return None


def bind_scope_var(
  scope,
  name: str,
  cpp_type: str,
  *,
  node: TypeNode | None = None,
  classes: dict | None = None,
) -> None:
  """写入作用域局部/推断类型：``var_type_nodes`` 优先，``var_types`` 为渲染缓存。"""
  scope.var_types[name] = cpp_type
  resolved = node
  if resolved is None:
    resolved = scope_type_node_from_cpp(cpp_type, classes=classes)
  if resolved is not None:
    scope.var_type_nodes[name] = resolved
  else:
    scope.var_type_nodes.pop(name, None)


def bind_scope_vararg(
  scope,
  name: str,
  cpp_type: str,
  *,
  classes: dict | None = None,
) -> None:
  """可变参数包形参：``param_types`` + ``bind_scope_var``。"""
  scope.param_types[name] = cpp_type
  bind_scope_var(scope, name, cpp_type, classes=classes)
  node = scope.var_type_nodes.get(name)
  if node is not None:
    scope.param_type_nodes[name] = node
  else:
    scope.param_type_nodes.pop(name, None)


def snapshot_scope_type_bindings(scope):
  """保存作用域四类类型表（块/临时 scope 恢复用）。"""
  return (
    dict(scope.var_types),
    dict(scope.var_type_nodes),
    dict(scope.param_types),
    dict(scope.param_type_nodes),
  )


def restore_scope_type_bindings(scope, snap) -> None:
  vtypes, vnodes, ptypes, pnodes = snap
  scope.var_types = vtypes
  scope.var_type_nodes = vnodes
  scope.param_types = ptypes
  scope.param_type_nodes = pnodes


def scope_all_storage_bindings(scope) -> dict[str, str]:
  """作用域内全部名称 → 存储 C++ 类型（node 优先）。"""
  names = (
    set(scope.var_types)
    | set(scope.param_types)
    | set(scope.var_type_nodes)
    | set(scope.param_type_nodes)
  )
  out: dict[str, str] = {}
  for name in names:
    t = scope_binding_storage_cpp(scope, name)
    if t:
      out[name] = t
  return out


def scope_storage_cpp(
  tr: "Translator",
  name: str,
  *,
  fallback: str = "",
) -> str:
  """当前作用域名称的存储 C++ 类型（优先 ``param_type_nodes`` / ``var_type_nodes``）。"""
  scope = tr.scope
  if scope is None:
    return fallback
  node = scope.param_type_nodes.get(name) or scope.var_type_nodes.get(name)
  if node is not None:
    return storage_cpp(node, fallback=fallback)
  return scope.var_types.get(name) or scope.param_types.get(name, fallback)


def scope_type_node(
  tr: "Translator",
  name: str,
):
  """当前作用域名称的 ``TypeNode``（无则 ``None``）。"""
  scope = tr.scope
  if scope is None:
    return None
  return scope.param_type_nodes.get(name) or scope.var_type_nodes.get(name)


def scope_has_type_binding(scope, name: str) -> bool:
  """名称在当前作用域是否已有类型绑定（node 或字符串缓存）。"""
  return (
    name in scope.var_types
    or name in scope.param_types
    or name in scope.var_type_nodes
    or name in scope.param_type_nodes
  )


def lookup_scope_storage_cpp(
  tr: "Translator",
  name: str,
  *,
  fallback: str = "",
) -> str:
  """沿 ``scopes`` 栈查找存储 C++ 类型（node 优先）。"""
  for scope in reversed(tr.scopes):
    node = scope.param_type_nodes.get(name) or scope.var_type_nodes.get(name)
    if node is not None:
      return storage_cpp(node, fallback=fallback)
    t = scope.var_types.get(name) or scope.param_types.get(name)
    if t:
      return t
  return fallback


def scope_binding_storage_cpp(
  scope,
  name: str,
  *,
  fallback: str = "",
) -> str:
  """单作用域内名称的存储 C++ 类型（node 优先）。"""
  node = scope.param_type_nodes.get(name) or scope.var_type_nodes.get(name)
  if node is not None:
    return storage_cpp(node, fallback=fallback)
  return scope.var_types.get(name) or scope.param_types.get(name, fallback)


def scope_has_param(scope, name: str) -> bool:
  """名称在当前作用域是否为形参（node 或字符串缓存）。"""
  return name in scope.param_types or name in scope.param_type_nodes


def lookup_scope_type_node(tr: "Translator", name: str):
  """沿 ``scopes`` 栈查找 ``TypeNode``。"""
  for scope in reversed(tr.scopes):
    node = scope.param_type_nodes.get(name) or scope.var_type_nodes.get(name)
    if node is not None:
      return node
  return None
