"""``int()`` / ``float()`` / ``complex()`` 与 ``char()`` / ``byte()`` 等标量转换 emit。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_byte_type, is_char_type, is_varint_type
from ..analysis.type_pred import is_complex_type
from ..analysis.ir import complex_element_cpp_type, complex_template_cpp_type, cpp_ident, format_cpp_complex_component, format_cpp_complex_literal, strip_cpp_ref
from .complex_literal_emit import complex_literal_parts
from .object_repr_emit import complex_operator_cpp_type
if TYPE_CHECKING:
    from ..translator import Translator

def _class_info_for_arg(tr: 'Translator', arg: ast.expr, arg_t: str | None):
    cinfo = tr._class_info_for_type(arg_t) if arg_t else None
    if cinfo is None:
        cinfo = tr._class_info_for_expr(arg)
    return cinfo

def _emit_static_cast(tr: 'Translator', arg: ast.expr, target_cpp: str) -> str:
    expr = tr._paren_expr(tr._visit_value_expr(arg))
    return f'static_cast<{target_cpp}>({expr})'

def _complex_cast_type(tr: 'Translator', arg: ast.expr, arg_t: str | None):
    cinfo = _class_info_for_arg(tr, arg, arg_t)
    if cinfo is not None and '__complex__' in cinfo.methods:
        return complex_operator_cpp_type(cinfo)
    if arg_t and is_complex_type(arg_t):
        return arg_t
    if complex_literal_parts(arg) is not None:
        return complex_template_cpp_type(None)
    return None

def try_emit_int_ctor(tr: 'Translator', node: ast.Call) -> str | None:
    if len(node.args) != 1:
        return None
    arg = node.args[0]
    arg_t = tr._infer_expr_cpp_type(arg)
    pi = cpp_ident('int')
    if arg_t == cpp_ident('str'):
        return _emit_static_cast(tr, arg, pi)
    cinfo = _class_info_for_arg(tr, arg, arg_t)
    if cinfo is not None and cinfo.is_enum:
        from .enum_emit import enum_to_int_cast_expr
        return enum_to_int_cast_expr(tr, cinfo, tr._paren_expr(tr.visit(arg)))
    if cinfo is not None and '__int__' in cinfo.methods:
        return _emit_static_cast(tr, arg, pi)
    if is_varint_type(arg_t):
        return _emit_static_cast(tr, arg, pi)
    return None

def try_emit_float_ctor(tr: 'Translator', node: ast.Call) -> str | None:
    if len(node.args) != 1:
        return None
    arg = node.args[0]
    arg_t = tr._infer_expr_cpp_type(arg)
    pf = cpp_ident('float')
    if arg_t == cpp_ident('str'):
        return _emit_static_cast(tr, arg, pf)
    if arg_t and is_complex_type(arg_t):
        return _emit_static_cast(tr, arg, pf)
    if complex_literal_parts(arg) is not None:
        return _emit_static_cast(tr, arg, pf)
    cinfo = _class_info_for_arg(tr, arg, arg_t)
    if cinfo is not None and '__float__' in cinfo.methods:
        return _emit_static_cast(tr, arg, pf)
    return None

def try_emit_complex_ctor(tr: 'Translator', node: ast.Call) -> str | None:
    cls = complex_template_cpp_type(None)
    if len(node.args) == 0:
        return format_cpp_complex_literal(0.0, 0.0, None)
    if len(node.args) == 1:
        arg = node.args[0]
        arg_t = tr._infer_expr_cpp_type(arg)
        if arg_t == cpp_ident('str'):
            return None
        cast_ty = _complex_cast_type(tr, arg, arg_t)
        if cast_ty:
            return _emit_static_cast(tr, arg, cast_ty)
        if arg_t in (cpp_ident('int'), cpp_ident('float'), cpp_ident('float64')):
            real = tr._visit_value_expr(arg)
            elem = complex_element_cpp_type(arg_t)
            cls = complex_template_cpp_type(arg_t)
            zero = format_cpp_complex_component(0.0, elem)
            return f'{cls}({real}, {zero})'
        return None
    if len(node.args) == 2:
        real = tr._visit_value_expr(node.args[0])
        imag = tr._visit_value_expr(node.args[1])
        elem = complex_element_cpp_type(None)
        return f'{cls}({real}, {imag})'
    return None

def try_emit_numeric_ctor(tr: 'Translator', name: str, node: ast.Call) -> str | None:
    if name == 'int':
        return try_emit_int_ctor(tr, node)
    if name == 'float':
        return try_emit_float_ctor(tr, node)
    if name == 'complex':
        return try_emit_complex_ctor(tr, node)
    return None
_PRIMITIVE_CAST_NAMES = frozenset({'char', 'byte', 'bool', 'int64', 'uint', 'uint64', 'uintptr', 'float64'})

def try_emit_primitive_ctor(tr: 'Translator', name: str, node: ast.Call) -> str | None:
    """``char(0)`` / ``byte(x)`` / ``int64(n)`` 等标量显式转换。"""
    if name not in _PRIMITIVE_CAST_NAMES:
        return None
    if node.keywords or len(node.args) != 1:
        return None
    arg = node.args[0]
    arg_t = strip_cpp_ref(tr._infer_expr_cpp_type(arg) or '')
    target = cpp_ident(name)
    expr = tr._visit_value_expr(arg)
    if name == 'char':
        if is_char_type(arg_t):
            return expr
        return f'PyChar({expr})'
    if name == 'byte':
        if is_byte_type(arg_t):
            return expr
        if is_char_type(arg_t):
            return f'PyByte(pychar_to_byte({tr._paren_expr(expr)}))'
        return f'PyByte({expr})'
    if name == 'bool':
        if arg_t in ('PyBool', cpp_ident('bool')):
            return expr
        return _emit_static_cast(tr, arg, cpp_ident('bool'))
    if arg_t == target:
        return expr
    return _emit_static_cast(tr, arg, target)
