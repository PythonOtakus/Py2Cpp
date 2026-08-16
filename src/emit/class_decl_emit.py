"""类声明 / 协议 traits / 字段与方法声明 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
import textwrap
from typing import TYPE_CHECKING
from ..analysis.type_pred import (
  is_byte_heap_array_type,
  is_byte_type,
  is_bytes_type,
  is_char_type,
  is_char_heap_array_type,
  is_list_type,
  is_stack_array_type,
)
from ..analysis.ir import INT_FIELDS, cpp_ident, cpp_stack_array_var_decl, field_property_getter_return_ref, field_property_getter_returns_mutable_ref, format_fn_sig, fn_noexcept_suffix, is_stub_function_body, strip_cpp_ref
from ..passes.descriptors import storage_field_for
from ..passes.generators import GENERATOR_SUFFIX
from ..passes.class_type_if import emit_class_type_if_declaration
from ..passes.protocol import is_protocol_instance_method, is_protocol_static_virtual_method
from ..analysis.type_emit import class_decl_return_cpp, field_decl_cpp, field_storage_cpp, field_storage_values, sig_return_storage_cpp

def sort_module_classes_for_declaration(classes: list[ClassInfo]) -> list[ClassInfo]:
    """生成器嵌套成员（如 ``Path_glob_generator::_for0_it``）须完整定义在前。"""
    gen_names = [c.name for c in classes if c.name.endswith(GENERATOR_SUFFIX)]
    if not gen_names:
        return classes
    by_name = {c.name: c for c in classes}
    deps: dict[str, set[str]] = {n: set() for n in gen_names}
    for name in gen_names:
        info = by_name[name]
        for ft in field_storage_values(info):
            if not ft:
                continue
            dep = strip_cpp_ref(ft).strip()
            if dep in deps and dep != name:
                deps[name].add(dep)
    ordered: list[str] = []
    pending = set(gen_names)
    while pending:
        ready = sorted((n for n in pending if not deps[n] - set(ordered)))
        if not ready:
            ordered.extend(sorted(pending))
            break
        ordered.extend(ready)
        pending -= set(ready)
    non_gens = [c for c in classes if c.name not in deps]
    return non_gens + [by_name[n] for n in ordered]
from ..constant.stdlib_layout import stdlib_module_path
from .dunder_ops_emit import emit_class_operator_overloads
from .enum_emit import emit_enum_declaration, emit_enum_support
from ..codegen.class_header_inject import class_header_inject_blobs
from ..constant.stdlib_layout import RUNTIME_PKG
from .object_repr_emit import complex_operator_cpp_type, emit_default_object_repr_decls, has_effective_bool, has_effective_complex, has_effective_float, has_effective_int, has_effective_str
from .copy_move_emit import is_frozen_dataclass
from ..codegen.protocol_traits_gen import compare_ops_no_pybool_only_helper_lines, protocol_module_preamble_lines, protocol_traits_lines
from ..codegen.expand_py2cpp_template import expand_exception_pystr_ctor, expand_template
from ..analysis.stubs.class_stubs import load_stdlib_exception_types

_EXCEPTION_REPR_DECL_SKIP = frozenset({"ExcTypeUnion"})


def _emit_exception_repr_decl(tr: "Translator", info: ClassInfo) -> None:
  mp = info.module_path.replace("\\", "/")
  if not mp.endswith("core/exceptions"):
    return
  if info.name in _EXCEPTION_REPR_DECL_SKIP:
    return
  ps = cpp_ident("str")
  if info.name == "Exception":
    tr.write_line(f"virtual {ps} __repr__() const;")
  elif info.name in load_stdlib_exception_types():
    tr.write_line(f"{ps} __repr__() const override;")
from ..emit.layout_config_emit import RUNTIME_PREFIX
from ..constant.class_header_inject import CLASS_HEADER_INJECT_SPECS
if TYPE_CHECKING:
    from ..analysis.class_info import ClassInfo
    from ..analysis.ir import MethodSig
    from ..translator import Translator

# 除拷贝/移动构造外，用户类声明一律 ``explicit``（conversion 见 ``explicit operator Py*``）。
_EXPLICIT = "explicit "

def _emit_class_type_param_usings(tr: 'Translator', info: ClassInfo) -> None:
    from ..analysis.ir import cpp_nttp_value_type_name, cpp_type_param_template_name
    nttp = getattr(info, 'type_param_nttp', None) or {}
    for p in info.type_params:
        if p in nttp:
            val_cpp = cpp_nttp_value_type_name(nttp[p])
            tr.write_line(
                f'static constexpr {val_cpp} {p} = {cpp_type_param_template_name(p)};'
            )
            continue
        tr.write_line(f'using {p} = {cpp_type_param_template_name(p)};')
    if info.typevar_tuple:
        tpl = info.typevar_tuple
        tr.write_line(f'using {tpl} = {cpp_type_param_template_name(tpl)};')

def _emit_class_type_usings(tr: 'Translator', info: ClassInfo) -> None:
    if info.is_protocol:
        return
    if not info.type_alias_list:
        return
    from ..passes.type_conditional import emit_conditional_type_alias, plan_conditional_alias
    for alias in info.type_alias_list:
        if alias.member_constraint:
            continue
        if alias.is_conditional:
            plan = plan_conditional_alias(tr, alias)
            emit_conditional_type_alias(tr, alias, plan)
            continue
        tr._emit_type_alias_using(alias, tr._type_alias_rhs_cpp(alias, info))

def _class_template_param_decls_plain(tr: 'Translator', info: ClassInfo) -> list[str]:
    """偏特化 ``template<…>`` 头：无默认实参（C++ 部分专用化禁止默认值）。"""
    from ..analysis.ir import cpp_nttp_value_type_name, cpp_type_param_template_name
    nttp = getattr(info, 'type_param_nttp', None) or {}
    parts: list[str] = []
    for p in info.type_params:
        cpp_p = cpp_type_param_template_name(p)
        val_ty = nttp.get(p)
        if val_ty is not None:
            val_cpp = cpp_nttp_value_type_name(val_ty)
            parts.append(f'{val_cpp} {cpp_p}')
        else:
            parts.append(f'typename {cpp_p}')
    if info.typevar_tuple:
        parts.append(f'typename... {cpp_type_param_template_name(info.typevar_tuple)}')
    return parts

def _emit_class_decorator_check_specialization(tr: 'Translator', info: ClassInfo, trait: str) -> None:
    """``@boxing`` / ``@copyable`` 类标记 ``py2cpp_*_check``（全局特化，须在 ``refcount.h`` 之后）。"""
    if info.is_protocol or info.is_mixin:
        return
    if trait == 'boxing':
        if info.is_native or not info.is_boxing:
            return
    elif trait == 'copyable':
        if not info.is_copyable:
            return
    else:
        return
    from ..analysis.module_namespace import namespace_qualifier_for_module
    from ..analysis.ir import cpp_type_param_template_name
    name = info.cpp_name()
    ns = namespace_qualifier_for_module(info.module_path)
    fq_base = f'{ns}::{name}' if ns else name
    all_params = list(info.type_params)
    if all_params or info.typevar_tuple:
        tpl_header = ', '.join(_class_template_param_decls_plain(tr, info))
        spec_parts = [cpp_type_param_template_name(p) for p in all_params]
        if info.typevar_tuple:
            spec_parts.append(f'...{cpp_type_param_template_name(info.typevar_tuple)}')
        spec_args = ', '.join(spec_parts)
        fq = f'{fq_base}<{spec_args}>'
        tpl_prefix = f'template<{tpl_header}> '
    else:
        fq = fq_base
        tpl_prefix = 'template<> '
    close = ' >' if fq.endswith('>') else '>'
    line = f'{tpl_prefix}struct py2cpp_{trait}_check<{fq}{close} : std::true_type {{}};'
    tr.per_module_global_traits_lines.setdefault(info.module_path, []).append(line)

def _emit_class_boxing_check_specializations(tr: 'Translator', info: ClassInfo) -> None:
    _emit_class_decorator_check_specialization(tr, info, 'boxing')

def _emit_class_copyable_check_specializations(tr: 'Translator', info: ClassInfo) -> None:
    _emit_class_decorator_check_specialization(tr, info, 'copyable')

def _emit_class_oneof_asserts(tr: 'Translator', info: ClassInfo) -> None:
    from ..analysis.ir import cpp_oneof_static_assert_expr, cpp_type_for_oneof_alternative
    from .compile_diagnostic_emit import compile_diag_c_utf8_literal, compile_diag_type_param_oneof

    emitted: set[tuple[str, tuple[str, ...]]] = set()
    loc_prefix = tr._compile_diag_loc_prefix(info.node)
    nttp = getattr(info, 'type_param_nttp', None) or {}
    for p in info.type_params:
        if p in nttp:
            continue
        alts = info.type_param_oneof_constraints.get(p, ())
        if not alts or (p, alts) in emitted:
            continue
        msg = compile_diag_type_param_oneof(p, alts, loc_prefix=loc_prefix)
        expr = cpp_oneof_static_assert_expr(p, alts)
        tr.write_line(f'static_assert({expr}, {compile_diag_c_utf8_literal(msg)});')
        emitted.add((p, alts))
    for concrete, alts in info.concrete_oneof_constraints.items():
        key = (concrete, alts)
        if key in emitted:
            continue
        cpp_t = cpp_type_for_oneof_alternative(concrete)
        msg = compile_diag_type_param_oneof(concrete, alts, loc_prefix=loc_prefix)
        expr = cpp_oneof_static_assert_expr(cpp_t, alts)
        tr.write_line(f'static_assert({expr}, {compile_diag_c_utf8_literal(msg)});')
        emitted.add(key)
    for alias in info.type_alias_list:
        for p, alts in alias.type_param_oneof_constraints.items():
            if (p, alts) in emitted:
                continue
            msg = compile_diag_type_param_oneof(p, alts, loc_prefix=loc_prefix)
            expr = cpp_oneof_static_assert_expr(p, alts)
            tr.write_line(f'static_assert({expr}, {compile_diag_c_utf8_literal(msg)});')
            emitted.add((p, alts))


def _emit_class_constraint_asserts(tr: 'Translator', info: ClassInfo) -> None:
    from .compile_diagnostic_emit import compile_diag_cpp_string, compile_diag_type_param_decorator, compile_diag_type_param_protocol
    emitted: set[tuple[str, str]] = set()
    loc_prefix = tr._compile_diag_loc_prefix(info.node)
    nttp = getattr(info, 'type_param_nttp', None) or {}
    for p in info.type_params:
        if p in nttp:
            continue
        for bound in info.type_param_constraints.get(p, ()):
            if (p, bound) in emitted:
                continue
            msg = compile_diag_type_param_protocol(p, bound, loc_prefix=loc_prefix)
            from .compile_diagnostic_emit import compile_diag_c_utf8_literal
            tr.write_line(f'static_assert(::{bound}_check<{p}>::value, {compile_diag_c_utf8_literal(msg)});')
            emitted.add((p, bound))
        for dec in getattr(info, 'type_param_decorator_constraints', {}).get(p, ()):
            key = (p, f'@{dec}')
            if key in emitted:
                continue
            msg = compile_diag_type_param_decorator(p, dec, loc_prefix=loc_prefix)
            from .compile_diagnostic_emit import compile_diag_c_utf8_literal
            tr.write_line(f'static_assert(py2cpp_{dec}_check<{p}>::value, {compile_diag_c_utf8_literal(msg)});')
            emitted.add(key)
    for alias in info.type_alias_list:
        for p, bounds in alias.type_param_constraints.items():
            for bound in bounds:
                if (p, bound) in emitted:
                    continue
                msg = compile_diag_type_param_protocol(p, bound, loc_prefix=loc_prefix)
                from .compile_diagnostic_emit import compile_diag_c_utf8_literal
                tr.write_line(f'static_assert(::{bound}_check<{p}>::value, {compile_diag_c_utf8_literal(msg)});')
                emitted.add((p, bound))

def _protocol_method_specs(tr: 'Translator', info: ClassInfo) -> list[tuple[str, str]]:
    """协议实例方法 ``(名, 返回 C++ 类型)``；合并父协议声明。"""
    assert tr.type_parser is not None
    merged: dict[str, str] = {}

    def collect(cls_info: ClassInfo) -> None:
        for base_name in cls_info.bases:
            parent = tr.classes.get(base_name)
            if parent and parent.is_protocol and (parent.module_path == cls_info.module_path):
                collect(parent)
        tr.type_parser.set_type_aliases(cls_info.type_aliases, use_as_cpp_name=True)
        tp = set(cls_info.type_params)
        for stmt in cls_info.node.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue
            if not is_protocol_instance_method(stmt, cls_info):
                continue
            ret_cpp = ''
            if stmt.returns is not None:
                ret_cpp = tr._parse_type(stmt.returns, tp).strip()
            merged[stmt.name] = ret_cpp
    collect(info)
    return list(merged.items())

def _protocol_static_method_specs(tr: 'Translator', info: ClassInfo) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    """协议静态虚方法 ``(名, 返回 C++ 类型, 形参 C++ 类型…, 方法级 TypeVar…)``。"""
    assert tr.type_parser is not None
    merged: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {}

    def method_type_params(stmt: ast.FunctionDef) -> tuple[str, ...]:
        out: list[str] = []
        for p in getattr(stmt, 'type_params', None) or ():
            if isinstance(p, ast.TypeVar):
                out.append(p.name)
        return tuple(out)

    def param_cpp_types(stmt: ast.FunctionDef, tp: set[str]) -> tuple[str, ...]:
        out: list[str] = []
        for arg in stmt.args.args:
            if arg.arg == 'self':
                continue
            if arg.annotation is None:
                out.append('void')
            else:
                out.append(tr._parse_type(arg.annotation, tp).strip())
        return tuple(out)

    def collect(cls_info: ClassInfo) -> None:
        for base_name in cls_info.bases:
            parent = tr.classes.get(base_name)
            if parent and parent.is_protocol and (parent.module_path == cls_info.module_path):
                collect(parent)
        tr.type_parser.set_type_aliases(cls_info.type_aliases, use_as_cpp_name=True)
        tp = set(cls_info.type_params)
        for stmt in cls_info.node.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue
            if not is_protocol_static_virtual_method(stmt):
                continue
            ret_cpp = ''
            if stmt.returns is not None:
                ret_cpp = tr._parse_type(stmt.returns, tp).strip()
            merged[stmt.name] = (ret_cpp, param_cpp_types(stmt, tp), method_type_params(stmt))
    collect(info)
    return [(name, ret, params, mtparams) for name, (ret, params, mtparams) in merged.items()]

def _protocol_member_specs(tr: 'Translator', info: ClassInfo) -> list[tuple[ProtocolMemberConstraint, str]]:
    """合并父协议成员约束：``name: T = ...``、``@property``、``type Element = ...``。"""
    from ..analysis.ir import ProtocolMemberConstraint
    assert tr.type_parser is not None
    merged: dict[str, tuple[ProtocolMemberConstraint, str]] = {}

    def ret_cpp_for(ann: ast.expr | None, type_params: set[str]) -> str:
        if ann is None:
            return ''
        return tr._parse_type(ann, type_params).strip()

    def collect(cls_info: ClassInfo) -> None:
        for base_name in cls_info.bases:
            parent = tr.classes.get(base_name)
            if parent and parent.is_protocol and (parent.module_path == cls_info.module_path):
                collect(parent)
        tp = set(cls_info.type_params)
        tr.type_parser.set_type_aliases(cls_info.type_aliases, use_as_cpp_name=False)
        for alias in cls_info.type_alias_list:
            if alias.member_constraint:
                spec = ProtocolMemberConstraint(alias.name, 'type_alias')
                merged[alias.name] = (spec, '')
        for member in cls_info.protocol_members:
            merged[member.name] = (member, ret_cpp_for(member.annotation, tp))
    collect(info)
    return list(merged.values())

def _emit_module_protocol_traits(tr: 'Translator', module_path: str) -> None:
    protocols = sorted((info for info in tr.classes.values() if info.is_protocol and info.module_path == module_path), key=lambda info: info.name)
    if not protocols:
        return
    tr.write_line('#include <type_traits>')
    tr.write_line('#include <utility>')
    for line in protocol_module_preamble_lines():
        tr.write_line(line)
    tr.write_line()
    if any((info.name in ('ComparableType', 'EquatableType') for info in protocols)):
        for line in compare_ops_no_pybool_only_helper_lines():
            tr.write_line(line)
        tr.write_line()
    for info in protocols:
        member_specs = _protocol_member_specs(tr, info)
        static_specs = _protocol_static_method_specs(tr, info)
        for line in protocol_traits_lines(info.name, _protocol_method_specs(tr, info), protocol_type_params=info.type_params or None, member_specs=member_specs or None, static_method_specs=static_specs or None):
            tr.write_line(line)
        tr.write_line()

def _emit_field_default_initializer(tr: 'Translator', cpp_type: str, default: ast.expr) -> str:
    from ..analysis.ir import scalar_type_static_attr_from_expr
    macro = scalar_type_static_attr_from_expr(default)
    if macro is not None:
        return macro
    if tr._is_new_call(default):
        assert isinstance(default, ast.Call)
        from ..emit.literal_ctor_emit import _emit_new_ctor_expr
        return _emit_new_ctor_expr(tr, cpp_type, default)
    if isinstance(default, ast.Constant) and isinstance(default.value, str):
        if is_char_heap_array_type(cpp_type) and default.value == '':
            return f'{cpp_type}(0)'
    if isinstance(default, ast.Constant) and default.value == b'':
        if is_bytes_type(cpp_type):
            return f"{cpp_ident('bytes')}()"
        if is_byte_heap_array_type(cpp_type):
            return f'{cpp_type}()'
    if isinstance(default, ast.Constant):
        return tr._literal(default.value, cpp_type=cpp_type)
    if isinstance(default, ast.UnaryOp) and isinstance(default.op, ast.USub) and isinstance(default.operand, ast.Constant) and isinstance(default.operand.value, int):
        return tr._literal(-default.operand.value, cpp_type=cpp_type)
    if isinstance(default, ast.List) and (not default.elts):
        from ..analysis.type_pred import is_deque_type, is_list_type
        if is_list_type(cpp_type) or is_deque_type(cpp_type):
            return f'{cpp_type}()'
    if isinstance(default, ast.Dict) and (not default.keys):
        from ..analysis.type_pred import is_dict_type, is_frozendict_type
        if is_dict_type(cpp_type) or is_frozendict_type(cpp_type):
            return f'{cpp_type}()'
    return tr.visit(default)

def _emit_class_static_mutable_field_decl(tr: 'Translator', info: ClassInfo, field: str) -> None:
    ftype = field_storage_cpp(info, field, fallback=cpp_ident('int') if field in INT_FIELDS else 'void*')
    cpp = info.cpp_member_name(field)
    default = info.field_defaults.get(field)
    init_suffix = ''
    if default is not None:
        init_suffix = f' = {_emit_field_default_initializer(tr, ftype, default)}'
    tr.write_line(f'static {ftype} {cpp}{init_suffix};')

def _emit_class_static_field_decl(tr: 'Translator', info: ClassInfo, stmt: ast.AnnAssign) -> None:
    name = stmt.target.id
    ann = stmt.annotation
    t = tr._parse_type(ann, info.type_params) if ann is not None else cpp_ident('int')
    val = _emit_field_default_initializer(tr, t, stmt.value) if stmt.value is not None else '0'
    cpp = info.cpp_member_name(name)
    if is_char_type(t) or is_byte_type(t):
        t = cpp_ident('int')
    tr.write_line(f'static constexpr {t} {cpp} = {val};')

def _emit_class_thread_local_field_decl(tr: 'Translator', info: ClassInfo, stmt: ast.AnnAssign) -> None:
    name = stmt.target.id
    ann = stmt.annotation
    t = tr._parse_type(ann, info.type_params) if ann is not None else cpp_ident('int')
    if info.is_template():
        t = tr._rewrite_template_args_to_cpp_params(t, info)
    cpp = info.cpp_member_name(name)
    tr.write_line(f'static thread_local {t} {cpp};')

def _emit_class_field_decl(tr: 'Translator', info: ClassInfo, field: str) -> None:
    from ..analysis.ir import resolve_self_in_cpp_type
    ftype = field_storage_cpp(info, field, fallback=cpp_ident('int') if field in INT_FIELDS else 'void*')
    ftype = resolve_self_in_cpp_type(ftype, info.cpp_name())
    cpp = info.cpp_member_name(field)
    default = info.field_defaults.get(field)
    init_suffix = ''
    if field in info.final_fields:
        if not info.inits:
            default = info.final_ctor_inits.get(field, default)
            if default is not None:
                init_suffix = f' = {_emit_field_default_initializer(tr, ftype, default)}'
        const_prefix = 'const '
    else:
        if default is not None:
            init_suffix = f' = {_emit_field_default_initializer(tr, ftype, default)}'
        const_prefix = ''
    mutable_prefix = ''
    for prop_name in info.field_properties | info.postsetter_properties:
        if storage_field_for(prop_name) == field and field_property_getter_returns_mutable_ref(ftype):
            mutable_prefix = 'mutable '
            break
    if is_stack_array_type(ftype):
        tr.write_line(f'{mutable_prefix}{const_prefix}{cpp_stack_array_var_decl(ftype, cpp)}{init_suffix};')
    else:
        tr.write_line(f'{mutable_prefix}{const_prefix}{ftype} {cpp}{init_suffix};')

def _class_decl_cpp_type(tr: 'Translator', cpp_type: str, info: ClassInfo) -> str:
    if info.is_template():
        return tr._rewrite_template_args_to_cpp_params(cpp_type, info)
    return cpp_type

def _class_decl_params(tr: 'Translator', params: str, info: ClassInfo) -> str:
    if not params or not info.is_template():
        return params
    return tr._rewrite_template_args_to_cpp_params(params, info)

def _emit_class_method_decl(tr: 'Translator', info: ClassInfo, method: ast.FunctionDef) -> None:
    if tr._skip_runtime_method_decl(info, method):
        return
    sig = info.method_sig_for(method)
    if sig is None:
        return
    mcpp = info.cpp_member_name(method.name)
    tr._write_doc_lines(sig.doc_lines)
    from ..analysis.variadic_template import typevar_tuple_names_for_emit
    if (sig.func_ft.template_names or typevar_tuple_names_for_emit(sig.func_ft, sig.variadic_template)) and (not (info.name == 'array' and method.name == '__copy__')):
        tr._emit_function_template_prefix(sig.func_ft, variadic_template=sig.variadic_template)
    if method.name == '__del__':
        v = 'virtual ' if info.has_virtual_methods else ''
        tr.write_line(f'{v}~{info.cpp_name()}();')
    else:
        ret_lead = class_decl_return_cpp(tr, sig, info)
        params_decl = _class_decl_params(tr, sig.params_decl, info)
        decl = format_fn_sig(ret_lead, sig.ret_trail, mcpp, params_decl)
        tr.write_line(tr._method_static_prefix(sig) + tr._method_virtual_prefix(sig) + decl + tr._method_const_suffix(sig, method.name) + fn_noexcept_suffix(sig.is_noexcept) + tr._method_override_suffix(sig, info, method.name) + tr._method_final_suffix(sig) + tr._method_pure_virtual_suffix(sig) + ';')
        if method.name == '__setitem__':
            from .setitem_emit import emit_setitem_extra_decls, parse_setitem_value_param
            parsed = parse_setitem_value_param(sig.params_decl)
            if parsed is not None:
                emit_setitem_extra_decls(tr.write_line, ret_lead=sig_return_storage_cpp(sig), ret_trail=sig.ret_trail, mcpp=mcpp, parsed=parsed, static_prefix=tr._method_static_prefix(sig), virtual_prefix=tr._method_virtual_prefix(sig), const_suffix=tr._method_const_suffix(sig, method.name), override_suffix=tr._method_override_suffix(sig, info, method.name))

def _generator_has_embedded_container(info: ClassInfo) -> bool:
    if not info.name.endswith(GENERATOR_SUFFIX):
        return False
    for ft in field_storage_values(info):
        if is_list_type(strip_cpp_ref(ft)):
            return True
    for stmt in info.node.body:
        if not isinstance(stmt, ast.AnnAssign) or stmt.annotation is None:
            continue
        if isinstance(stmt.annotation, ast.Subscript) and isinstance(stmt.annotation.value, ast.Name) and (stmt.annotation.value.id == 'list'):
            return True
    return False

def _emit_class_declaration(tr: 'Translator', info: ClassInfo):
    if info.is_descriptor or info.is_mixin or info.is_annotation or info.is_variant_mixin or tr._is_type_marker(info):
        return
    if info.class_type_if_plan is not None:
        prev_info = tr.class_info
        tr.class_info = info
        try:
            with tr._use_module_decl(info.module_path) if not _generator_has_embedded_container(info) else tr._use_module_deferred_decl(info.module_path):
                emit_class_type_if_declaration(tr, info)
        finally:
            tr.class_info = prev_info
        return
    from ..analysis.access import is_dunder
    if info.is_enum:
        with tr._use_module_decl(info.module_path):
            tr._write_doc_lines(info.doc_lines)
            emit_enum_declaration(tr, info)
            if info.module_path != stdlib_module_path('core/exceptions'):
                emit_enum_support(tr, info)
        return
    if info.is_union:
        from .union_emit import _emit_msvc_variant_macro_guard, emit_union_class_declaration
        with tr._use_module_decl(info.module_path):
            tr._write_doc_lines(info.doc_lines)
            _emit_msvc_variant_macro_guard(tr, info)
            tr._emit_template_prefix(info)
            emit_union_class_declaration(tr, info)
        return
    prev_info = tr.class_info
    tr.class_info = info
    gen_deferred = _generator_has_embedded_container(info)
    if gen_deferred:
        with tr._use_module_decl(info.module_path):
            tr._emit_template_prefix(info)
            tr.write_line(f'class {info.cpp_name()};')
    decl_ctx = tr._use_module_deferred_decl(info.module_path) if gen_deferred else tr._use_module_decl(info.module_path)
    try:
        with decl_ctx:
            tr._write_doc_lines(info.doc_lines)
            if info.name == 'Exception' and info.module_path.replace('\\', '/').endswith('core/exceptions'):
                blob = expand_template('core/~exception_forward_decls.inl', apply_allman=False)
                for line in blob.strip().splitlines():
                    if line.strip():
                        tr.write_line(line)
                tr.write_line()
            tr._emit_template_prefix(info)
            bases = tr._cpp_public_bases(info)
            final_kw = ' final' if info.is_final else ''
            if bases:
                base_cpp = ', '.join((f'public {b}' for b in bases))
                tr.write_line(f'class {info.cpp_name()}{final_kw} : {base_cpp}')
            else:
                tr.write_line(f'class {info.cpp_name()}{final_kw}')
            tr.write_line('{')
            from ..analysis.proxy import CPP_PROXY_PREFIX, is_cpp_proxy_type
            if info.type_params or info.typevar_tuple:
                if not info.is_protocol:
                    with tr._use_indent():
                        _emit_class_type_param_usings(tr, info)
                    tr.write_line()
            if getattr(info, 'is_proxy_derived', False):
                proxy_bases = [b for b in bases if is_cpp_proxy_type(b)]
                if proxy_bases and (not info.inits):
                    with tr._use_indent():
                        for b in proxy_bases:
                            tr.write_line(f'using {b}::{CPP_PROXY_PREFIX};')
                    tr.write_line()
            friend_decls = tr._friend_class_decl_lines(info)
            if friend_decls:
                with tr._use_indent():
                    for line in friend_decls:
                        tr.write_line(line)
                tr.write_line()
            access_sections: list[tuple[str, list]] = [('public', []), ('protected', []), ('private', [])]
            buckets = {a: items for a, items in access_sections}
            for storage in sorted(info.static_property_storage):
                acc = info.member_access_level(storage)
                buckets[acc].append(('static_mutable_field', storage))
            for _name, stmt in info.static_class_fields.items():
                buckets['public'].append(('static_field', stmt))
            for _name, stmt in getattr(info, 'thread_local_fields', {}).items():
                buckets[info.member_access_level(_name)].append(('thread_local_field', stmt))
            for field in info.fields:
                if field in info.static_class_fields or field in info.static_property_storage or field in getattr(info, 'thread_local_fields', {}):
                    continue
                buckets[info.member_access_level(field)].append(('field', field))
            overload_defs = {id(ov) for ovs in info.method_overloads.values() for ov in ovs}
            for method in info.methods.values():
                if id(method) in overload_defs:
                    continue
                if tr._translator_only_skip_method(info, method):
                    continue
                acc = 'public' if is_dunder(method.name) else info.member_access_level(method.name)
                buckets[acc].append(('method', method))
            for overloads in info.method_overloads.values():
                for method in overloads:
                    acc = 'public' if is_dunder(method.name) else info.member_access_level(method.name)
                    buckets[acc].append(('method', method))

            def emit_special_public() -> None:
                for init, sig in zip(info.inits, info.init_sigs):
                    tr._write_doc_lines(sig.doc_lines)
                    if sig.func_ft.template_names:
                        tr._emit_function_template_prefix(sig.func_ft)
                    tr.write_line(f'{_EXPLICIT}{info.cpp_name()}({sig.params_decl});')
                from ..emit.class_emit import _coroutine_param_default_ctor_needed, _generator_host_init
                if _generator_host_init(info):
                    tr.write_line(f'{_EXPLICIT}{info.cpp_name()}();')
                if _coroutine_param_default_ctor_needed(info):
                    tr.write_line(f'{_EXPLICIT}{info.cpp_name()}();')
                from ..analysis.ir import class_needs_explicit_default_ctor
                if class_needs_explicit_default_ctor(info):
                    tr.write_line(f'{_EXPLICIT}{info.cpp_name()}() = default;')
                for prop in info.properties.values():
                    if prop.getter_sig:
                        gs = prop.getter_sig
                        tr._write_doc_lines(gs.doc_lines)
                        getter_cpp = tr._property_getter_cpp_name(info, prop.name)
                        ret = class_decl_return_cpp(tr, gs, info)
                        if prop.name in info.field_properties or prop.name in info.postsetter_properties:
                            storage = storage_field_for(prop.name)
                            stype = field_storage_cpp(info, storage, fallback=ret)
                            ret = field_property_getter_return_ref(stype or ret)
                        tr.write_line(f'{ret}{gs.ret_trail} {getter_cpp}() const;')
                    if prop.setter_sig:
                        ss = prop.setter_sig
                        tr._write_doc_lines(ss.doc_lines)
                        tr.write_line(f'void {tr._property_setter_cpp_name(info, prop.name)}({_class_decl_params(tr, ss.params_decl, info)});')
                    if prop.postsetter_sig:
                        ps = prop.postsetter_sig
                        tr._write_doc_lines(ps.doc_lines)
                        tr.write_line(f'void {tr._property_postsetter_cpp_name(info, prop.name)}({_class_decl_params(tr, ps.params_decl, info)});')
                for prop in info.static_properties.values():
                    if prop.getter_sig:
                        gs = prop.getter_sig
                        tr._write_doc_lines(gs.doc_lines)
                        getter_cpp = tr._property_getter_cpp_name(info, prop.name)
                        tr.write_line(f'static {class_decl_return_cpp(tr, gs, info)}{gs.ret_trail} {getter_cpp}();')
                    if prop.setter_sig:
                        ss = prop.setter_sig
                        tr._write_doc_lines(ss.doc_lines)
                        setter_cpp = tr._property_setter_cpp_name(info, prop.name)
                        tr.write_line(f'static void {setter_cpp}({ss.params_decl});')
                    if prop.postsetter_sig:
                        ps = prop.postsetter_sig
                        tr._write_doc_lines(ps.doc_lines)
                        postset_cpp = tr._property_postsetter_cpp_name(info, prop.name)
                        tr.write_line(f'static void {postset_cpp}({ps.params_decl});')
                if info.needs_auto_dtor():
                    v = 'virtual ' if info.has_virtual_methods else ''
                    tr.write_line(f'{v}~{info.cpp_name()}();')
                elif tr._needs_virtual_dtor_decl(info) and (not info.needs_auto_dtor()):
                    tr.write_line(f'virtual ~{info.cpp_name()}();')
                cpp = info.cpp_specialization() if info.is_template() else info.cpp_name()
                if info.needs_auto_copy() and '__copy__' not in info.methods:
                    tr.write_line(f'void __copy__(const {cpp}& other);')
                if info.needs_auto_move() and '__move__' not in info.methods:
                    tr.write_line(f'void __move__({cpp}& other);')
                if info.is_uncopyable:
                    tr.write_line(f'{cpp}(const {cpp}& other) = delete;')
                    tr.write_line(f'{cpp}& operator=(const {cpp}& other) = delete;')
                    tr.write_line(f'{cpp}({cpp}&& other);')
                    tr.write_line(f'{cpp}& operator=({cpp}&& other);')
                else:
                    if info.has_copy:
                        tr.write_line(f'{cpp}(const {cpp}& other);')
                        tr.write_line(f'{cpp}& operator=(const {cpp}& other);')
                    if info.has_move:
                        tr.write_line(f'{cpp}({cpp}&& other);')
                        tr.write_line(f'{cpp}& operator=({cpp}&& other);')
                    if is_frozen_dataclass(info) and not info.has_copy:
                        tr.write_line(f'{cpp}& operator=(const {cpp}& other);')
                if info.repr_aliases_str and '__repr__' in info.method_sigs:
                    sig = info.method_sigs['__repr__']
                    mcpp = info.cpp_member_name('__repr__')
                    tr._write_doc_lines(sig.doc_lines)
                    if sig.func_ft.template_names:
                        tr._emit_function_template_prefix(sig.func_ft)
                    ret_lead = class_decl_return_cpp(tr, sig, info)
                    decl = format_fn_sig(ret_lead, sig.ret_trail, mcpp, sig.params_decl)
                    tr.write_line(tr._method_static_prefix(sig) + tr._method_virtual_prefix(sig) + decl + tr._method_const_suffix(sig, '__repr__') + fn_noexcept_suffix(sig.is_noexcept) + tr._method_override_suffix(sig, info, '__repr__') + tr._method_final_suffix(sig) + tr._method_pure_virtual_suffix(sig) + ';')
                if not info.is_union:
                    emit_default_object_repr_decls(tr, info)
                if not info.is_union and has_effective_str(info, tr) and (info.name != 'str'):
                    ps = cpp_ident('str')
                    tr.write_line(f'{_EXPLICIT}operator {ps}() const;')
                if not info.is_union and has_effective_bool(info):
                    pb = cpp_ident('bool')
                    tr.write_line(f'{_EXPLICIT}operator {pb}() const;')
                if not info.is_union and has_effective_int(info):
                    tr.write_line(f"{_EXPLICIT}operator {cpp_ident('int')}() const;")
                if not info.is_union and has_effective_float(info):
                    tr.write_line(f"{_EXPLICIT}operator {cpp_ident('float')}() const;")
                if not info.is_union and has_effective_complex(info):
                    cpx = complex_operator_cpp_type(info)
                    if cpx:
                        cpx = tr._typename_member_alias_type(cpx, info)
                        tr.write_line(f'{_EXPLICIT}operator {cpx}() const;')
                if not info.is_union and info.name == 'str' and info.module_path.replace('\\', '/').endswith('text/str'):
                    tr.write_line(f"{_EXPLICIT}operator {cpp_ident('int')}() const;")
                    tr.write_line(f"{_EXPLICIT}operator {cpp_ident('float')}() const;")
                _emit_exception_repr_decl(tr, info)
                from .type_id_emit import emit_type_id_decls
                emit_type_id_decls(tr, info)
                for line in emit_class_operator_overloads(info):
                    if info.is_template():
                        line = tr._rewrite_template_args_to_cpp_params(line, info)
                    tr.write_line(line)
                if info.module_path.replace('\\', '/').endswith('core/exceptions'):
                    pystr_ctor = expand_exception_pystr_ctor(info.cpp_name())
                    if pystr_ctor:
                        for line in pystr_ctor.strip().splitlines():
                            tr.write_line(line)
                for inject_key in CLASS_HEADER_INJECT_SPECS.get(info.name, ()):
                    if inject_key != 'exception_group_header':
                        continue
                    from ..codegen.exception_group_gen import render_exception_group_header
                    blob = render_exception_group_header(tr)
                    for line in textwrap.dedent(blob).strip().splitlines():
                        tr.write_line(line)

            def _emit_py2cpp_inject_class_tail() -> None:
                mp = info.module_path.replace('\\', '/')
                prefix = f'{RUNTIME_PKG}/'
                module_rel = mp[len(prefix):] if mp.startswith(prefix) else mp
                for blob in class_header_inject_blobs(module_rel, info.cpp_name()):
                    for line in textwrap.dedent(blob).strip().splitlines():
                        tr.write_line(line)
            for access, items in access_sections:
                if access != 'public' and (not items):
                    continue
                tr.write_line(f'{access}:')
                with tr._use_indent():
                    if access == 'public':
                        _emit_class_type_usings(tr, info)
                        _emit_class_constraint_asserts(tr, info)
                        _emit_class_oneof_asserts(tr, info)
                    for kind, data in items:
                        match kind:
                            case 'static_field':
                                _emit_class_static_field_decl(tr, info, data)
                            case 'thread_local_field':
                                _emit_class_thread_local_field_decl(tr, info, data)
                            case 'static_mutable_field':
                                _emit_class_static_mutable_field_decl(tr, info, data)
                            case 'field':
                                _emit_class_field_decl(tr, info, data)
                            case 'method':
                                _emit_class_method_decl(tr, info, data)
                    if access == 'public':
                        emit_special_public()
            with tr._use_indent():
                _emit_py2cpp_inject_class_tail()
            tr.write_line('};')
            _emit_class_boxing_check_specializations(tr, info)
            _emit_class_copyable_check_specializations(tr, info)
            tr.write_line()
    finally:
        tr.class_info = prev_info
