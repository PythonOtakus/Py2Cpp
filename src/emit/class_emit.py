"""类方法体 / 属性 / 特殊成员 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations

import ast
from contextlib import nullcontext
from typing import TYPE_CHECKING

from ..analysis.ir import (
  INT_FIELDS,
  cpp_ident,
  field_property_getter_return_ref,
  format_fn_sig,
  fn_noexcept_suffix,
)
from ..analysis.type_emit import bind_scope_param, bind_scope_var, bind_scope_vararg, field_storage_cpp, method_impl_return_cpp, method_param_storage_cpp, method_param_types_map, sig_return_storage_cpp
from .copy_move_emit import emit_auto_copy_move, emit_copy_move_special_members
from .object_repr_emit import (
  complex_operator_cpp_type,
  emit_default_object_repr_impls,
  has_effective_bool,
  has_effective_complex,
  has_effective_float,
  has_effective_int,
  has_effective_str,
)
from .refcount_emit import emit_refcount_class_impl
from .union_emit import emit_union_class_impl, emit_union_user_methods
from ..passes.decorators import has_named_decorator
from ..passes.descriptors import storage_field_for
from ..passes.generator_emit import emit_generator_next
from ..passes.move_state import (
  emit_move_state_epilogue_lines,
  emit_move_state_prologue_lines,
)
from ..passes.class_type_if import emit_class_type_if_method_bodies
from ..passes.type_if import emit_type_if_dispatch, emit_type_if_return, plan_type_if_chain
from ..emit.stdlib_inject_emit import emit_stdlib_class_runtime

if TYPE_CHECKING:
  from ..analysis.class_info import ClassInfo
  from ..analysis.ir import MethodSig
  from ..translator import Translator


def _mark_scope_variable(tr: "Translator", name: str) -> None:
  from ..translator import NameContext
  tr.scope.vars[name] = NameContext.Variable


def _mark_scope_argument(tr: "Translator", name: str) -> None:
  from ..translator import NameContext
  tr.scope.vars[name] = NameContext.Argument


def _emit_class_methods_body(tr: "Translator", info: ClassInfo):
  prev_class = tr.current_class
  prev_info = tr.class_info
  tr.current_class = info.name
  tr.class_info = info
  tr._sync_type_aliases(info)
  try:
    _emit_class_methods_body_impl(tr, info)
  finally:
    tr.current_class = prev_class
    tr.class_info = prev_info
    tr._sync_type_aliases(prev_info)

def _emit_static_property_storage_defs(tr: "Translator", info: ClassInfo) -> None:
  """``@staticproperty`` 存储 ``name__value`` → 类外 ``static`` 成员定义（C++11）。"""
  if not info.static_property_storage:
    return
  from .class_decl_emit import _emit_field_default_initializer

  qual = tr._class_method_qualifier(info)
  for field in sorted(info.static_property_storage):
    ftype = field_storage_cpp(
      info, field, fallback=cpp_ident("int") if field in INT_FIELDS else "void*",
    )
    member = info.cpp_member_name(field)
    default = info.field_defaults.get(field)
    init_suffix = ""
    if default is not None:
      init_suffix = f" = {_emit_field_default_initializer(tr, ftype, default)}"
    if info.is_template():
      tr._emit_template_prefix(info)
    tr.write_line(f"{ftype} {qual}::{member}{init_suffix};")
    tr.write_line()


def _emit_thread_local_field_defs(tr: "Translator", info: ClassInfo) -> None:
  """``T @thread_local`` → 类外 ``thread_local`` 静态成员定义（C++11）。"""
  if not getattr(info, "thread_local_fields", {}):
    return
  from .class_decl_emit import _emit_field_default_initializer

  qual = tr._class_method_qualifier(info)
  for field, stmt in info.thread_local_fields.items():
    ftype = field_storage_cpp(
      info, field, fallback=cpp_ident("int") if field in INT_FIELDS else "void*",
    )
    if info.is_template():
      ftype = tr._typename_member_alias_type(ftype, info)
    member = info.cpp_member_name(field)
    init = f"{ftype}()"
    if stmt.value is not None:
      init = _emit_field_default_initializer(tr, ftype, stmt.value)
    if info.is_template():
      tr._emit_template_prefix(info)
    tr.write_line(f"thread_local {ftype} {qual}::{member} = {init};")
    tr.write_line()


def _emit_class_properties(tr: "Translator", info: ClassInfo) -> None:
  for prop in info.properties.values():
    if prop.getter and prop.getter_sig:
      if prop.name in info.field_properties or prop.name in info.postsetter_properties:
        _emit_field_backed_property_getter(tr, info, prop.name, prop.getter_sig)
      elif not (info.is_native or has_named_decorator(prop.getter, "native")):
        _emit_property_method(
          tr,
          info,
          prop.getter,
          prop.getter_sig,
          tr._property_getter_cpp_name(info, prop.name),
          is_const=True,
        )
    if (
      prop.postsetter and prop.setter_sig and prop.postsetter_sig
      and not (info.is_native or has_named_decorator(prop.postsetter, "native"))
    ):
      _emit_postsetter_property_setter(tr, info, prop.name, prop.setter_sig)
      _emit_property_method(
        tr,
        info,
        prop.postsetter,
        prop.postsetter_sig,
        tr._property_postsetter_cpp_name(info, prop.name),
      )
    elif (
      prop.setter and prop.setter_sig
      and not (info.is_native or has_named_decorator(prop.setter, "native"))
    ):
      _emit_property_method(
        tr,
        info,
        prop.setter,
        prop.setter_sig,
        tr._property_setter_cpp_name(info, prop.name),
        descriptor_protocol_bounds=prop.descriptor_protocol_bounds,
      )
  for prop in info.static_properties.values():
    if (
      prop.getter and prop.getter_sig
      and not (info.is_native or has_named_decorator(prop.getter, "native"))
    ):
      _emit_static_property_method(
        tr,
        info,
        prop.getter,
        prop.getter_sig,
        tr._property_getter_cpp_name(info, prop.name),
      )
    if (
      prop.postsetter and prop.setter_sig and prop.postsetter_sig
      and not (info.is_native or has_named_decorator(prop.postsetter, "native"))
    ):
      _emit_postsetter_static_property_setter(tr, info, prop.name, prop.setter_sig)
      _emit_static_property_setter(
        tr,
        info,
        prop.postsetter,
        prop.postsetter_sig,
        tr._property_postsetter_cpp_name(info, prop.name),
      )
    elif (
      prop.setter and prop.setter_sig
      and not (info.is_native or has_named_decorator(prop.setter, "native"))
    ):
      _emit_static_property_setter(
        tr,
        info,
        prop.setter,
        prop.setter_sig,
        tr._property_setter_cpp_name(info, prop.name),
      )


def _emit_class_methods_body_impl(tr: "Translator", info: ClassInfo):
  if info.class_type_if_plan is not None:
    emit_class_type_if_method_bodies(tr, info)
    return
  if info.is_variant_mixin:
    return
  if info.is_enum:
    return
  if info.is_union:
    emit_union_class_impl(tr, info)
    emit_union_user_methods(tr, info)
    return
  if info.is_refcount:
    emit_refcount_class_impl(tr, info)
    emit_default_object_repr_impls(tr, info)
    _emit_operator_pystr_conversion(tr, info)
    _emit_operator_pybool_conversion(tr, info)
    _emit_operator_pyint_conversion(tr, info)
    _emit_operator_pyfloat_conversion(tr, info)
    _emit_operator_pycomplex_conversion(tr, info)
    _emit_pystr_scalar_operators(tr, info)
    tr._emit_virtual_dtor_definition(info)
    return
  _emit_static_property_storage_defs(tr, info)
  _emit_thread_local_field_defs(tr, info)
  for init, sig in zip(info.inits, info.init_sigs):
    if tr._io_skip_runtime_method(info, init):
      continue
    if has_named_decorator(init, "native"):
      continue
    _emit_method(tr, info, init, sig)
  _emit_generator_default_ctor(tr, info)
  if info.needs_auto_dtor():
    _emit_auto_dtor(tr, info)
  for name in ("__del__", "__copy__", "__move__"):
    if name in info.methods:
      m = info.methods[name]
      if tr._io_skip_runtime_method(info, m):
        continue
      _emit_method(tr, info, m, info.method_sigs[name])
  if not info.is_uncopyable:
    emit_auto_copy_move(tr, info)
  if (not info.is_uncopyable) or (info.has_move and not info.is_native):
    emit_copy_move_special_members(tr, info)
  overload_names = set(info.method_overloads.keys())
  for _name, overloads in info.method_overload_sigs.items():
    for method, sig in zip(info.method_overloads[_name], overloads):
      if method.name == "__init__":
        continue
      if tr._skip_runtime_method_emit(info, method):
        continue
      _emit_method(tr, info, method, sig)
  for method in info.methods.values():
    if method.name in ("__del__", "__copy__", "__move__"):
      continue
    if method.name in overload_names:
      continue
    if tr._skip_runtime_method_emit(info, method):
      continue
    sig = info.method_sig_for(method)
    if sig is not None:
      _emit_method(tr, info, method, sig)
  _emit_class_properties(tr, info)
  if info.repr_aliases_str and "__repr__" in info.method_sigs:
    _emit_repr_alias_method(tr, info)
  emit_default_object_repr_impls(tr, info)
  emit_stdlib_class_runtime(tr, info.name)
  from .type_id_emit import emit_type_id_impls

  emit_type_id_impls(tr, info)
  _emit_operator_pystr_conversion(tr, info)
  _emit_operator_pybool_conversion(tr, info)
  _emit_operator_pyint_conversion(tr, info)
  _emit_operator_pyfloat_conversion(tr, info)
  _emit_operator_pycomplex_conversion(tr, info)
  _emit_pystr_scalar_operators(tr, info)
  tr._emit_virtual_dtor_definition(info)

def _emit_repr_alias_method(tr: "Translator", info: ClassInfo) -> None:
  """``__repr__ = __str__`` → ``return __str__();``。"""
  sig = info.method_sigs.get("__repr__")
  if sig is None:
    return
  with tr._method_emit_context(info, sig), tr._use_source():
    mcpp = info.cpp_member_name("__repr__")
    qual = (
      f"{info.cpp_specialization()}::{mcpp}"
      if info.is_template()
      else f"{info.cpp_name()}::{mcpp}"
    )
    ret_def = method_impl_return_cpp(tr, sig, info)
    params_def = tr._typename_member_alias_params(sig.params_def, info)
    header = format_fn_sig(ret_def, sig.ret_trail, qual, params_def)
    header = header + tr._method_const_suffix(sig, "__repr__")
    if info.is_template():
      tr._emit_template_prefix(info)
    if sig.func_ft.template_names:
      tr._emit_function_template_prefix(sig.func_ft)
    with tr._use_block(header):
      tr.write_line("return __str__();")
    tr.write_line()

def _emit_operator_pystr_conversion(tr: "Translator", info: ClassInfo) -> None:
  if not has_effective_str(info, tr) or info.name == "str":
    return
  ps = cpp_ident("str")
  cpp = info.cpp_name()
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::operator {ps}() const"):
      tr.write_line("return __str__();")

def _emit_operator_pybool_conversion(tr: "Translator", info: ClassInfo) -> None:
  """``__bool__`` → ``explicit operator PyBool()``；调用侧经 ``static_cast<PyBool>``。"""
  if not has_effective_bool(info) or info.name == "TextIOWrapper":
    return
  pb = cpp_ident("bool")
  cpp = info.cpp_name()
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::operator {pb}() const"):
      tr.write_line("return __bool__();")

def _emit_operator_pyint_conversion(tr: "Translator", info: ClassInfo) -> None:
  if not has_effective_int(info):
    return
  pi = cpp_ident("int")
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::operator {pi}() const"):
      tr.write_line("return __int__();")

def _emit_operator_pyfloat_conversion(tr: "Translator", info: ClassInfo) -> None:
  if not has_effective_float(info):
    return
  pf = cpp_ident("float")
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::operator {pf}() const"):
      tr.write_line("return __float__();")

def _emit_operator_pycomplex_conversion(tr: "Translator", info: ClassInfo) -> None:
  if not has_effective_complex(info):
    return
  cpx = complex_operator_cpp_type(info)
  if not cpx:
    return
  cpx = tr._typename_member_alias_type(cpx, info)
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::operator {cpx}() const"):
      tr.write_line("return __complex__();")

def _emit_pystr_scalar_operators(tr: "Translator", info: ClassInfo) -> None:
  """``PyStr``：``int(s)`` / ``float(s)`` → ``static_cast``（无 ``__int__`` / ``__float__`` 成员）。"""
  if info.name != "str" or not info.module_path.replace("\\", "/").endswith("text/str"):
    return
  from ..codegen.expand_py2cpp_template import expand_template

  qual = tr._class_method_qualifier(info)
  pi = cpp_ident("int")
  pf = cpp_ident("float")
  pyint_body = expand_template("text/+str_operator_pyint.inl", apply_allman=True).strip()
  pyfloat_body = expand_template("text/+str_operator_pyfloat.inl", apply_allman=True).strip()
  with tr._method_emit_context(info), tr._use_source():
    with tr._use_block(f"{qual}::operator {pi}() const"):
      for line in pyint_body.splitlines():
        tr.write_line(line)
    tr.write_line()
    with tr._use_block(f"{qual}::operator {pf}() const"):
      for line in pyfloat_body.splitlines():
        tr.write_line(line)
    tr.write_line()

def _emit_auto_dtor(tr: "Translator", info: ClassInfo) -> None:
  cpp = info.cpp_name()
  qual = tr._class_method_qualifier(info)
  with tr._method_emit_context(info), tr._use_source():
    if info.is_template():
      tr._emit_template_prefix(info)
    with tr._use_block(f"{qual}::~{cpp}()"):
      for field, (elem, kind) in info.owned_fields.items():
        fn = "freeArray" if kind == "freeArray" else "free"
        with tr._use_block(f"if ((this->{field} != nullptr))"):
          tr.write_line(f"{fn}<{elem}>(this->{field});")
    tr.write_line()

def _emit_method(tr: "Translator", info: ClassInfo, method: ast.FunctionDef, msig: MethodSig):
  if method.name == "__setitem__":
    from .setitem_emit import (
      canonical_const_lref_param,
      emit_setitem_forwarders,
      params_with_last,
      parse_setitem_value_param,
    )

    parsed = parse_setitem_value_param(msig.params_def)
    if parsed is not None and parsed.ref != "value":
      canon_def = params_with_last(parsed.prefix, canonical_const_lref_param(parsed))
      _emit_method_impl(tr, info, method, msig, params_def_override=canon_def)
      cls_qual = tr._class_method_qualifier(info)
      mcpp = info.cpp_member_name(method.name)
      ret_def = method_impl_return_cpp(tr, msig, info)
      parsed_inl = parse_setitem_value_param(
        tr._typename_member_alias_params(canon_def, info),
      )
      if parsed_inl is not None:
        if info.is_template():
          tr._emit_template_prefix(info)
        from ..analysis.variadic_template import typevar_tuple_names_for_emit

        if (
          (
            msig.func_ft.template_names
            or typevar_tuple_names_for_emit(msig.func_ft, msig.variadic_template)
          )
          and not (info.name == "array" and method.name == "__copy__")
        ):
          tr._emit_function_template_prefix(
            msig.func_ft,
            default_constraint=False,
            variadic_template=msig.variadic_template,
          )
        emit_setitem_forwarders(
          tr.write_line,
          qual=cls_qual,
          ret_lead=ret_def,
          ret_trail=msig.ret_trail,
          mcpp=mcpp,
          parsed=parsed_inl,
          const_suffix=tr._method_const_suffix(msig, method.name),
        )
      return
  _emit_method_impl(tr, info, method, msig)

def _emit_method_impl(
  tr: "Translator",
  info: ClassInfo,
  method: ast.FunctionDef,
  msig: MethodSig,
  *,
  params_def_override: str | None = None,
):
  with tr._method_emit_context(info, msig), tr._use_source():
    cls_qual = tr._class_method_qualifier(info)
    params_def = params_def_override or msig.params_def
    if method.name == "__init__":
      from .final_emit import emit_final_ctor_init_suffix

      init_suffix = emit_final_ctor_init_suffix(tr, info, method)
      params_def = tr._typename_member_alias_params(params_def, info)
      sig = f"{cls_qual}::{info.cpp_name()}({params_def}){init_suffix}"
    elif method.name == "__del__":
      qual = f"{cls_qual}::~{info.cpp_name()}"
      sig = f"{qual}()"
    else:
      mcpp = info.cpp_member_name(method.name)
      qual = f"{cls_qual}::{mcpp}"
      ret_def = method_impl_return_cpp(tr, msig, info)
      params_def = tr._typename_member_alias_params(params_def, info)
      sig = format_fn_sig(ret_def, msig.ret_trail, qual, params_def)
      sig = sig + tr._method_const_suffix(msig, method.name)
      sig = sig + fn_noexcept_suffix(msig.is_noexcept)
    prev_method = tr.current_method
    tr.current_method = method
    try:
      with tr._use_self_type(info), tr._use_scope(method) as scope:
        for arg in method.args.args:
          if arg.arg == "self":
            _mark_scope_argument(tr, arg.arg)
            continue
          _mark_scope_argument(tr, arg.arg)
          bind_scope_param(scope, arg.arg, msig)
        if msig.variadic_template is not None:
          vt = msig.variadic_template
          bind_scope_param(scope, vt.param_name, msig)
        elif msig.vararg_pack is not None:
          vp = msig.vararg_pack
          bind_scope_vararg(scope, vp.param_name, vp.cpp_type, classes=tr.classes)
        if msig.lazy_params:
          scope.lazy_params = dict(msig.lazy_params)
        if info.is_template():
          tr._emit_template_prefix(info)
        type_if_plan = plan_type_if_chain(tr, method)
        type_if_pick = None
        if type_if_plan is not None:
          type_if_pick = emit_type_if_dispatch(
            tr, type_if_plan, msig,
          )
        if msig.variadic_template is not None:
          from .variadic_template_emit import prescan_emit_vt_loop_structs

          prescan_emit_vt_loop_structs(
            tr, method, msig.variadic_template, param_types=method_param_types_map(msig),
          )
        from ..analysis.variadic_template import typevar_tuple_names_for_emit

        if (
          (
            msig.func_ft.template_names
            or typevar_tuple_names_for_emit(msig.func_ft, msig.variadic_template)
          )
          and not (info.name == "array" and method.name == "__copy__")
        ):
          tr._emit_function_template_prefix(
            msig.func_ft,
            default_constraint=False,
            variadic_template=msig.variadic_template,
          )
        with tr._use_block(sig):
          bounds = info.descriptor_method_protocol_bounds.get(method.name)
          if bounds:
            value_cpp = tr._descriptor_validate_value_cpp_type(msig)
            if value_cpp:
              tr._emit_descriptor_protocol_static_asserts(
                value_cpp, bounds, node=method
              )
          for line in emit_move_state_prologue_lines(info, method):
            tr.write_line(line)
          if msig.lazy_params:
            from .lazy_param_emit import emit_lazy_param_prologue

            emit_lazy_param_prologue(tr, msig.lazy_params)
          if (info.module_path, info.name, method.name) in tr.generator_methods:
            emit_generator_next(tr, method.body, class_info=info)
          else:
            tr._emit_generic_body_or_type_if(
              method,
              msig,
              type_if_plan=type_if_plan,
              type_if_pick=type_if_pick,
            )
          for line in emit_move_state_epilogue_lines(info, method):
            tr.write_line(line)
    finally:
      tr.current_method = prev_method
    tr.write_line()

def _emit_field_backed_property_getter(
  tr: "Translator",
  info: ClassInfo,
  name: str,
  msig: MethodSig,
):
  cpp_field = info.cpp_member_name(storage_field_for(name))
  getter_cpp = tr._property_getter_cpp_name(info, name)
  qual = (
    f"{info.cpp_specialization()}::{getter_cpp}"
    if info.is_template()
    else f"{info.cpp_name()}::{getter_cpp}"
  )
  ret_def = method_impl_return_cpp(tr, msig, info)
  if info.is_template():
    tr._emit_template_prefix(info)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit

    if msig.func_ft.template_names or typevar_tuple_names_for_emit(
      msig.func_ft, msig.variadic_template,
    ):
      tr._emit_function_template_prefix(
        msig.func_ft,
        default_constraint=False,
        variadic_template=msig.variadic_template,
      )
    tr._write_doc_lines(msig.doc_lines)
  ret = sig_return_storage_cpp(msig).rstrip()
  if ret and not ret.endswith("&") and not ret.endswith("*"):
    ret = field_property_getter_return_ref(ret_def or ret)
  else:
    ret = f"{ret_def}{msig.ret_trail}".strip() or ret
  tr.write_line(f"{ret} {qual}() const {{ return {cpp_field}; }}")
  tr.write_line()


def _emit_postsetter_property_setter(
  tr: "Translator",
  info: ClassInfo,
  name: str,
  msig: MethodSig,
):
  from ..analysis.ir import cpp_param

  cpp_field = info.cpp_member_name(storage_field_for(name))
  setter_cpp = tr._property_setter_cpp_name(info, name)
  postset_cpp = tr._property_postsetter_cpp_name(info, name)
  qual = (
    f"{info.cpp_specialization()}::{setter_cpp}"
    if info.is_template()
    else f"{info.cpp_name()}::{setter_cpp}"
  )
  if info.is_template():
    tr._emit_template_prefix(info)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit

    if msig.func_ft.template_names or typevar_tuple_names_for_emit(
      msig.func_ft, msig.variadic_template,
    ):
      tr._emit_function_template_prefix(
        msig.func_ft,
        default_constraint=False,
        variadic_template=msig.variadic_template,
      )
  tr._write_doc_lines(msig.doc_lines)
  tr.write_line(f"void {qual}({msig.params_decl}) {{")
  tr.write_line(f"  this->{cpp_field} = {cpp_param('value')};")
  tr.write_line(f"  this->{postset_cpp}({cpp_param('value')});")
  tr.write_line("}")
  tr.write_line()


def _emit_postsetter_static_property_setter(
  tr: "Translator",
  info: ClassInfo,
  name: str,
  msig: MethodSig,
):
  from ..analysis.ir import cpp_param

  cpp_field = info.cpp_member_name(storage_field_for(name))
  setter_cpp = tr._property_setter_cpp_name(info, name)
  postset_cpp = tr._property_postsetter_cpp_name(info, name)
  qual = f"{info.cpp_name()}::{setter_cpp}"
  if info.is_template():
    tr._emit_template_prefix(info)
  tr._write_doc_lines(msig.doc_lines)
  tr.write_line(f"void {qual}({msig.params_decl}) {{")
  tr.write_line(f"  {info.cpp_name()}::{cpp_field} = {cpp_param('value')};")
  tr.write_line(f"  {info.cpp_name()}::{postset_cpp}({cpp_param('value')});")
  tr.write_line("}")
  tr.write_line()


def _emit_property_method(
  tr: "Translator",
  info: ClassInfo,
  method: ast.FunctionDef,
  msig: MethodSig,
  cpp_name: str,
  *,
  is_const: bool = False,
  descriptor_protocol_bounds: tuple[str, ...] = (),
):
  with tr._method_emit_context(info), tr._use_source():
    qual = f"{info.cpp_specialization()}::{cpp_name}" if info.is_template() else f"{info.cpp_name()}::{cpp_name}"
    ret_def = method_impl_return_cpp(tr, msig, info)
    params_def = tr._typename_member_alias_params(msig.params_def, info)
    if is_const:
      sig = format_fn_sig(ret_def, msig.ret_trail, qual, "") + " const"
      sig = sig + fn_noexcept_suffix(msig.is_noexcept)
    else:
      sig = format_fn_sig(ret_def, msig.ret_trail, qual, params_def)
      sig = sig + fn_noexcept_suffix(msig.is_noexcept)
    if info.is_template():
      tr._emit_template_prefix(info)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit

    if msig.func_ft.template_names or typevar_tuple_names_for_emit(
      msig.func_ft, msig.variadic_template,
    ):
      tr._emit_function_template_prefix(
        msig.func_ft,
        default_constraint=False,
        variadic_template=msig.variadic_template,
      )
    prev_method = tr.current_method
    tr.current_method = method
    try:
      with tr._use_self_type(info), tr._use_scope(method) as scope:
        for arg in method.args.args:
          if arg.arg == "self":
            _mark_scope_argument(tr, arg.arg)
            continue
          _mark_scope_argument(tr, arg.arg)
          bind_scope_param(scope, arg.arg, msig)
        if msig.variadic_template is not None:
          vt = msig.variadic_template
          bind_scope_param(scope, vt.param_name, msig)
        elif msig.vararg_pack is not None:
          vp = msig.vararg_pack
          bind_scope_vararg(scope, vp.param_name, vp.cpp_type, classes=tr.classes)
        with tr._use_block(sig):
          if descriptor_protocol_bounds:
            value_cpp = tr._descriptor_validate_value_cpp_type(msig)
            if value_cpp:
              tr._emit_descriptor_protocol_static_asserts(
                value_cpp, descriptor_protocol_bounds, node=method
              )
          tr._emit_body(method.body)
    finally:
      tr.current_method = prev_method
    tr.write_line()

def _emit_static_property_method(
  tr: "Translator",
  info: ClassInfo,
  method: ast.FunctionDef,
  msig: MethodSig,
  cpp_name: str,
):
  with tr._method_emit_context(info), tr._use_source():
    qual = tr._class_method_qualifier(info)
    ret_def = method_impl_return_cpp(tr, msig, info)
    sig = format_fn_sig(ret_def, msig.ret_trail, f"{qual}::{cpp_name}", "")
    if info.is_template():
      tr._emit_template_prefix(info)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit

    if msig.func_ft.template_names or typevar_tuple_names_for_emit(
      msig.func_ft, msig.variadic_template,
    ):
      tr._emit_function_template_prefix(
        msig.func_ft,
        default_constraint=False,
        variadic_template=msig.variadic_template,
      )
    prev_method = tr.current_method
    tr.current_method = method
    try:
      with tr._use_self_type(info), tr._use_scope(method) as scope:
        for arg in method.args.args:
          if arg.arg in ("self", "cls"):
            continue
          _mark_scope_argument(tr, arg.arg)
          bind_scope_param(scope, arg.arg, msig)
        with tr._use_block(sig):
          tr._emit_body(method.body)
    finally:
      tr.current_method = prev_method
    tr.write_line()


def _emit_static_property_setter(
  tr: "Translator",
  info: ClassInfo,
  method: ast.FunctionDef,
  msig: MethodSig,
  cpp_name: str,
):
  with tr._method_emit_context(info), tr._use_source():
    qual = f"{info.cpp_name()}::{cpp_name}"
    params_def = tr._typename_member_alias_params(msig.params_def, info)
    sig = format_fn_sig("void", "", qual, params_def)
    if info.is_template():
      tr._emit_template_prefix(info)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit

    if msig.func_ft.template_names or typevar_tuple_names_for_emit(
      msig.func_ft, msig.variadic_template,
    ):
      tr._emit_function_template_prefix(
        msig.func_ft,
        default_constraint=False,
        variadic_template=msig.variadic_template,
      )
    prev_method = tr.current_method
    tr.current_method = method
    try:
      with tr._use_self_type(info), tr._use_scope(method) as scope:
        for arg in method.args.args:
          if arg.arg in ("self", "cls"):
            continue
          _mark_scope_argument(tr, arg.arg)
          bind_scope_param(scope, arg.arg, msig)
        with tr._use_block(sig):
          tr._emit_body(method.body)
    finally:
      tr.current_method = prev_method
    tr.write_line()


def _generator_host_init(info: ClassInfo) -> str | None:
  """类方法生成器/协程 ``__init__(self, host)`` → 宿主 C++ 类型（默认委托构造）。"""
  from ..passes.generators import COROUTINE_SUFFIX, GENERATOR_SUFFIX, _field_name

  if not (
    info.name.endswith(GENERATOR_SUFFIX) or info.name.endswith(COROUTINE_SUFFIX)
  ):
    return None
  host_field = _field_name("self")
  if host_field not in info.fields:
    return None
  if not info.inits:
    return None
  init = info.inits[0]
  args = [a for a in init.args.args if a.arg != "self"]
  if len(args) != 1 or args[0].arg != "host":
    return None
  return field_storage_cpp(info, host_field)


def _coroutine_param_default_ctor_needed(info: ClassInfo) -> bool:
  """带形参的 ``*_coroutine`` 须有默认构造，供父协程 ``_yf*_it`` 成员占位（不含 ``*_generator``）。"""
  from ..passes.generators import COROUTINE_SUFFIX

  if not info.name.endswith(COROUTINE_SUFFIX):
    return False
  if _generator_host_init(info):
    return False
  if not info.inits:
    return False
  init = info.inits[0]
  params = [a for a in init.args.args if a.arg not in ("self", "host")]
  return bool(params)


def _emit_coroutine_param_default_ctor(tr: "Translator", info: ClassInfo) -> None:
  if not _coroutine_param_default_ctor_needed(info):
    return
  from ..analysis.type_emit import class_body_cpp, field_type_node
  from ..analysis.ir import cpp_param, strip_cpp_ref
  from ..analysis.type_pred import is_erased_protocol_storage_type

  init = info.inits[0]
  cpp = info.cpp_name()
  with tr._use_source():
    tr.write_line(f"{info.cpp_specialization()}::{cpp}()")
    tr.write_line("{")
    tr.indent_level += 1
    tr.write_line("this->_state = 0;")
    tr.write_line("this->_send_pending = false;")
    tr.write_line("this->_send_value = ::py2cpp::core::none::PyNone();")
    for fname in info.fields:
      if fname.endswith("_active") and (
        fname.startswith("_yf") or fname.startswith("_for")
      ):
        tr.write_line(f"this->{cpp_param(fname)} = false;")
    for arg in init.args.args:
      if arg.arg in ("self", "host"):
        continue
      ft_node = field_type_node(info, arg.arg)
      if is_erased_protocol_storage_type(ft_node):
        ft_base = strip_cpp_ref(class_body_cpp(ft_node))
        tr.write_line(f"this->{cpp_param(arg.arg)} = {ft_base}();")
      else:
        ft = class_body_cpp(ft_node) if ft_node else field_storage_cpp(info, arg.arg)
        if ft and ft in tr.classes:
          tr.write_line(f"this->{cpp_param(arg.arg)} = {ft}();")
        else:
          tr.write_line(f"this->{cpp_param(arg.arg)} = 0;")
    tr.indent_level -= 1
    tr.write_line("}")
    tr.write_line()


def _emit_generator_default_ctor(tr: "Translator", info: ClassInfo) -> None:
  host_ty = _generator_host_init(info)
  if host_ty:
    cpp = info.cpp_name()
    with tr._use_source():
      tr.write_line(
        f"{info.cpp_specialization()}::{cpp}() : {cpp}({host_ty}()) {{}}"
      )
      tr.write_line()
  _emit_coroutine_param_default_ctor(tr, info)

