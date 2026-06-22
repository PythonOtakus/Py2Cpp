"""``@union``：嵌套 ``Tag`` + C++ ``union`` 载荷 + 默认 ``__repr__`` / ``__str__``。"""
from __future__ import annotations
from contextlib import nullcontext
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_stack_array_type
from ..analysis.ir import ClassInfo, UnionVariantInfo, cpp_ident, format_cpp_int, quote_cpp_string
from ..analysis.patterns import property_getter_method_for
_ENUM_GET = property_getter_method_for('__enum__')
if TYPE_CHECKING:
    from ..translator import Translator

def _tag_enum_name(info: ClassInfo) -> str:
    return 'Enum'

def _storage_union_name(info: ClassInfo) -> str:
    return f'{info.cpp_name()}_Storage'

def _variant_struct_name(info: ClassInfo, variant: UnionVariantInfo) -> str:
    return f'{info.cpp_name()}_Variant_{variant.name}'
_TAG_FIELD = '_tag'
_STORAGE_FIELD = '_storage'
_WIN32_VARIANT_MACRO_NAMES = frozenset({'Yield', 'Return'})

def _emit_msvc_variant_macro_guard(tr: Translator, info: ClassInfo) -> None:
    macros = [v.name for v in info.union_variants if v.name in _WIN32_VARIANT_MACRO_NAMES]
    if not macros:
        return
    tr.write_line('#if defined(_MSC_VER)')
    for name in macros:
        tr.write_line(f'#ifdef {name}')
        tr.write_line(f'#undef {name}')
        tr.write_line('#endif')
    tr.write_line('#endif')
    tr.write_line()

def _union_member_name(variant: UnionVariantInfo) -> str:
    """与 Python ``@variant class`` 名一致（如 ``Quit``、``Move``）。"""
    return variant.name or 'Unit'

def _storage_access_expr(info: ClassInfo, prefix: str='') -> str:
    """``prefix`` 为空时用 ``_stor()``；``out._storage`` → ``out._stor().``。"""
    if not prefix:
        return '_stor().'
    if prefix.endswith(_STORAGE_FIELD):
        return f'{prefix[:-len(_STORAGE_FIELD)]}_stor().'
    stor = _storage_union_name(info)
    return f'reinterpret_cast<{stor}*>({prefix})->'

def _storage_member_ref(info: ClassInfo, variant: UnionVariantInfo, prefix: str='') -> str:
    return f'{_storage_access_expr(info, prefix)}{_union_member_name(variant)}'

def _tag_member_cpp(info: ClassInfo, variant: UnionVariantInfo) -> str:
    return f'Enum::{variant.name}'

def _union_param_cpp_type(tr: Translator, info: ClassInfo, variant: UnionVariantInfo, fname: str) -> str:
    """``@union.mro`` 变体工厂形参须全限定，避免与同名 static 方法冲突。"""
    ft = variant.field_cpp_types.get(fname, cpp_ident('int'))
    if not info.is_union_mro or fname != 'value':
        return ft
    cls_info = tr.classes.get(variant.name)
    if cls_info is None:
        return ft
    from ..analysis.module_namespace import qualify_symbol_in_module
    return qualify_symbol_in_module(cls_info.module_path, cls_info.cpp_name())

def _union_enum_return_cpp(tr: Translator, info: ClassInfo, qual: str) -> str:
    dep = 'typename ' if info.is_template() else ''
    return f'{dep}{qual}::Enum'

def _union_enum_underlying(info: ClassInfo) -> str:
    if info.is_union_mro:
        return info.union_enum_underlying_cpp
    return 'unsigned char'

def _emit_union_enum_members(tr: Translator, info: ClassInfo) -> None:
    n = len(info.union_enum_members) if info.is_union_mro else len(info.union_variants)
    if info.is_union_mro:
        for i, member in enumerate(info.union_enum_members):
            val = format_cpp_int(member.value)
            comma = ',' if i + 1 < n else ''
            tr.write_line(f'{member.name} = {val}{comma}')
    else:
        for i, v in enumerate(info.union_variants):
            comma = ',' if i + 1 < n else ''
            tr.write_line(f'{v.name}{comma}')

def _needs_union_repr(info: ClassInfo) -> bool:
    return '__repr__' not in info.methods and (not info.repr_aliases_str)

def _emit_ctx(tr: Translator, info: ClassInfo):
    if info.is_template() and tr._is_stdlib_module(info.module_path):
        return tr._use_module_inl(info.module_path)
    if tr._is_stdlib_module(info.module_path):
        return tr._use_module_inl(info.module_path)
    return nullcontext()

def _qual(tr: Translator, info: ClassInfo) -> str:
    if hasattr(tr, '_class_method_qualifier'):
        return tr._class_method_qualifier(info)
    return info.cpp_specialization() if info.is_template() else info.cpp_name()

def _emit_tpl_prefix(tr: Translator, info: ClassInfo) -> None:
    if info.is_template():
        tr._emit_template_prefix(info)

def _is_copyable_field_cpp(cpp_t: str) -> bool:
    if cpp_t == cpp_ident('str') or cpp_t.startswith('PyStr'):
        return True
    if cpp_t.startswith('PyList<') or cpp_t.startswith('PyFrozenList<'):
        return True
    if cpp_t.startswith('PyDict<') or cpp_t.startswith('PyFrozenDict<'):
        return True
    if is_stack_array_type(cpp_t):
        return True
    return cpp_t in (cpp_ident('list'), cpp_ident('dict'))

def _is_movable_field_cpp(cpp_t: str) -> bool:
    if cpp_t == cpp_ident('str'):
        return True
    if cpp_t.startswith('PyList<') or cpp_t.startswith('PyFrozenList<'):
        return True
    if cpp_t.startswith('PyDict<') or cpp_t.startswith('PyFrozenDict<'):
        return True
    if is_stack_array_type(cpp_t):
        return True
    return cpp_t in (cpp_ident('list'), cpp_ident('dict'))

def _field_copy_line(lhs: str, rhs: str, cpp_t: str) -> str:
    if _is_copyable_field_cpp(cpp_t):
        return f'{lhs}.__copy__({rhs});'
    return f'{lhs} = {rhs};'

def _field_move_line(lhs: str, rhs: str, cpp_t: str) -> str:
    if cpp_t == cpp_ident('str') or cpp_t.startswith('PyStr'):
        return f'{lhs}.__copy__({rhs});'
    if _is_movable_field_cpp(cpp_t):
        return f'{lhs}.__move__({rhs});'
    return f'{lhs} = {rhs};'

def _destroy_active_member(tr: Translator, info: ClassInfo, variant: UnionVariantInfo, obj: str='') -> None:
    mem = _storage_member_ref(info, variant, obj)
    if variant.is_unit:
        return
    pstruct = _variant_struct_name(info, variant)
    if any((variant.field_cpp_types.get(fname, cpp_ident('int')) == cpp_ident('str') for fname in variant.fields)):
        for fname in variant.fields:
            if variant.field_cpp_types.get(fname, cpp_ident('int')) == cpp_ident('str'):
                tr.write_line(f"{mem}.{fname}.~{cpp_ident('str')}();")
    else:
        tr.write_line(f'{mem}.~{pstruct}();')

def _emit_union_nested_types(tr: Translator, info: ClassInfo) -> None:
    tag = _tag_enum_name(info)
    stor = _storage_union_name(info)
    for v in info.union_variants:
        if v.is_unit:
            continue
        tr.write_line(f'struct {_variant_struct_name(info, v)}')
        tr.write_line('{')
        with tr._use_indent():
            for fname in v.fields:
                ft = v.field_cpp_types.get(fname, cpp_ident('int'))
                tr.write_line(f'{ft} {fname};')
        tr.write_line('};')
        tr.write_line()
    tr.write_line('#if defined(_MSC_VER)')
    tr.write_line('#pragma warning(push)')
    tr.write_line('#pragma warning(disable: 4624)')
    tr.write_line('#endif')
    tr.write_line(f'union {stor}')
    tr.write_line('{')
    with tr._use_indent():
        for v in info.union_variants:
            if v.is_unit:
                tr.write_line(f'char {_union_member_name(v)};')
            else:
                tr.write_line(f'{_variant_struct_name(info, v)} {_union_member_name(v)};')
    tr.write_line('};')
    tr.write_line('#if defined(_MSC_VER)')
    tr.write_line('#pragma warning(pop)')
    tr.write_line('#endif')
    tr.write_line()

def _emit_union_repr_decls(tr: Translator, info: ClassInfo) -> None:
    if not _needs_union_repr(info):
        return
    from ..analysis.type_emit import pystr_header_decl_cpp
    ps = pystr_header_decl_cpp(info.module_path)
    tr.write_line(f'{ps} __repr__() const;')
    tr.write_line(f'{ps} __str__() const;')
    tr.write_line(f'explicit operator {ps}() const;')

def _emit_union_repr_impls(tr: Translator, info: ClassInfo) -> None:
    if not _needs_union_repr(info):
        return
    from ..analysis.type_emit import pystr_header_decl_cpp
    ps = cpp_ident('str')
    ps_op = pystr_header_decl_cpp(info.module_path)
    qual = _qual(tr, info)
    spec = info.cpp_specialization()
    tag = _tag_enum_name(info)
    cls = info.name
    with _emit_ctx(tr, info), tr._use_source():
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{ps} {qual}::__repr__() const'):
            first = True
            for v in info.union_variants:
                kw = 'if' if first else 'else if'
                first = False
                with tr._use_block(f'{kw} ((_tag == {_tag_member_cpp(info, v)}))'):
                    variant_label = quote_cpp_string(f'{cls}.{v.name}')
                    if v.is_unit:
                        tr.write_line(f'return {ps}({variant_label});')
                        continue
                    mem = f'_variant_{v.name}()'
                    tr.write_line(f'{ps} out = {ps}({variant_label});')
                    for i, fname in enumerate(v.fields):
                        frag = quote_cpp_string(('(' if i == 0 else ', ') + f'{fname}=')
                        tr.write_line(f'out = out + {ps}({frag});')
                        tr.write_line(f'out = out + ::repr({mem}.{fname});')
                    tr.write_line(f'out = out + {ps}(")");')
                    tr.write_line('return out;')
            tr.write_line(f'return {ps}("");')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{ps} {qual}::__str__() const'):
            tr.write_line('return __repr__();')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{qual}::operator {ps_op}() const'):
            tr.write_line('return __str__();')
        tr.write_line()

def _emit_union_property_decls(tr: Translator, info: ClassInfo) -> None:
    from ..analysis.type_emit import sig_return_full_cpp
    for prop in info.properties.values():
        if prop.getter_sig:
            gs = prop.getter_sig
            getter_cpp = tr._property_getter_cpp_name(info, prop.name)
            tr.write_line(f'{sig_return_full_cpp(gs)} {getter_cpp}() const;')

def _emit_union_extra_method_decls(tr: Translator, info: ClassInfo) -> None:
    """``@serializable`` / ``@property`` 等用户方法声明（须在类体 ``};`` 之前）。"""
    skip = frozenset({'__copy__', '__move__', '__del__', '__init__'})
    _emit_union_property_decls(tr, info)
    for method in sorted(info.methods.values(), key=lambda m: m.name):
        if method.name in skip:
            continue
        if tr._translator_only_skip_method(info, method):
            continue
        sig = info.method_sig_for(method)
        if sig is not None:
            from ..emit.class_decl_emit import _emit_class_method_decl
            _emit_class_method_decl(tr, info, method)

def emit_union_class_declaration(tr: Translator, info: ClassInfo) -> None:
    tag = _tag_enum_name(info)
    stor = _storage_union_name(info)
    cpp = info.cpp_name()
    tr.write_line(f'class {cpp}')
    tr.write_line('{')
    if info.type_params or info.typevar_tuple:
        from .class_decl_emit import _emit_class_type_param_usings
        _emit_class_type_param_usings(tr, info)
    if info.type_alias_list:
        from .class_decl_emit import _emit_class_type_usings
        _emit_class_type_usings(tr, info)
    if info.type_params or info.typevar_tuple or info.type_alias_list:
        tr.write_line()
    tr.write_line('private:')
    with tr._use_indent():
        _emit_union_nested_types(tr, info)
    tr.write_line('public:')
    with tr._use_indent():
        underlying = _union_enum_underlying(info)
        tr.write_line(f'enum class Enum : {underlying}')
        tr.write_line('{')
        with tr._use_indent():
            _emit_union_enum_members(tr, info)
        tr.write_line('};')
        tr.write_line()
        if info.is_union_mro and info.static_class_fields:
            from ..emit.class_decl_emit import _emit_class_static_field_decl
            for _name in sorted(info.static_class_fields):
                _emit_class_static_field_decl(tr, info, info.static_class_fields[_name])
            tr.write_line()
        for v in info.union_variants:
            params: list[str] = []
            for fname in v.fields:
                ft = _union_param_cpp_type(tr, info, v, fname)
                params.append(f'{ft} {fname}')
            ps = ', '.join(params)
            if ps:
                tr.write_line(f'static {cpp} {v.name}({ps});')
            else:
                tr.write_line(f'static {cpp} {v.name}();')
        tr.write_line(f'explicit {cpp}();')
        tr.write_line(f'{cpp}(const {cpp}& other);')
        tr.write_line(f'{cpp}& operator=(const {cpp}& other);')
        tr.write_line(f'void __copy__(const {cpp}& other);')
        tr.write_line(f'void __move__({cpp}& other);')
        tr.write_line(f'~{cpp}();')
        tr.write_line(f'Enum {_ENUM_GET}() const;')
        for v in info.union_variants:
            if v.is_unit:
                continue
            pstruct = _variant_struct_name(info, v)
            tr.write_line(f'const {pstruct}& _variant_{v.name}() const;')
        _emit_union_repr_decls(tr, info)
        _emit_union_extra_method_decls(tr, info)
    tr.write_line('private:')
    with tr._use_indent():
        tr.write_line(f'Enum {_TAG_FIELD};')
        tr.write_line(f'alignas({stor}) unsigned char {_STORAGE_FIELD}[sizeof({stor})];')
        tr.write_line()
        tr.write_line(f'{stor}& _stor() {{ return *reinterpret_cast<{stor}*>({_STORAGE_FIELD}); }}')
        tr.write_line(f'const {stor}& _stor() const {{ return *reinterpret_cast<const {stor}*>({_STORAGE_FIELD}); }}')
        tr.write_line('void _destroy();')
    tr.write_line('};')
    tr.write_line()

def emit_union_class_impl(tr: Translator, info: ClassInfo) -> None:
    cpp = info.cpp_name()
    spec = info.cpp_specialization()
    qual = _qual(tr, info)
    first = info.union_variants[0]
    for v in info.union_variants:
        if v.is_unit:
            first = v
            break
    with _emit_ctx(tr, info), tr._use_source():
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{qual}::{cpp}()'):
            tr.write_line(f'{_TAG_FIELD} = {_tag_member_cpp(info, first)};')
            if not first.is_unit:
                mem = _storage_member_ref(info, first)
                pstruct = _variant_struct_name(info, first)
                tr.write_line(f'::new (&{mem}) {pstruct}();')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        enum_ret = _union_enum_return_cpp(tr, info, qual)
        with tr._use_block(f'{enum_ret} {qual}::{_ENUM_GET}() const'):
            tr.write_line(f'return {_TAG_FIELD};')
        tr.write_line()
        for v in info.union_variants:
            if v.is_unit:
                continue
            dep = 'typename ' if info.is_template() else ''
            pstruct = f'{dep}{qual}::{_variant_struct_name(info, v)}'
            mem = _storage_member_ref(info, v)
            _emit_tpl_prefix(tr, info)
            with tr._use_block(f'const {pstruct}& {qual}::_variant_{v.name}() const'):
                tr.write_line(f'return {mem};')
            tr.write_line()
        for v in info.union_variants:
            params: list[str] = []
            for fname in v.fields:
                ft = _union_param_cpp_type(tr, info, v, fname)
                params.append(f'{ft} {fname}')
            ps = ', '.join(params)
            header = f'{spec} {qual}::{v.name}({ps})' if ps else f'{spec} {qual}::{v.name}()'
            _emit_tpl_prefix(tr, info)
            with tr._use_block(header):
                tr.write_line(f'{spec} out;')
                if v is first and (not v.is_unit):
                    mem = _storage_member_ref(info, v, f'out.{_STORAGE_FIELD}')
                    for fname in v.fields:
                        ft = v.field_cpp_types.get(fname, cpp_ident('int'))
                        tr.write_line(_field_move_line(f'{mem}.{fname}', fname, ft))
                else:
                    tr.write_line('out._destroy();')
                    tr.write_line(f'out.{_TAG_FIELD} = {_tag_member_cpp(info, v)};')
                    if not v.is_unit:
                        mem = _storage_member_ref(info, v, f'out.{_STORAGE_FIELD}')
                        pstruct = _variant_struct_name(info, v)
                        tr.write_line(f'::new (&{mem}) {pstruct}();')
                        for fname in v.fields:
                            ft = v.field_cpp_types.get(fname, cpp_ident('int'))
                            tr.write_line(_field_copy_line(f'{mem}.{fname}', fname, ft))
                tr.write_line('return out;')
            tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'void {qual}::_destroy()'):
            for v in info.union_variants:
                with tr._use_block(f'if (({_TAG_FIELD} == {_tag_member_cpp(info, v)}))'):
                    _destroy_active_member(tr, info, v)
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{qual}::~{cpp}()'):
            tr.write_line('_destroy();')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'void {qual}::__copy__(const {spec}& other)'):
            tr.write_line('if ((this == &other))')
            with tr._use_indent():
                tr.write_line('return;')
            tr.write_line('_destroy();')
            tr.write_line(f'{_TAG_FIELD} = other.{_TAG_FIELD};')
            for v in info.union_variants:
                if v.is_unit:
                    continue
                mem = _storage_member_ref(info, v)
                omem = _storage_member_ref(info, v, f'other.{_STORAGE_FIELD}')
                pstruct = _variant_struct_name(info, v)
                with tr._use_block(f'if (({_TAG_FIELD} == {_tag_member_cpp(info, v)}))'):
                    tr.write_line(f'::new (&{mem}) {pstruct}();')
                    for fname in v.fields:
                        ft = v.field_cpp_types.get(fname, cpp_ident('int'))
                        tr.write_line(_field_copy_line(f'{mem}.{fname}', f'{omem}.{fname}', ft))
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'void {qual}::__move__({spec}& other)'):
            tr.write_line('if ((this == &other))')
            with tr._use_indent():
                tr.write_line('return;')
            tr.write_line('_destroy();')
            tr.write_line(f'{_TAG_FIELD} = other.{_TAG_FIELD};')
            for v in info.union_variants:
                if v.is_unit:
                    continue
                mem = _storage_member_ref(info, v)
                omem = _storage_member_ref(info, v, f'other.{_STORAGE_FIELD}')
                pstruct = _variant_struct_name(info, v)
                with tr._use_block(f'if (({_TAG_FIELD} == {_tag_member_cpp(info, v)}))'):
                    tr.write_line(f'::new (&{mem}) {pstruct}();')
                    for fname in v.fields:
                        ft = v.field_cpp_types.get(fname, cpp_ident('int'))
                        tr.write_line(_field_move_line(f'{mem}.{fname}', f'{omem}.{fname}', ft))
            tr.write_line('other._destroy();')
            tr.write_line(f'other.{_TAG_FIELD} = {_tag_member_cpp(info, first)};')
            if not first.is_unit:
                omem = _storage_member_ref(info, first, f'other.{_STORAGE_FIELD}')
                pstruct = _variant_struct_name(info, first)
                tr.write_line(f'::new (&{omem}) {pstruct}();')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{qual}::{cpp}(const {spec}& other)'):
            tr.write_line(f'{_TAG_FIELD} = {_tag_member_cpp(info, first)};')
            if not first.is_unit:
                mem = _storage_member_ref(info, first)
                pstruct = _variant_struct_name(info, first)
                tr.write_line(f'::new (&{mem}) {pstruct}();')
            tr.write_line('__copy__(other);')
        tr.write_line()
        _emit_tpl_prefix(tr, info)
        with tr._use_block(f'{qual}& {qual}::operator=(const {spec}& other)'):
            tr.write_line('if ((this != &other))')
            with tr._use_indent():
                tr.write_line('__copy__(other);')
            tr.write_line('return *this;')
        tr.write_line()
        _emit_union_repr_impls(tr, info)

def emit_union_user_methods(tr: Translator, info: ClassInfo) -> None:
    """``@union`` 上用户定义的 ``@property`` 与普通方法。"""
    from ..emit.class_emit import _emit_method, _emit_property_method
    overload_names = set(info.method_overloads.keys())
    for prop in info.properties.values():
        if prop.getter and prop.getter_sig:
            _emit_property_method(tr, info, prop.getter, prop.getter_sig, tr._property_getter_cpp_name(info, prop.name), is_const=True)
        if prop.setter and prop.setter_sig:
            _emit_property_method(tr, info, prop.setter, prop.setter_sig, tr._property_setter_cpp_name(info, prop.name))
    for method in info.methods.values():
        if method.name in ('__copy__', '__move__', '__del__', '__init__'):
            continue
        if method.name in overload_names:
            continue
        if tr._skip_runtime_method_emit(info, method):
            continue
        sig = info.method_sig_for(method)
        if sig is not None:
            _emit_method(tr, info, method, sig)

def try_emit_union_enum_member(tr: Translator, node) -> str | None:
    import ast
    from ..analysis.module_namespace import qualify_symbol_in_module
    from ..passes.union_expand import union_variant_names
    if not isinstance(node, ast.Attribute):
        return None
    if not isinstance(node.value, ast.Attribute):
        return None
    if node.value.attr != 'Enum':
        return None
    if not isinstance(node.value.value, ast.Name):
        return None
    info = tr._class_info_for_ref(node.value.value.id)
    if info is None or not info.is_union or info.is_union_mro:
        return None
    if node.attr not in union_variant_names(info):
        return None
    qual_enum = qualify_symbol_in_module(info.module_path, f'{info.cpp_name()}::Enum')
    return f'{qual_enum}::{node.attr}'
