"""序列字面量内联：``[a,b,c][i]``、``x in [a,b]``、``"abc"[i]``、``"abc".find(x)`` 等。

常量下标 / 小表查表直接展开；否则 IIFE 内临时 ``PyList`` / ``PyStr``。见 reference §8.3.2。
"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_char_type
from ..analysis.ir import cpp_ident, cpp_template_type, str_cpp_from_literal
from ..constant.stdlib_layout import cpp_exception_ctor
from .comprehensions_emit import _temp_name
from .iife_emit import emit_iife
from .literal_map_lookup_emit import (
  _literal_membership_or_chain,
  _literal_membership_or_chain_from_elts,
)
if TYPE_CHECKING:
    from ..translator import Translator
_STR_FIND_METHODS = frozenset({'find', 'index', 'rfind', 'rindex'})
_STR_END_SENTINEL = -2147483648
_MAX_INLINE_HAYSTACK = 64

def _striplines_literal(text: str, min_indent: int) -> str:
    lines = text.splitlines()
    begin = 0
    end = len(lines)
    while begin < end and not lines[begin].strip():
        begin += 1
    while end > begin and not lines[end - 1].strip():
        end -= 1
    if begin >= end:
        return ''
    common: int | None = None
    for line in lines[begin:end]:
        if not line.strip():
            continue
        indent = 0
        while indent < len(line) and line[indent] == ' ':
            indent += 1
        common = indent if common is None else min(common, indent)
    if common is None:
        return ''
    prefix = ' ' * min_indent
    return '\n'.join((prefix + line[common:] if line.strip() else '' for line in lines[begin:end]))

def try_emit_str_literal_striplines_call(text: str, node: ast.Call) -> str | None:
    """Fold ``"literal".striplines([constant])`` into one PyStr literal."""
    if len(node.args) > 1:
        return None
    min_indent_node: ast.expr | None = None
    if node.args:
        min_indent_node = node.args[0]
    for keyword in node.keywords:
        if keyword.arg != 'min_indent' or min_indent_node is not None:
            return None
        min_indent_node = keyword.value
    min_indent = 0
    if min_indent_node is not None:
        if not isinstance(min_indent_node, ast.Constant) or not isinstance(min_indent_node.value, int) or isinstance(min_indent_node.value, bool):
            return None
        min_indent = min_indent_node.value
    if min_indent < 0:
        return None
    return str_cpp_from_literal(_striplines_literal(text, min_indent))

def list_literal_has_starred(node: ast.List) -> bool:
    return any((isinstance(e, ast.Starred) for e in node.elts))

def list_literal_elems_all_constant(node: ast.List) -> bool:
    return all((isinstance(e, ast.Constant) for e in node.elts))

def list_literal_elem_cpp(tr: Translator, node: ast.List) -> str:
    if not node.elts:
        return cpp_ident('int')
    return tr._infer_expr_cpp_type(node.elts[0])

def _const_index_value(slice_node: ast.expr, *, length: int) -> int | None:
    if not isinstance(slice_node, ast.Constant) or not isinstance(slice_node.value, int):
        return None
    idx = slice_node.value
    if idx < 0:
        idx = length + idx
    if idx < 0 or idx >= length:
        return None
    return idx

def _emit_runtime_list_getitem(tr: Translator, list_node: ast.List, slice_node: ast.expr) -> str:
    elem_t = list_literal_elem_cpp(tr, list_node)
    spec = cpp_template_type('list', elem_t)
    lname = _temp_name('lseq')
    stmts: list[str] = [f'{spec} {lname};']
    for elt in list_node.elts:
        if isinstance(elt, ast.Starred):
            stmts.append(f'{lname}.extend({tr.visit(elt.value)});')
        else:
            stmts.append(f'{lname}.append({tr._visit_value_expr(elt)});')
    idx = tr._visit_value_expr(slice_node)
    stmts.append(f'return {lname}.__getitem__({idx});')
    return emit_iife(elem_t, stmts)

def try_emit_list_literal_getitem(tr: Translator, list_node: ast.List, slice_node: ast.expr) -> str:
    if list_literal_has_starred(list_node):
        return _emit_runtime_list_getitem(tr, list_node, slice_node)
    n = len(list_node.elts)
    if n == 0:
        throw_ix = cpp_exception_ctor('IndexError')
        elem_t = list_literal_elem_cpp(tr, list_node)
        return emit_iife(elem_t, [f'throw {throw_ix}'])
    const_idx = _const_index_value(slice_node, length=n)
    if const_idx is not None:
        return tr._visit_value_expr(list_node.elts[const_idx])
    if list_literal_elems_all_constant(list_node):
        elem_t = list_literal_elem_cpp(tr, list_node)
        vals = ', '.join((tr._visit_value_expr(e) for e in list_node.elts))
        idx_expr = tr._visit_value_expr(slice_node)
        throw_ix = cpp_exception_ctor('IndexError')
        return emit_iife(elem_t, [f'static const {elem_t} _tbl[] = {{{vals}}}', f'if ({idx_expr} < 0 || {idx_expr} >= {n}) throw {throw_ix}', f'return _tbl[{idx_expr}]'])
    return _emit_runtime_list_getitem(tr, list_node, slice_node)

def try_emit_list_literal_contains(tr: Translator, list_node: ast.List, member_node: ast.expr, *, negate: bool=False) -> str:
    core = _literal_membership_or_chain_from_elts(tr, member_node, list_node.elts)
    if negate:
        return f'(!({core}))'
    return core

def _emit_runtime_list_contains(tr: Translator, list_node: ast.List, member_expr: str) -> str:
    elem_t = list_literal_elem_cpp(tr, list_node)
    spec = cpp_template_type('list', elem_t)
    lname = _temp_name('lseq')
    stmts: list[str] = [f'{spec} {lname};']
    for elt in list_node.elts:
        if isinstance(elt, ast.Starred):
            stmts.append(f'{lname}.extend({tr.visit(elt.value)});')
        else:
            stmts.append(f'{lname}.append({tr._visit_value_expr(elt)});')
    stmts.append(f'return {lname}.__contains__({member_expr});')
    return emit_iife('PyBool', stmts)

def _str_literal_codepoints(text: str) -> list[int]:
    return [ord(ch) for ch in text]

def try_emit_str_literal_getitem(tr: Translator, text: str, slice_node: ast.expr) -> str | None:
    cps = _str_literal_codepoints(text)
    n = len(cps)
    if n == 0:
        throw_ix = cpp_exception_ctor('IndexError')
        return emit_iife('PyChar', [f'throw {throw_ix}'])
    const_idx = _const_index_value(slice_node, length=n)
    if const_idx is not None:
        return f'PyChar({cps[const_idx]})'
    idx_expr = tr._visit_value_expr(slice_node)
    s_expr = str_cpp_from_literal(text)
    return f'{s_expr}.__getitem__({idx_expr})'

def try_emit_str_literal_contains(tr: Translator, text: str, member_node: ast.expr, *, negate: bool=False) -> str:
    from ..analysis.type_pred import is_str_type
    from ..analysis.ir import cpp_ident, strip_cpp_ref

    member_expr = tr._visit_value_expr(member_node)
    member_t = strip_cpp_ref(tr._infer_expr_cpp_type(member_node) or '')
    cps = _str_literal_codepoints(text)
    if not cps:
        core = 'false'
    else:
        ps = cpp_ident('str')
        if is_str_type(member_t, classes=tr.classes):
            parts = [f'({member_expr} == {ps}(PyChar({cp})))' for cp in cps]
        else:
            parts = [f'({member_expr} == PyChar({cp}))' for cp in cps]
        core = parts[0] if len(parts) == 1 else '(' + ' || '.join(parts) + ')'
    if negate:
        return f'(!({core}))'
    return core

def _norm_start(n: int, start: int) -> int:
    if start < 0:
        start += n
    if start < 0:
        return 0
    if start > n:
        return n
    return start

def _norm_end(n: int, end: int) -> int:
    if end == _STR_END_SENTINEL:
        return n
    if end < 0:
        end += n
    if end < 0:
        return 0
    if end > n:
        return n
    return end

def _parse_find_range(node: ast.Call, haystack_len: int) -> tuple[int, int] | None:
    if node.keywords:
        return None
    if len(node.args) == 1:
        return (0, haystack_len)
    if len(node.args) != 3:
        return None
    a_start, a_end = (node.args[1], node.args[2])
    if not isinstance(a_start, ast.Constant) or not isinstance(a_start.value, int):
        return None
    if not isinstance(a_end, ast.Constant) or not isinstance(a_end.value, int):
        return None
    i = _norm_start(haystack_len, a_start.value)
    j = _norm_end(haystack_len, a_end.value)
    return (i, j)

def _parse_find_needle(tr: Translator, sub_node: ast.expr) -> tuple[list[int] | None, str | None]:
    """``(常量子串码点, None)`` 或 ``(None, 单 ``char`` 变量表达式)``；否则回退。"""
    if isinstance(sub_node, ast.Constant) and isinstance(sub_node.value, str):
        return (_str_literal_codepoints(sub_node.value), None)
    if is_char_type(tr._infer_expr_cpp_type(sub_node)):
        return (None, tr._visit_value_expr(sub_node))
    return (None, None)

def _pychar_init_list(cps: list[int]) -> str:
    return ', '.join((f'PyChar({cp})' for cp in cps))

def _haystack_array_decl(cps: list[int]) -> str:
    vals = _pychar_init_list(cps)
    return f'static const PyChar _h[] = {{{vals}}}; const int _n = {len(cps)};'

def _emit_char_find_stmts(cps: list[int], needle_expr: str, i: int, j: int, *, from_right: bool) -> list[str]:
    decl = _haystack_array_decl(cps)
    stmts = [decl, f'PyChar _c = {needle_expr};']
    if from_right:
        stmts.append(f'for (int pos = {j} - 1; pos >= {i}; --pos) {{')
        stmts.append('if (_h[pos] == _c) return pos;')
        stmts.append('}')
    else:
        stmts.append(f'for (int pos = {i}; pos < {j}; ++pos) {{')
        stmts.append('if (_h[pos] == _c) return pos;')
        stmts.append('}')
    return stmts

def _emit_substr_find_stmts(cps: list[int], sub_cps: list[int], i: int, j: int, *, from_right: bool) -> list[str]:
    hay = _pychar_init_list(cps)
    sub = _pychar_init_list(sub_cps)
    sn = len(sub_cps)
    stmts = [f'static const PyChar _h[] = {{{hay}}};', f'static const PyChar _s[] = {{{sub}}};', f'const int _i = {i}, _j = {j}, _sn = {sn};']
    if from_right:
        stmts.append('for (int pos = _j - _sn; pos >= _i; --pos) {')
    else:
        stmts.append('for (int pos = _i; pos <= _j - _sn; ++pos) {')
    stmts.append('bool _ok = true;')
    stmts.append('for (int t = 0; t < _sn; ++t) {')
    stmts.append('if (_h[pos + t] != _s[t]) { _ok = false; break; }')
    stmts.append('}')
    stmts.append('if (_ok) return pos;')
    stmts.append('}')
    return stmts

def _find_fail_stmt(method: str) -> str:
    if method in ('index', 'rindex'):
        return f"throw {cpp_exception_ctor('ValueError')};"
    return 'return -1;'

def _wrap_find_iife(stmts: list[str], method: str) -> str:
    stmts.append(_find_fail_stmt(method))
    return emit_iife('PyInt', stmts)

def try_emit_str_literal_find_method(tr: Translator, text: str, method: str, node: ast.Call) -> str | None:
    if method not in _STR_FIND_METHODS:
        return None
    bounds = _parse_find_range(node, len(text))
    if bounds is None:
        return None
    if len(text) > _MAX_INLINE_HAYSTACK:
        return None
    i, j = bounds
    sub_cps, char_expr = _parse_find_needle(tr, node.args[0])
    if sub_cps is None and char_expr is None:
        return None
    cps = _str_literal_codepoints(text)
    from_right = method in ('rfind', 'rindex')
    if sub_cps is not None and len(sub_cps) == 0:
        pos = j if from_right else i
        return _wrap_find_iife([_haystack_array_decl(cps), f'return {pos};'], method)
    if char_expr is not None:
        stmts = _emit_char_find_stmts(cps, char_expr, i, j, from_right=from_right)
        return _wrap_find_iife(stmts, method)
    assert sub_cps is not None
    if len(sub_cps) == 1:
        stmts = _emit_char_find_stmts(cps, f'PyChar({sub_cps[0]})', i, j, from_right=from_right)
        return _wrap_find_iife(stmts, method)
    stmts = _emit_substr_find_stmts(cps, sub_cps, i, j, from_right=from_right)
    return _wrap_find_iife(stmts, method)

def _emit_runtime_str_find(tr: Translator, text: str, method: str, node: ast.Call) -> str:
    from ..emit.call_emit import call_param_cpp_types, emit_call_args
    s_expr = str_cpp_from_literal(text)
    arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func))
    return f'{s_expr}.{method}({arg_str})'

def try_emit_str_literal_find_call(tr: Translator, text: str, method: str, node: ast.Call) -> str:
    inline = try_emit_str_literal_find_method(tr, text, method, node)
    if inline is not None:
        return inline
    return _emit_runtime_str_find(tr, text, method, node)
