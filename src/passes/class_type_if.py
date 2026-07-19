"""泛型类体内编译期 ``if T is int:`` / ``elif`` / ``else`` → C++ 类模板（全/部分）特化。"""
from __future__ import annotations
import ast
import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from ..analysis.type_emit import bind_scope_param, method_param_storage_cpp, sig_return_full_cpp, sig_return_storage_cpp
from ..analysis.type_pred import is_byte_type, is_char_type, is_stack_array_type
from ..analysis.ir import MethodSig, TypeAliasInfo, cpp_type_param_template_name, format_fn_sig, fn_noexcept_suffix, parse_type_alias_stmt
from .type_if import TypeIfChain, TypePattern, _DefaultElseSpec, _ExactSpec, _PatternSpec, _SpliceSpec, _branch_is_not, _branch_not_in, _collect_type_if_chain, _looks_like_type_if_head, _select_body_for_spec, _strip_docstring, _validate_chain, _validate_single_type_if_chain, branch_emit_patterns, find_type_if_chains
if TYPE_CHECKING:
    from ..analysis.analyzer import SemanticAnalyzer
    from ..analysis.ir import ClassInfo
    from ..translator import Translator

@dataclass(frozen=True)
class ClassTypeIfPlan:
    chain: TypeIfChain
    tail: tuple[ast.stmt, ...]
    class_node: ast.ClassDef

@dataclass
class ClassTypeIfSpec:
    header_lines: list[str]
    splice_spec: _SpliceSpec
    cpp_specialization: str
    extra_tparams: tuple[str, ...]
    concrete_bind: tuple[str, str] | None
    type_aliases: list[TypeAliasInfo]
    methods: dict[str, ast.FunctionDef]
    method_sigs: dict[str, MethodSig] = field(default_factory=dict)
    is_primary_else: bool = False
    fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)
    field_type_nodes: dict = field(default_factory=dict)
    field_defaults: dict[str, ast.expr] = field(default_factory=dict)
    static_class_fields: dict[str, ast.AnnAssign] = field(default_factory=dict)
    field_properties: set[str] = field(default_factory=set)

def plan_class_type_if(tr: Translator, info: ClassInfo) -> ClassTypeIfPlan | None:
    if not info.type_params or info.is_protocol or info.is_enum or info.is_union:
        return None
    tparams = set(info.type_params)
    capture = set(info.capture_params)
    call_tparams = tparams - capture
    body = _strip_docstring(info.node.body)
    if not body:
        return None
    first = body[0]
    if not isinstance(first, ast.If) or not _looks_like_type_if_head(first.test, call_tparams, capture_params=capture):
        return None
    if first is not body[0]:
        return None
    chain = _collect_type_if_chain(tr, first, tparams=tparams, call_tparams=call_tparams, capture_params=capture)
    _validate_chain(chain)
    if chain.type_param not in call_tparams:
        raise ValueError(f'class {info.name}: 类型 if 须使用类调用形参 ``{chain.type_param}``')
    extra_chains = find_type_if_chains(tr, list(body[1:]), tparams=tparams, capture_params=capture)
    if extra_chains:
        raise ValueError(f'class {info.name}: 类体内至多一条类型 if 链；链后成员与分支成员由编译期分派合并')
    _validate_single_type_if_chain(chain, tparams=tparams, capture_params=capture)
    return ClassTypeIfPlan(chain=chain, tail=tuple(body[1:]), class_node=info.node)

def _merged_body_for_spec(plan: ClassTypeIfPlan, spec: _SpliceSpec) -> list[ast.stmt]:
    branch = _select_body_for_spec(plan.chain, spec)
    return branch + copy.deepcopy(list(plan.tail))

def _is_class_type_if_synthetic_member(method: ast.FunctionDef) -> bool:
    """``expand_default_bool`` 等 pass 在类体末尾注入的成员，勿并入特化。"""
    if not method.name.startswith('__') or not method.name.endswith('__'):
        return False
    return _has_immutable_decorator(method)

def _has_immutable_decorator(node: ast.FunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == 'immutable':
            return True
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and (dec.func.id == 'immutable'):
            return True
    return False

def _stmts_to_class_members(stmts: list[ast.stmt]) -> tuple[list[TypeAliasInfo], dict[str, ast.FunctionDef]]:
    type_aliases: list[TypeAliasInfo] = []
    methods: dict[str, ast.FunctionDef] = {}
    for stmt in stmts:
        if isinstance(stmt, ast.TypeAlias):
            type_aliases.append(parse_type_alias_stmt(stmt))
        elif isinstance(stmt, ast.FunctionDef):
            if _is_class_type_if_synthetic_member(stmt):
                continue
            methods[stmt.name] = stmt
    return (type_aliases, methods)

def _collect_spec_fields_from_stmts(stmts: list[ast.stmt]) -> tuple[list[str], dict[str, ast.expr], dict[str, ast.AnnAssign], dict[str, ast.expr | None], set[str]]:
    from ..analysis.ir import is_const_type_annotation, strip_type_annotation_markers
    from ..passes.descriptors import storage_field_for
    fields: list[str] = []
    field_defaults: dict[str, ast.expr] = {}
    static_class_fields: dict[str, ast.AnnAssign] = {}
    field_anns: dict[str, ast.expr | None] = {}
    field_properties: set[str] = set()
    for stmt in stmts:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        markers = set()
        from ..analysis.ir import iter_matmult_marker_names
        if stmt.annotation is not None:
            markers = set(iter_matmult_marker_names(stmt.annotation))
        name = stmt.target.id
        base_ann = strip_type_annotation_markers(stmt.annotation)
        if 'property' in markers:
            storage = storage_field_for(name)
            field_properties.add(name)
            if storage not in fields:
                fields.append(storage)
            if stmt.value is not None:
                field_defaults[storage] = stmt.value
            field_anns[storage] = base_ann
            continue
        if is_const_type_annotation(stmt.annotation):
            static_class_fields[name] = stmt
            continue
        if name not in fields:
            fields.append(name)
        if stmt.value is not None:
            field_defaults[name] = stmt.value
        field_anns[name] = base_ann
    return (fields, field_defaults, static_class_fields, field_anns, field_properties)

def _resolve_spec_field_types(analyzer: SemanticAnalyzer, info: ClassInfo, spec_fields: list[str], field_anns: dict[str, ast.expr | None], extra_tparams: tuple[str, ...]) -> tuple[dict[str, str], dict]:
    from ..analysis.ir import resolve_self_in_cpp_type
    from ..analysis.type_emit import storage_cpp
    from ..analysis.type_render import CLASS_BODY
    tparams = set(info.type_params) | set(extra_tparams)
    out: dict[str, str] = {}
    nodes: dict = {}
    for fname in spec_fields:
        ann = field_anns.get(fname)
        if ann is None:
            out[fname] = 'void*'
            continue
        node = analyzer.sigs._parse_ann_storage_type_node(ann, tparams, info=info)
        rendered = node.render(CLASS_BODY)
        ft = resolve_self_in_cpp_type(rendered, info.cpp_name())
        if ft != rendered:
            node = analyzer.sigs._type_node_from_cpp(ft)
        out[fname] = storage_cpp(node)
        nodes[fname] = node
    return out, nodes

def _spec_header_and_meta(info: ClassInfo, pat: TypePattern | None, *, is_default_else: bool) -> tuple[list[str], str, tuple[str, ...], tuple[str, str] | None, _SpliceSpec]:
    cpp_name = info.cpp_name()
    tp = info.type_params[0] if info.type_params else 'T'
    if pat is not None:
        if pat.extra_template_params:
            tdecl = ', '.join((f'typename {p}' for p in pat.extra_template_params))
            header = [f'template<{tdecl}>', f'class {cpp_name}<{pat.cpp_type}>']
            spec = _PatternSpec(pat)
            bind: tuple[str, str] | None = (tp, pat.cpp_type)
            return (header, pat.cpp_type, pat.extra_template_params, bind, spec)
        header = ['template<>', f'class {cpp_name}<{pat.cpp_type}>']
        spec = _ExactSpec(pat.cpp_type)
        bind = (tp, pat.cpp_type)
        return (header, pat.cpp_type, (), bind, spec)
    if is_default_else:
        cpp_tp = cpp_type_param_template_name(tp)
        header = [f'template<typename {cpp_tp}>', f'class {cpp_name}']
        spec = _DefaultElseSpec()
        return (header, cpp_tp, (), (tp, tp), spec)
    raise ValueError('internal: class type if spec needs pattern or default else')

def analyze_class_type_if_specs(analyzer: SemanticAnalyzer, tr: Translator, info: ClassInfo) -> None:
    assert info.class_type_if_plan is not None
    plan = info.class_type_if_plan
    specs: list[ClassTypeIfSpec] = []
    chain = plan.chain

    def add_spec(pat: TypePattern | None, *, is_default_else: bool=False) -> None:
        header, cpp_spec, extra, bind, splice_spec = _spec_header_and_meta(info, pat, is_default_else=is_default_else)
        merged = _merged_body_for_spec(plan, splice_spec)
        type_aliases, methods = _stmts_to_class_members(merged)
        fields, field_defaults, static_class_fields, field_anns, field_properties = _collect_spec_fields_from_stmts(merged)
        prev_aliases = dict(info.type_aliases)
        branch_aliases = {a.name: a for a in type_aliases}
        analyzer.types.set_type_aliases(branch_aliases, use_as_cpp_name=True)
        prev_extra = set(tr._type_if_extra_params)
        prev_bind = tr._type_if_concrete_bind
        tr._type_if_extra_params |= set(extra)
        if bind is not None:
            tr._type_if_concrete_bind = bind
        method_sigs: dict[str, MethodSig] = {}
        field_types: dict[str, str] = {}
        field_type_nodes: dict = {}
        try:
            field_types, field_type_nodes = _resolve_spec_field_types(analyzer, info, fields, field_anns, extra)
            for method in methods.values():
                method_sigs[method.name] = analyzer.sigs.build_method_sig(info, method)
            for prop in field_properties:
                from ..passes.descriptors import storage_field_for
                from ..passes.field_properties import _synthetic_field_property_getter
                storage = storage_field_for(prop)
                ann = field_anns.get(storage)
                getter = _synthetic_field_property_getter(prop, storage, ann)
                methods[prop] = getter
                method_sigs[prop] = analyzer.sigs.build_method_sig(info, getter)
        finally:
            tr._type_if_extra_params = prev_extra
            tr._type_if_concrete_bind = prev_bind
            analyzer.types.set_type_aliases(prev_aliases, use_as_cpp_name=not info.is_protocol)
        specs.append(ClassTypeIfSpec(header_lines=header, splice_spec=splice_spec, cpp_specialization=cpp_spec, extra_tparams=extra, concrete_bind=bind, type_aliases=type_aliases, methods=methods, method_sigs=method_sigs, is_primary_else=is_default_else, fields=fields, field_types=field_types, field_type_nodes=field_type_nodes, field_defaults=field_defaults, static_class_fields=static_class_fields, field_properties=field_properties))
    for br in chain.branches:
        if _branch_is_not(br):
            raise ValueError('类体内类型 if 不支持 ``T is not …`` 首分支')
        if _branch_not_in(br):
            raise ValueError('类体内类型 if 不支持 ``T not in {{…}}``')
        for pat in branch_emit_patterns(br, chain.type_param):
            add_spec(pat)
    if chain.else_body is not None:
        add_spec(None, is_default_else=True)
    elif not chain.branches:
        raise ValueError(f'class {info.name}: 类型 if 链无分支')
    else:
        raise ValueError(f'class {info.name}: 类体内类型 if 须写 ``else:``（与函数 type if 一致）')
    info.class_type_if_specs = specs
    info.method_sigs.clear()
    info.methods.clear()
    info.fields.clear()
    info.field_types.clear()
    info.field_type_nodes.clear()
    info.field_defaults.clear()
    info.static_class_fields.clear()

def _emit_spec_field_decls(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec) -> None:
    from ..analysis.ir import INT_FIELDS, cpp_ident, field_property_getter_returns_mutable_ref, resolve_self_in_cpp_type
    from ..emit.class_decl_emit import _emit_field_default_initializer
    from ..passes.descriptors import storage_field_for
    prev = dict(info.type_aliases)
    branch = {a.name: a for a in spec.type_aliases}
    info.type_aliases = branch
    tr.type_parser.set_type_aliases(branch, use_as_cpp_name=True)
    try:
        for _name, stmt in spec.static_class_fields.items():
            from ..emit.class_decl_emit import _emit_class_static_field_decl
            _emit_class_static_field_decl(tr, info, stmt)
        for field in spec.fields:
            ftype = spec.field_types.get(field, cpp_ident('int') if field in INT_FIELDS else 'void*')
            ftype = resolve_self_in_cpp_type(ftype, info.cpp_name())
            cpp = info.cpp_member_name(field)
            default = spec.field_defaults.get(field)
            init_suffix = ''
            if default is not None:
                init_suffix = f' = {_emit_field_default_initializer(tr, ftype, default)}'
            mutable_prefix = ''
            for prop in spec.field_properties:
                if storage_field_for(prop) == field and field_property_getter_returns_mutable_ref(ftype):
                    mutable_prefix = 'mutable '
                    break
            if is_stack_array_type(ftype):
                from ..analysis.ir import cpp_stack_array_var_decl
                tr.write_line(f'{mutable_prefix}{cpp_stack_array_var_decl(ftype, cpp)}{init_suffix};')
            else:
                tr.write_line(f'{mutable_prefix}{ftype} {cpp}{init_suffix};')
    finally:
        info.type_aliases = prev
        tr.type_parser.set_type_aliases(prev, use_as_cpp_name=True)

def emit_class_type_if_forward_decl(tr: Translator, info: ClassInfo) -> None:
    tp = info.type_params[0]
    tr._emit_template_prefix(info)
    tr.write_line(f'class {info.cpp_name()};')
    tr.write_line()

def _emit_spec_type_usings(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec) -> None:
    prev = dict(info.type_aliases)
    branch = {a.name: a for a in spec.type_aliases}
    info.type_aliases = branch
    tr.type_parser.set_type_aliases(branch, use_as_cpp_name=True)
    try:
        for alias in spec.type_aliases:
            if alias.member_constraint:
                continue
            tr._emit_type_alias_using(alias, tr._type_alias_rhs_cpp(alias, info))
    finally:
        info.type_aliases = prev
        tr.type_parser.set_type_aliases(prev, use_as_cpp_name=True)

def _emit_spec_method_decl(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec, method: ast.FunctionDef, msig: MethodSig) -> None:
    from ..analysis.access import is_dunder
    if tr._translator_only_skip_method(info, method):
        return
    if method.name in spec.field_properties:
        from ..analysis.ir import field_property_getter_return_ref
        from ..passes.descriptors import storage_field_for
        storage = storage_field_for(method.name)
        stype = spec.field_types.get(storage, sig_return_storage_cpp(msig))
        ret = field_property_getter_return_ref(stype or sig_return_storage_cpp(msig))
        getter_cpp = tr._property_getter_cpp_name(info, method.name)
        tr._write_doc_lines(msig.doc_lines)
        tr.write_line(f'{ret}{msig.ret_trail} {getter_cpp}() const;')
        return
    mcpp = info.cpp_member_name(method.name)
    tr._write_doc_lines(msig.doc_lines)
    if msig.func_ft.template_names:
        tr._emit_function_template_prefix(msig.func_ft)
    decl = format_fn_sig(sig_return_storage_cpp(msig), msig.ret_trail, mcpp, msig.params_decl)
    prefix = tr._method_static_prefix(msig)
    if is_dunder(method.name):
        prefix = ''
    tr.write_line(prefix + tr._method_virtual_prefix(msig) + decl + tr._method_const_suffix(msig, method.name) + fn_noexcept_suffix(msig.is_noexcept) + tr._method_override_suffix(msig, info, method.name) + tr._method_final_suffix(msig) + tr._method_pure_virtual_suffix(msig) + ';')

def emit_class_type_if_declaration(tr: Translator, info: ClassInfo) -> None:
    if not info.class_type_if_specs:
        return
    tr._write_doc_lines(info.doc_lines)
    emit_class_type_if_forward_decl(tr, info)
    for spec in info.class_type_if_specs:
        for line in spec.header_lines:
            tr.write_line(line)
        tr.write_line('{')
        with tr._use_indent():
            tr.write_line('public:')
            with tr._use_indent():
                _emit_spec_type_usings(tr, info, spec)
                _emit_spec_field_decls(tr, info, spec)
                for name, method in spec.methods.items():
                    msig = spec.method_sigs[name]
                    _emit_spec_method_decl(tr, info, spec, method, msig)
        tr.write_line('};')
        tr.write_line()

def class_type_if_method_sig(info: ClassInfo, method: str) -> MethodSig | None:
    """``class_type_if`` 分析后 ``info.method_sigs`` 已清空，调用点须查各特化。"""
    for spec in info.class_type_if_specs:
        msig = spec.method_sigs.get(method)
        if msig is not None:
            return msig
    return None

def class_type_if_method_def(info: ClassInfo, method: str) -> ast.FunctionDef | None:
    for spec in info.class_type_if_specs:
        m = spec.methods.get(method)
        if m is not None:
            return m
    return None

def emit_class_type_if_method_bodies(tr: Translator, info: ClassInfo) -> None:
    if not info.class_type_if_specs:
        return
    from ..analysis.module_namespace import namespace_qualifier_for_module
    ns = namespace_qualifier_for_module(info.module_path)
    for spec in info.class_type_if_specs:
        inner = f'{info.cpp_name()}<{spec.cpp_specialization}>'
        base = f'{ns}::{inner}' if ns else inner
        prev_extra = set(tr._type_if_extra_params)
        prev_bind = tr._type_if_concrete_bind
        tr._type_if_extra_params |= set(spec.extra_tparams)
        if spec.concrete_bind is not None:
            tr._type_if_concrete_bind = spec.concrete_bind
        prev_aliases = dict(info.type_aliases)
        branch = {a.name: a for a in spec.type_aliases}
        info.type_aliases = branch
        tr.type_parser.set_type_aliases(branch, use_as_cpp_name=False)
        try:
            for method in spec.methods.values():
                msig = spec.method_sigs[method.name]
                mcpp = info.cpp_member_name(method.name)
                qual = f'{base}::{mcpp}'
                if spec.extra_tparams:
                    tdecl = ', '.join((f'typename {p}' for p in spec.extra_tparams))
                    tr.write_line(f'template<{tdecl}>')
                elif spec.is_primary_else and info.type_params:
                    from ..analysis.ir import cpp_type_param_template_name
                    tr.write_line(f'template<typename {cpp_type_param_template_name(info.type_params[0])}>')
                if method.name in spec.field_properties:
                    _emit_spec_field_property_getter(tr, info, spec, method.name, msig, base)
                else:
                    _emit_class_type_if_method_body(tr, info, spec, method, msig, qual, base)
        finally:
            tr._type_if_extra_params = prev_extra
            tr._type_if_concrete_bind = prev_bind
            info.type_aliases = prev_aliases
            tr.type_parser.set_type_aliases(prev_aliases, use_as_cpp_name=True)

def _emit_spec_field_property_getter(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec, prop: str, msig: MethodSig, base: str) -> None:
    from ..analysis.ir import field_property_getter_return_ref
    from ..passes.descriptors import storage_field_for
    storage = storage_field_for(prop)
    cpp_field = info.cpp_member_name(storage)
    getter_cpp = tr._property_getter_cpp_name(info, prop)
    qual = f'{base}::{getter_cpp}'
    stype = spec.field_types.get(storage, sig_return_storage_cpp(msig))
    ret = field_property_getter_return_ref(stype or sig_return_storage_cpp(msig))
    tr._write_doc_lines(msig.doc_lines)
    tr.write_line(f'{ret} {qual}() const {{ return {cpp_field}; }}')
    tr.write_line()

def _emit_class_type_if_method_body(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec, method: ast.FunctionDef, msig: MethodSig, qual: str, base: str) -> None:
    from ..emit.final_emit import emit_final_ctor_init_suffix
    params_def = msig.params_def
    if method.name == '__init__':
        init_suffix = emit_final_ctor_init_suffix(tr, info, method)
        sig = f'{qual}({params_def}){init_suffix}'
    elif method.name == '__del__':
        sig = f'{qual}()'
    else:
        ret_def = _class_type_if_ret_cpp(tr, info, spec, msig, base)
        params_def = _class_type_if_params_cpp(tr, info, spec, msig, base)
        sig = format_fn_sig(ret_def, msig.ret_trail, qual, params_def)
        sig = sig + tr._method_const_suffix(msig, method.name)
        sig = sig + fn_noexcept_suffix(msig.is_noexcept)
    prev_method = tr.current_method
    tr.current_method = method
    try:
        with tr._use_self_type(info), tr._use_scope(method) as scope:
            for arg in method.args.args:
                if arg.arg == 'self':
                    continue
                bind_scope_param(scope, arg.arg, msig)
            with tr._use_block(sig):
                tr._emit_body(method.body)
    finally:
        tr.current_method = prev_method
    tr.write_line()

def _class_type_if_ret_cpp(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec, msig: MethodSig, base: str) -> str:
    t = sig_return_storage_cpp(msig).strip()
    for alias in spec.type_aliases:
        if t == alias.name:
            return f'typename {base}::{alias.name}'
    return tr._typename_member_alias_type(sig_return_storage_cpp(msig), info)

def _class_type_if_params_cpp(tr: Translator, info: ClassInfo, spec: ClassTypeIfSpec, msig: MethodSig, base: str) -> str:
    if not msig.params_def:
        return msig.params_def
    alias_names = {a.name for a in spec.type_aliases}
    parts: list[str] = []
    for piece in msig.params_def.split(','):
        piece = piece.strip()
        if not piece:
            continue
        name = piece.rsplit(' ', 1)[-1]
        pt = method_param_storage_cpp(msig, name)
        if pt is None:
            parts.append(piece)
            continue
        t = pt.strip()
        if t in alias_names:
            t = f'typename {base}::{t}'
        else:
            t = tr._typename_member_alias_type(pt, info)
        parts.append(f'{t} {name}')
    return ', '.join(parts)
