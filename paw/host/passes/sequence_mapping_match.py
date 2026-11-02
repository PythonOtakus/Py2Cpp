"""``match`` 序列模式（``MatchSequence`` / ``MatchStar``）与映射模式（``MatchMapping``）。"""
from __future__ import annotations
import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..analysis.patterns import temp_name
from ..passes.descriptors import property_getter_method_for
from ..analysis.type_pred import is_bytes_type, is_counter_type, is_dict_type, is_deque_type, is_frozendict_type, is_frozenlist_type, is_list_type, is_str_type, is_tuple_type
from ..analysis.type_extract import dict_type_args, frozendict_type_args
from ..analysis.ir import ClassInfo, cpp_ident, cpp_template_type, cpp_tuple_arity, cpp_tuple_element_types, format_cpp_int, is_mapping_match_subject, is_sequence_match_subject, mapping_match_key_value_cpp, quote_cpp_string, sequence_match_elem_cpp, str_cpp_from_literal
from ..emit.layout_config_emit import SLICE_START_UNSET, SLICE_STOP_UNSET
if TYPE_CHECKING:
    from ..translator import Translator
    from .match_case import PatternMatch

@dataclass
class _SeqLayout:
    prefix: list[ast.pattern]
    star: ast.MatchStar | None
    suffix: list[ast.pattern]

def _split_sequence_layout(patterns: list[ast.pattern]) -> _SeqLayout:
    star_idx: int | None = None
    for i, pat in enumerate(patterns):
        if isinstance(pat, ast.MatchStar):
            if star_idx is not None:
                raise ValueError('序列模式仅允许一个 ``*``')
            star_idx = i
    if star_idx is None:
        return _SeqLayout(prefix=list(patterns), star=None, suffix=[])
    return _SeqLayout(prefix=patterns[:star_idx], star=patterns[star_idx], suffix=patterns[star_idx + 1:])

def _member_sep(subject_expr: str) -> str:
    return '->' if subject_expr == 'this' else '.'

def _runtime_getitem(subject_expr: str, index_expr: str) -> str:
    sep = _member_sep(subject_expr)
    return f'{subject_expr}{sep}__getitem__({index_expr})'

def _tuple_get_expr(subject_expr: str, index: int) -> str:
    return f'{subject_expr}.template get<{index}>()'

def _sequence_access_expr(subject_expr: str, subject_cpp: str, *, pos_index: int | None=None, neg_index: int | None=None, tuple_abs_index: int | None=None) -> str:
    if tuple_abs_index is not None and is_tuple_type(subject_cpp):
        return _tuple_get_expr(subject_expr, tuple_abs_index)
    if neg_index is not None:
        return _runtime_getitem(subject_expr, str(neg_index))
    assert pos_index is not None
    if is_tuple_type(subject_cpp):
        return _tuple_get_expr(subject_expr, pos_index)
    return _runtime_getitem(subject_expr, str(pos_index))

def _slice_rest_type(subject_cpp: str) -> str:
    if is_str_type(subject_cpp):
        return cpp_ident('str')
    if is_bytes_type(subject_cpp):
        return cpp_ident('bytes')
    if is_list_type(subject_cpp) or is_frozenlist_type(subject_cpp) or is_deque_type(subject_cpp):
        return subject_cpp
    if is_tuple_type(subject_cpp):
        return subject_cpp
    elem = sequence_match_elem_cpp(subject_cpp)
    if elem:
        return cpp_template_type('list', elem)
    return subject_cpp

def _emit_slice_getitem(subject_expr: str, start: int | str, stop: int | str) -> str:
    lo = str(start) if isinstance(start, int) else start
    hi = str(stop) if isinstance(stop, int) else stop
    sl = f"{cpp_ident('slice')}<int, int>({lo}, {hi}, 1)"
    return _runtime_getitem(subject_expr, sl)

def _emit_tuple_star_bind(name: str, subject_expr: str, elem_types: list[str], indices: list[int]) -> str:
    if not indices:
        return f'auto {name} = PyTuple<>();'
    if len(indices) == 1:
        t0 = elem_types[0]
        return f'auto {name} = PyTuple<{t0}>({_tuple_get_expr(subject_expr, indices[0])});'
    types = ', '.join(elem_types)
    args = ', '.join((_tuple_get_expr(subject_expr, i) for i in indices))
    return f'auto {name} = PyTuple<{types}>({args});'

def _emit_deque_star_bind(name: str, subject_expr: str, subject_cpp: str, *, prefix_len: int, suffix_len: int) -> list[str]:
    sep = _member_sep(subject_expr)
    lines = [f'{subject_cpp} {name} = {subject_cpp}();']
    if suffix_len == 0:
        if prefix_len == 0:
            lines[0] = f'{subject_cpp} {name} = {subject_expr};'
            return lines
        start = prefix_len
        end_expr = f'{subject_expr}{sep}__len__()'
    elif prefix_len == 0:
        start = 0
        end_expr = f'({subject_expr}{sep}__len__() - {suffix_len})'
    else:
        start = prefix_len
        end_expr = f'({subject_expr}{sep}__len__() - {suffix_len})'
    si_var = temp_name("si")
    lines.append(f'for (int {si_var} = {start}; {si_var} < {end_expr}; ++{si_var})')
    lines.append('{')
    lines.append(f'  {name}.append({subject_expr}{sep}__getitem__({si_var}));')
    lines.append('}')
    return lines

def _emit_runtime_star_bind(name: str, subject_expr: str, subject_cpp: str, *, prefix_len: int, suffix_len: int) -> str | list[str]:
    if is_deque_type(subject_cpp):
        return _emit_deque_star_bind(name, subject_expr, subject_cpp, prefix_len=prefix_len, suffix_len=suffix_len)
    rest_ty = _slice_rest_type(subject_cpp)
    if suffix_len == 0:
        if prefix_len == 0:
            return f'{rest_ty} {name} = {subject_expr};'
        start: int | str = prefix_len
        stop: int | str = SLICE_STOP_UNSET
    elif prefix_len == 0:
        start = SLICE_START_UNSET
        stop = -suffix_len
    else:
        start = prefix_len
        stop = -suffix_len
    expr = _emit_slice_getitem(subject_expr, start, stop)
    return f'{rest_ty} {name} = {expr};'

def _emit_star_binding(star: ast.MatchStar, subject_expr: str, subject_cpp: str, *, prefix_len: int, suffix_len: int, tuple_arity: int | None) -> str | list[str] | None:
    if not star.name or star.name == '_':
        return None
    name = star.name
    if is_tuple_type(subject_cpp) and tuple_arity is not None:
        mid_start = prefix_len
        mid_end = tuple_arity - suffix_len
        indices = list(range(mid_start, mid_end))
        elem_types = cpp_tuple_element_types(subject_cpp)
        mid_types = [elem_types[i] for i in indices]
        return _emit_tuple_star_bind(name, subject_expr, mid_types, indices)
    return _emit_runtime_star_bind(name, subject_expr, subject_cpp, prefix_len=prefix_len, suffix_len=suffix_len)

def _subpattern_match(tr: Translator, pat: ast.pattern, *, elem_cpp: str, elem_expr: str, classes: dict[str, ClassInfo]):
    from .match_case import pattern_to_match
    capture_name: str | None = None
    inner_pat = pat
    if isinstance(pat, ast.MatchAs) and pat.name and (pat.name != '_'):
        capture_name = pat.name
        inner_pat = pat.pattern if pat.pattern is not None else ast.MatchAs(name='_')
    dummy = ast.Name(id=temp_name("match_elem"), ctx=ast.Load())
    pm = pattern_to_match(tr, inner_pat, subject_cpp=elem_cpp, subject=dummy, subject_expr=elem_expr, classes=classes)
    if capture_name:
        pm.prelude_lines.insert(0, f'auto {capture_name} = {elem_expr};')
    return pm

def _merge_pattern_match(pm, *, conds: list[str], bindings: list[ast.stmt], prelude: list[str]) -> None:
    if pm.condition and pm.condition != 'true':
        conds.append(f'({pm.condition})')
    bindings.extend(pm.bindings)
    prelude.extend(pm.prelude_lines)

def pattern_sequence_to_match(tr: Translator, pattern: ast.MatchSequence, *, subject_cpp: str, subject_expr: str, classes: dict[str, ClassInfo]):
    from .match_case import PatternMatch
    if not is_sequence_match_subject(subject_cpp):
        raise TypeError(f'序列 ``case [...]`` 要求主体为 list/tuple/str/…，当前为 {subject_cpp}')
    elem_cpp = sequence_match_elem_cpp(subject_cpp) or 'auto'
    layout = _split_sequence_layout(pattern.patterns)
    prefix_len = len(layout.prefix)
    suffix_len = len(layout.suffix)
    is_tuple = is_tuple_type(subject_cpp)
    tuple_arity = cpp_tuple_arity(subject_cpp) if is_tuple else None
    sep = _member_sep(subject_expr)
    conds: list[str] = []
    bindings: list[ast.stmt] = []
    prelude: list[str] = []
    if layout.star is None:
        total = prefix_len + suffix_len
        if is_tuple and tuple_arity is not None:
            if tuple_arity != total:
                return PatternMatch(condition='false')
        elif not is_tuple:
            conds.append(f'({subject_expr}{sep}__len__() == {total})')
        for i, pat in enumerate(layout.prefix + layout.suffix):
            if is_tuple and tuple_arity is not None:
                access = _sequence_access_expr(subject_expr, subject_cpp, tuple_abs_index=i)
            else:
                access = _sequence_access_expr(subject_expr, subject_cpp, pos_index=i)
            pm = _subpattern_match(tr, pat, elem_cpp=elem_cpp, elem_expr=access, classes=classes)
            _merge_pattern_match(pm, conds=conds, bindings=bindings, prelude=prelude)
    else:
        min_len = prefix_len + suffix_len
        if is_tuple and tuple_arity is not None:
            if tuple_arity < min_len:
                return PatternMatch(condition='false')
        elif not is_tuple:
            conds.append(f'({subject_expr}{sep}__len__() >= {min_len})')
        for i, pat in enumerate(layout.prefix):
            if is_tuple and tuple_arity is not None:
                access = _sequence_access_expr(subject_expr, subject_cpp, tuple_abs_index=i)
            else:
                access = _sequence_access_expr(subject_expr, subject_cpp, pos_index=i)
            pm = _subpattern_match(tr, pat, elem_cpp=elem_cpp, elem_expr=access, classes=classes)
            _merge_pattern_match(pm, conds=conds, bindings=bindings, prelude=prelude)
        for j, pat in enumerate(layout.suffix):
            if is_tuple and tuple_arity is not None:
                abs_i = tuple_arity - suffix_len + j
                access = _sequence_access_expr(subject_expr, subject_cpp, tuple_abs_index=abs_i)
            else:
                neg_i = j - suffix_len
                access = _sequence_access_expr(subject_expr, subject_cpp, neg_index=neg_i)
            pm = _subpattern_match(tr, pat, elem_cpp=elem_cpp, elem_expr=access, classes=classes)
            _merge_pattern_match(pm, conds=conds, bindings=bindings, prelude=prelude)
        star_out = _emit_star_binding(layout.star, subject_expr, subject_cpp, prefix_len=prefix_len, suffix_len=suffix_len, tuple_arity=tuple_arity)
        if star_out:
            if isinstance(star_out, list):
                prelude.extend(star_out)
            else:
                prelude.append(star_out)
    cond = ' && '.join(conds) if conds else 'true'
    return PatternMatch(condition=cond, bindings=bindings, prelude_lines=prelude)

def _mapping_key_literal_ast(key_pat: ast.pattern) -> ast.expr:
    if isinstance(key_pat, ast.Constant):
        return copy.deepcopy(key_pat)
    if isinstance(key_pat, ast.MatchValue):
        val = key_pat.value
        if isinstance(val, ast.Constant):
            return copy.deepcopy(val)
        raise NotImplementedError('映射模式键须为字面量')
    if isinstance(key_pat, ast.MatchSingleton):
        return ast.Constant(value=key_pat.value)
    raise NotImplementedError('映射模式键须为字面量（首期不支持键捕获）')

def _mapping_key_literal_expr(tr: Translator, key_pat: ast.pattern, key_cpp: str) -> str:
    lit = _mapping_key_literal_ast(key_pat)
    if not isinstance(lit, ast.Constant):
        raise NotImplementedError('映射模式键须为字面量')
    v = lit.value
    if isinstance(v, str):
        if is_str_type(key_cpp) or key_cpp == cpp_ident('str'):
            return str_cpp_from_literal(v)
        return quote_cpp_string(v)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if v is None:
        return '0'
    if isinstance(v, int):
        return format_cpp_int(v)
    raise NotImplementedError(f'不支持的映射键字面量: {v!r}')

def _mapping_rest_type(subject_cpp: str) -> str:
    if is_counter_type(subject_cpp):
        return subject_cpp
    if is_frozendict_type(subject_cpp):
        return subject_cpp
    return subject_cpp

def _mapping_empty_ctor(subject_cpp: str) -> str:
    if is_frozendict_type(subject_cpp):
        inner = frozendict_type_args(subject_cpp) or ''
        return f"{cpp_template_type('frozendict', inner)}()"
    if is_counter_type(subject_cpp):
        return f'{subject_cpp}()'
    inner = dict_type_args(subject_cpp) if is_dict_type(subject_cpp) else ''
    return f"{cpp_template_type('dict', inner)}()"

def _mapping_rest_prelude_lines(tr: Translator, *, rest_name: str, subject_expr: str, subject_cpp: str, key_cpp: str, matched_key_exprs: list[str]) -> list[str]:
    sep = _member_sep(subject_expr)
    rest_ty = _mapping_rest_type(subject_cpp)
    k = temp_name("mk_k")
    it_var = temp_name("mk_it")
    r_var = temp_name("mk_r")
    lines = [f'{rest_ty} {rest_name} = {_mapping_empty_ctor(subject_cpp)};']
    lines.append(f'{{')
    lines.append(f'  auto& {it_var} = {subject_expr}{sep}__iter__();')
    lines.append('  while (true)')
    lines.append('  {')
    lines.append(f'    auto {r_var} = {it_var}.__next__();')
    lines.append(f"    if ({r_var}.{property_getter_method_for('done')}()) break;")
    lines.append(f"    auto {k} = {r_var}.{property_getter_method_for('value')}();")
    val_k = k
    if matched_key_exprs:
        skip = ' && '.join((f'({val_k} != {ke})' for ke in matched_key_exprs))
        lines.append(f'    if ({skip})')
        lines.append('    {')
        lines.append(f'      {rest_name}.__setitem__({val_k}, {subject_expr}{sep}__getitem__({val_k}));')
        lines.append('    }')
    else:
        lines.append(f'    {rest_name}.__setitem__({val_k}, {subject_expr}{sep}__getitem__({val_k}));')
    lines.append('  }')
    lines.append('}')
    return lines

def pattern_mapping_to_match(tr: Translator, pattern: ast.MatchMapping, *, subject_cpp: str, subject: ast.expr, subject_expr: str, classes: dict[str, ClassInfo]):
    from .match_case import PatternMatch
    if not is_mapping_match_subject(subject_cpp):
        raise TypeError(f'映射 ``case {{...}}`` 要求主体为 dict/frozendict/Counter，当前为 {subject_cpp}')
    kv = mapping_match_key_value_cpp(subject_cpp)
    if kv is None:
        raise TypeError(f'无法解析映射主体键值类型: {subject_cpp}')
    key_cpp, val_cpp = kv
    sep = _member_sep(subject_expr)
    conds: list[str] = []
    bindings: list[ast.stmt] = []
    prelude: list[str] = []
    for key_pat, val_pat in zip(pattern.keys, pattern.patterns):
        key_expr = _mapping_key_literal_expr(tr, key_pat, key_cpp)
        conds.append(f'({subject_expr}{sep}__contains__({key_expr}))')
        val_access = _runtime_getitem(subject_expr, key_expr)
        pm = _subpattern_match(tr, val_pat, elem_cpp=val_cpp, elem_expr=val_access, classes=classes)
        _merge_pattern_match(pm, conds=conds, bindings=bindings, prelude=prelude)
    matched_key_exprs = [_mapping_key_literal_expr(tr, key_pat, key_cpp) for key_pat in pattern.keys]
    if pattern.rest and pattern.rest != '_':
        prelude.extend(_mapping_rest_prelude_lines(tr, rest_name=pattern.rest, subject_expr=subject_expr, subject_cpp=subject_cpp, key_cpp=key_cpp, matched_key_exprs=matched_key_exprs))
    cond = ' && '.join(conds) if conds else 'true'
    return PatternMatch(condition=cond, bindings=bindings, prelude_lines=prelude)
