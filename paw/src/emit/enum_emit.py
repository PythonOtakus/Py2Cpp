"""``@enum`` → C++11 ``enum class``（底层 ``PyInt`` / ``PyInt64``）及 Flag 运算 / 表示。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..analysis.ir import ClassInfo
    from ..translator import Translator
from ..analysis.type_pred import is_int64_type
from ..analysis.ir import ClassInfo, EnumMemberInfo, cpp_ident, format_cpp_int, format_cpp_int64, quote_cpp_string
from ..analysis.module_namespace import qualify_symbol_in_module
from ..analysis.type_emit import bind_scope_var

def enum_class_for_name(tr: Translator, name: str) -> ClassInfo | None:
    """``Name`` 是否指模块内 ``@enum`` 类（含 import 绑定）。"""
    info = tr._class_info_for_ref(name)
    if info is None or not info.is_enum or (not info.enum_members):
        return None
    return info

def enum_class_for_iter_expr(tr: Translator, node: ast.expr) -> ClassInfo | None:
    """``for x in Mode`` / ``len(Mode)`` 的可迭代对象：须为枚举类名 ``Name``。"""
    if not isinstance(node, ast.Name):
        return None
    return enum_class_for_name(tr, node.id)

def emit_enum_len_expr(info: ClassInfo) -> str:
    """``len(E)`` → 成员个数（编译期常量）。"""
    return str(len(info.enum_members))

def try_emit_enum_len(tr: Translator, arg: ast.expr) -> str | None:
    info = enum_class_for_iter_expr(tr, arg)
    if info is None:
        return None
    return emit_enum_len_expr(info)

def try_emit_enum_for_loop(tr: Translator, node: ast.For) -> bool:
    """``for x in EnumClass:`` → 成员表 + 索引 ``for``（无迭代器）。"""
    from ..translator import NameContext, temp_name
    info = enum_class_for_iter_expr(tr, node.iter)
    if info is None:
        return False
    if not isinstance(node.target, ast.Name):
        raise NotImplementedError('for x in Enum 仅支持简单变量目标')
    cpp = info.cpp_name()
    name = node.target.id
    members = info.enum_members
    n = len(members)
    vals = ', '.join((f'{cpp}::{m.name}' for m in members))
    tbl = temp_name('enum_tbl')
    idx = temp_name('ei')
    with tr._loop_with_else(node.orelse):
        tr.write_line(f'static const {cpp} {tbl}[{n}] = {{ {vals} }};')
        with tr._use_block(f'for (PyInt {idx} = 0; {idx} < {n}; {idx} += 1)'):
            tr.write_line(f'{cpp} {name} = {tbl}[{idx}];')
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp, classes=tr.classes)
                tr.scope.vars[name] = NameContext.Variable
            tr._emit_body(node.body)
    return True

def _member_value_cpp(info: ClassInfo, member: str) -> str:
    for m in info.enum_members:
        if m.name == member:
            if is_int64_type(info.enum_underlying_cpp):
                return format_cpp_int64(m.value)
            return format_cpp_int(m.value)
    return '0'

def _all_members_mask(info: ClassInfo) -> str:
    underlying = info.enum_underlying_cpp
    vals = [format_cpp_int64(m.value) if is_int64_type(underlying) else format_cpp_int(m.value) for m in info.enum_members]
    if not vals:
        return '0'
    if len(vals) == 1:
        return vals[0]
    return ' | '.join(vals)

def _flag_members(info: ClassInfo) -> list[EnumMemberInfo]:
    """Flag 分解用：非零成员，按值升序。"""
    return sorted((m for m in info.enum_members if m.value != 0), key=lambda m: m.value)

def emit_enum_declaration(tr: Translator, info: ClassInfo) -> None:
    cpp = info.cpp_name()
    underlying = info.enum_underlying_cpp
    tr.write_line(f'enum class {cpp} : {underlying}')
    tr.write_line('{')
    with tr._use_indent():
        n = len(info.enum_members)
        for i, member in enumerate(info.enum_members):
            val = _member_value_cpp(info, member.name)
            comma = ',' if i + 1 < n else ''
            tr.write_line(f'{member.name} = {val}{comma}')
    tr.write_line('};')
    tr.write_line()

def _emit_flag_operators(tr: Translator, info: ClassInfo) -> None:
    cpp = info.cpp_name()
    u = info.enum_underlying_cpp
    cast_back = f'static_cast<{cpp}>'
    cast_u = f'static_cast<{u}>'
    for op, sym in (('|', '|'), ('&', '&'), ('^', '^')):
        tr.write_line(f'inline {cpp} operator{sym}({cpp} a, {cpp} b)')
        tr.write_line('{')
        with tr._use_indent():
            tr.write_line(f'return {cast_back}({cast_u}(a) {sym} {cast_u}(b));')
        tr.write_line('}')
        tr.write_line(f'inline {cpp}& operator{sym}=({cpp}& a, {cpp} b)')
        tr.write_line('{')
        with tr._use_indent():
            tr.write_line(f'a = {cast_back}({cast_u}(a) {sym} {cast_u}(b));')
            tr.write_line('return a;')
        tr.write_line('}')
    mask = _all_members_mask(info)
    tr.write_line(f'inline {cpp} operator~({cpp} a)')
    tr.write_line('{')
    with tr._use_indent():
        tr.write_line(f'return {cast_back}((~{cast_u}(a)) & ({mask}));')
    tr.write_line('}')
    tr.write_line()

def enum_scalar_helper_name(info: ClassInfo) -> str:
    """``Mode`` → ``ModePyInt`` / ``ModePyInt64``（``operator PyInt()`` / ``operator PyInt64()``）。"""
    suffix = 'PyInt64' if is_int64_type(info.enum_underlying_cpp) else 'PyInt'
    return f'{info.cpp_name()}{suffix}'

def enum_pystr_helper_name(info: ClassInfo) -> str:
    """``Mode`` → ``ModePyStr``（``operator PyStr()`` 包装，供 ``static_cast<PyStr>``）。"""
    return f'{info.cpp_name()}PyStr'

def _enum_helper_cpp(tr: Translator, info: ClassInfo, helper: str) -> str:
    """枚举辅助 struct 名：与 emit 处同命名空间（``.inl`` 全局或用户模块块内）。"""
    mp = info.module_path.replace('\\', '/')
    entry = tr.entry_module_path.replace('\\', '/')
    if mp == entry:
        return helper
    if tr._is_stdlib_module(info.module_path):
        return helper
    return qualify_symbol_in_module(info.module_path, helper)

def enum_pystr_helper_cpp(tr: Translator, info: ClassInfo) -> str:
    """``ModePyStr`` / ``ExcTypePyStr``：与 emit 处同命名空间（``.inl`` 全局或用户模块块内）。"""
    return _enum_helper_cpp(tr, info, enum_pystr_helper_name(info))

def enum_scalar_helper_cpp(tr: Translator, info: ClassInfo) -> str:
    return _enum_helper_cpp(tr, info, enum_scalar_helper_name(info))

def enum_pystr_cast_expr(tr: Translator, info: ClassInfo, value_expr: str) -> str:
    """``str(E.MEM)`` → ``static_cast<PyStr>(ModePyStr{…})``。"""
    ps = cpp_ident('str')
    helper = enum_pystr_helper_cpp(tr, info)
    return f'static_cast<{ps}>({helper}{{{value_expr}}})'

def enum_to_underlying_cast_expr(tr: Translator, info: ClassInfo, value_expr: str) -> str:
    """``int(E.MEM)`` / ``int64(E.MEM)`` → ``static_cast<底层>(…)``（勿经临时 helper，避免 MSVC 实参临时触雷）。"""
    u = info.enum_underlying_cpp
    return f'static_cast<{u}>({value_expr})'

def enum_to_int_cast_expr(tr: Translator, info: ClassInfo, value_expr: str) -> str:
    """``int(E.MEM)`` → ``PyInt``（``int64`` 底层时经 ``PyInt64`` 再收窄）。"""
    pi = cpp_ident('int')
    u = info.enum_underlying_cpp
    if is_int64_type(u):
        return f'static_cast<{pi}>({enum_to_underlying_cast_expr(tr, info, value_expr)})'
    return enum_to_underlying_cast_expr(tr, info, value_expr)

def try_emit_enum_ctor(tr: Translator, node: ast.Call) -> str | None:
    """``StatusCodeEnum(200)`` → ``static_cast<StatusCodeEnum>(static_cast<PyInt>(200))``。"""
    if not isinstance(node.func, ast.Name):
        return None
    info = enum_class_for_name(tr, node.func.id)
    if info is None:
        return None
    if node.keywords:
        raise NotImplementedError('@enum 构造仅支持单 positional 实参')
    if len(node.args) != 1:
        raise NotImplementedError('@enum 构造须恰好一个实参')
    cpp = info.cpp_name()
    u = info.enum_underlying_cpp
    arg = tr._visit_value_expr(node.args[0])
    return f'static_cast<{cpp}>(static_cast<{u}>({arg}))'

def _emit_enum_str_body(tr: Translator, info: ClassInfo) -> None:
    """``operator PyStr()`` 函数体：``Cls.MEM`` 或 Flag ``Cls.A|Cls.B``（CPython 3.13）。"""
    cpp = info.cpp_name()
    cls = info.name
    ps = cpp_ident('str')
    u = info.enum_underlying_cpp
    tr.write_line(f'const {u} u = static_cast<{u}>(v);')
    if info.enum_is_flag:
        members = _flag_members(info)
        tr.write_line(f'{ps} out;')
        tr.write_line('bool first = true;')
        for m in members:
            mv = _member_value_cpp(info, m.name)
            tr.write_line(f'if ((u & ({mv})) == ({mv}))')
            tr.write_line('{')
            with tr._use_indent():
                part = quote_cpp_string(f'{cls}.{m.name}')
                tr.write_line(f'if (!first)')
                tr.write_line(f'  out = out.__add__({ps}("|"));')
                tr.write_line(f'out = out.__add__({ps}({part}));')
                tr.write_line('first = false;')
            tr.write_line('}')
        tr.write_line('if (first)')
        tr.write_line('{')
        with tr._use_indent():
            tr.write_line('char buf[96];')
            if is_int64_type(u):
                tr.write_line(f'snprintf(buf, sizeof(buf), "{cls}: %lld", (long long)u);')
            else:
                tr.write_line(f'snprintf(buf, sizeof(buf), "{cls}: %d", (int)u);')
            tr.write_line(f'return {ps}(buf);')
        tr.write_line('}')
        tr.write_line(f'return out;')
        return
    for m in info.enum_members:
        mv = _member_value_cpp(info, m.name)
        tr.write_line(f'if (u == ({mv}))')
        tr.write_line(f"  return {ps}({quote_cpp_string(f'{cls}.{m.name}')});")
    tr.write_line('char buf[96];')
    if is_int64_type(u):
        tr.write_line(f'snprintf(buf, sizeof(buf), "{cls}: %lld", (long long)u);')
    else:
        tr.write_line(f'snprintf(buf, sizeof(buf), "{cls}: %d", (int)u);')
    tr.write_line(f'return {ps}(buf);')

def _emit_enum_scalar_converter(tr: Translator, info: ClassInfo) -> None:
    """``{E}PyInt`` / ``{E}PyInt64`` 包装 + ``operator PyInt()`` / ``operator PyInt64()``。"""
    cpp = info.cpp_name()
    u = info.enum_underlying_cpp
    helper = enum_scalar_helper_name(info)
    tr.write_line(f'struct {helper}')
    tr.write_line('{')
    with tr._use_indent():
        tr.write_line(f'{cpp} v;')
        tr.write_line(f'explicit {helper}({cpp} x) : v(x) {{}}')
        tr.write_line(f'explicit operator {u}() const {{ return static_cast<{u}>(v); }}')
    tr.write_line('};')
    tr.write_line()

def _emit_enum_pystr_converter(tr: Translator, info: ClassInfo) -> None:
    """``{E}PyStr`` 包装 + ``operator PyStr()``（对齐用户类 ``static_cast<PyStr>`` 路径）。"""
    cpp = info.cpp_name()
    ps = cpp_ident('str')
    helper = enum_pystr_helper_name(info)
    tr.write_line(f'struct {helper}')
    tr.write_line('{')
    with tr._use_indent():
        tr.write_line(f'{cpp} v;')
        tr.write_line(f'explicit {helper}({cpp} x) : v(x) {{}}')
        tr.write_line(f'explicit operator {ps}() const')
        tr.write_line('{')
        with tr._use_indent():
            _emit_enum_str_body(tr, info)
        tr.write_line('}')
    tr.write_line('};')
    tr.write_line()

def _emit_enum_repr_fn(tr: Translator, info: ClassInfo) -> None:
    cpp = info.cpp_name()
    ps = cpp_ident('str')
    helper = enum_pystr_helper_name(info)
    u = info.enum_underlying_cpp
    tr.write_line(f'inline {ps} repr({cpp} v)')
    tr.write_line('{')
    with tr._use_indent():
        tr.write_line(f'{ps} name = static_cast<{ps}>({helper}{{v}});')
        tr.write_line('char vbuf[32];')
        if is_int64_type(u):
            tr.write_line('snprintf(vbuf, sizeof(vbuf), "%lld", (long long)static_cast<PyInt64>(v));')
        else:
            tr.write_line('snprintf(vbuf, sizeof(vbuf), "%d", (int)static_cast<PyInt>(v));')
        tr.write_line(f'return {ps}("<").__add__(name).__add__({ps}(": ")).__add__({ps}(vbuf)).__add__({ps}(">"));')
    tr.write_line('}')
    tr.write_line()

def emit_enum_support(tr: Translator, info: ClassInfo) -> None:
    """Flag 运算符、标量/``PyStr`` 转换包装与模块 ``repr(E)``（CPython 3.13 形态）。"""
    if info.enum_is_flag:
        _emit_flag_operators(tr, info)
    _emit_enum_scalar_converter(tr, info)
    _emit_enum_pystr_converter(tr, info)
    _emit_enum_repr_fn(tr, info)
