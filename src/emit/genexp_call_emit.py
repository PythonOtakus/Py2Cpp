"""``Iterable[T]`` 形参 + genexp 实参：调用点 IIFE 内联（非内建五函数）。"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from ..analysis.imports import ImportBinding
from ..analysis.ir import FunctionSig, MethodSig, cpp_param, is_overload_stub
from ..analysis.type_emit import bind_scope_param, method_param_storage_cpp, sig_return_full_cpp, bind_scope_var
from ..passes.genexp_inline_analyze import (
  GenexpInlinePlan,
  analyze_genexp_inline_body,
  literal_iterable_param_names,
)
from ..translation_error import TranslationError, location_from_node
from .builtin_aggregate_emit import _temp_name
from .call_emit import class_info_from_receiver
from .comprehensions_emit import append_generator_exp_loops, infer_generator_exp_elem_type
from .iife_emit import emit_iife

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


@dataclass(frozen=True)
class _GenexpCallTarget:
  func_def: ast.FunctionDef
  sig: FunctionSig | MethodSig
  class_info: ClassInfo | None
  receiver: ast.expr | None
  module_path: str


def try_emit_iterable_genexp_call(tr: Translator, node: ast.Call) -> str | None:
  genexp_slots = _genexp_arg_slots(node)
  if not genexp_slots:
    return None

  target = _resolve_genexp_call_target(tr, node)
  if target is None:
    return None

  if is_overload_stub(target.func_def):
    raise TranslationError(
      "genexp 内联不能绑定到 @overload 桩",
      location=location_from_node(tr, node),
    )

  iterable_params = literal_iterable_param_names(target.func_def)
  if not iterable_params:
    raise TranslationError(
      "生成器表达式实参须传给注解为 Iterable[...] 的形参",
      location=location_from_node(tr, node),
    )

  bound = _bind_call_to_params(tr, node, target, iterable_params)
  genexp_hits = [
    (pname, gexp)
    for pname, gexp in bound.genexp_by_param.items()
    if pname in iterable_params
  ]
  non_iterable_genexp = [
    pname for pname in bound.genexp_by_param if pname not in iterable_params
  ]
  if non_iterable_genexp:
    raise TranslationError(
      "生成器表达式实参须传给注解为 Iterable[...] 的形参",
      location=location_from_node(tr, genexp_slots[0][1]),
    )
  if len(genexp_hits) > 1:
    raise TranslationError(
      "不支持多个 Iterable 形参同时传入生成器表达式",
      location=location_from_node(tr, node),
    )
  if not genexp_hits:
    return None

  iterable_param, genexp = genexp_hits[0]
  plan = analyze_genexp_inline_body(
    tr, target.func_def, iterable_param, site=node,
  )
  ret_t = sig_return_full_cpp(target.sig)
  stmts: list[str] = []
  caller_var_types = dict(tr.scope.var_types) if tr.scope else {}

  with _genexp_inline_emit_context(tr, target):
    for decl in bound.prelude_decls:
      stmts.append(decl)
    with tr._use_scope(target.func_def):
      _seed_inline_scope(tr, target, bound, skip_param=iterable_param)
      with capture_emit_lines(tr) as prelude_lines:
        for stmt in plan.prelude:
          tr.visit(stmt)
      stmts.extend(_strip_semicolons(prelude_lines))

      def loop_inner() -> list[str]:
        elem_t = infer_generator_exp_elem_type(tr, genexp)
        elt_cpp = tr._visit_value_expr(genexp.elt)
        lv_cpp = _temp_name(plan.loop_var)
        inner: list[str] = [f"{elem_t} {lv_cpp} = {elt_cpp};"]
        if tr.scope:
          from ..translator import NameContext

          bind_scope_var(tr.scope, plan.loop_var, elem_t, classes=tr.classes)
          tr.scope.vars[plan.loop_var] = NameContext.Variable
        tr._genexp_inline_name_map[plan.loop_var] = lv_cpp
        with capture_emit_lines(tr) as body_lines:
          for stmt in plan.loop_body:
            tr.visit(stmt)
        tr._genexp_inline_name_map.pop(plan.loop_var, None)
        inner.extend(_strip_semicolons(body_lines))
        return inner

      with _merge_caller_var_types(tr, caller_var_types):
        append_generator_exp_loops(tr, stmts, genexp, loop_inner)

      with capture_emit_lines(tr) as ret_lines:
        tr.visit(plan.return_stmt)
      for line in _strip_semicolons(ret_lines):
        if line.startswith("return "):
          stmts.append(line if line.endswith(";") else f"{line};")
        else:
          stmts.append(line)

  return emit_iife(ret_t, stmts)


def _genexp_arg_slots(node: ast.Call) -> list[tuple[int, ast.GeneratorExp]]:
  out: list[tuple[int, ast.GeneratorExp]] = []
  for i, arg in enumerate(node.args):
    if isinstance(arg, ast.GeneratorExp):
      out.append((i, arg))
  for kw in node.keywords:
    if kw.arg is not None and isinstance(kw.value, ast.GeneratorExp):
      out.append((-1, kw.value))
  return out


@dataclass
class _BoundGenexpCall:
  prelude_decls: list[str]
  genexp_by_param: dict[str, ast.GeneratorExp]


def _bind_call_to_params(
  tr: Translator,
  call: ast.Call,
  target: _GenexpCallTarget,
  iterable_params: dict[str, str | None],
) -> _BoundGenexpCall:
  func_def = target.func_def
  sig = target.sig
  param_names = [
    a.arg for a in func_def.args.args if a.arg not in ("self", "cls")
  ]
  if sig.variadic_template is not None:
    param_names.append(sig.variadic_template.param_name)
  elif sig.vararg_pack is not None:
    param_names.append(sig.vararg_pack.param_name)

  defaults = func_def.args.defaults
  n_required = len(func_def.args.args) - len(defaults)
  default_by_name: dict[str, ast.expr] = {}
  for i, arg in enumerate(func_def.args.args):
    di = i - n_required
    if di >= 0:
      default_by_name[arg.arg] = defaults[di]

  bound_exprs: dict[str, ast.expr] = {}
  genexp_by_param: dict[str, ast.GeneratorExp] = {}
  pos = 0
  for arg in call.args:
    if pos >= len(param_names):
      raise TranslationError("位置参数过多", location=location_from_node(tr, call))
    name = param_names[pos]
    if isinstance(arg, ast.GeneratorExp):
      genexp_by_param[name] = arg
    else:
      bound_exprs[name] = arg
    pos += 1
  for kw in call.keywords:
    if kw.arg is None:
      raise TranslationError("genexp 内联不支持 **kwargs", location=location_from_node(tr, call))
    if kw.arg not in param_names:
      raise TranslationError(
        f"未知关键字参数: {kw.arg}", location=location_from_node(tr, call),
      )
    if isinstance(kw.value, ast.GeneratorExp):
      genexp_by_param[kw.arg] = kw.value
    else:
      bound_exprs[kw.arg] = kw.value

  prelude_decls: list[str] = []
  skip = set(genexp_by_param)
  if target.receiver is not None and target.class_info is not None:
    recv_cpp = tr._paren_expr(tr.visit(target.receiver))
    recv_t = tr._infer_expr_cpp_type(target.receiver) or target.class_info.cpp_name()
    prelude_decls.append(f"{recv_t}& {cpp_param('self')} = {recv_cpp};")

  for pname in param_names:
    if pname in skip or pname in ("self", "cls"):
      continue
    if pname in bound_exprs:
      expr = bound_exprs[pname]
    elif pname in default_by_name:
      expr = default_by_name[pname]
    else:
      raise TranslationError(
        f"缺少实参 {pname!r}", location=location_from_node(tr, call),
      )
    pt = method_param_storage_cpp(sig, pname)
    val = tr._visit_value_for_type(expr, pt) if pt else tr._visit_value_expr(expr)
    if pt:
      prelude_decls.append(f"{pt} {cpp_param(pname)} = {val};")
    else:
      prelude_decls.append(f"auto {cpp_param(pname)} = {val};")

  return _BoundGenexpCall(prelude_decls=prelude_decls, genexp_by_param=genexp_by_param)


def _seed_inline_scope(
  tr: Translator,
  target: _GenexpCallTarget,
  bound: _BoundGenexpCall,
  *,
  skip_param: str,
) -> None:
  from ..translator import NameContext

  assert tr.scope is not None
  sig = target.sig
  for arg in target.func_def.args.args:
    name = arg.arg
    if name in ("self", "cls") or name == skip_param:
      continue
    pt = method_param_storage_cpp(sig, name)
    if pt:
      bind_scope_param(tr.scope, name, sig, cpp_type=pt, classes=tr.classes)
      tr.scope.vars[name] = NameContext.Argument


def _resolve_genexp_call_target(
  tr: Translator, call: ast.Call,
) -> _GenexpCallTarget | None:
  func = call.func
  if isinstance(func, ast.Name):
    name = func.id
    if tr.class_info and (
      name in tr.class_info.methods or name in tr.class_info.method_overloads
    ):
      method_def = tr._method_def_for_call(tr.class_info, name, call)
      if method_def is not None:
        sig = tr.class_info.method_sig_for(method_def)
        if sig is not None:
          return _GenexpCallTarget(
            func_def=method_def,
            sig=sig,
            class_info=tr.class_info,
            receiver=ast.Name(id="self"),
            module_path=tr.class_info.module_path,
          )
    mp, func_def = _resolve_module_function(tr, name, call)
    if func_def is None or mp is None:
      return None
    sig = tr._function_sig_for(mp, func_def)
    return _GenexpCallTarget(
      func_def=func_def,
      sig=sig,
      class_info=None,
      receiver=None,
      module_path=mp,
    )
  match func:
    case ast.Attribute(value=recv, attr=method):
      info = class_info_from_receiver(tr, recv)
      if info is None or (
        method not in info.methods and method not in info.method_overloads
      ):
        return None
      method_def = tr._method_def_for_call(info, method, call)
      if method_def is None:
        return None
      sig = info.method_sig_for(method_def)
      if sig is None:
        return None
      return _GenexpCallTarget(
        func_def=method_def,
        sig=sig,
        class_info=info,
        receiver=recv,
        module_path=info.module_path,
      )
    case _:
      return None


def _resolve_module_function(
  tr: Translator, name: str, call: ast.Call,
) -> tuple[str | None, ast.FunctionDef | None]:
  binding: ImportBinding | None = tr._effective_import_bindings().get(name)
  if binding is not None and binding.kind == "function":
    mp = binding.module_path
    sym = binding.symbol
    fd = tr._module_function_def_for_call(mp, sym, call)
    if fd is not None:
      return mp, fd

  for mp in _module_lookup_order(tr):
    fd = tr._module_function_def_for_call(mp, name, call)
    if fd is not None:
      return mp, fd
  return None, None


def _module_lookup_order(tr: Translator) -> list[str]:
  seen: set[str] = set()
  order: list[str] = []
  for mp in (tr.source_target, tr.entry_module_path, *tr.module_order):
    if mp and mp not in seen:
      order.append(mp)
      seen.add(mp)
  return order


@contextmanager
def _merge_caller_var_types(
  tr: Translator,
  caller_var_types: dict[str, str],
) -> Iterator[None]:
  """genexp ``for x in data``：``data`` 在调用方 scope，合并类型以启用索引 ``for``。"""
  if not tr.scope or not caller_var_types:
    yield
    return
  from ..analysis.type_emit import bind_scope_var, snapshot_scope_type_bindings, restore_scope_type_bindings

  saved = snapshot_scope_type_bindings(tr.scope)
  for name, ty in caller_var_types.items():
    if ty and name not in tr.scope.var_types:
      bind_scope_var(tr.scope, name, ty, classes=tr.classes)
  try:
    yield
  finally:
    restore_scope_type_bindings(tr.scope, saved)


@contextmanager
def _genexp_inline_emit_context(
  tr: Translator, target: _GenexpCallTarget,
) -> Iterator[None]:
  prev_class = tr.class_info
  prev_self_type = tr._self_type_class
  prev_inline_self = tr._genexp_inline_self_cpp
  prev_name_map = dict(tr._genexp_inline_name_map)
  tr.class_info = target.class_info
  tr._self_type_class = target.class_info
  tr._genexp_inline_name_map.clear()
  if target.receiver is not None:
    tr._genexp_inline_self_cpp = cpp_param("self")
  else:
    tr._genexp_inline_self_cpp = None
  try:
    yield
  finally:
    tr.class_info = prev_class
    tr._self_type_class = prev_self_type
    tr._genexp_inline_self_cpp = prev_inline_self
    tr._genexp_inline_name_map.clear()
    tr._genexp_inline_name_map.update(prev_name_map)


@contextmanager
def capture_emit_lines(tr: Translator) -> Iterator[list[str]]:
  lines: list[str] = []
  prev = tr._emit_line_sink
  prev_indent = tr.indent_level
  tr._emit_line_sink = lines
  tr.indent_level = 0
  try:
    yield lines
  finally:
    tr._emit_line_sink = prev
    tr.indent_level = prev_indent


def _strip_semicolons(lines: list[str]) -> list[str]:
  out: list[str] = []
  for line in lines:
    s = line.strip()
    if not s:
      continue
    if s.endswith(";"):
      s = s[:-1].rstrip()
    out.append(s)
  return out
